"""同步 Core 模板的公共时间块；默认只读，不生成项目产物或真实时间。"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path, PurePosixPath
import stat
import tempfile


FRAGMENT = "template/_fragments/document-timestamps.md"
START = b"<!-- atlas:generated document-timestamps:start -->"
END = b"<!-- atlas:generated document-timestamps:end -->"
MARKER = b"atlas:generated"
# 显式登记保证标记被整块删除后仍能检测；不从正文猜测哪些文件应被写入。
TEMPLATE_PATHS = (
    "template/develop/backend/checklist-template.md",
    "template/develop/backend/exec-module-template.md",
    "template/develop/backend/exec-overview-template.md",
    "template/develop/backend/external-design-template.md",
    "template/develop/backend/external-minio-template.md",
    "template/develop/backend/external-nacos-template.md",
    "template/develop/backend/external-permission-template.md",
    "template/develop/backend/external-sql-template.md",
    "template/develop/backend/interface-document-template.md",
    "template/develop/backend/interface-test-template.md",
    "template/develop/backend/plan-overview-template.md",
    "template/develop/backend/plan-template.md",
    "template/develop/backend/review-overview-template.md",
    "template/develop/backend/review-template.md",
    "template/develop/backend/tdd-overview-template.md",
    "template/develop/backend/tdd-template.md",
    "template/develop/frontend/api-plan-template.md",
    "template/develop/frontend/review-template.md",
    "template/develop/frontend/task-exec-template.md",
    "template/develop/frontend/test-feed-template.md",
    "template/develop/frontend/ui-exec-template.md",
    "template/develop/frontend/ui-plan-module-template.md",
    "template/develop/frontend/ui-plan-template.md",
    "template/develop/frontend-mock/mock-plan-template.md",
    "template/develop/frontend-mock/mock-source-matrix-template.md",
    "template/develop/frontend-mock/mock-verification-template.md",
    "template/develop/testhub/cases-template.md",
    "template/develop/testhub/change-impact-analysis-template.md",
    "template/develop/testhub/coverage-matrix-template.md",
    "template/develop/testhub/sync-report-template.md",
    "template/develop/testhub/test-design-template.md",
)


@dataclass(frozen=True)
class Change:
    relative: str
    before: bytes
    after: bytes


@dataclass(frozen=True)
class Plan:
    root: Path
    inputs: dict[str, bytes]
    changes: tuple[Change, ...]


def _reject_redirect(path: Path) -> os.stat_result:
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
        raise ValueError(f"拒绝路径重定向：{path}")
    return info


def _file(root: Path, relative: str) -> Path:
    parts = PurePosixPath(relative)
    if parts.is_absolute() or "\\" in relative or ":" in relative or any(p in {"", ".", ".."} for p in relative.split("/")):
        raise ValueError(f"非法相对路径：{relative}")
    for parent in (root, *root.parents):
        if not stat.S_ISDIR(_reject_redirect(parent).st_mode):
            raise ValueError(f"不是目录：{parent}")
    path = root
    for index, part in enumerate(parts.parts):
        path = path / part
        info = _reject_redirect(path)
        required = stat.S_ISREG if index == len(parts.parts) - 1 else stat.S_ISDIR
        if not required(info.st_mode):
            raise ValueError(f"文件类型不符：{path}")
    return path


def _read(root: Path, relative: str) -> bytes:
    data = _file(root, relative).read_bytes()
    data.decode("utf-8")
    return data


def _markdown_files(root: Path):
    pending = [root / "template"]
    while pending:
        directory = pending.pop()
        _reject_redirect(directory)
        for path in sorted(directory.iterdir()):
            info = _reject_redirect(path)
            if stat.S_ISDIR(info.st_mode):
                pending.append(path)
            elif stat.S_ISREG(info.st_mode) and path.suffix == ".md":
                yield path.relative_to(root).as_posix()


def render(data: bytes, fragment: bytes, label: str) -> bytes:
    """只替换唯一标记对之间的字节；正文和标记行保持原样。"""
    lines = data.splitlines(keepends=True)
    markers = [index for index, line in enumerate(lines) if MARKER in line]
    if len(markers) != 2:
        raise ValueError(f"{label}：必须有唯一完整的时间块标记对")
    start, end = markers
    if lines[start].rstrip(b"\r\n") != START or lines[end].rstrip(b"\r\n") != END:
        raise ValueError(f"{label}：未知片段、错误顺序或非法标记")
    if not lines[start].endswith(b"\n"):
        raise ValueError(f"{label}：开始标记须独占一行")
    newline = b"\r\n" if lines[start].endswith(b"\r\n") else b"\n"
    return b"".join(lines[:start + 1]) + fragment.replace(b"\n", newline) + b"".join(lines[end:])


def make_plan(root: Path, targets: tuple[str, ...] = TEMPLATE_PATHS) -> Plan:
    """targets 仅供测试和受控迁移使用；CLI 总是检查全部登记模板。"""
    root = root.absolute()
    if not targets or len(targets) != len(set(targets)) or not set(targets).issubset(TEMPLATE_PATHS):
        raise ValueError("只能选择已登记的 Core 模板，且不得重复")
    original = _read(root, FRAGMENT)
    fragment = original.replace(b"\r\n", b"\n")
    if not fragment.strip() or not fragment.endswith(b"\n") or b"\r" in fragment or fragment.startswith(b"\xef\xbb\xbf") or MARKER in fragment:
        raise ValueError("时间片段必须是非空 UTF-8 正文，以换行结束且不包含生成标记")
    inputs = {FRAGMENT: original}
    for relative in _markdown_files(root):
        data = _read(root, relative)
        inputs[relative] = data
        if MARKER in data and relative not in TEMPLATE_PATHS:
            raise ValueError(f"未登记模板包含生成标记：{relative}")
    changes = []
    for relative in targets:
        data = inputs.get(relative)
        if data is None:
            raise ValueError(f"缺少登记模板：{relative}")
        rendered = render(data, fragment, relative)
        if rendered != data:
            changes.append(Change(relative, data, rendered))
    return Plan(root, inputs, tuple(changes))


def _stage(path: Path, data: bytes, suffix: str) -> Path:
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.atlas-", suffix=suffix, dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        temporary.chmod(stat.S_IMODE(path.stat().st_mode))
        return temporary
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def apply_plan(plan: Plan) -> None:
    """预检、暂存、再核对后逐文件原子替换；失败时保护并发编辑并尝试回滚。"""
    def verify_inputs():
        for relative, before in plan.inputs.items():
            if _read(plan.root, relative) != before:
                raise ValueError(f"输入已变化，请重新检查：{relative}")

    verify_inputs()
    staged: dict[str, tuple[Path, Path]] = {}
    temporaries: set[Path] = set()
    applied: list[Change] = []
    try:
        for change in plan.changes:
            path = _file(plan.root, change.relative)
            new = _stage(path, change.after, ".tmp")
            temporaries.add(new)
            old = _stage(path, change.before, ".bak")
            temporaries.add(old)
            staged[change.relative] = (new, old)
        verify_inputs()
        for change in plan.changes:
            path = _file(plan.root, change.relative)
            if _read(plan.root, change.relative) != change.before:
                raise ValueError(f"模板已变化，停止写入：{change.relative}")
            os.replace(staged[change.relative][0], path)
            applied.append(change)
    except BaseException as error:
        recovery = []
        for change in reversed(applied):
            backup = staged[change.relative][1]
            try:
                if _read(plan.root, change.relative) != change.after:
                    raise ValueError("检测到后续编辑")
                os.replace(backup, _file(plan.root, change.relative))
            except (OSError, ValueError) as rollback_error:
                temporaries.discard(backup)
                recovery.append(f"{change.relative}（{rollback_error}）；原文备份：{backup}")
        if recovery:
            raise RuntimeError("回滚未完成，已保留现场：" + "；".join(recovery)) from error
        raise
    finally:
        for path in temporaries:
            path.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="只读检查（默认），漂移时返回 1")
    mode.add_argument("--write", action="store_true", help="更新已登记 Core 模板的生成区域")
    args = parser.parse_args(argv)
    try:
        plan = make_plan(Path(__file__).absolute().parent.parent)
        if args.write:
            apply_plan(plan)
            print(f"已同步 {len(plan.changes)} 份模板；共检查 {len(TEMPLATE_PATHS)} 份。")
            return 0
        for change in plan.changes:
            print(f"[DRIFT] {change.relative}")
        if plan.changes:
            print("修改公共片段后，运行 --write 同步；正文不由本工具生成。")
            return 1
        print(f"时间片段一致：{len(TEMPLATE_PATHS)} 份模板；未写入文件。")
        return 0
    except (OSError, ValueError, RuntimeError) as error:
        print(f"[ERROR] {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
