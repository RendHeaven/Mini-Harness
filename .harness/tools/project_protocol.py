"""Current project configuration for Schema 20."""
from dataclasses import replace
from pathlib import Path
from core_validation import (
    HarnessConfig, Result, default_project_config, _exact_keys, _relative_path,
    HASH_PATTERN, REVISION_PATTERN,
)

PRODUCT = {
    "root": "product", "discovery": "discovery.md", "prd": "{version}-prd.md",
    "prdReview": "prd-review.md", "devGuide": "dev-guide.md",
}
UI = {"root": "ui", "handoff": "ui-handoff.md"}
DEVELOPMENT = {
    "root": "develop", "execution": "execution.yaml", "frontend": "frontend",
    "backend": "backend", "testhub": "testhub",
}


def default_config():
    return replace(
        default_project_config(), schema_version=20, core_version="0.35.0",
        demand_cycle_root=Path(".harness/demandCycle"), history_root=Path(".harness/history"),
        service_catalog=Path(".harness/projectContext/services.yaml"),
    )


def parse_project_config(path: Path, data: dict, result: Result) -> HarnessConfig | None:
    start = len(result.errors)
    _exact_keys(data, {"schemaVersion", "kind", "core", "project", "cycle", "product", "ui", "development"}, "harness.yaml", result)
    if data.get("kind") != "project":
        result.error("kind 必须为 project")
    for section in ("core", "project", "cycle", "product", "ui", "development"):
        if not isinstance(data.get(section), dict):
            result.error(f"{section} 必须是映射")
    if len(result.errors) != start:
        return None
    core, project = data["core"], data["project"]
    _exact_keys(core, {"localPath", "version", "revision", "contentHash"}, "core", result)
    _exact_keys(project, {"id", "name", "demandCycleRoot", "historyRoot", "serviceCatalog", "prototypeRoot", "gateFile"}, "project", result)
    _exact_keys(data["cycle"], {"manifest"}, "cycle", result)
    if data["cycle"].get("manifest") != "manifest.yaml":
        result.error("cycle.manifest 必须为 manifest.yaml")
    for section, expected in (("product", PRODUCT), ("ui", UI), ("development", DEVELOPMENT)):
        _exact_keys(data[section], set(expected), section, result)
        for key, value in expected.items():
            if data[section].get(key) != value:
                result.error(f"{section}.{key} 必须为 {value}")
    for key in ("localPath", "version", "revision", "contentHash"):
        if not isinstance(core.get(key), str) or not core[key].strip():
            result.error(f"core.{key} 必须为非空字符串")
    for key in ("id", "name"):
        if not isinstance(project.get(key), str) or not project[key].strip():
            result.error(f"project.{key} 必须为非空字符串")
    if not REVISION_PATTERN.fullmatch(str(core.get("revision", ""))):
        result.error("core.revision 必须为 40 位小写 Git commit")
    if not HASH_PATTERN.fullmatch(str(core.get("contentHash", ""))):
        result.error("core.contentHash 必须为 64 位小写 SHA256")
    expected_paths = {
        "demandCycleRoot": ".harness/demandCycle", "historyRoot": ".harness/history",
        "serviceCatalog": ".harness/projectContext/services.yaml",
        "prototypeRoot": "原型仓库", "gateFile": "Gate.yaml",
    }
    paths = {}
    for key, expected in expected_paths.items():
        paths[key] = _relative_path(project.get(key), f"project.{key}", result)
        if project.get(key) != expected:
            result.error(f"Schema 20 project.{key} 必须为 {expected}")
    if len(result.errors) != start:
        return None
    return replace(
        default_config(), core_local_path=Path(core["localPath"]), core_version=core["version"],
        core_revision=core["revision"], core_content_hash=core["contentHash"],
        project_id=project["id"], project_name=project["name"],
        demand_cycle_root=paths["demandCycleRoot"], history_root=paths["historyRoot"],
        service_catalog=paths["serviceCatalog"], prototype_root=paths["prototypeRoot"],
        gate_file=paths["gateFile"],
    )
