from __future__ import annotations

import os
import json
import re
import runpy
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TELEMETRY_URL = ""
DEFAULT_TELEMETRY_TIMEOUT_SECONDS = "3"


def core_root() -> Path:
    config_path = PROJECT_ROOT / ".harness" / "harness.yaml"
    if not config_path.is_file():
        raise ValueError("项目 .harness/harness.yaml 配置缺失")
    config = config_path.read_text(encoding="utf-8-sig")
    if not re.search(r"(?m)^kind:\s*['\"]?project['\"]?\s*(?:#.*)?$", config):
        raise ValueError("hook 入口仅用于 kind: project")
    core_section = re.search(
        r"(?ms)^core:\s*$\n(?P<body>(?:^[ \t]+.*(?:\n|$))*)",
        config,
    )
    if core_section is None:
        raise RuntimeError("harness.yaml 缺少 core 配置")
    matches = re.findall(r"(?m)^[ \t]+localPath:[ \t]*(.*)$", core_section.group("body"))
    if len(matches) != 1:
        raise ValueError("core.localPath 缺失或重复")
    raw = matches[0].strip()
    # 项目模板使用单行路径标量；复杂 YAML 写法应在项目配置校验时修正。
    if raw.startswith('"'):
        local_path, end = json.JSONDecoder().raw_decode(raw)
        remainder = raw[end:].strip()
    elif raw.startswith("'"):
        quoted = re.fullmatch(r"'((?:[^']|'')*)'\s*(#.*)?", raw)
        if quoted is None:
            raise ValueError("core.localPath 单引号未闭合")
        local_path, remainder = quoted.group(1).replace("''", "'"), ""
    else:
        local_path, remainder = re.split(r"\s+#", raw, maxsplit=1)[0].strip(), ""
    if remainder and not remainder.startswith("#"):
        raise ValueError("core.localPath 尾部存在无效内容")
    if not isinstance(local_path, str) or not local_path or local_path[0] in "<[{&*!|>":
        raise ValueError("core.localPath 必须填写实际单行路径")
    return (PROJECT_ROOT / local_path).resolve()


def main() -> int:
    os.environ["HARNESS_PROJECT_ROOT"] = str(PROJECT_ROOT)
    os.environ.setdefault("HARNESS_TELEMETRY_URL", DEFAULT_TELEMETRY_URL)
    os.environ.setdefault(
        "HARNESS_TELEMETRY_TIMEOUT_SECONDS",
        DEFAULT_TELEMETRY_TIMEOUT_SECONDS,
    )
    try:
        collector = core_root() / ".harness" / "hooks" / "usage_hook.py"
        if collector.resolve() == Path(__file__).resolve():
            raise ValueError("项目入口不能作为 Core 采集器加载")
        if not collector.is_file():
            raise FileNotFoundError("Core 采集器不存在")
        runpy.run_path(str(collector), run_name="__main__")
    except SystemExit as error:
        if error.code not in (None, 0):
            print("[project-harness-hook] Core 采集器退出异常，已跳过采集", file=sys.stderr)
    except Exception as error:
        # 不输出异常正文、配置内容或 Hook payload，避免诊断泄露用户内容。
        print(f"[project-harness-hook] 加载失败（{type(error).__name__}），已跳过采集", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
