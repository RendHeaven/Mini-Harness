"""公共片段同步的写入边界、漂移、失败恢复与真实模板契约。"""
from contextlib import redirect_stdout
import ast
import io
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import sync_template_fragments as sync


class FragmentSyncTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / ".harness"
        self.fragment = b"- time: <placeholder>\n"
        self.write(sync.FRAGMENT, self.fragment)
        for relative in sync.TEMPLATE_PATHS:
            self.write(relative, self.document())
        self.first, self.second = sync.TEMPLATE_PATHS[:2]

    def write(self, relative, data):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def document(self, content=None, newline=b"\n"):
        content = self.fragment if content is None else content
        return (b"# title\n\n## document info\n\n" + sync.START + b"\n" + content + sync.END +
                b"\n\n| user-owned | table |\n| --- | --- |\n").replace(b"\n", newline)

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
                for p in self.root.rglob("*") if p.is_file()}

    def invoke(self, *args):
        output = io.StringIO()
        with mock.patch.object(sync, "__file__", str(self.root / "tools/sync_template_fragments.py")), redirect_stdout(output):
            code = sync.main(list(args))
        return code, output.getvalue()

    def assert_no_temporary_files(self):
        self.assertFalse(list(self.root.rglob("*.tmp")))
        self.assertFalse(list(self.root.rglob("*.bak")))

    def test_default_and_check_are_read_only_and_report_drift(self):
        self.write(self.first, self.document(b"manual drift\n"))
        before = self.snapshot()
        for args in ((), ("--check",)):
            with self.subTest(args=args):
                code, output = self.invoke(*args)
                self.assertEqual(1, code)
                self.assertIn(self.first, output)
                self.assertEqual(before, self.snapshot())

    def test_write_preserves_body_position_and_lf_or_crlf(self):
        for newline, relative in ((b"\n", self.first), (b"\r\n", self.second),
                                  (b"\n", "template/develop/testhub/cases-template.md")):
            self.write(relative, self.document(b"old\n", newline))
        code, output = self.invoke("--write")
        self.assertEqual(0, code, output)
        for newline, relative in ((b"\n", self.first), (b"\r\n", self.second),
                                  (b"\n", "template/develop/testhub/cases-template.md")):
            self.assertEqual(self.document(newline=newline), (self.root / relative).read_bytes())
        self.assert_no_temporary_files()

    def test_fragment_change_updates_all_templates_and_second_write_is_noop(self):
        self.write(sync.FRAGMENT, b"- time: <changed-format>\n")
        plan = sync.make_plan(self.root)
        self.assertEqual(31, len(plan.changes))
        sync.apply_plan(plan)
        before = self.snapshot()
        self.assertEqual(0, self.invoke("--write")[0])
        self.assertEqual(before, self.snapshot())
        self.assertEqual(0, self.invoke("--check")[0])
        self.assert_no_temporary_files()

    def test_crlf_fragment_does_not_change_template_line_endings(self):
        self.write(sync.FRAGMENT, self.fragment.replace(b"\n", b"\r\n"))
        self.write(self.second, self.document(newline=b"\r\n"))
        before = self.snapshot()
        self.assertEqual(0, self.invoke("--write")[0])
        self.assertEqual(before, self.snapshot())

    def test_invalid_markers_fail_before_any_write(self):
        valid = self.document()
        invalid = [
            valid.replace(sync.START + b"\n", b""),
            valid.replace(sync.END + b"\n", b""),
            valid.replace(sync.START + b"\n", b"").replace(sync.END + b"\n", b""),
            valid + sync.START + b"\n" + sync.END + b"\n",
            valid.replace(sync.START, b"@start@").replace(sync.END, sync.START).replace(b"@start@", sync.END),
            valid.replace(b"document-timestamps:start", b"unknown:start"),
            valid.replace(sync.START, b"prefix " + sync.START),
        ]
        self.write(self.first, self.document(b"drift before later error\n"))
        for data in invalid:
            with self.subTest(data=data):
                self.write(self.second, data)
                before = self.snapshot()
                self.assertEqual(2, self.invoke("--write")[0])
                self.assertEqual(before, self.snapshot())

    def test_missing_template_or_fragment_is_not_recreated(self):
        for relative in (self.first, sync.FRAGMENT):
            path = self.root / relative
            original = path.read_bytes()
            path.unlink()
            before = self.snapshot()
            self.assertEqual(2, self.invoke("--write")[0])
            self.assertEqual(before, self.snapshot())
            self.write(relative, original)

    def test_empty_invalid_or_recursive_fragment_is_rejected(self):
        for data in (b"", b"no-final-newline", b"\xff\n", sync.START + b"\n", b"\xef\xbb\xbftext\n", b"text\rnext\n"):
            with self.subTest(data=data):
                self.write(sync.FRAGMENT, data)
                before = self.snapshot()
                self.assertEqual(2, self.invoke("--write")[0])
                self.assertEqual(before, self.snapshot())

    def test_unregistered_template_markers_are_rejected(self):
        self.write("template/product/unregistered.md", self.document())
        before = self.snapshot()
        self.assertEqual(2, self.invoke("--write")[0])
        self.assertEqual(before, self.snapshot())

    def test_arbitrary_targets_and_path_aliases_are_rejected(self):
        for relative in ("../project/document.md", "/absolute.md", "C:/outside.md", "template\\outside.md", "template/./other.md", self.first + "/../alias.md"):
            with self.subTest(relative=relative):
                with self.assertRaises(ValueError):
                    sync.make_plan(self.root, (relative,))
                with self.assertRaises(ValueError):
                    sync._file(self.root, relative)

    def test_reparse_directory_is_rejected(self):
        real_lstat = Path.lstat
        redirected = self.root / "template/develop"
        def lstat(path, *args, **kwargs):
            if path == redirected:
                return SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400)
            return real_lstat(path, *args, **kwargs)
        with mock.patch.object(Path, "lstat", lstat):
            with self.assertRaisesRegex(ValueError, "路径重定向"):
                sync.make_plan(self.root)

    def test_symbolic_file_is_rejected(self):
        path = self.root / self.first
        original = path.read_bytes()
        target = self.root / "outside.md"
        target.write_bytes(original)
        path.unlink()
        try:
            path.symlink_to(target)
        except OSError:
            path.write_bytes(original)
            self.skipTest("系统未提供符号链接权限；reparse 分支另有覆盖")
        with self.assertRaisesRegex(ValueError, "路径重定向"):
            sync.make_plan(self.root)
        self.assertEqual(original, target.read_bytes())

    def test_changed_source_or_template_stops_stale_plan(self):
        self.write(self.first, self.document(b"old\n"))
        for relative in (sync.FRAGMENT, self.first):
            plan = sync.make_plan(self.root)
            original = (self.root / relative).read_bytes()
            self.write(relative, original + b"user edit\n")
            before = self.snapshot()
            with self.assertRaisesRegex(ValueError, "输入已变化"):
                sync.apply_plan(plan)
            self.assertEqual(before, self.snapshot())
            self.write(relative, original)

    def test_changes_during_staging_are_preserved(self):
        self.write(self.first, self.document(b"old\n"))
        plan = sync.make_plan(self.root)
        original = sync._stage
        def stage(path, data, suffix):
            result = original(path, data, suffix)
            self.write(self.second, b"concurrent user edit\n")
            return result
        with mock.patch.object(sync, "_stage", stage):
            with self.assertRaisesRegex(ValueError, "输入已变化"):
                sync.apply_plan(plan)
        self.assertEqual(b"concurrent user edit\n", (self.root / self.second).read_bytes())
        self.assertEqual(self.document(b"old\n"), (self.root / self.first).read_bytes())
        self.assert_no_temporary_files()

    def test_failed_replace_rolls_back_previous_writes(self):
        self.write(sync.FRAGMENT, b"new\n")
        before = {p: data for p, (data, _) in self.snapshot().items()}
        plan = sync.make_plan(self.root)
        original = os.replace
        calls = 0
        def replace(source, target):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("simulated failure")
            original(source, target)
        with mock.patch.object(sync.os, "replace", replace):
            with self.assertRaisesRegex(OSError, "simulated failure"):
                sync.apply_plan(plan)
        self.assertEqual(before, {p: data for p, (data, _) in self.snapshot().items()})
        self.assert_no_temporary_files()

    def test_rollback_does_not_overwrite_concurrent_edit_and_retains_backup(self):
        self.write(sync.FRAGMENT, b"new\n")
        before = (self.root / self.first).read_bytes()
        plan = sync.make_plan(self.root)
        original = os.replace
        calls = 0
        def replace(source, target):
            nonlocal calls
            calls += 1
            if calls == 2:
                self.write(self.first, b"new user content\n")
                raise OSError("simulated failure")
            original(source, target)
        with mock.patch.object(sync.os, "replace", replace):
            with self.assertRaisesRegex(RuntimeError, "原文备份"):
                sync.apply_plan(plan)
        self.assertEqual(b"new user content\n", (self.root / self.first).read_bytes())
        backups = list(self.root.rglob("*.bak"))
        self.assertEqual(1, len(backups))
        self.assertEqual(before, backups[0].read_bytes())


