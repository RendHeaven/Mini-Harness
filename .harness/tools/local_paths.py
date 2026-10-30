"""Explicit per-invocation service paths; never changes repository ownership."""
from __future__ import annotations

import subprocess
from pathlib import Path
from urllib.parse import urlsplit

_OVERRIDES: dict[tuple[str, str], Path] = {}


def repository_identity(value: str) -> str:
    text = value.strip().rstrip("/")
    if "://" not in text and "@" in text and ":" in text:
        host, path = text.split(":", 1)
        text = "ssh://" + host + "/" + path
    parsed = urlsplit(text)
    if not parsed.hostname:
        return str(Path(text).resolve()).removesuffix(".git")
    return (parsed.hostname.lower() + (":" + str(parsed.port) if parsed.port else "")
            + parsed.path.rstrip("/").removesuffix(".git"))


def verify_repository(path: Path, expected: str) -> None:
    if not path.is_dir():
        raise ValueError("服务目录不存在")
    top = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, encoding="utf-8", check=True, timeout=10,
    )
    if Path(top.stdout.strip()).resolve() != path.resolve():
        raise ValueError("服务路径必须是 Git checkout 根目录")
    actual = subprocess.run(
        ["git", "-C", str(path), "remote", "get-url", "origin"],
        capture_output=True, text=True, encoding="utf-8", check=True, timeout=10,
    )
    if repository_identity(actual.stdout) != repository_identity(expected):
        raise ValueError("本地服务 origin 与项目服务目录不一致")


def configure_services(project_root: Path, services: dict, overrides: dict) -> None:
    _OVERRIDES.clear()
    for identifier, value in overrides.items():
        if identifier not in services or not isinstance(value, str) or not Path(value).is_absolute():
            raise ValueError("本地映射必须使用已登记服务 ID 和绝对路径")
        path = Path(value).resolve()
        verify_repository(path, services[identifier]["repository"])
        _OVERRIDES[(str(project_root.resolve()), identifier)] = path


def resolve_service_path(project_root: Path, identifier: str, local_path: str) -> Path:
    return _OVERRIDES.get((str(project_root.resolve()), identifier), (project_root / local_path).resolve())


def project_config_path(root: Path) -> Path:
    if (root / "harness" / "harness.yaml").exists():
        raise ValueError("只支持 .harness/harness.yaml；不支持 harness 配置路径")
    return root / ".harness" / "harness.yaml"
