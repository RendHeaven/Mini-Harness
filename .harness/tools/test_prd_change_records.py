"""Current PRD change records, unsupported input rejection and interruption safety."""
import copy
import hashlib
import json
import tempfile
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

import yaml

from asset_io import atomic_write, exclusive
from core_validation import Result
import prd_revision as revisions


class PrdChangeRecordsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.product = Path(self.temp.name).resolve() / "product"
        self.product.mkdir()
        self.prd = self.product / "v1.2-prd.md"
        atomic_write(self.prd, "# PRD\n\nREQ-001 原始内容\n")

    def initialize(self):
        revisions.initialize(self.product, self.prd, "产品负责人")

    def revise(self, content="# PRD\n\nREQ-001 新内容\n"):
        return revisions.revise(self.product, self.prd, content, "产品负责人", "用户反馈", "REQ-001")

    def assert_valid(self):
        result = Result.empty()
        revisions.validate_revisions(self.product, self.prd, result)
        self.assertEqual([], result.errors)

    def inventory(self):
        return {p.relative_to(self.product).as_posix(): p.read_bytes() for p in self.product.rglob("*") if p.is_file()}

    def write_log(self, log):
        atomic_write(self.product / revisions.LOG_PATH, yaml.safe_dump(log, allow_unicode=True, sort_keys=False))
        atomic_write(self.product / revisions.INDEX_PATH, revisions.render_index(log))

    def legacy(self):
        at = "2026-09-20T09:00:00+08:00"
        text = b"# Legacy CHG\r\n\r\nPreserve bytes and old hashes.\r\n"
        log = dict(schemaVersion=1, prd=self.prd.name,
                   baseline=dict(path="prd-changes/baseline.md", sha256="a" * 64, at=at, actor="旧创建者"),
                   changes=[dict(id="CHG-001", at="2026-09-21T10:00:00+08:00", actor="旧修订者",
                                 reason="旧原因", impact="REQ-001", beforeSha256="a" * 64,
                                 afterSha256="b" * 64, documentSha256=hashlib.sha256(text).hexdigest())])
        atomic_write(self.product / "prd-changes/CHG-001.md", text)
        atomic_write(self.product / revisions.LOG_PATH, yaml.safe_dump(log, allow_unicode=True))
        atomic_write(self.product / revisions.INDEX_PATH, "# 原有修订索引\n")
        return log, text

    def test_initialize_creates_no_snapshot_or_persistent_hash(self):
        before = self.prd.read_bytes()
        self.initialize()
        log = revisions.load_log(self.product)
        self.assertEqual(2, log["schemaVersion"])
        self.assertEqual(set(log), revisions.LOG_FIELDS)
        self.assertEqual([], log["changes"])
        self.assertEqual(before, self.prd.read_bytes())
        self.assertEqual({self.prd.name, revisions.LOG_PATH, revisions.INDEX_PATH}, set(self.inventory()))
        self.assertNotIn("SHA256", (self.product / revisions.INDEX_PATH).read_text(encoding="utf-8"))
        self.assert_valid()

    def test_revisions_preserve_notes_and_store_only_local_diff(self):
        original = "".join(f"REQ-{n:03d} 原始内容\n" for n in range(1, 80))
        atomic_write(self.prd, original)
        self.initialize()
        changed = original.replace("REQ-040 原始内容", "REQ-040 新内容")
        self.assertEqual("CHG-001", self.revise(changed))
        first = (self.product / "prd-changes/CHG-001.md").read_bytes()
        self.assertIn(b"@@ -37,7 +37,7 @@", first)
        self.assertNotIn(b"REQ-001", first.split(b"~~~~diff", 1)[1])
        self.assertNotIn(b"REQ-079", first)
        self.assertEqual("CHG-002", self.revise(changed + "REQ-080 新需求\n"))
        self.assertEqual(first, (self.product / "prd-changes/CHG-001.md").read_bytes())
        self.assertEqual(["CHG-001", "CHG-002"], revisions.log_changes(self.product))
        log = revisions.load_log(self.product)
        self.assertEqual(revisions.CHANGE_FIELDS, set(log["changes"][0]))
        self.assertEqual("prd-changes/CHG-001.md", log["changes"][0]["document"])
        for name, content in self.inventory().items():
            self.assertNotIn("baseline", name)
            self.assertNotIn(".before.", name)
            self.assertNotIn(".after.", name)
            self.assertNotIn(b"Sha256", content)
            self.assertNotIn(b"SHA256", content)
        self.assert_valid()

    def test_no_change_does_not_write_or_append(self):
        self.initialize()
        before = self.inventory()
        with mock.patch.object(revisions, "atomic_write") as write:
            self.assertIsNone(self.revise(self.prd.read_text(encoding="utf-8")))
        write.assert_not_called()
        self.assertEqual(before, self.inventory())

    def test_current_prd_is_not_a_persistent_digest_gate(self):
        self.initialize()
        atomic_write(self.prd, "外部编辑\n")
        self.assert_valid()
        self.revise("继续变更\n")
        note = (self.product / "prd-changes/CHG-001.md").read_text(encoding="utf-8")
        self.assertIn("-外部编辑\n+继续变更", note)

    def test_missing_final_newline_has_readable_diff(self):
        atomic_write(self.prd, "旧正文")
        self.initialize()
        self.revise("新正文")
        note = (self.product / "prd-changes/CHG-001.md").read_text(encoding="utf-8")
        self.assertIn("-旧正文\n\\ No newline at end of file\n+新正文\n", note)

    def test_unsupported_log_is_rejected_without_write(self):
        self.legacy()
        before = self.inventory()
        result = Result.empty()
        revisions.validate_revisions(self.product, self.prd, result)
        self.assertTrue(any("仅支持" in error for error in result.errors))
        with self.assertRaisesRegex(ValueError, "仅支持"):
            revisions.log_changes(self.product)
        with self.assertRaisesRegex(ValueError, "仅支持"):
            self.revise()
        with self.assertRaisesRegex(ValueError, "已有修订"):
            self.initialize()
        with self.assertRaisesRegex(ValueError, "仅支持"):
            revisions.render_index(revisions.load_log(self.product))
        self.assertEqual(before, self.inventory())

    def test_unsupported_schema_requires_integer_two(self):
        self.initialize()
        original = revisions.load_log(self.product)
        for version in (1, 3, "2", 2.0, True, None, []):
            with self.subTest(version=version):
                log = copy.deepcopy(original)
                log["schemaVersion"] = version
                atomic_write(self.product / revisions.LOG_PATH, yaml.safe_dump(log))
                before = self.inventory()
                with self.assertRaisesRegex(ValueError, "仅支持"):
                    self.revise()
                self.assertEqual(before, self.inventory())

    def test_cli_does_not_offer_or_accept_migration(self):
        self.initialize()
        before = self.inventory()
        completed = subprocess.run([sys.executable, "-B", str(Path(revisions.__file__)), "--prd", str(self.prd), "--init", "--migrate"], capture_output=True)
        self.assertEqual(2, completed.returncode)
        self.assertIn(b"unrecognized arguments: --migrate", completed.stderr)
        self.assertEqual(before, self.inventory())

    def test_sequence_duplicate_and_document_escape_are_rejected(self):
        self.initialize()
        self.revise()
        original = revisions.load_log(self.product)
        for field, value in (("id", "CHG-003"), ("document", "../outside.md"), ("actor", ""), ("impact", None)):
            with self.subTest(field=field):
                log = copy.deepcopy(original)
                log["changes"][0][field] = value
                atomic_write(self.product / revisions.LOG_PATH, yaml.safe_dump(log))
                result = Result.empty()
                revisions.validate_revisions(self.product, self.prd, result)
                self.assertTrue(result.errors)
        self.write_log(original)
        duplicated = copy.deepcopy(original)
        duplicated["changes"].append(copy.deepcopy(duplicated["changes"][0]))
        with self.assertRaisesRegex(ValueError, "连续"):
            revisions.validate_log(duplicated)

    def test_unknown_snapshot_fields_are_rejected_in_v2(self):
        self.initialize()
        log = revisions.load_log(self.product)
        log["baseline"] = {"path": "prd-changes/baseline.md"}
        with self.assertRaisesRegex(ValueError, "不保存"):
            revisions.validate_log(log)

    def test_missing_or_orphan_note_blocks_next_change(self):
        self.initialize()
        stray = self.product / "prd-changes/CHG-001.md"
        atomic_write(stray, "不能覆盖\n")
        with self.assertRaisesRegex(ValueError, "未登记"):
            self.revise()
        self.assertEqual("不能覆盖\n", stray.read_text(encoding="utf-8"))
        stray.unlink()
        self.revise()
        stray.unlink()
        with self.assertRaisesRegex(ValueError, "缺失"):
            self.revise("第二次修改\n")

    def test_concurrent_writer_lock_blocks_revision(self):
        self.initialize()
        before = self.prd.read_bytes()
        with exclusive(self.product / ".prd-revision.lock"):
            with self.assertRaisesRegex(ValueError, "操作锁"):
                self.revise()
        self.assertEqual(before, self.prd.read_bytes())

    def interrupted_revision(self):
        original = revisions.atomic_write
        def interrupted(path, content):
            if Path(path) == self.prd:
                raise OSError("模拟断电")
            original(path, content)
        with mock.patch.object(revisions, "atomic_write", side_effect=interrupted):
            with self.assertRaisesRegex(OSError, "断电"):
                self.revise()

    def test_interrupted_write_recovers_then_removes_temporary_content_and_hashes(self):
        self.initialize()
        self.interrupted_revision()
        self.assertTrue((self.product / revisions.JOURNAL_PATH).is_file())
        revisions.complete_pending(self.product)
        self.assert_valid()
        self.assertEqual(["CHG-001"], revisions.log_changes(self.product))
        self.assertFalse((self.product / revisions.JOURNAL_PATH).exists())
        self.assertFalse(any(name.endswith(".tmp") for name in self.inventory()))

    def test_recovery_rejects_external_prd_edit_without_overwriting_anything(self):
        self.initialize()
        self.interrupted_revision()
        atomic_write(self.prd, "第三方编辑\n")
        before = self.inventory()
        with self.assertRaisesRegex(ValueError, "第三方修改"):
            revisions.complete_pending(self.product)
        self.assertEqual(before, self.inventory())

    def test_recovery_checks_all_metadata_before_any_write(self):
        self.initialize()
        self.interrupted_revision()
        atomic_write(self.product / revisions.INDEX_PATH, "第三方索引修改\n")
        before = self.inventory()
        with self.assertRaisesRegex(ValueError, "冲突"):
            revisions.complete_pending(self.product)
        self.assertEqual(before, self.inventory())

    def test_recovery_rejects_journal_path_injection(self):
        self.initialize()
        self.interrupted_revision()
        journal = self.product / revisions.JOURNAL_PATH
        data = json.loads(journal.read_text(encoding="utf-8"))
        data["files"]["../outside.md"] = "越界"
        data["expected"]["../outside.md"] = None
        atomic_write(journal, json.dumps(data))
        before = self.inventory()
        with self.assertRaisesRegex(ValueError, "清单外"):
            revisions.complete_pending(self.product)
        self.assertEqual(before, self.inventory())
        self.assertFalse((self.product.parent / "outside.md").exists())

    def test_initialize_interruption_is_recoverable_without_a_baseline(self):
        original = revisions.atomic_write
        def interrupted(path, content):
            if Path(path) == self.product / revisions.INDEX_PATH:
                raise OSError("模拟断电")
            original(path, content)
        with mock.patch.object(revisions, "atomic_write", side_effect=interrupted):
            with self.assertRaises(OSError):
                self.initialize()
        revisions.complete_pending(self.product)
        self.assert_valid()
        self.assertFalse((self.product / "prd-changes/baseline.md").exists())

    def test_recovery_rejects_unsupported_schema_operation_and_log_without_write(self):
        self.initialize()
        self.interrupted_revision()
        journal = self.product / revisions.JOURNAL_PATH
        original = json.loads(journal.read_text(encoding="utf-8"))
        cases = [("schemaVersion", value) for value in (1, "2", 2.0, True)] + [("operation", "migrate"), ("planned-log", 1)]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                job = copy.deepcopy(original)
                if field == "planned-log":
                    log = yaml.safe_load(job["files"][revisions.LOG_PATH])
                    log["schemaVersion"] = value
                    job["files"][revisions.LOG_PATH] = yaml.safe_dump(log)
                else:
                    job[field] = value
                atomic_write(journal, json.dumps(job))
                before = self.inventory()
                with self.assertRaisesRegex(ValueError, "仅支持"):
                    revisions.complete_pending(self.product)
                self.assertEqual(before, self.inventory())

    def test_prd_symbolic_link_is_rejected(self):
        outside = self.product.parent / "outside.md"
        atomic_write(outside, "外部文件")
        self.prd.unlink()
        try:
            self.prd.symlink_to(outside)
        except OSError:
            self.skipTest("系统禁止创建符号链接")
        with self.assertRaisesRegex(ValueError, "符号链接"):
            self.initialize()


if __name__ == "__main__":
    unittest.main(verbosity=2)