class RepositoryContractTest(unittest.TestCase):
    def test_actual_templates_match_fragment_and_testhub_keeps_info_scope(self):
        root = Path(sync.__file__).absolute().parent.parent
        self.assertEqual((), sync.make_plan(root).changes)
        text = (root / "template/develop/testhub/cases-template.md").read_text(encoding="utf-8")
        self.assertLess(text.index("## 文档信息"), text.index(sync.START.decode()))
        self.assertLess(text.index(sync.END.decode()), text.index("## 参考上下文"))

    def test_assets_are_registered_and_ci_uses_existing_paths(self):
        root = Path(sync.__file__).absolute().parent.parent
        tree = ast.parse((root / "tools/core_validation.py").read_text(encoding="utf-8"))
        required = next(ast.literal_eval(node.value) for node in tree.body
                        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "REQUIRED_ACTIVE_FILES" for t in node.targets))
        self.assertIn("tools/sync_template_fragments.py", required)
        self.assertIn(sync.FRAGMENT, required)
        ci = (root.parent / ".gitlab-ci.yml").read_text(encoding="utf-8")
        self.assertIn(".harness/tools/sync_template_fragments.py --check", ci)
        self.assertIn(".harness/tools/test_sync_template_fragments.py", ci)
        self.assertNotIn("sync_template_fragments.py --write", ci)
        self.assertNotRegex(ci, r"(?<!\.)harness/(?:tools|hooks)/")
        for relative in re.findall(r"(?:project-harness-template/)?\.harness/[\w/.-]+", ci):
            self.assertTrue((root.parent / relative).is_file(), relative)

    def test_cli_finds_core_from_an_unrelated_working_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            process = subprocess.run([sys.executable, "-B", str(Path(sync.__file__).absolute()), "--check"],
                                     cwd=directory, capture_output=True)
        self.assertEqual(0, process.returncode, process.stdout + process.stderr)


if __name__ == "__main__":
    unittest.main()
