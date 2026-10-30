"""原型打包的内容完整性、输出冲突及路径边界测试。"""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from unittest import mock
import zipfile

import package_prototype as pack


class PackagePrototypeTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "产品原型 示例"
        self.root.mkdir()

    def invoke(self, root):
        output, errors = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            code = pack.main(["--prototype-root", str(root)])
        return code, output.getvalue(), errors.getvalue()

    def test_all_contents_and_empty_directories_preserve_source(self):
        expected = {
            "index.html": b"<html>prototype</html>",
            "资源 目录/示例.bin": bytes(range(256)),
            ".配置": "保留隐藏文件".encode(),
            ".hidden/nested.txt": b"nested",
            "existing.zip": b"include every source file",
        }
        for name, content in expected.items():
            target = self.root / name
            target.parent.mkdir(exist_ok=True, parents=True)
            target.write_bytes(content)
        (self.root / "空目录" / "内部空目录").mkdir(parents=True)
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns)
                  for p in self.root.rglob("*") if p.is_file()}
        code, output, errors = self.invoke(self.root)
        self.assertEqual(0, code, errors)
        result = json.loads(output)
        archive_path = Path(result["archive_path"])
        self.assertEqual(self.base / f"{self.root.name}.zip", archive_path)
        self.assertTrue(archive_path.is_absolute())
        self.assertEqual(len(expected), result["file_count"])
        self.assertEqual(sum(map(len, expected.values())), result["source_bytes"])
        self.assertEqual(archive_path.stat().st_size, result["archive_bytes"])
        with zipfile.ZipFile(archive_path) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(set(expected) | {"资源 目录/", ".hidden/", "空目录/", "空目录/内部空目录/"},
                             set(archive.namelist()))
            for name, content in expected.items():
                self.assertEqual(content, archive.read(name))
        self.assertEqual(before, {p: (p.read_bytes(), p.stat().st_mtime_ns)
                                  for p in self.root.rglob("*") if p.is_file()})

    def test_repeated_packages_never_overwrite_existing_outputs(self):
        first = Path(pack.package_prototype(self.root)["archive_path"])
        original = first.read_bytes()
        second = Path(pack.package_prototype(self.root)["archive_path"])
        self.assertEqual(self.base / f"{self.root.name}-1.zip", second)
        self.assertEqual(original, first.read_bytes())
        with zipfile.ZipFile(second) as archive:
            self.assertEqual([], archive.namelist())
        (self.base / f"{self.root.name}-2.zip").mkdir()
        third = Path(pack.package_prototype(self.root)["archive_path"])
        self.assertEqual(self.base / f"{self.root.name}-3.zip", third)

    def test_invalid_source_fails_without_creating_outputs(self):
        file_path = self.base / "file.txt"
        file_path.write_bytes(b"not a directory")
        for root in (self.base / "missing", file_path, Path(self.root.anchor)):
            with self.subTest(root=root):
                code, output, errors = self.invoke(root)
                self.assertNotEqual(0, code)
                self.assertEqual("", output)
                self.assertIn("原型打包失败", errors)
        self.assertFalse(list(self.base.glob("*.zip")))

    def test_reparse_attribute_is_rejected(self):
        info = mock.Mock(st_mode=stat.S_IFDIR, st_file_attributes=0x400)
        with mock.patch.object(Path, "lstat", return_value=info):
            with self.assertRaisesRegex(ValueError, "reparse"):
                pack.package_prototype(self.root)

    def test_actual_redirects_at_source_ancestor_and_child_are_rejected(self):
        outside = self.base / "outside"
        (outside / "nested").mkdir(parents=True)
        (outside / "secret.txt").write_bytes(b"must not be included")
        link = self.base / "redirect"
        if os.name == "nt":
            # 使用固定 PowerShell 代码及环境参数，避免通过 shell 拼接路径。
            env = dict(os.environ, ATLAS_TEST_LINK=str(link), ATLAS_TEST_TARGET=str(outside))
            completed = subprocess.run([
                "powershell", "-NoProfile", "-NonInteractive", "-Command",
                "$ErrorActionPreference = 'Stop'; New-Item -ItemType Junction "
                "-Path $env:ATLAS_TEST_LINK -Target $env:ATLAS_TEST_TARGET | Out-Null",
            ], env=env, capture_output=True, text=True)
            self.assertEqual(0, completed.returncode, completed.stderr)
        else:
            link.symlink_to(outside, target_is_directory=True)
        self.assertTrue(link.is_dir())
        # 只移除位于本测试临时目录中的链接入口，不递归删除链接目标。
        def remove_link():
            if link.parent != self.base or self.base.parent == self.base:
                raise AssertionError("测试清理路径越界")
            if os.name == "nt":
                link.rmdir()
            else:
                link.unlink()
        self.addCleanup(remove_link)
        for root in (link, link / "nested", link / ".." / self.root.name, self.base):
            with self.subTest(root=root):
                with self.assertRaisesRegex(ValueError, "符号链接"):
                    pack.package_prototype(root)
        self.assertEqual(b"must not be included", (outside / "secret.txt").read_bytes())
        self.assertFalse(list(self.base.glob("*.zip")))

    def test_write_and_crc_failures_remove_only_new_partial_archive(self):
        (self.root / "index.html").write_bytes(b"prototype")
        existing = self.base / f"{self.root.name}.zip"
        existing.write_bytes(b"existing output")
        cases = (
            mock.patch.object(pack.shutil, "copyfileobj", side_effect=OSError("write failed")),
            mock.patch.object(zipfile.ZipFile, "testzip", return_value="index.html"),
        )
        for patch in cases:
            with self.subTest(patch=patch), patch:
                code, output, errors = self.invoke(self.root)
                self.assertNotEqual(0, code)
                self.assertEqual("", output)
                self.assertIn("原型打包失败", errors)
            self.assertEqual([existing], list(self.base.glob("*.zip")))
            self.assertEqual(b"existing output", existing.read_bytes())


if __name__ == "__main__":
    unittest.main()
