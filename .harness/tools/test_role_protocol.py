from __future__ import annotations
import copy
import json
import subprocess
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

import yaml

from asset_io import atomic_write, directory_hash, exclusive, file_hash, safe_path
from core_validation import Result, parse_config
from project_protocol import default_config
import role_gates as gates
import prd_revision as revisions


class RoleProtocolTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        for args in (("init",), ("config", "--local", "user.name", "UI 确认者"), ("config", "--local", "user.email", "ui-reviewer@example.test")):
            subprocess.run(["git", "-C", str(self.root), *args], check=True, capture_output=True)
        self.config = replace(default_config(), project_id="demo")
        self.cycle = self.root / ".harness/demandCycle/v1.2"
        self.product = self.cycle / "product"
        self.product.mkdir(parents=True)
        self.prd = self.product / "v1.2-prd.md"
        self.prd.write_text("# PRD\n\nREQ-001 内容\n", encoding="utf-8")
        manifest = dict(schemaVersion=8, version="v1.2", title="需求", phase="discovery", state="active",
                        owners={"product": "产品负责人"}, createdAt="2026-09-16", updatedAt="2026-09-16", blockedBy=[])
        atomic_write(self.cycle / "manifest.yaml", yaml.safe_dump(manifest, allow_unicode=True))
        atomic_write(self.root / "原型仓库/index.html", "<html>原型</html>")
        for rel in ("ui/adjustment-log.md", "ui/ui-handoff.md", "ui/adjustments/UI-ADJ-001.md"):
            atomic_write(self.cycle / rel, "# 实际调整\n\n2026-09-16 10:00:00 Asia/Shanghai\nREQ-001\n\n| 页面/REQ | 调整前 | 调整后 | UI 规则 | 文件 | 验证与证据 |\n| --- | --- | --- | --- | --- | --- |\n| REQ-001 | 单列 | 双列 | 间距规则 | 原型仓库/index.html | 浏览器检查通过 |\n")
        gates.initialize_cycle(self.root, self.config, "v1.2")
        self.evidence = ".harness/demandCycle/v1.2/ui/adjustments/UI-ADJ-001.md"

    def update(self, status, **kwargs):
        gates.update_role(self.root, self.config, "v1.2", "ui", status, "UI负责人", "本轮确认", **kwargs)

    def ledger(self):
        return gates.load_ledger(self.root, self.config)

    def confirm_ui(self):
        self.update("in_progress")
        self.update("pending_confirmation", evidence=[self.evidence])
        self.update("confirmed")

    def test_ui_can_confirm_with_other_roles_not_started(self):
        self.confirm_ui()
        roles = self.ledger()["cycles"]["v1.2"]["roles"]
        self.assertEqual("confirmed", roles["ui"]["status"])
        for role in ("product", "frontend", "backend"):
            self.assertEqual("not_started", roles[role]["status"])
        result = Result.empty()
        outcomes = gates.validate_cycle(self.cycle, self.config, self.root, result)
        self.assertEqual([], result.errors)
        self.assertTrue(outcomes["ui"].passed)
        self.assertFalse(outcomes["product"].passed)

    def git_config(self, key, value):
        subprocess.run(["git", "-C", str(self.root), "config", "--local", key, value], check=True, capture_output=True)

    def test_confirmation_records_git_identity(self):
        self.confirm_ui()
        record = self.ledger()["cycles"]["v1.2"]["roles"]["ui"]
        expected = {"name": "UI 确认者", "email": "ui-reviewer@example.test"}
        self.assertEqual(expected, record["confirmedGit"])
        self.assertEqual(expected, record["history"][-1]["record"]["confirmedGit"])
        self.assertEqual("UI负责人", record["confirmedBy"])

    def test_missing_git_identity_leaves_pending_gate_unchanged(self):
        for key in ("user.name", "user.email"):
            with self.subTest(key=key):
                self.git_config("user.name", "UI 确认者")
                self.git_config("user.email", "ui-reviewer@example.test")
                record = self.ledger()["cycles"]["v1.2"]["roles"]["ui"]
                if record["status"] == "not_started":
                    self.update("in_progress")
                    self.update("pending_confirmation", evidence=[self.evidence])
                self.git_config(key, "")
                before = (self.root / "Gate.yaml").read_bytes()
                with self.assertRaisesRegex(ValueError, "Git"):
                    self.update("confirmed")
                self.assertEqual(before, (self.root / "Gate.yaml").read_bytes())

    def test_git_configuration_changes_preserve_prior_confirmation(self):
        self.confirm_ui()
        before = self.ledger()["cycles"]["v1.2"]["roles"]["ui"]["history"][-1]
        self.git_config("user.name", "第二位确认者")
        self.git_config("user.email", "second@example.test")
        self.update("in_progress")
        record = self.ledger()["cycles"]["v1.2"]["roles"]["ui"]
        self.assertIsNone(record["confirmedGit"])
        self.assertEqual(before, record["history"][-2])
        self.update("pending_confirmation", evidence=[self.evidence])
        self.update("confirmed")
        record = self.ledger()["cycles"]["v1.2"]["roles"]["ui"]
        self.assertEqual("second@example.test", record["confirmedGit"]["email"])
        self.assertEqual(before, record["history"][2])

    def test_invalid_current_and_historical_git_identity_are_rejected(self):
        self.confirm_ui()
        original = self.ledger()["cycles"]["v1.2"]["roles"]["ui"]
        for value in (None, {}, {"name": "A", "email": ""}, {"name": 12, "email": "a@b"}):
            with self.subTest(value=value):
                current = copy.deepcopy(original)
                current["confirmedGit"] = value
                with self.assertRaisesRegex(ValueError, "Git|confirmedGit"):
                    gates.validate_record(self.root, self.config, "v1.2", "ui", current)
        self.update("in_progress")
        historical = self.ledger()["cycles"]["v1.2"]["roles"]["ui"]
        historical["history"][2]["record"]["confirmedGit"] = None
        with self.assertRaisesRegex(ValueError, "confirmedGit"):
            gates.validate_record(self.root, self.config, "v1.2", "ui", historical)

    def test_non_root_directory_cannot_borrow_parent_identity(self):
        nested = self.root / "child"
        nested.mkdir()
        with self.assertRaisesRegex(ValueError, "仓库根"):
            gates.read_confirming_git(nested)

    def test_effective_git_configuration_uses_local_then_global(self):
        import os
        global_config = self.root / "isolated-global-config"
        global_config.write_text('[user]\n    name = Global Reviewer\n    email = global@example.test\n', encoding="utf-8")
        for key in ("user.name", "user.email"):
            subprocess.run(["git", "-C", str(self.root), "config", "--local", "--unset", key], check=True, capture_output=True)
        with mock.patch.dict(os.environ, {"GIT_CONFIG_GLOBAL": str(global_config), "GIT_CONFIG_NOSYSTEM": "1"}):
            self.assertEqual({"name": "Global Reviewer", "email": "global@example.test"}, gates.read_confirming_git(self.root))
            self.git_config("user.name", "项目确认者")
            self.assertEqual({"name": "项目确认者", "email": "global@example.test"}, gates.read_confirming_git(self.root))

    def test_git_unavailable_is_a_clear_error(self):
        with mock.patch.object(gates.subprocess, "run", side_effect=FileNotFoundError):
            with self.assertRaisesRegex(ValueError, "Git"):
                gates.read_confirming_git(self.root)

    def test_validation_does_not_confirm_or_write(self):
        before = (self.root / "Gate.yaml").read_bytes()
        result = Result.empty()
        gates.validate_cycle(self.cycle, self.config, self.root, result)
        self.assertEqual(before, (self.root / "Gate.yaml").read_bytes())

    def test_confirmation_keeps_event_without_content_snapshots(self):
        self.confirm_ui()
        saved = self.ledger()["cycles"]["v1.2"]["roles"]["ui"]
        self.assertEqual({"path", "changes"}, set(saved["sources"]["prd"]))
        self.assertFalse((self.root / ".harness/evidence").exists())
        atomic_write(self.root / "原型仓库/index.html", "<html>修改后的原型</html>")
        atomic_write(self.cycle / "product/mock-changelog.md", "# CHG-001 原型调整\n")
        self.assertFalse(gates.source_state(self.root, self.config, "v1.2", saved["sources"]))
        result = Result.empty()
        outcomes = gates.validate_cycle(self.cycle, self.config, self.root, result)
        self.assertTrue(outcomes["ui"].passed)
        self.assertEqual(saved, self.ledger()["cycles"]["v1.2"]["roles"]["ui"])

    def test_explicit_confirmation_records_latest_change_scope(self):
        self.update("in_progress")
        self.update("pending_confirmation", evidence=[self.evidence])
        atomic_write(self.root / "原型仓库/index.html", "新内容")
        atomic_write(self.cycle / "product/mock-changelog.md", "# CHG-001 原型调整\n")
        self.update("confirmed")
        source = self.ledger()["cycles"]["v1.2"]["roles"]["ui"]["sources"]["prototype"]
        self.assertTrue(any(ref.endswith("#CHG-001") for ref in source["changes"]))
        self.assertFalse((self.root / ".harness/evidence").exists())

    def test_current_reconstruction_changes_are_captured(self):
        path = self.cycle / "ui/reconstruction/reconstruction.yaml"
        atomic_write(path, yaml.safe_dump({"recordVersion": 2, "iterations": [{"changedArtifacts": []}, {"changedArtifacts": ["原型仓库/index.html"]}]}))
        sources = gates.capture_sources(self.root, self.config, "v1.2")
        self.assertIn(".harness/demandCycle/v1.2/ui/reconstruction/reconstruction.yaml#iteration-2", sources["prototype"]["changes"])
        self.confirm_ui()

    def test_unsupported_reconstruction_is_rejected_without_gate_write(self):
        self.update("in_progress")
        path = self.cycle / "ui/reconstruction/reconstruction.yaml"
        for version in (1, "2", 2.0, True, None):
            with self.subTest(version=version):
                atomic_write(path, yaml.safe_dump({"recordVersion": version, "iterations": []}))
                before = (self.root / "Gate.yaml").read_bytes()
                with self.assertRaisesRegex(ValueError, "仅支持 recordVersion: 2"):
                    gates.capture_sources(self.root, self.config, "v1.2")
                with self.assertRaisesRegex(ValueError, "仅支持 recordVersion: 2"):
                    self.update("pending_confirmation", evidence=[self.evidence])
                self.assertEqual(before, (self.root / "Gate.yaml").read_bytes())

    def test_evidence_is_a_reference_without_content_binding(self):
        self.update("in_progress")
        self.update("pending_confirmation", evidence=[self.evidence])
        path = self.root / self.evidence
        atomic_write(path, path.read_text(encoding="utf-8") + "\n新增验证结果\n")
        self.update("confirmed")
        self.assertEqual([{"path": self.evidence}], self.ledger()["cycles"]["v1.2"]["roles"]["ui"]["evidence"])

    def test_empty_adjustment_table_cannot_pass(self):
        atomic_write(self.root / self.evidence, "# 调整\n2026-09-16 10:00:00\n")
        self.update("in_progress")
        with self.assertRaisesRegex(ValueError, "调整"):
            self.update("pending_confirmation", evidence=[self.evidence])

    def test_cannot_initialize_nonexistent_cycle(self):
        with self.assertRaisesRegex(ValueError, "周期清单"):
            gates.initialize_cycle(self.root, self.config, "v9.9")

    def test_stale_writer_cannot_erase_other_role(self):
        digest = file_hash(self.root / "Gate.yaml")
        gates.update_role(self.root, self.config, "v1.2", "backend", "in_progress", "后端", "实现")
        with self.assertRaisesRegex(ValueError, "其他任务"):
            self.update("in_progress", expected_digest=digest)
        self.assertEqual("in_progress", self.ledger()["cycles"]["v1.2"]["roles"]["backend"]["status"])

    def test_lock_blocks_competing_updates(self):
        with exclusive(self.root / "Gate.yaml.lock"):
            with self.assertRaisesRegex(ValueError, "操作锁"):
                self.update("in_progress")

    def test_confirmation_requires_explicit_transition(self):
        with self.assertRaisesRegex(ValueError, "非法状态"):
            self.update("confirmed")

    def test_tampered_history_or_proof_rejected(self):
        self.confirm_ui()
        data = self.ledger()
        data["cycles"]["v1.2"]["roles"]["ui"]["confirmedAt"] = None
        atomic_write(self.root / "Gate.yaml", yaml.safe_dump(data, allow_unicode=True))
        result = Result.empty()
        gates.validate_ledger(self.root, self.config, result)
        self.assertTrue(result.errors)

    def test_cancelled_cycle_cannot_be_updated(self):
        path = self.cycle / "manifest.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        data["state"] = "cancelled"
        atomic_write(path, yaml.safe_dump(data))
        with self.assertRaisesRegex(ValueError, "取消"):
            self.update("in_progress")

    def test_paths_cannot_escape_or_use_aliases(self):
        for value in ("../outside", "C:/outside", "/outside", "原型仓库/../service", "原型仓库\\index.html"):
            with self.assertRaises(ValueError):
                safe_path(self.root, value)

    def test_symbolic_link_rejected(self):
        link = self.root / "原型仓库/link.html"
        try:
            link.symlink_to(self.prd)
        except OSError:
            self.skipTest("操作系统未提供符号链接权限")
        with self.assertRaisesRegex(ValueError, "符号链接"):
            directory_hash(link.parent)

    def test_windows_junction_is_rejected(self):
        import os
        import subprocess
        if os.name != "nt":
            self.skipTest("Windows 专属联接测试")
        link = self.root / "原型仓库/junction"
        completed = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(self.product)], capture_output=True)
        if completed.returncode:
            self.skipTest("系统禁止创建目录联接")
        self.addCleanup(lambda: os.rmdir(link) if link.exists() else None)
        with self.assertRaisesRegex(ValueError, "联接"):
            safe_path(self.root, "原型仓库/junction/v1.2-prd.md")
        with self.assertRaisesRegex(ValueError, "联接"):
            directory_hash(self.root / "原型仓库")

    def test_two_prd_revisions_preserve_change_records_without_snapshots(self):
        original = self.prd.read_bytes()
        revisions.initialize(self.product, self.prd, "产品")
        self.assertEqual("CHG-001", revisions.revise(self.product, self.prd, "# PRD\n修改一\n", "产品", "反馈一", "REQ-001"))
        first = (self.product / "prd-changes/CHG-001.md").read_bytes()
        self.assertEqual("CHG-002", revisions.revise(self.product, self.prd, "# PRD\n修改二\n", "产品", "反馈二", "REQ-001"))
        self.assertEqual(first, (self.product / "prd-changes/CHG-001.md").read_bytes())
        self.assertFalse((self.product / "prd-changes/baseline.md").exists())
        self.assertFalse(list((self.product / "prd-changes").glob("*.before.md")))
        self.assertFalse(list((self.product / "prd-changes").glob("*.after.md")))
        result = Result.empty()
        revisions.validate_revisions(self.product, self.prd, result)
        self.assertEqual([], result.errors)

    def test_changes_are_logged_without_persistent_content_hashes(self):
        revisions.initialize(self.product, self.prd, "产品")
        self.assertEqual([], revisions.log_changes(self.product))
        revisions.revise(self.product, self.prd, "新正文", "产品", "修订", "REQ-001")
        self.assertEqual(["CHG-001"], revisions.log_changes(self.product))
        self.assertNotIn("sha256", (self.product / "prd-changes/revisions.yaml").read_text(encoding="utf-8").lower())

    def test_interrupted_prd_write_is_recoverable(self):
        revisions.initialize(self.product, self.prd, "产品")
        original = revisions.atomic_write
        def interrupted(path, content):
            if Path(path) == self.prd:
                raise OSError("模拟断电")
            original(path, content)
        with mock.patch.object(revisions, "atomic_write", side_effect=interrupted):
            with self.assertRaises(OSError):
                revisions.revise(self.product, self.prd, "修订正文\n", "产品", "反馈", "REQ-001")
        self.assertTrue((self.product / "pending-revision.json").is_file())
        revisions.complete_pending(self.product)
        result = Result.empty()
        revisions.validate_revisions(self.product, self.prd, result)
        self.assertEqual([], result.errors)

    def test_unknown_scope_does_not_need_snapshot(self):
        self.confirm_ui()
        sources = self.ledger()["cycles"]["v1.2"]["roles"]["ui"]["sources"]
        for source in sources.values():
            source["changes"] = None
        self.assertFalse(gates.source_state(self.root, self.config, "v1.2", sources))
        sources["prd"]["path"] = "../outside"
        with self.assertRaisesRegex(ValueError, "路径"):
            gates.source_state(self.root, self.config, "v1.2", sources)

    def test_unsupported_record_is_rejected_without_any_gate_write(self):
        data = self.ledger()
        original = {"status": "confirmed", "confirmedBy": "旧确认人", "confirmedGit": "unverified"}
        data["cycles"]["v1.2"]["roles"]["product"] = {"legacyRecord": original}
        atomic_write(self.root / "Gate.yaml", yaml.safe_dump(data, allow_unicode=True))
        before = (self.root / "Gate.yaml").read_bytes()
        result = Result.empty()
        self.assertFalse(gates.validate_cycle(self.cycle, self.config, self.root, result)["product"].passed)
        self.assertTrue(any("不支持" in error for error in result.errors))
        with self.assertRaisesRegex(ValueError, "不支持"):
            gates.update_role(self.root, self.config, "v1.2", "product", "in_progress", "产品", "新工作")
        with self.assertRaisesRegex(ValueError, "不支持"):
            self.update("in_progress")
        self.assertEqual(before, (self.root / "Gate.yaml").read_bytes())

    def test_unsupported_gate_schema_is_rejected_without_write(self):
        original = self.ledger()
        for version in (1, 0, 3, "2", 2.0, True, None, []):
            with self.subTest(version=version):
                data = copy.deepcopy(original)
                data["schemaVersion"] = version
                atomic_write(self.root / "Gate.yaml", yaml.safe_dump(data))
                before = (self.root / "Gate.yaml").read_bytes()
                result = Result.empty()
                self.assertIsNone(gates.validate_ledger(self.root, self.config, result))
                self.assertTrue(any("仅支持" in error for error in result.errors))
                for operation in (lambda: self.update("in_progress"), lambda: gates.initialize_cycle(self.root, self.config, "v1.3")):
                    with self.assertRaisesRegex(ValueError, "仅支持"):
                        operation()
                self.assertEqual(before, (self.root / "Gate.yaml").read_bytes())

    def test_existing_execution_is_checked_even_before_role_starts(self):
        path = self.cycle / "develop/execution.yaml"
        before = (self.root / "Gate.yaml").read_bytes()
        for version in (6, "7", 7.0, True, None):
            with self.subTest(version=version):
                atomic_write(path, yaml.safe_dump({"schemaVersion": version, "version": "v1.2"}))
                result = Result.empty()
                gates.validate_cycle(self.cycle, self.config, self.root, result)
                self.assertTrue(any("Execution 仅支持" in error for error in result.errors))
                with self.assertRaisesRegex(ValueError, "Execution 仅支持"):
                    self.update("in_progress")
                self.assertEqual(before, (self.root / "Gate.yaml").read_bytes())
        atomic_write(path, yaml.safe_dump({"schemaVersion": 7, "version": "v1.2"}))
        result = Result.empty()
        outcomes = gates.validate_cycle(self.cycle, self.config, self.root, result)
        self.assertEqual([], result.errors)
        self.assertTrue(all(not outcome.passed for outcome in outcomes.values()))
        self.update("in_progress")

    def test_unsupported_execution_blocks_initializing_gate(self):
        path = self.root / "Gate.yaml"
        path.unlink()
        atomic_write(self.cycle / "develop/execution.yaml", yaml.safe_dump({"schemaVersion": 6, "version": "v1.2"}))
        with self.assertRaisesRegex(ValueError, "Execution 仅支持"):
            gates.initialize_cycle(self.root, self.config, "v1.2")
        self.assertFalse(path.exists())

    def test_snapshot_source_and_digest_evidence_rejected_in_any_event(self):
        self.confirm_ui()
        self.update("in_progress")
        original = self.ledger()
        for location in ("current", "initial-event", "confirmed-event"):
            for field in ("sources", "evidence"):
                with self.subTest(location=location, field=field):
                    data = copy.deepcopy(original)
                    record = data["cycles"]["v1.2"]["roles"]["ui"]
                    target = record if location == "current" else record["history"][0 if location == "initial-event" else 2]["record"]
                    if field == "sources":
                        target[field] = gates.capture_sources(self.root, self.config, "v1.2")
                        target[field]["prd"] = {"path": target[field]["prd"]["path"], "sha256": "a" * 64, "snapshot": ".harness/evidence/prd/old.md"}
                    else:
                        target[field] = [{"path": self.evidence, "sha256": "a" * 64}]
                    atomic_write(self.root / "Gate.yaml", yaml.safe_dump(data))
                    before = (self.root / "Gate.yaml").read_bytes()
                    result = Result.empty()
                    gates.validate_ledger(self.root, self.config, result)
                    self.assertTrue(any("仅支持" in error for error in result.errors))
                    with self.assertRaisesRegex(ValueError, "仅支持"):
                        self.update("in_progress")
                    self.assertEqual(before, (self.root / "Gate.yaml").read_bytes())

    def test_invalid_first_role_reports_errors_without_crashing(self):
        data = self.ledger()
        data["cycles"]["v1.2"]["roles"]["product"]["status"] = "invalid"
        atomic_write(self.root / "Gate.yaml", yaml.safe_dump(data, allow_unicode=True))
        result = Result.empty()
        outcomes = gates.validate_cycle(self.cycle, self.config, self.root, result)
        self.assertFalse(outcomes["product"].passed)
        self.assertTrue(result.errors)

    def test_config_rejects_cycle_specific_prototype(self):
        template = Path(__file__).parents[2] / "project-harness-template/.harness/harness.yaml"
        data = yaml.safe_load(template.read_text(encoding="utf-8"))
        data["core"].update(revision="a"*40, contentHash="b"*64)
        data["project"].update(id="demo", name="demo", prototypeRoot="原型仓库/v1.2")
        path = self.root / ".harness/harness.yaml"
        atomic_write(path, yaml.safe_dump(data, allow_unicode=True))
        result = Result.empty()
        self.assertIsNone(parse_config(path, result))
        self.assertTrue(any("prototypeRoot" in error for error in result.errors))


if __name__ == "__main__":
    unittest.main(verbosity=2)
