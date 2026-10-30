from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


HOOK_PATH = Path(__file__).with_name("usage_hook.py")
SPEC = importlib.util.spec_from_file_location("usage_hook", HOOK_PATH)
assert SPEC and SPEC.loader
usage_hook = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(usage_hook)


class UsageHookTest(unittest.TestCase):

    def test_resource_pattern_matches_harness_directory_boundary(self) -> None:
        for path in (
            ".harness/workflow/backend-workflow.md",
            "/workspace/Mini-Harness/.harness/skills/backend/01-plan.md",
            r"D:\workspace\Mini-Harness\.harness\rules\review.md",
        ):
            with self.subTest(path=path):
                self.assertIsNotNone(usage_hook.RESOURCE_PATTERN.search(path))
        self.assertIsNone(
            usage_hook.RESOURCE_PATTERN.search("other-harness/workflow/example.md")
        )
        self.assertIsNone(usage_hook.RESOURCE_PATTERN.search(
            "/workspace/Mini-Harness/harness/workflow/backend-workflow.md"
        ))

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.core = self.root / "core"
        self.telemetry = self.root / "telemetry"
        (self.root / ".harness").mkdir()
        (self.root / ".harness" / "harness.yaml").write_text(
            "schemaVersion: 20\n"
            "kind: project\n"
            "core:\n"
            "  localPath: core\n"
            "project:\n"
            "  id: test-project\n"
            "  name: 测试项目\n",
            encoding="utf-8",
        )
        for category in usage_hook.RESOURCE_CATEGORIES:
            (self.core / ".harness" / category).mkdir(parents=True)
        (self.core / ".harness" / "workflow" / "backend-workflow.md").write_text(
            "workflow", encoding="utf-8"
        )
        (self.core / ".harness" / "skills" / "backend").mkdir()
        (self.core / ".harness" / "skills" / "backend" / "01-plan.md").write_text(
            "skill", encoding="utf-8"
        )
        (self.core / ".harness" / "template" / "plan.yaml").write_text(
            "template", encoding="utf-8"
        )
        (self.core / ".harness" / "rules" / "review.md").write_text(
            "rule", encoding="utf-8"
        )
        self.transcript = self.root / "transcript.jsonl"
        self.environment = patch.dict(
            os.environ,
            {
                "HARNESS_PROJECT_ROOT": str(self.root),
                "HARNESS_TELEMETRY_URL": "",
                "HARNESS_TELEMETRY_DIR": str(self.telemetry),
            },
        )
        self.environment.start()

    def tearDown(self) -> None:
        self.environment.stop()
        self.temp.cleanup()

    def test_atlas_root_resolves_project_core_path(self) -> None:
        self.assertEqual(self.core.resolve(), usage_hook.atlas_root(self.root))

    def test_atlas_root_without_project_config_returns_none(self) -> None:
        self.assertIsNone(usage_hook.atlas_root(self.root / "missing"))

    def test_project_metadata_and_core_path_accept_quoted_comments(self) -> None:
        config = self.root / ".harness/harness.yaml"
        config.write_text(
            "kind: 'project' # 项目\ncore:\n  localPath: \"core\" # checkout\n"
            "project:\n  id: test-project # ID\n  name: '测试项目' # 名称\n",
            encoding="utf-8",
        )
        self.assertEqual(self.core.resolve(), usage_hook.atlas_root(self.root))
        self.assertEqual({"id": "test-project", "name": "测试项目"}, usage_hook.project_metadata(self.root))

    def rows(self) -> list[sqlite3.Row]:
        connection = sqlite3.connect(self.telemetry / "spool.db")
        connection.row_factory = sqlite3.Row
        try:
            return connection.execute(
                "SELECT * FROM interactions ORDER BY created_at"
            ).fetchall()
        finally:
            connection.close()

    def append(self, record: dict) -> None:
        with self.transcript.open("a", encoding="utf-8") as output:
            output.write(json.dumps(record, ensure_ascii=False) + "\n")

    def token_record(
        self,
        input_tokens: int,
        cached: int,
        output: int,
        reasoning: int,
        total: int,
    ) -> dict:
        return {
            "type": "event_msg",
            "payload": {
                "type": "token_count",
                "info": {
                    "total_token_usage": {
                        "input_tokens": input_tokens,
                        "cached_input_tokens": cached,
                        "output_tokens": output,
                        "reasoning_output_tokens": reasoning,
                        "total_tokens": total,
                    }
                },
            },
        }

    def prompt(self, text: str = "问题") -> dict:
        return {
            "hook_event_name": "UserPromptSubmit",
            "session_id": "session-1",
            "turn_id": "turn-1",
            "cwd": str(self.root),
            "prompt": text,
            "transcript_path": str(self.transcript),
        }

    def stop(self, text: str = "回答") -> dict:
        return {
            "hook_event_name": "Stop",
            "session_id": "session-1",
            "turn_id": "turn-1",
            "cwd": str(self.root),
            "last_assistant_message": text,
            "transcript_path": str(self.transcript),
        }

    def test_unicode_boundaries_and_redaction(self) -> None:
        usage_hook.process_hook(self.prompt("中" * 500), self.telemetry)
        row = self.rows()[0]
        self.assertEqual("中" * 500, row["input_text"])
        self.assertEqual(0, row["input_truncated"])

        usage_hook.process_hook(
            {
                **self.prompt("password=super-secret-value " + "文" * 600),
                "turn_id": "turn-2",
            },
            self.telemetry,
        )
        row = self.rows()[1]
        self.assertEqual(500, len(row["input_text"]))
        self.assertEqual(1, row["input_truncated"])
        self.assertIn("[REDACTED]", row["input_text"])
        self.assertNotIn("super-secret-value", row["input_text"])

    def test_redacts_json_cli_and_uri_credentials(self) -> None:
        text = (
            '"password": "json-secret", '
            "--token cli-secret "
            "https://alice:uri-secret@example.test/path"
        )

        redacted, truncated = usage_hook.redact_and_truncate(text)

        self.assertFalse(truncated)
        self.assertNotIn("json-secret", redacted)
        self.assertNotIn("cli-secret", redacted)
        self.assertNotIn("uri-secret", redacted)
        self.assertGreaterEqual(redacted.count("[REDACTED]"), 3)

    def test_output_is_redacted_and_truncated_to_500(self) -> None:
        self.append(self.token_record(10, 0, 0, 0, 10))
        usage_hook.process_hook(self.prompt(), self.telemetry)
        self.append(self.token_record(20, 0, 8, 2, 28))

        usage_hook.process_hook(
            self.stop("token=private-value " + "答" * 600),
            self.telemetry,
        )

        row = self.rows()[0]
        self.assertEqual(2, row["revision"])
        self.assertEqual(500, len(row["output_text"]))
        self.assertEqual(1, row["output_truncated"])
        self.assertNotIn("private-value", row["output_text"])

    def test_git_local_overrides_global_and_missing_is_allowed(self) -> None:
        subprocess.run(["git", "init", "--quiet"], cwd=self.root, check=True)
        global_config = self.root / "global.gitconfig"
        subprocess.run(
            ["git", "config", "--file", str(global_config), "user.name", "Global"],
            check=True,
        )
        subprocess.run(
            [
                "git",
                "config",
                "--file",
                str(global_config),
                "user.email",
                "global@example.com",
            ],
            check=True,
        )
        with patch.dict(os.environ, {"GIT_CONFIG_GLOBAL": str(global_config)}):
            self.assertEqual("Global", usage_hook.git_user(self.root)["name"])
            subprocess.run(
                ["git", "config", "user.name", "Local"],
                cwd=self.root,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.email", "local@example.com"],
                cwd=self.root,
                check=True,
            )
            user = usage_hook.git_user(self.root)
        self.assertEqual("Local", user["name"])
        self.assertEqual("local@example.com", user["email"])

        with patch.object(usage_hook, "git_config", return_value=None):
            usage_hook.process_hook(
                {**self.prompt(), "turn_id": "missing-git"},
                self.telemetry,
            )
        row = self.rows()[0]
        self.assertIsNone(row["git_user_name"])
        self.assertIsNone(row["git_user_email"])

    def test_token_delta_cache_rate_and_resource_order(self) -> None:
        self.append(self.token_record(100, 40, 20, 5, 120))
        usage_hook.process_hook(self.prompt(), self.telemetry)
        commands = [
            self.core / ".harness" / "skills" / "backend" / "01-plan.md",
            self.core / ".harness" / "workflow" / "backend-workflow.md",
            self.core / ".harness" / "skills" / "backend" / "01-plan.md",
            self.core / ".harness" / "template" / "plan.yaml",
            self.core / ".harness" / "rules" / "review.md",
        ]
        for path in commands:
            self.append(
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": json.dumps(
                            {"command": f"Get-Content '{path}'"}
                        ),
                    },
                }
            )
        self.append(
            {
                "type": "response_item",
                "payload": {
                    "type": "function_call_output",
                    "output": str(
                        self.core
                        / ".harness"
                        / "workflow"
                        / "not-used.md"
                    ),
                },
            }
        )
        self.append(self.token_record(180, 100, 50, 15, 230))

        usage_hook.process_hook(self.stop(), self.telemetry)

        row = self.rows()[0]
        self.assertEqual(80, row["input_tokens"])
        self.assertEqual(30, row["output_tokens"])
        self.assertEqual(10, row["reasoning_tokens"])
        self.assertEqual(110, row["total_tokens"])
        self.assertEqual(60, row["cached_input_tokens"])
        self.assertAlmostEqual(0.75, row["cache_hit_rate"])
        self.assertEqual(
            ["skills/backend/01-plan.md"],
            json.loads(row["skills_json"]),
        )
        self.assertEqual(
            ["workflow/backend-workflow.md"],
            json.loads(row["workflows_json"]),
        )
        self.assertEqual(["template/plan.yaml"], json.loads(row["templates_json"]))
        self.assertEqual(["rules/review.md"], json.loads(row["rules_json"]))

    def test_directory_scan_and_tool_output_do_not_count(self) -> None:
        self.append(self.token_record(0, 0, 0, 0, 0))
        usage_hook.process_hook(self.prompt(), self.telemetry)
        self.append(
            {
                "type": "response_item",
                "payload": {
                    "type": "function_call",
                    "arguments": json.dumps(
                        {"command": f"rg --files {self.core / 'harness' / 'workflow'}"}
                    ),
                },
            }
        )
        self.append(
            {
                "type": "response_item",
                "payload": {
                    "type": "function_call_output",
                    "output": str(
                        self.core
                        / ".harness"
                        / "workflow"
                        / "backend-workflow.md"
                    ),
                },
            }
        )
        self.append(self.token_record(1, 0, 1, 0, 2))

        usage_hook.process_hook(self.stop(), self.telemetry)

        self.assertEqual([], json.loads(self.rows()[0]["workflows_json"]))

    def test_resources_are_scoped_to_current_turn_and_atlas_core(self) -> None:
        other_core = self.root / "other-core"
        other_resource = (
            other_core / ".harness" / "workflow" / "other-workflow.md"
        )
        other_resource.parent.mkdir(parents=True)
        other_resource.write_text("other", encoding="utf-8")
        self.append(self.token_record(0, 0, 0, 0, 0))
        usage_hook.process_hook(self.prompt(), self.telemetry)
        for turn_id, path in (
            (
                "another-turn",
                self.core / ".harness" / "workflow" / "backend-workflow.md",
            ),
            ("turn-1", other_resource),
            (
                "turn-1",
                self.core / ".harness" / "skills" / "backend" / "01-plan.md",
            ),
        ):
            self.append(
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "arguments": json.dumps(
                            {"command": f"Get-Content '{path}'"}
                        ),
                        "internal_chat_message_metadata_passthrough": {
                            "turn_id": turn_id
                        },
                    },
                }
            )
        self.append(self.token_record(2, 0, 1, 0, 3))

        usage_hook.process_hook(self.stop(), self.telemetry)

        row = self.rows()[0]
        self.assertEqual([], json.loads(row["workflows_json"]))
        self.assertEqual(
            ["skills/backend/01-plan.md"],
            json.loads(row["skills_json"]),
        )

    def test_same_revision_snapshot_is_immutable(self) -> None:
        self.append(self.token_record(1, 0, 0, 0, 1))
        usage_hook.process_hook(self.prompt("原始问题"), self.telemetry)
        usage_hook.process_hook(self.prompt("被重放的问题"), self.telemetry)
        self.assertEqual("原始问题", self.rows()[0]["input_text"])

        self.append(self.token_record(2, 0, 1, 0, 3))
        usage_hook.process_hook(self.stop("原始回答"), self.telemetry)
        usage_hook.process_hook(self.stop("被重放的回答"), self.telemetry)

        row = self.rows()[0]
        self.assertEqual("原始回答", row["output_text"])
        self.assertEqual(2, row["revision"])

    def test_missing_transcript_keeps_text_and_null_metrics(self) -> None:
        usage_hook.process_hook(
            {**self.prompt(), "transcript_path": str(self.root / "missing.jsonl")},
            self.telemetry,
        )
        usage_hook.process_hook(
            {**self.stop(), "transcript_path": str(self.root / "missing.jsonl")},
            self.telemetry,
        )

        row = self.rows()[0]
        self.assertEqual("问题", row["input_text"])
        self.assertEqual("回答", row["output_text"])
        self.assertIsNone(row["input_tokens"])
        self.assertEqual([], json.loads(row["rules_json"]))
        log = (self.telemetry / "collector.log").read_text(encoding="utf-8")
        self.assertIn("transcript_unavailable", log)
        self.assertNotIn("问题", log)
        self.assertNotIn("回答", log)

    def test_counter_rollback_sets_all_metrics_null(self) -> None:
        self.append(self.token_record(100, 20, 30, 5, 130))
        usage_hook.process_hook(self.prompt(), self.telemetry)
        self.append(self.token_record(90, 10, 20, 4, 110))
        usage_hook.process_hook(self.stop(), self.telemetry)
        row = self.rows()[0]
        self.assertIsNone(row["input_tokens"])
        self.assertIsNone(row["cache_hit_rate"])

    def assert_database_unchanged(self) -> None:
        before = {path.name: path.read_bytes() for path in self.telemetry.iterdir()}
        with self.assertRaisesRegex(RuntimeError, "unsupported_outbox_schema"):
            usage_hook.connect_database(self.telemetry)
        after = {path.name: path.read_bytes() for path in self.telemetry.iterdir()}
        self.assertEqual(before, after)

    def test_non_current_outbox_is_rejected_before_any_write(self) -> None:
        self.telemetry.mkdir()
        for version in (0, 1, usage_hook.OUTBOX_SCHEMA_VERSION + 1):
            with self.subTest(version=version):
                database = self.telemetry / "spool.db"
                connection = sqlite3.connect(database)
                connection.execute("CREATE TABLE user_data (payload TEXT)")
                connection.execute("INSERT INTO user_data VALUES ('keep')")
                connection.execute(f"PRAGMA user_version={version}")
                connection.commit()
                connection.close()
                self.assert_database_unchanged()
                database.unlink()

    def wal_database_fixture(self, version: int, *, with_shm: bool = False) -> None:
        source = self.root / "wal-source"
        source.mkdir(exist_ok=True)
        database = source / "spool.db"
        writer = sqlite3.connect(database)
        try:
            writer.execute("PRAGMA journal_mode=WAL")
            if version == usage_hook.OUTBOX_SCHEMA_VERSION:
                writer.execute(usage_hook.OUTBOX_TABLE_SQL)
                writer.execute(usage_hook.OUTBOX_INDEX_SQL)
            else:
                writer.execute("CREATE TABLE old_events (value TEXT)")
                writer.execute("INSERT INTO old_events VALUES ('keep')")
            writer.execute(f"PRAGMA user_version={version}")
            writer.commit()
            self.telemetry.mkdir()
            for suffix in ("", "-wal", "-shm") if with_shm else ("", "-wal"):
                shutil.copyfile(source / ("spool.db" + suffix), self.telemetry / ("spool.db" + suffix))
        finally:
            writer.close()

    def test_old_wal_without_shared_memory_is_rejected_without_creating_files(self) -> None:
        self.wal_database_fixture(1)
        self.assert_database_unchanged()

    def test_old_wal_with_shared_memory_is_rejected_without_mutating_files(self) -> None:
        self.wal_database_fixture(1, with_shm=True)
        self.assert_database_unchanged()

    def test_current_schema_only_in_wal_can_connect(self) -> None:
        self.wal_database_fixture(usage_hook.OUTBOX_SCHEMA_VERSION)
        connection = usage_hook.connect_database(self.telemetry)
        try:
            self.assertEqual(usage_hook.OUTBOX_SCHEMA_VERSION, connection.execute(
                "PRAGMA user_version"
            ).fetchone()[0])
            self.assertEqual(0, connection.execute("SELECT count(*) FROM interactions").fetchone()[0])
        finally:
            connection.close()

    def test_source_change_during_inspection_is_rejected_before_opening_original(self) -> None:
        self.wal_database_fixture(usage_hook.OUTBOX_SCHEMA_VERSION)
        copy = shutil.copyfile
        changed = False

        def concurrent_write(source, target):
            nonlocal changed
            result = copy(source, target)
            if not changed:
                changed = True
                wal = self.telemetry / "spool.db-wal"
                with wal.open("ab") as stream:
                    stream.write(b"writer-change")
            return result

        with patch.object(usage_hook.shutil, "copyfile", side_effect=concurrent_write):
            with self.assertRaisesRegex(RuntimeError, "outbox_changed_during_inspection"):
                usage_hook.connect_database(self.telemetry)
        self.assertFalse((self.telemetry / "spool.db-shm").exists())

    def test_matching_version_with_wrong_schema_is_rejected_unchanged(self) -> None:
        self.telemetry.mkdir()
        database = self.telemetry / "spool.db"
        connection = sqlite3.connect(database)
        connection.execute("CREATE TABLE interactions (input_text TEXT)")
        connection.execute("INSERT INTO interactions VALUES ('keep')")
        connection.execute(f"PRAGMA user_version={usage_hook.OUTBOX_SCHEMA_VERSION}")
        connection.commit()
        connection.close()
        self.assert_database_unchanged()

    def test_current_database_connects_without_replacing_existing_rows(self) -> None:
        usage_hook.process_hook(self.prompt("keep"), self.telemetry)
        connection = usage_hook.connect_database(self.telemetry)
        try:
            self.assertEqual("keep", connection.execute(
                "SELECT input_text FROM interactions"
            ).fetchone()[0])
            self.assertEqual(usage_hook.OUTBOX_SCHEMA_VERSION, connection.execute(
                "PRAGMA user_version"
            ).fetchone()[0])
        finally:
            connection.close()

    def test_current_version_with_changed_constraints_or_extra_objects_is_rejected(self) -> None:
        self.telemetry.mkdir()
        for extra in (False, True):
            with self.subTest(extra=extra):
                database = self.telemetry / "spool.db"
                connection = sqlite3.connect(database)
                sql = usage_hook.OUTBOX_TABLE_SQL
                if not extra:
                    sql = sql.replace("CHECK (revision BETWEEN 1 AND 2)", "")
                connection.execute(sql)
                connection.execute(usage_hook.OUTBOX_INDEX_SQL)
                if extra:
                    connection.execute("CREATE TABLE unexpected (value TEXT)")
                connection.execute(f"PRAGMA user_version={usage_hook.OUTBOX_SCHEMA_VERSION}")
                connection.commit()
                connection.close()
                self.assert_database_unchanged()
                database.unlink()

    def test_existing_empty_database_is_initialized(self) -> None:
        self.telemetry.mkdir()
        sqlite3.connect(self.telemetry / "spool.db").close()
        connection = usage_hook.connect_database(self.telemetry)
        try:
            self.assertEqual(0, connection.execute("SELECT count(*) FROM interactions").fetchone()[0])
        finally:
            connection.close()

    def test_configuration_only_uses_dot_harness(self) -> None:
        config = self.root / ".harness/harness.yaml"
        old = self.root / "harness/harness.yaml"
        old.parent.mkdir()
        config.rename(old)
        self.assertIsNone(usage_hook.find_project_root(self.root))
        self.assertIsNone(usage_hook.project_metadata(self.root))
        self.assertIsNone(usage_hook.atlas_root(self.root))

    def test_revision_one_and_two_upload_same_interaction(self) -> None:
        sent: list[dict] = []

        def accept(request, timeout):
            body = json.loads(request.data.decode("utf-8"))
            interaction = body["interactions"][0]
            sent.append(interaction)
            response = MagicMock()
            response.read.return_value = json.dumps(
                {
                    "upserted": [interaction["interaction_id"]],
                    "unchanged": [],
                    "rejected": [],
                }
            ).encode("utf-8")
            response.__enter__.return_value = response
            return response

        self.append(self.token_record(1, 0, 0, 0, 1))
        with (
            patch.dict(
                os.environ,
                {"HARNESS_TELEMETRY_URL": "http://telemetry.test"},
            ),
            patch.object(usage_hook.urllib_request, "urlopen", side_effect=accept),
        ):
            self.assertEqual(
                "http://telemetry.test/api/v1/interactions/batch",
                usage_hook.telemetry_endpoint(),
            )
            usage_hook.process_hook(self.prompt(), self.telemetry)
            self.append(self.token_record(3, 1, 2, 1, 5))
            usage_hook.process_hook(self.stop(), self.telemetry)

        self.assertEqual([1, 2], [item["revision"] for item in sent])
        self.assertEqual(sent[0]["interaction_id"], sent[1]["interaction_id"])
        row = self.rows()[0]
        self.assertEqual(2, row["upload_revision"])

    def test_upload_has_no_authorization_and_failure_is_retried(self) -> None:
        captured = []

        def fail(request, timeout):
            captured.append(request)
            raise OSError("secret question content")

        with (
            patch.dict(
                os.environ,
                {"HARNESS_TELEMETRY_URL": "http://telemetry.test"},
            ),
            patch.object(usage_hook.urllib_request, "urlopen", side_effect=fail),
        ):
            self.assertTrue(
                usage_hook.process_hook(self.prompt("敏感问题"), self.telemetry)
            )

        self.assertIsNone(captured[0].get_header("Authorization"))
        row = self.rows()[0]
        self.assertEqual(1, row["upload_attempts"])
        self.assertEqual("OSError", row["last_upload_error"])
        self.assertIsNotNone(row["next_attempt_at"])

    def test_utf8_subprocess_entrypoint(self) -> None:
        payload = {
            **self.prompt("中文输入"),
            "turn_id": "utf8-turn",
        }
        result = subprocess.run(
            [sys.executable, "-X", "utf8", str(HOOK_PATH)],
            input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            env=os.environ.copy(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr.decode("utf-8"))
        rows = self.rows()
        self.assertEqual("中文输入", rows[0]["input_text"])


if __name__ == "__main__":
    unittest.main()
