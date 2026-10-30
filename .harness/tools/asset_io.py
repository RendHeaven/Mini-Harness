"""Safe project-local assets and exclusive, atomic writes."""
import hashlib
import os
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path, PurePosixPath, PureWindowsPath
from uuid import uuid4

IGNORED = {".git", "node_modules", "__pycache__", ".cache"}


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def safe_path(root, raw):
    if not isinstance(raw, str) or not raw or "\\" in raw or ":" in raw:
        raise ValueError("资产路径必须是项目内 POSIX 相对路径")
    rel = PurePosixPath(raw)
    if rel.is_absolute() or PureWindowsPath(raw).is_absolute() or ".." in rel.parts or raw != rel.as_posix():
        raise ValueError("资产路径不可越界或包含路径别名")
    root = Path(root).resolve()
    path = root / raw
    current = root
    for part in rel.parts:
        current = current / part
        if current.is_symlink() or (hasattr(current, "is_junction") and current.is_junction()):
            raise ValueError("资产路径禁止符号链接或目录联接")
    if not path.resolve().is_relative_to(root):
        raise ValueError("资产路径越出项目")
    return path


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def asset_files(root):
    root = Path(root)
    if not root.is_dir():
        raise ValueError("原型目录不存在")
    files = []
    for path in root.rglob("*"):
        # Reject links even when their contents would have been ignored.
        if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
            raise ValueError("原型中禁止符号链接或目录联接")
        rel = path.relative_to(root)
        if path.is_file() and not any(part in IGNORED for part in rel.parts):
            files.append(path)
    return sorted(files, key=lambda p: p.relative_to(root).as_posix())


def directory_hash(root):
    root = Path(root)
    digest = hashlib.sha256()
    for path in asset_files(root):
        digest.update(path.relative_to(root).as_posix().encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


def atomic_write(path, content):
    path = Path(path)
    if os.name == "nt":
        # Extended absolute paths work even when Windows long-path opt-in is off.
        # UNC shares use a different prefix; do not prefix an extended path twice.
        absolute = os.path.abspath(os.fspath(path))
        if not absolute.startswith("\\\\?\\"):
            absolute = "\\\\?\\UNC\\" + absolute[2:] if absolute.startswith("\\\\") else "\\\\?\\" + absolute
        path = Path(absolute)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Do not append to the target name: it may already approach a component limit.
    temporary = path.with_name(".atlas-" + uuid4().hex + ".tmp")
    owned = False
    try:
        with temporary.open("xb") as handle:
            owned = True
            handle.write(content if isinstance(content, bytes) else content.encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        owned = False
    finally:
        # A failed exclusive create belongs to someone else; never remove it.
        if owned:
            temporary.unlink(missing_ok=True)


@contextmanager
def exclusive(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        handle = path.open("x", encoding="utf-8")
    except FileExistsError:
        raise ValueError(f"操作锁已存在，请核对并发任务或中断现场: {path.name}") from None
    try:
        with handle:
            handle.write(str(os.getpid()))
            handle.flush()
            yield
    finally:
        path.unlink()
