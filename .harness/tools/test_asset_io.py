"""Atomic writes preserve target paths, including native Windows long paths."""
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import asset_io


def io_path(path):
    """Test-side long-path access, independent from atomic_write's implementation."""
    absolute = os.path.abspath(os.fspath(path))
    if os.name != "nt" or absolute.startswith("\\\\?\\"):
        return Path(absolute)
    if absolute.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + absolute[2:])
    return Path("\\\\?\\" + absolute)


class AtomicWriteTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="atlas-atomic-test-")).resolve()
        self.addCleanup(self.cleanup)

    def cleanup(self):
        # Delete only the independently created temporary directory, never a fixture.
        target = self.root.resolve()
        temporary_root = Path(tempfile.gettempdir()).resolve()
        if target.parent != temporary_root or not target.name.startswith("atlas-atomic-test-"):
            raise AssertionError("临时清理目录身份不符")
        shutil.rmtree(io_path(target))

    def test_writes_utf8_and_bytes_atomically(self):
        target = self.root / "nested/记录.md"
        asset_io.atomic_write(target, "第一版\n")
        self.assertEqual("第一版\n".encode(), target.read_bytes())
        with mock.patch.object(asset_io.os, "fsync", wraps=os.fsync) as fsync:
            asset_io.atomic_write(target, b"second version\r\n")
        self.assertEqual(b"second version\r\n", target.read_bytes())
        fsync.assert_called_once()
        self.assertEqual([target], list(target.parent.iterdir()))

    def test_near_component_limit_does_not_extend_original_filename(self):
        target = self.root / ("a" * 240 + ".md")
        asset_io.atomic_write(target, b"original")
        asset_io.atomic_write(target, b"replacement")
        self.assertEqual(b"replacement", io_path(target).read_bytes())
        self.assertEqual([target.name], [path.name for path in self.root.iterdir()])

    @unittest.skipUnless(os.name == "nt", "Windows 专属长路径测试")
    def test_windows_existing_target_near_max_path_keeps_exact_path(self):
        parent = self.root / ("目录" * 36) / ("x" * 48)
        filename_length = 251 - len(str(parent)) - 1
        self.assertGreater(filename_length, 10)
        target = parent / ("n" * (filename_length - 3) + ".md")
        self.assertEqual(251, len(str(target)))
        io_path(parent).mkdir(parents=True)
        io_path(target).write_bytes(b"existing bytes")
        asset_io.atomic_write(target, b"restored bytes")
        self.assertEqual(b"restored bytes", io_path(target).read_bytes())
        self.assertEqual([target.name], [path.name for path in io_path(parent).iterdir()])

    @unittest.skipUnless(os.name == "nt", "Windows 专属长路径测试")
    def test_windows_directory_and_file_over_max_path(self):
        parent = self.root / ("a" * 100) / ("b" * 100) / ("c" * 100)
        target = parent / "原始路径.md"
        self.assertGreater(len(str(parent)), 260)
        asset_io.atomic_write(target, "长路径新内容\n")
        asset_io.atomic_write(target, b"restored original bytes\r\n")
        self.assertEqual(b"restored original bytes\r\n", io_path(target).read_bytes())
        self.assertEqual([target.name], [path.name for path in io_path(parent).iterdir()])

    @unittest.skipUnless(os.name == "nt", "Windows 专属扩展路径测试")
    def test_already_extended_target_is_not_prefixed_again(self):
        target = io_path(self.root / "already-extended.md")
        asset_io.atomic_write(target, b"content")
        self.assertEqual(b"content", target.read_bytes())

    def test_replace_failure_preserves_target_and_removes_only_owned_temporary(self):
        target = self.root / "target.md"
        target.write_bytes(b"original")
        unrelated = self.root / "another.tmp"
        unrelated.write_bytes(b"other writer")
        with mock.patch.object(asset_io.os, "replace", side_effect=OSError("模拟替换失败")):
            with self.assertRaisesRegex(OSError, "替换失败"):
                asset_io.atomic_write(target, b"updated")
        self.assertEqual(b"original", target.read_bytes())
        self.assertEqual(b"other writer", unrelated.read_bytes())
        self.assertEqual({"target.md", "another.tmp"}, {path.name for path in self.root.iterdir()})

    def test_fsync_failure_preserves_original_and_cleans_temporary(self):
        target = self.root / "target.md"
        target.write_bytes(b"original")
        with mock.patch.object(asset_io.os, "fsync", side_effect=OSError("模拟刷新失败")):
            with self.assertRaisesRegex(OSError, "刷新失败"):
                asset_io.atomic_write(target, "updated")
        self.assertEqual(b"original", target.read_bytes())
        self.assertEqual([target], list(self.root.iterdir()))

    def test_exclusive_create_collision_never_deletes_existing_temporary(self):
        target = self.root / "target.md"
        target.write_bytes(b"original")
        collided = self.root / (".atlas-" + "a" * 32 + ".tmp")
        collided.write_bytes(b"another writer owns this")
        with mock.patch.object(asset_io, "uuid4", return_value=SimpleNamespace(hex="a" * 32)):
            with self.assertRaises(FileExistsError):
                asset_io.atomic_write(target, b"updated")
        self.assertEqual(b"original", target.read_bytes())
        self.assertEqual(b"another writer owns this", collided.read_bytes())

    def test_success_does_not_delete_new_file_reusing_temporary_name(self):
        target = self.root / "target.md"
        original_replace = os.replace
        reused = []
        def replace_then_reuse(source, destination):
            original_replace(source, destination)
            Path(source).write_bytes(b"other writer reused the name")
            reused.append(Path(source))
        with mock.patch.object(asset_io.os, "replace", side_effect=replace_then_reuse):
            asset_io.atomic_write(target, b"written")
        self.assertEqual(b"written", target.read_bytes())
        self.assertEqual(b"other writer reused the name", reused[0].read_bytes())


if __name__ == "__main__":
    unittest.main(verbosity=2)
