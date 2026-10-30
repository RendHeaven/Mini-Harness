"""References to recorded changes, without duplicating product contents."""
import re
from pathlib import Path

from asset_io import safe_path
from core_validation import Result, load_yaml_mapping, parse_cycle_identity


def source_paths(config, cycle):
    identity = parse_cycle_identity(cycle)
    if identity is None:
        raise ValueError("周期标识非法")
    return {
        "prd": f"{config.demand_cycle_root.as_posix()}/{cycle}/product/{identity.version}-prd.md",
        "prototype": config.prototype_root.as_posix(),
    }


def change_references(root, config, cycle):
    from prd_revision import log_changes
    base = f"{config.demand_cycle_root.as_posix()}/{cycle}"
    product = safe_path(root, f"{base}/product")
    prd_changes = log_changes(product) if (product / "prd-changes/revisions.yaml").is_file() else []
    prototype_changes = []
    for relative in (f"{base}/product/mock-changelog.md", f"{base}/ui/adjustment-log.md"):
        log = safe_path(root, relative)
        if log.is_file():
            for identifier in dict.fromkeys(re.findall(r"\bCHG-\d{3,}\b", log.read_text(encoding="utf-8"))):
                prototype_changes.append(f"{relative}#{identifier}")
    adjustments = safe_path(root, f"{base}/ui/adjustments")
    if adjustments.is_dir():
        for path in sorted(adjustments.glob("UI-ADJ-*.md")):
            raw = path.relative_to(root).as_posix()
            safe_path(root, raw)
            prototype_changes.append(raw)
    reconstruction = safe_path(root, f"{base}/ui/reconstruction")
    if reconstruction.is_dir():
        for path in sorted(reconstruction.glob("*.yaml")):
            raw = path.relative_to(root).as_posix()
            safe_path(root, raw)
            result = Result.empty()
            data = load_yaml_mapping(path, result)
            if result.errors:
                raise ValueError("; ".join(result.errors))
            if not isinstance(data, dict) or type(data.get("recordVersion")) is not int or data["recordVersion"] != 2:
                raise ValueError(f"{raw} 仅支持 recordVersion: 2")
            iterations = data.get("iterations")
            if not isinstance(iterations, list) or any(not isinstance(entry, dict) for entry in iterations):
                raise ValueError(f"{raw} iterations 必须为事件记录列表")
            for index, entry in enumerate(iterations, 1):
                if entry.get("changedArtifacts"):
                    prototype_changes.append(f"{raw}#iteration-{index}")
    return {"prd": prd_changes, "prototype": prototype_changes}


def capture_sources(root, config, cycle):
    root = Path(root).resolve()
    changes = change_references(root, config, cycle)
    sources = {}
    for kind, raw in source_paths(config, cycle).items():
        live = safe_path(root, raw)
        if not (live.is_file() if kind == "prd" else live.is_dir()):
            raise ValueError(f"{kind} 当前产物不存在")
        sources[kind] = {"path": raw, "changes": changes[kind]}
    return sources


def source_state(root, config, cycle, sources):
    """Validate references; False means changes/unknown scope, never revoked consent."""
    if not isinstance(sources, dict) or set(sources) != {"prd", "prototype"}:
        raise ValueError("来源必须包含 PRD 和项目原型")
    expected = source_paths(config, cycle)
    latest = change_references(Path(root), config, cycle)
    current = True
    for kind, source in sources.items():
        if not isinstance(source, dict) or set(source) != {"path", "changes"}:
            raise ValueError("来源仅支持 path、changes 字段")
        if source["path"] != expected[kind]:
            raise ValueError(f"{kind} 来源路径不合法")
        safe_path(root, source["path"])
        refs = source["changes"]
        if refs is None:
            current = False
            continue
        if not isinstance(refs, list) or any(not isinstance(ref, str) or not ref for ref in refs):
            raise ValueError("来源 changes 必须为唯一变更引用列表，范围未知时为 null")
        if len(refs) != len(set(refs)):
            raise ValueError("来源 changes 不可重复")
        for ref in refs:
            if kind == "prd":
                if not re.fullmatch(r"CHG-\d{3,}", ref):
                    raise ValueError("PRD 来源必须引用 CHG 编号")
            else:
                safe_path(root, ref.split("#", 1)[0])
        current = current and refs == latest[kind]
    return current
