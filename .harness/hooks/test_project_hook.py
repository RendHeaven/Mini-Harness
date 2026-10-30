from __future__ import annotations

import json
import os
import shutil
import shlex
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from contextlib import closing


REPOSITORY = Path(__file__).resolve().parents[2]
TEMPLATE = REPOSITORY / "project-harness-template"


class ProjectHookTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.project = self.root / "项目 harness"
        shutil.copytree(TEMPLATE, self.project)
        self.core = self.root / "Atlas Core"
        self.collector = self.core / ".harness/hooks/usage_hook.py"
        self.collector.parent.mkdir(parents=True)
        self.capture = self.root / "capture.json"
        self.collector.write_text(
            "import json, os, sys\nfrom pathlib import Path\n"
            "Path(os.environ['TEST_CAPTURE']).write_text(json.dumps({"
            "'payload': json.load(sys.stdin), 'root': os.environ['HARNESS_PROJECT_ROOT'], "
            "'url': os.environ['HARNESS_TELEMETRY_URL'], "
            "'timeout': os.environ['HARNESS_TELEMETRY_TIMEOUT_SECONDS']}), encoding='utf-8')\n",
            encoding="utf-8",
        )
        self.environment = dict(os.environ)
        self.environment.update({
            "HARNESS_PROJECT_ROOT": str(self.project),
            "HARNESS_PYTHON": sys.executable,
            "HARNESS_TELEMETRY_URL": "",
            "HARNESS_TELEMETRY_TIMEOUT_SECONDS": "0.1",
            "HARNESS_TELEMETRY_DIR": str(self.root / "telemetry"),
            "TEST_CAPTURE": str(self.capture),
        })
        self.config = self.project / ".harness/harness.yaml"
        self.configure()
        self.payload = {
            "hook_event_name": "UserPromptSubmit", "cwd": str(self.root),
            "session_id": "session", "turn_id": "turn", "prompt": "测试问题",
        }

    def configure(self, path: str = "../Atlas Core", kind: str = "project") -> None:
        self.config.write_text(
            f"kind: {kind}\ncore:\n  localPath: {path}\n"
            "project:\n  id: template-test\n  name: 模板测试\n",
            encoding="utf-8",
        )

    def run_hook(self, command=None, cwd=None):
        return subprocess.run(
            command or [sys.executable, "-B", "-X", "utf8", str(self.project / ".harness/hooks/usage_hook.py")],
            input=json.dumps(self.payload, ensure_ascii=False),
            capture_output=True, text=True, encoding="utf-8", timeout=15,
            cwd=cwd or self.root, env=self.environment,
        )

    def captured(self):
        return json.loads(self.capture.read_text(encoding="utf-8"))

    def test_delegate_preserves_payload_project_and_environment(self) -> None:
        self.environment["HARNESS_PROJECT_ROOT"] = str(self.root / "wrong-project")
        result = self.run_hook()
        self.assertEqual(0, result.returncode, result.stderr)
        data = self.captured()
        self.assertEqual(self.payload, data["payload"])
        self.assertEqual(str(self.project.resolve()), data["root"])
        self.assertEqual("", data["url"])
        self.assertEqual("0.1", data["timeout"])

    def test_defaults_disable_upload_when_unset(self) -> None:
        del self.environment["HARNESS_TELEMETRY_URL"]
        del self.environment["HARNESS_TELEMETRY_TIMEOUT_SECONDS"]
        result = self.run_hook()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("", self.captured()["url"])
        self.assertEqual("3", self.captured()["timeout"])

    def test_quoted_paths_and_inline_comments(self) -> None:
        for path in ("'../Atlas Core' # 锁定 checkout", '"../Atlas Core" # comment', "../Atlas Core # comment"):
            with self.subTest(path=path):
                self.configure(path)
                result = self.run_hook()
                self.assertEqual("", result.stderr)
                self.assertEqual(self.payload, self.captured()["payload"])

    def test_missing_config_and_missing_collector_skip_without_payload_leak(self) -> None:
        self.config.unlink()
        missing_config = self.run_hook()
        self.configure("../private-missing-core")
        missing_collector = self.run_hook()
        for result in (missing_config, missing_collector):
            self.assertEqual(0, result.returncode)
            self.assertIn("加载失败", result.stderr)
            self.assertNotIn("private-missing-core", result.stderr)
            self.assertNotIn(self.payload["prompt"], result.stderr)
        self.assertFalse(self.capture.exists())

    def test_non_project_config_skips(self) -> None:
        self.configure(kind="core")
        self.assertIn("加载失败", self.run_hook().stderr)
        self.assertFalse(self.capture.exists())

    def test_only_dot_harness_configuration_is_read(self) -> None:
        other = self.project / "harness"
        other.mkdir()
        (other / "harness.yaml").write_text("kind: core\n", encoding="utf-8")
        self.assertEqual("", self.run_hook().stderr)
        self.assertEqual(self.payload, self.captured()["payload"])
        self.capture.unlink()
        self.config.unlink()
        self.assertIn("加载失败", self.run_hook().stderr)
        self.assertFalse(self.capture.exists())

    def test_self_reference_and_duplicate_path_skip(self) -> None:
        self.configure(".")
        self.assertIn("加载失败", self.run_hook().stderr)
        self.configure("../Atlas Core\n  localPath: ../other")
        self.assertIn("加载失败", self.run_hook().stderr)

    def test_collector_failure_does_not_propagate_or_leak(self) -> None:
        for script in ("raise RuntimeError('private payload')", "raise SystemExit(3)"):
            self.collector.write_text(script, encoding="utf-8")
            result = self.run_hook()
            self.assertEqual(0, result.returncode)
            self.assertIn("跳过采集", result.stderr)
            self.assertNotIn("private payload", result.stderr)

    def test_real_collector_round_trip_keeps_project_attribution(self) -> None:
        self.configure(json.dumps(REPOSITORY.as_posix()) + " # pinned checkout")
        self.assertEqual(0, self.run_hook().returncode)
        self.payload.update(hook_event_name="Stop", last_assistant_message="测试回答")
        self.assertEqual(0, self.run_hook().returncode)
        with closing(sqlite3.connect(self.root / "telemetry/spool.db")) as database:
            row = database.execute(
                "SELECT project_id, input_text, output_text, revision, upload_revision FROM interactions"
            ).fetchone()
        self.assertEqual(("template-test", "测试问题", "测试回答", 2, 0), row)

    def test_registered_commands_forward_events(self) -> None:
        config = json.loads((self.project / ".codex/hooks.json").read_text(encoding="utf-8"))
        self.assertEqual({"UserPromptSubmit", "Stop"}, set(config["hooks"]))
        nested = self.project / "nested folder"
        nested.mkdir()
        for name, groups in config["hooks"].items():
            hook = groups[0]["hooks"][0]
            self.payload["hook_event_name"] = name
            if os.name == "nt":
                # Codex executes commandWindows inside the selected shell. Direct
                # spawning misses PowerShell's expansion of nested -Command text.
                command = ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive",
                           "-Command", hook["commandWindows"]]
            else:
                command = ["sh", "-c", hook["command"]]
            result = self.run_hook(command=command, cwd=nested)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(self.payload, self.captured()["payload"])

    @unittest.skipUnless(os.name == "nt", "Windows shell compatibility")
    def test_windows_shells_find_git_root_and_preserve_stdin(self) -> None:
        subprocess.run(["git", "init", "--quiet", str(self.project)], check=True,
                       capture_output=True)
        config = json.loads((self.project / ".codex/hooks.json").read_text(encoding="utf-8"))
        nested = self.project / "中文 子目录"
        nested.mkdir()
        self.payload["prompt"] = '中文 $variable "双引号" \\path'
        for explicit_root in (True, False):
            if explicit_root:
                self.environment["HARNESS_PROJECT_ROOT"] = str(self.project)
            else:
                self.environment.pop("HARNESS_PROJECT_ROOT", None)
            for shell in ("powershell", "cmd"):
                for event, groups in config["hooks"].items():
                    with self.subTest(explicit_root=explicit_root, shell=shell, event=event):
                        self.capture.unlink(missing_ok=True)
                        self.payload["hook_event_name"] = event
                        command = groups[0]["hooks"][0]["commandWindows"]
                        if shell == "powershell":
                            args = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command]
                        else:
                            # raw command line matches Codex's cmd /C outer quoting.
                            args = 'cmd.exe /d /s /c "' + command + '"'
                        result = self.run_hook(command=args, cwd=self.root if explicit_root else nested)
                        self.assertEqual(0, result.returncode, result.stderr)
                        self.assertEqual(self.payload, self.captured()["payload"])
                        self.assertEqual(str(self.project.resolve()), self.captured()["root"])
                        self.assertEqual("", self.captured()["url"])

    def test_portable_command_finds_parent_or_explicit_project(self) -> None:
        config = json.loads((self.project / ".codex/hooks.json").read_text(encoding="utf-8"))
        command = shlex.split(config["hooks"]["Stop"][0]["hooks"][0]["command"])
        command[0] = sys.executable
        nested = self.project / "nested folder"
        nested.mkdir()
        del self.environment["HARNESS_PROJECT_ROOT"]
        self.assertEqual(0, self.run_hook(command=command, cwd=nested).returncode)
        self.assertEqual(self.payload, self.captured()["payload"])
        self.environment["HARNESS_PROJECT_ROOT"] = str(self.project)
        self.assertEqual(0, self.run_hook(command=command, cwd=self.root).returncode)
        self.assertEqual(str(self.project.resolve()), self.captured()["root"])


if __name__ == "__main__":
    unittest.main()
