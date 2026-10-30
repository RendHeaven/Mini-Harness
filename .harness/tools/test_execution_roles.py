"""Replay full service fixtures through Schema 20 without Product/UI handoff inputs."""
from dataclasses import replace
import unittest
import yaml
from asset_io import atomic_write
from core_validation import Result
from project_protocol import default_config
import test_validate_harness as fixtures
import role_gates as gates
import prd_revision


class IndependentEngineeringTest(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ProductCycleValidationTest()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        f = self.fixture
        old_cycle = f.create_cycle()
        f.create_development(old_cycle)
        self.root = f.project
        for args in (("init",), ("config", "--local", "user.name", "角色确认者"), ("config", "--local", "user.email", "role-reviewer@example.test")):
            f.git(*args, cwd=self.root)
        self.cycle = self.root / ".harness/demandCycle/v1.2"
        self.config = replace(default_config(), project_id="sample")
        atomic_write(self.root / "原型仓库/index.html", "<html>项目持续原型</html>")
        self.prd = self.cycle / "product/v1.2-prd.md"
        gates.initialize_cycle(self.root, self.config, "v1.2")
        sources = gates.capture_sources(self.root, self.config, "v1.2")
        execution = self.cycle / "develop/execution.yaml"
        data = yaml.safe_load(execution.read_text(encoding="utf-8"))
        data.update(schemaVersion=7, sources=sources)
        for role in ("frontend", "backend"):
            data["tracks"][role]["sources"] = sources
        data["tracks"]["frontend"]["uiScopeReason"] = "仅接口接入，无页面改动"
        atomic_write(execution, yaml.safe_dump(data, allow_unicode=True, sort_keys=False))

    def confirm(self, role):
        prefix = ".harness/demandCycle/v1.2/"
        evidence = prefix + ("product/mock-changelog.md" if role == "product" else "develop/execution.yaml")
        for status in ("in_progress", "pending_confirmation", "confirmed"):
            gates.update_role(self.root, self.config, "v1.2", role, status, "测试负责人", "独立确认验证", [evidence])
        record = gates.load_ledger(self.root, self.config)["cycles"]["v1.2"]["roles"]
        self.assertEqual("confirmed", record[role]["status"])
        self.assertEqual({"name": "角色确认者", "email": "role-reviewer@example.test"}, record[role]["confirmedGit"])
        self.assertEqual(record[role]["confirmedGit"], record[role]["history"][-1]["record"]["confirmedGit"])
        self.assertTrue(all(record[other]["status"] == "not_started" for other in gates.ROLES if other != role))
        result = Result.empty()
        outcomes = gates.validate_cycle(self.cycle, self.config, self.root, result)
        self.assertEqual([], result.errors)
        self.assertTrue(outcomes[role].passed, outcomes[role].failed_checks)

    def test_frontend_confirmation_without_product_ui_backend_gates(self):
        self.confirm("frontend")

    def test_backend_confirmation_without_product_ui_frontend_gates(self):
        self.confirm("backend")

    def test_product_confirmation_without_frontend_implementation(self):
        self.confirm("product")


if __name__ == "__main__":
    unittest.main(verbosity=2)
