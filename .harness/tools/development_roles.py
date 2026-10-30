"""Engineering evidence per role, without dependencies on any other Gate."""
import re

from core_validation import Result, load_yaml_mapping, parse_cycle_identity, REVISION_PATTERN, _exact_keys
from role_gates import source_state
import backend_validation as backend


def validate_development_role(root, config, cycle, paths, role, result):
    data = load_yaml_mapping(paths["execution"], result)
    if data is None:
        return
    identity = parse_cycle_identity(cycle.name)
    if (type(data.get("schemaVersion")) is not int or data["schemaVersion"] != 7
            or identity is None or data.get("version") != identity.version):
        result.error("Execution 必须为 Schema 7 且版本与周期一致")
        return
    _exact_keys(data, {"schemaVersion", "version", "sources", "services", "tracks", "contracts", "releaseOrder"}, "execution", result)
    try:
        source_state(root, config, cycle.name, data.get("sources"))
    except (ValueError, OSError, TypeError) as error:
        result.error(str(error))
        return
    tracks, services = data.get("tracks"), data.get("services")
    if not isinstance(tracks, dict) or not isinstance(services, dict):
        result.error("Execution tracks/services 必须为映射")
        return
    track = tracks.get(role)
    if not isinstance(track, dict):
        result.error(f"{role} 轨道缺失")
        return
    expected = {"applicable", "services", "status", "sources"}
    if role == "frontend":
        expected |= {"uiStages", "uiScopeReason"}
    _exact_keys(track, expected, f"tracks.{role}", result)
    try:
        if not source_state(root, config, cycle.name, track.get("sources")):
            result.warn(f"{role} 有后续变更或采用范围未登记；按具体变更复核，不重置确认")
    except (ValueError, OSError, TypeError) as error:
        result.error(str(error))
    own = track.get("services")
    if not isinstance(own, list) or not own or any(not isinstance(x, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", x) for x in own):
        result.error("角色服务列表必须为已登记的服务 ID")
        return
    if len(set(own)) != len(own) or track.get("applicable") is not True or track.get("status") != "completed":
        result.error("角色轨道尚未完成或服务列表重复")
    if {name for name, raw in services.items() if isinstance(raw, dict) and raw.get("type") == role} != set(own):
        result.error("角色轨道必须覆盖自身全部适用服务")
    catalog_data = load_yaml_mapping(root / config.service_catalog, result)
    catalog = (catalog_data or {}).get("services", {})
    if not isinstance(catalog, dict):
        result.error("服务目录 services 必须为映射")
        return
    service_roots, service_catalogs = {}, {}
    from local_paths import resolve_service_path
    for name, raw in services.items():
        registered = catalog.get(name)
        if isinstance(registered, dict) and isinstance(raw, dict):
            service_roots[name] = resolve_service_path(root, name, str(registered.get("localPath", "")))
            service_catalogs[name] = registered
    revisions = {}
    for name in own:
        raw = services.get(name)
        if not isinstance(raw, dict) or raw.get("type") != role or name not in service_catalogs:
            result.error(f"{role}/{name} 服务归属不符")
            continue
        _exact_keys(raw, {"type", "repository", "branch", "remote", "baseRevision", "finalRevision", "status"}, name, result)
        if raw.get("status") != "completed" or not REVISION_PATTERN.fullmatch(str(raw.get("finalRevision", ""))):
            result.error(f"{name} 缺少完成状态或实际 finalRevision")
        backend._validate_service_git(name, raw, service_catalogs[name], service_roots[name], identity.version, result)
        revisions[name] = raw.get("finalRevision", "")
    contracts = data.get("contracts")
    if not isinstance(contracts, list) or any(not isinstance(c, dict) for c in contracts):
        result.error("contracts 必须为结构化接口文档列表")
        return
    if any(not isinstance(c.get("consumers"), list) for c in contracts):
        result.error("接口 consumers 必须为列表")
        return
    if not isinstance(catalog, dict):
        result.error("服务目录 services 必须为映射")
        return
    relevant = [c for c in contracts if (c.get("ownerService") in own if role == "backend" else any(s in c.get("consumers", []) for s in own))]
    _, by_consumer = backend._validate_contracts(relevant, service_roots, service_catalogs, services, root, config, result)
    prd = paths["prd"].read_text(encoding="utf-8") if paths["prd"].is_file() else ""
    requirements = set(re.findall(r"\bREQ-\d{3}\b", prd))
    if not requirements:
        result.error("PRD 缺少 REQ 输入")
    if role == "frontend":
        ui_stages = track.get("uiStages")
        reason = track.get("uiScopeReason")
        if ui_stages == "not-applicable" and (not isinstance(reason, str) or not reason.strip()):
            result.error("无页面改动必须提供 uiScopeReason")
            return
        backend._frontend_artifacts_valid(
            paths["developmentFrontend"], own, ui_stages,
            {"scopeReason": reason}, paths, by_consumer, requirements, revisions, result)
    else:
        backend._backend_artifacts_valid(
            paths["developmentBackend"], own, relevant, revisions, requirements, identity.version, result)
