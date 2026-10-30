# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "psycopg[binary]>=3.2,<4",
#   "sqlparse>=0.5.3,<0.6",
# ]
# ///

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import psycopg


TEMPLATE = Path(__file__).resolve().parents[2] / "project-harness-template"
TOOLS = TEMPLATE / ".harness/tools"
SPEC = importlib.util.spec_from_file_location("project_db_tool", TOOLS / "db_tool.py")
assert SPEC and SPEC.loader
db = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = db
SPEC.loader.exec_module(db)


class ProjectDatabaseToolTest(unittest.TestCase):
    def test_uv_metadata_declares_runtime_and_matches_test_dependencies(self) -> None:
        def metadata(path):
            text = path.read_text(encoding="utf-8")
            block = text.split("# /// script\n", 1)[1].split("# ///", 1)[0]
            return tomllib.loads("\n".join(line.removeprefix("# ") for line in block.splitlines()))

        runtime = metadata(TOOLS / "db_tool.py")
        tests = metadata(Path(__file__))
        self.assertEqual(">=3.10", runtime["requires-python"])
        self.assertEqual(set(runtime["dependencies"]), set(tests["dependencies"]))
        self.assertFalse((TOOLS / "requirements.txt").exists())

    def test_cli_help_is_utf8_without_python_encoding_configuration(self) -> None:
        environment = dict(os.environ)
        environment.pop("PYTHONIOENCODING", None)
        environment.pop("PYTHONUTF8", None)
        result = subprocess.run(
            [sys.executable, "-X", "utf8=0", str(TOOLS / "db_tool.py"), "--help"],
            capture_output=True, timeout=15, env=environment,
        )
        self.assertEqual(0, result.returncode)
        self.assertIn("只读查询", result.stdout.decode("utf-8"))

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.config = self.root / ".env.local"
        self.content = (
            "DB_HOST=example.invalid\nDB_PORT=5432\nDB_NAME=test_database\n"
            "DB_USERNAME=test_reader\nDB_PASSWORD='not-a-real-password # $value'\nDB_MAX_ROWS=2\n"
        )
        self.config.write_text(self.content, encoding="utf-8")

    def test_load_config_uses_local_values_not_environment(self) -> None:
        with patch.dict(os.environ, {"DB_HOST": "other.invalid", "DB_PASSWORD": "other", "PGDATABASE": "other"}):
            config = db.load_config(self.config)
        self.assertEqual("example.invalid", config.host)
        self.assertEqual("test_database", config.database)
        self.assertEqual("test_reader", config.username)
        self.assertEqual("not-a-real-password # $value", config.password)
        self.assertNotIn(config.password, repr(config))

    def test_empty_example_cannot_connect(self) -> None:
        with self.assertRaises(db.ToolError):
            db.load_config(TOOLS / ".env.example")
        with self.assertRaises(db.ToolError):
            db.load_config(self.root / "absent")

    def test_invalid_config_is_rejected_without_values(self) -> None:
        for extra in ("DB_HOST=private-value", "DB_PORT=0", "UNKNOWN=private-value", "DB_PASSWORD=\"unclosed-private-value"):
            with self.subTest(extra=extra):
                self.config.write_text(self.content + extra + "\n", encoding="utf-8")
                with self.assertRaises(db.ToolError) as error:
                    db.load_config(self.config)
                self.assertNotIn("private-value", str(error.exception))

    def test_config_quotes_comments_and_ranges(self) -> None:
        self.assertEqual('x"y # z', db.parse_value('"x\\\"y # z" # comment', 1))
        self.assertEqual("x#y", db.parse_value("x#y # comment", 1))
        for key, value in (("DB_PORT", "0"), ("DB_MAX_ROWS", "10001"), ("DB_SSLMODE", "invalid")):
            lines = [line for line in self.content.splitlines() if not line.startswith(key + "=")]
            self.config.write_text("\n".join(lines + [f"{key}={value}"]), encoding="utf-8")
            with self.assertRaises(db.ToolError):
                db.load_config(self.config)

    def test_read_only_sql_handles_literals_and_comments(self) -> None:
        for sql in (
            "SELECT 'delete; update' AS value; -- comment",
            "/* read-only query */ SELECT 1",
            "WITH result AS (SELECT 1 AS value) SELECT * FROM result",
            'SELECT 1 AS "update"',
            "SELECT $$delete; drop$$ AS text",
            "SHOW transaction_read_only", "EXPLAIN SELECT 1",
        ):
            with self.subTest(sql=sql):
                self.assertTrue(db.validate_read_only_sql(sql))

    def test_writes_multi_statements_and_session_changes_are_rejected(self) -> None:
        for sql in (
            "", "-- comment", "SELECT 1; SELECT 2", "DELETE FROM files",
            "WITH removed AS (DELETE FROM files RETURNING *) SELECT * FROM removed",
            "SELECT * INTO temp_copy FROM files", "SELECT * FROM files FOR UPDATE",
            "EXPLAIN ANALYZE SELECT 1", "SET transaction_read_only = off",
            "SELECT set_config('transaction_read_only', 'off', true)",
            "/* outer /* nested */ comment */ SELECT 1",
        ):
            with self.subTest(sql=sql), self.assertRaises(db.ToolError):
                db.validate_read_only_sql(sql)

    def connection(self):
        connection = MagicMock()
        connection.__enter__.return_value = connection
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.description = [SimpleNamespace(name="value")]
        cursor.fetchmany.return_value = [(1,), (2,), (3,)]
        return connection, cursor

    def test_readonly_transaction_binding_limit_and_cleanup(self) -> None:
        connection, cursor = self.connection()
        with patch.object(psycopg, "connect", return_value=connection) as connect:
            result = db.run_query(db.load_config(self.config), "SELECT %s AS value", [42])
        self.assertTrue(connection.read_only)
        self.assertFalse(connect.call_args.kwargs["autocommit"])
        self.assertEqual("test_database", connect.call_args.kwargs["dbname"])
        self.assertEqual(("SELECT %s AS value", [42]), cursor.execute.call_args.args)
        cursor.fetchmany.assert_called_once_with(3)
        connection.rollback.assert_called_once()
        connection.__exit__.assert_called_once()
        self.assertEqual([{"value": 1}, {"value": 2}], result.rows)
        self.assertTrue(result.truncated)

    def test_database_errors_redact_details_and_rollback(self) -> None:
        connection, cursor = self.connection()
        cursor.execute.side_effect = psycopg.OperationalError("private host private password SQL text")
        with patch.object(psycopg, "connect", return_value=connection):
            with self.assertRaises(db.ToolError) as error:
                db.run_query(db.load_config(self.config), "SELECT 1")
        self.assertNotIn("private", str(error.exception))
        connection.rollback.assert_called_once()
        connection.__exit__.assert_called_once()

    def test_duplicate_column_names_do_not_silently_lose_data(self) -> None:
        connection, cursor = self.connection()
        cursor.description = [SimpleNamespace(name="id"), SimpleNamespace(name="id")]
        with patch.object(psycopg, "connect", return_value=connection), self.assertRaises(db.ToolError):
            db.run_query(db.load_config(self.config), "SELECT 1 AS id, 2 AS id")
        connection.rollback.assert_called_once()

    def test_cli_sql_file_stdin_params_and_json(self) -> None:
        sql_file = self.root / "查询.sql"
        sql_file.write_text("SELECT 42 AS value", encoding="utf-8")
        cases = [
            ["--sql", "SELECT %s AS value", "--params", "[42]"],
            ["--file", str(sql_file)], [],
        ]
        for arguments in cases:
            output = io.StringIO()
            with patch.object(db, "run_query", return_value=db.QueryResult(["value"], [{"value": 42}], False)) as run:
                with patch.object(sys, "stdin", io.StringIO("SELECT 42 AS value")), contextlib.redirect_stdout(output):
                    self.assertEqual(0, db.main(["--config", str(self.config), "query", *arguments, "--format", "json"]))
            self.assertEqual([{"value": 42}], json.loads(output.getvalue()))
            self.assertTrue(run.call_args.args[1].startswith("SELECT"))

    def test_csv_empty_results_and_truncation_notice(self) -> None:
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            db.print_result(db.QueryResult(["id"], [], False), "csv")
            db.print_result(db.QueryResult(["id"], [{"id": 1}], True), "json")
        self.assertTrue(output.getvalue().startswith("id"))
        self.assertIn("截断", errors.getvalue())

    def test_git_ignores_local_config_but_not_example(self) -> None:
        (self.root / ".gitignore").write_bytes((TEMPLATE / ".gitignore").read_bytes())
        subprocess.run(["git", "init", str(self.root)], check=True, capture_output=True)
        for path, ignored in ((".harness/tools/.env.local", True), (".harness/tools/.env.example", False)):
            result = subprocess.run(["git", "-C", str(self.root), "check-ignore", "--no-index", path], capture_output=True)
            self.assertEqual(0 if ignored else 1, result.returncode)


if __name__ == "__main__":
    unittest.main()
