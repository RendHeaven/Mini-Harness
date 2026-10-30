"""将原型目录全部内容打包到同级 ZIP；只读取源文件，不覆盖已有产物。"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import zipfile


def _plain_entry(path: Path) -> os.stat_result:
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise ValueError(f"拒绝符号链接、junction 或 reparse point：{path}")
    return info


def _directory(path: Path) -> Path:
    path = path.expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.is_absolute():
        raise ValueError(f"请使用完整路径，不支持其他驱动器的相对路径：{path}")
    current = Path(path.anchor)
    # 逐段检查，不能先 resolve/abspath 抹去 link/.. 中的路径重定向。
    for part in (None, *path.parts[1:]):
        if part is not None:
            current = current.parent if part == ".." else current / part
        if not stat.S_ISDIR(_plain_entry(current).st_mode):
            raise ValueError(f"不是目录：{current}")
    return current


def _entries(root: Path) -> list[tuple[Path, os.stat_result]]:
    entries = []
    pending = [root]
    while pending:
        directory = _directory(pending.pop())
        for path in sorted(directory.iterdir()):
            info = _plain_entry(path)
            if stat.S_ISDIR(info.st_mode):
                pending.append(path)
            elif not stat.S_ISREG(info.st_mode):
                raise ValueError(f"不支持的文件类型：{path}")
            entries.append((path, info))
    return entries


def _same_file(left: os.stat_result, right: os.stat_result) -> bool:
    return (left.st_dev, left.st_ino) == (right.st_dev, right.st_ino)


def package_prototype(prototype_root: Path | str) -> dict[str, str | int]:
    root = _directory(Path(prototype_root))
    if root == root.parent:
        raise ValueError("不能打包文件系统根目录")
    entries = _entries(root)
    index = 0
    while True:
        _directory(root.parent)
        suffix = f"-{index}" if index else ""
        output = root.with_name(f"{root.name}{suffix}.zip")
        try:
            output.lstat()
        except FileNotFoundError:
            try:
                stream = output.open("x+b")
                break
            except FileExistsError:
                pass
        index += 1

    created = os.fstat(stream.fileno())
    file_count = source_bytes = 0
    try:
        with stream:
            with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path, original in entries:
                    _directory(path.parent)
                    current = _plain_entry(path)
                    if not _same_file(original, current) or original.st_mode != current.st_mode:
                        raise ValueError(f"打包期间源路径发生变化：{path}")
                    relative = path.relative_to(root).as_posix()
                    item = zipfile.ZipInfo.from_file(path, relative, strict_timestamps=False)
                    item.compress_type = zipfile.ZIP_DEFLATED
                    if stat.S_ISDIR(current.st_mode):
                        archive.writestr(item, b"")
                        continue
                    with path.open("rb") as source:
                        if not _same_file(current, os.fstat(source.fileno())):
                            raise ValueError(f"打开文件时源路径发生变化：{path}")
                        with archive.open(item, "w", force_zip64=True) as target:
                            shutil.copyfileobj(source, target)
                    file_count += 1
                    source_bytes += item.file_size
            stream.flush()
            stream.seek(0)
            with zipfile.ZipFile(stream, "r") as archive:
                bad_entry = archive.testzip()
                if bad_entry is not None:
                    raise ValueError(f"ZIP CRC 检查失败：{bad_entry}")
            archive_bytes = os.fstat(stream.fileno()).st_size
    except BaseException:
        # 仅删除本次排他创建的文件，避免误删已被其他程序替换的同名产物。
        try:
            if _same_file(created, output.lstat()):
                output.unlink()
        except FileNotFoundError:
            pass
        raise
    return {
        "archive_path": str(output),
        "file_count": file_count,
        "source_bytes": source_bytes,
        "archive_bytes": archive_bytes,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prototype-root", required=True, type=Path, help="产品原型目录")
    args = parser.parse_args(argv)
    try:
        result = package_prototype(args.prototype_root)
    except (OSError, ValueError, zipfile.BadZipFile, RuntimeError) as error:
        print(f"原型打包失败：{error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
