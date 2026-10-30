"""Explicit project assets; declarations never exempt a demand cycle from its gates."""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import os
from pathlib import Path, PurePosixPath
import re

import yaml

from core_validation import HarnessConfig, Result, UniqueKeyLoader, parse_cycle_identity


@dataclass
class AssetRegistry:
    valid: bool = True
    history_imports: dict[str, tuple[Path, ...]] = field(default_factory=dict)


def _keys(value: object, expected: set[str]) -> dict:
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError(f"字段必须恰为 {', '.join(sorted(expected))}")
    return value


def _text(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError('必须提供非空文本')
    return value


def _path(root: Path, value: object) -> Path:
    text = _text(value)
    parts = text.split('/')
    if (any(part in {'', '.', '..'} or part.endswith((' ', '.')) for part in parts)
            or any(ord(c) < 32 or c in '\\:*?"<>|' for c in text)
            or PurePosixPath(text).is_absolute()):
        raise ValueError(f'路径必须为规范项目相对路径: {text}')
    path = root.resolve().joinpath(*parts)
    if path.resolve() != path or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f'路径发生重定向: {text}')
    return path


def _cycle(root: Path, config: HarnessConfig, value: object) -> str:
    name = _text(value)
    if parse_cycle_identity(name) is None:
        raise ValueError(f'消费周期名非法: {name}')
    path = _path(root, (config.demand_cycle_root / name).as_posix())
    if not path.is_dir():
        raise ValueError(f'消费周期不存在: {name}')
    return name


def load_asset_registry(root: Path, config: HarnessConfig, result: Result) -> AssetRegistry:
    """Validate each declaration at every public gate entry; invalid files grant nothing."""
    relative = config.service_catalog.parent / 'asset-registry.yaml'
    candidate = root / relative
    # lexists also catches dangling registry symlinks rather than treating them as absent.
    if not os.path.lexists(candidate):
        return AssetRegistry()
    try:
        path = _path(root, relative.as_posix())
        if not path.is_file():
            raise ValueError('资产登记必须为普通 YAML 文件')
        data = _keys(yaml.load(path.read_text(encoding='utf-8'), Loader=UniqueKeyLoader),
                     {'schemaVersion', 'prototypes', 'historyImports'})
        if type(data['schemaVersion']) is not int or data['schemaVersion'] != 1:
            raise ValueError('资产登记仅支持 schemaVersion: 1')
        if not isinstance(data['prototypes'], list) or not isinstance(data['historyImports'], list):
            raise ValueError('prototypes 和 historyImports 必须为列表')
        if data['prototypes']:
            raise ValueError('Schema 20 原型只由 project.prototypeRoot 指定，不登记周期原型')
        registry = AssetRegistry()
        seen = set()
        imports: dict[str, list[Path]] = {}
        for value in data['historyImports']:
            item = _keys(value, {'cycle', 'path', 'hashMode', 'sha256', 'rationale', 'boundaries'})
            cycle = _cycle(root, config, item['cycle'])
            document = _path(root, item['path'])
            history = _path(root, config.history_root.as_posix())
            if (not document.is_relative_to(history) or not document.is_file()
                    or document.suffix.lower() not in {'.md', '.pdf', '.docx'}):
                raise ValueError('历史导入必须是项目历史根内的 Markdown/PDF/DOCX 文件')
            _text(item['rationale'])
            _text(item['boundaries'])
            digest = _text(item['sha256'])
            mode = item['hashMode']
            data = document.read_bytes()
            if mode == 'text-lf' and document.suffix.lower() == '.md':
                data.decode('utf-8')  # Reject binary data rather than normalizing it silently.
                data = data.replace(b'\r\n', b'\n')
            elif mode != 'raw':
                raise ValueError('hashMode 必须为 raw；UTF-8 Markdown 也可显式使用 text-lf')
            if not re.fullmatch('[0-9a-f]{64}', digest) or hashlib.sha256(data).hexdigest() != digest:
                raise ValueError(f'历史导入 SHA256 不匹配: {item["path"]}')
            key = (cycle.casefold(), str(document).casefold())
            if key in seen:
                raise ValueError('重复的消费周期/历史文件登记')
            seen.add(key)
            imports.setdefault(cycle, []).append(document)
        registry.history_imports = {cycle: tuple(paths) for cycle, paths in imports.items()}
        return registry
    except (OSError, ValueError, TypeError, yaml.YAMLError, RuntimeError) as error:
        result._hard_error(f'{candidate} 资产登记无效: {error}')
        return AssetRegistry(valid=False)
