"""Four independent role records. Validation never confirms or mutates a Gate."""
import argparse
import copy
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

import yaml

from asset_io import atomic_write, directory_hash, exclusive, file_hash, now, safe_path
from change_sources import capture_sources, source_state
from core_validation import (
    Result, GateOutcome, load_yaml_mapping, parse_cycle_identity, validate_manifest,
)

ROLES = ("product", "ui", "frontend", "backend")
STATES = {"not_started", "in_progress", "pending_confirmation", "confirmed", "changes_requested", "not_applicable"}
TRANSITIONS = {
    "not_started": {"in_progress", "not_applicable"},
    "in_progress": {"in_progress", "pending_confirmation", "not_applicable"},
    "pending_confirmation": {"confirmed", "changes_requested", "in_progress"},
    "changes_requested": {"in_progress", "not_applicable"},
    "confirmed": {"in_progress", "confirmed"},
    "not_applicable": {"in_progress"},
}
FIELDS = {"status", "statusChangedAt", "updatedAt", "confirmedAt", "confirmedBy", "confirmedGit", "reason", "sources", "evidence", "history"}


def timestamp(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+]08:00", value):
        raise ValueError("时间必须为秒级 ISO 8601 +08:00")
    return datetime.fromisoformat(value)


def blank_record(at=None):
    at = at or now()
    return dict(status="not_started", statusChangedAt=at, updatedAt=at, confirmedAt=None,
                confirmedBy=None, confirmedGit=None, reason="", sources={}, evidence=[], history=[])


def validate_confirming_git(identity):
    if not isinstance(identity, dict) or set(identity) != {"name", "email"}:
        raise ValueError("确认必须记录 confirmedGit.name 和 confirmedGit.email")
    for key, value in identity.items():
        if not isinstance(value, str) or not value.strip() or any(ord(char) < 32 for char in value):
            raise ValueError(f"确认者 Git {key} 缺失或非法")


def read_confirming_git(root):
    """Read only the effective identity, never guess from commit authors or remotes."""
    root = Path(root).resolve()

    def git(*args):
        try:
            completed = subprocess.run(
                ["git", "-C", str(root), *args], capture_output=True, text=True,
                encoding="utf-8", timeout=10, check=False,
            )
        except (OSError, subprocess.TimeoutExpired, UnicodeError) as error:
            raise ValueError("无法读取确认者 Git 身份，请检查 Git 与项目仓库") from error
        if completed.returncode:
            raise ValueError("无法读取确认者 Git 身份；请配置项目生效的 user.name 和 user.email")
        return completed.stdout.rstrip("\r\n")

    if Path(git("rev-parse", "--show-toplevel")).resolve() != root:
        raise ValueError("确认者 Git 身份必须从项目 Harness 仓库根读取")
    identity = {key: git("config", "--get", f"user.{key}").strip() for key in ("name", "email")}
    validate_confirming_git(identity)
    return identity


def load_ledger(root, config):
    result = Result.empty()
    data = load_yaml_mapping(safe_path(root, config.gate_file.as_posix()), result)
    if result.errors or data is None:
        raise ValueError("; ".join(result.errors))
    return data


def validate_record_fields(root, config, cycle, record):
    """Validate the current record and every historical event with the same rules."""
    status = record["status"]
    if not isinstance(status, str) or status not in STATES:
        raise ValueError("Gate 状态非法")
    changed, updated = timestamp(record["statusChangedAt"]), timestamp(record["updatedAt"])
    if updated < changed:
        raise ValueError("更新时间早于状态时间")
    if not isinstance(record["reason"], str) or not isinstance(record["sources"], dict) or not isinstance(record["evidence"], list):
        raise ValueError("reason/sources/evidence 类型非法")
    if status != "not_started" and not record["reason"].strip():
        raise ValueError("状态变化必须说明原因")
    if status == "confirmed":
        if not record["confirmedBy"] or not isinstance(record["confirmedBy"], str):
            raise ValueError("确认必须记录实际负责人")
        validate_confirming_git(record["confirmedGit"])
        if timestamp(record["confirmedAt"]) != changed:
            raise ValueError("确认时间必须等于本次状态时间")
    elif record["confirmedAt"] is not None or record["confirmedBy"] is not None or record["confirmedGit"] is not None:
        raise ValueError("当前未确认，旧确认只能保留在 history")
    current = True
    if record["sources"]:
        current = source_state(root, config, cycle, record["sources"])
    elif status in {"pending_confirmation", "confirmed"}:
        raise ValueError("提交或确认缺少 PRD/原型来源")
    for evidence in record["evidence"]:
        if not isinstance(evidence, dict) or set(evidence) != {"path"}:
            raise ValueError("交付记录仅支持 path 字段")
        safe_path(root, evidence["path"])
    if status in {"pending_confirmation", "confirmed"} and not record["evidence"]:
        raise ValueError("提交或确认缺少证据")
    return current


def validate_record(root, config, cycle, role, record):
    if not isinstance(record, dict) or set(record) != FIELDS:
        raise ValueError(f"{role} Gate 不支持此记录格式：字段缺失或存在未知字段")
    current = validate_record_fields(root, config, cycle, record)
    status = record["status"]
    history = record["history"]
    if not isinstance(history, list):
        raise ValueError("history 必须为列表")
    previous, last_at = "not_started", None
    for index, event in enumerate(history):
        if not isinstance(event, dict) or set(event) != {"eventId", "from", "to", "at", "actor", "record"}:
            raise ValueError("Gate 历史事件字段非法")
        if event["eventId"] != f"{role}-{index+1:04d}" or event["from"] != previous:
            raise ValueError("Gate 历史身份或状态链断裂")
        if not isinstance(event["to"], str) or event["to"] not in TRANSITIONS.get(previous, set()):
            raise ValueError("Gate 历史包含非法状态转换")
        event_at = timestamp(event["at"])
        if last_at and event_at < last_at:
            raise ValueError("Gate 历史时间倒序")
        if not isinstance(event["actor"], str) or not event["actor"].strip():
            raise ValueError("Gate 历史缺少执行主体")
        saved = event["record"]
        if not isinstance(saved, dict) or set(saved) != FIELDS - {"history"}:
            raise ValueError("Gate 历史必须保留完整事件记录")
        validate_record_fields(root, config, cycle, saved)
        if saved["status"] != event["to"] or saved["statusChangedAt"] != event["at"]:
            raise ValueError("Gate 历史与事件状态不一致")
        previous, last_at = event["to"], event_at
    if history:
        if history[-1]["record"] != {k: v for k, v in record.items() if k != "history"}:
            raise ValueError("Gate 当前记录与历史末条不一致")
    elif status != "not_started":
        raise ValueError("状态变化缺少历史")
    return current


def validate_execution_protocol(root, config, cycle):
    """Reject unsupported existing executions without requiring a role to finish."""
    relative = config.demand_cycle_root / cycle / config.development_root / config.development_execution
    path = safe_path(root, relative.as_posix())
    if not path.exists():
        return
    result = Result.empty()
    data = load_yaml_mapping(path, result)
    if result.errors or data is None:
        raise ValueError("; ".join(result.errors))
    if type(data.get("schemaVersion")) is not int or data["schemaVersion"] != 7:
        raise ValueError("Execution 仅支持 schemaVersion: 7")
    if data.get("version") != parse_cycle_identity(cycle).version:
        raise ValueError("Execution 版本必须与周期一致")


def validate_ledger(root, config, result):
    try:
        data = load_ledger(root, config)
        if set(data) != {"schemaVersion", "projectId", "timezone", "cycles"}:
            raise ValueError("Gate.yaml 字段非法")
        if type(data["schemaVersion"]) is not int or data["schemaVersion"] != 2:
            raise ValueError("Gate.yaml 仅支持 schemaVersion: 2")
        if data["projectId"] != config.project_id or data["timezone"] != "Asia/Shanghai":
            raise ValueError("Gate.yaml 身份、版本或时区错误")
        if not isinstance(data["cycles"], dict):
            raise ValueError("cycles 必须是映射")
        for cycle, entry in data["cycles"].items():
            if not isinstance(cycle, str) or parse_cycle_identity(cycle) is None:
                raise ValueError("Gate 周期标识非法")
            if not isinstance(entry, dict) or set(entry) != {"roles"} or not isinstance(entry["roles"], dict) or set(entry["roles"]) != set(ROLES):
                raise ValueError("每个周期必须且只能拥有四角色")
            try:
                validate_execution_protocol(root, config, cycle)
            except (ValueError, OSError, TypeError) as error:
                result.error(f"{cycle}: {error}")
            for role, record in entry["roles"].items():
                try:
                    if not validate_record(root, config, cycle, role, record):
                        result.warn(f"{cycle}/{role} 有后续变更或确认范围未登记；保留当次确认，不代表新增内容已确认")
                except (ValueError, OSError, TypeError) as error:
                    result.error(f"{cycle}/{role}: {error}")
        return data
    except (ValueError, OSError, TypeError) as error:
        result.error(str(error))
        return None


def role_checks(root, config, cycle, role, result):
    """Own deliverables only. Never inspect another role's confirmation."""
    from validate_harness import artifact_paths
    from product_ui_validation import (validate_markdown_prd, validate_discovery,
        validate_history_review, markdown_req_decision_references)
    from asset_registry import load_asset_registry
    from core_validation import DEC_REFERENCE
    from prd_revision import validate_revisions
    from development_roles import validate_development_role
    paths = artifact_paths(cycle, config)
    identity = parse_cycle_identity(cycle.name)
    if not identity:
        result.error("周期标识非法")
        return
    manifest = validate_manifest(paths["manifest"], identity.version, result)
    if manifest and manifest.get("state") == "cancelled":
        result.error("已取消周期不得新增交付或确认")
    try:
        prototype = safe_path(root, config.prototype_root.as_posix())
        directory_hash(prototype)
        if not (prototype / "index.html").is_file():
            result.error("项目原型缺少 index.html")
    except (ValueError, OSError) as error:
        result.error(str(error))
    if role == "product":
        validate_discovery(paths["discovery"], result)
        prd = validate_markdown_prd(paths["prd"], result)
        accepted = set(prd.accepted_decisions)
        for requirement, source in prd.requirement_sources.items():
            references = set(DEC_REFERENCE.findall(source.upper()))
            if not references & accepted or references - accepted:
                result.error(f"{requirement} 缺少有效 accepted DEC 来源")
        if not accepted <= markdown_req_decision_references(prd.text):
            result.error("已接受决策缺少 REQ 追溯")
        assets = load_asset_registry(root, config, result)
        history = safe_path(root, config.history_root.as_posix())
        product_lines = {
            parsed.product_line for sibling in cycle.parent.iterdir() if sibling.is_dir()
            if (parsed := parse_cycle_identity(sibling.name)) is not None and parsed.product_line
        }
        scoped = safe_path(root, (config.history_root / identity.product_line).as_posix()) if identity.product_line else history
        validate_history_review(prd.text, scoped, result, paths["prd"], project_root=root,
            excluded_roots=tuple(history / line for line in product_lines) if not identity.product_line else (),
            strict_references=bool(product_lines), imported_documents=assets.history_imports.get(cycle.name, ()))
        validate_revisions(paths["product"], paths["prd"], result)
        required = [paths["product"] / "mock-changelog.md"]
    elif role == "ui":
        required = [paths["ui"] / "adjustment-log.md", paths["uiHandoff"]]
        adjustments = list((paths["ui"] / "adjustments").glob("UI-ADJ-*.md"))
        if not adjustments:
            result.error("UI 缺少逐轮调整文档")
        required.extend(adjustments)
    else:
        validate_development_role(root, config, cycle, paths, role, result)
        required = []
    for path in required:
        try:
            safe_path(root, path.relative_to(root).as_posix())
            text = path.read_text(encoding="utf-8")
            if not text.strip() or not re.search(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}", text):
                result.error(f"{path.name} 缺少内容或秒级时间")
            if path.name.startswith("UI-ADJ-"):
                columns = ("页面/REQ", "调整前", "调整后", "UI 规则", "文件", "验证与证据")
                if not all(column in text for column in columns):
                    result.error(f"{path.name} 缺少完整调整对照表")
                rows = [line for line in text.splitlines() if line.strip().startswith("|") and re.search(r"REQ-\d{3}", line)]
                if not rows or not any(len(line.strip().strip("|").split("|")) >= 6 and all(cell.strip() and not re.search(r"<[^>]+>", cell) for cell in line.strip().strip("|").split("|")) for line in rows):
                    result.error(f"{path.name} 缺少实际调整、规则和验证证据")
        except (OSError, ValueError) as error:
            result.error(f"{path.name}: {error}")


def validate_cycle(cycle, config, root, result):
    root, cycle = Path(root).resolve(), Path(cycle).resolve()
    expected = safe_path(root, config.demand_cycle_root.as_posix())
    if cycle.parent != expected or parse_cycle_identity(cycle.name) is None:
        result.error("需求周期必须位于配置的周期根内")
        return {role: GateOutcome(False, ("cycle-path",)) for role in ROLES}
    ledger_result = Result.empty()
    data = validate_ledger(root, config, ledger_result)
    result.errors.extend(ledger_result.errors)
    result.warnings.extend(ledger_result.warnings)
    entry = (data or {}).get("cycles", {}).get(cycle.name)
    if entry is None:
        result.error(f"{cycle.name} 尚未初始化 Gate 记录")
        return {role: GateOutcome(False, ("record-missing",)) for role in ROLES}
    outcomes = {}
    for role in ROLES:
        own = Result.empty()
        record = entry.get("roles", {}).get(role)
        current = False
        try:
            current = validate_record(root, config, cycle.name, role, record)
            if record["status"] == "pending_confirmation":
                role_checks(root, config, cycle, role, own)
            confirmed = record["status"] == "confirmed"
            failed = tuple(own.errors) + (() if confirmed else ("not-confirmed",))
        except (ValueError, OSError, TypeError) as error:
            own.error(str(error))
            failed = tuple(own.errors)
        outcomes[role] = GateOutcome(not failed, failed)
        # Incomplete role work is reported, not transformed into another role's prerequisite.
        result.warnings.extend(f"{cycle.name}/{role}: {message}" for message in own.errors + own.warnings)
        result.info(f"{cycle.name}/{role}: {record.get('status') if isinstance(record, dict) else 'invalid'}; 已记录确认={not failed}；本周期已登记变更引用一致={current}（不代表共享原型全部内容已确认）")
    return outcomes


def update_role(root, config, cycle, role, status, actor, reason, evidence=(), expected_digest=None):
    if role not in ROLES or status not in STATES or not actor.strip() or not reason.strip():
        raise ValueError("角色、状态、执行主体、原因必填且合法")
    path = safe_path(root, config.gate_file.as_posix())
    with exclusive(path.with_suffix(".yaml.lock")):
        if expected_digest is not None and file_hash(path) != expected_digest:
            raise ValueError("Gate 已被其他任务更新，请重读")
        errors = Result.empty()
        data = validate_ledger(root, config, errors)
        if errors.errors:
            raise ValueError("; ".join(errors.errors))
        if cycle not in data["cycles"]:
            raise ValueError("周期尚未初始化 Gate")
        record = data["cycles"][cycle]["roles"][role]
        if status not in TRANSITIONS[record["status"]]:
            raise ValueError("非法状态转换")
        target_cycle = safe_path(root, f"{config.demand_cycle_root.as_posix()}/{cycle}")
        identity = parse_cycle_identity(cycle)
        manifest = load_yaml_mapping(target_cycle / "manifest.yaml", errors)
        if manifest is None or manifest.get("state") == "cancelled":
            raise ValueError("周期缺失或已取消")
        updated = blank_record()
        updated.update(status=status, reason=reason, history=copy.deepcopy(record["history"]))
        if status in {"pending_confirmation", "confirmed"}:
            role_checks(root, config, target_cycle, role, errors)
            if errors.errors:
                raise ValueError("; ".join(errors.errors))
            updated["sources"] = capture_sources(root, config, cycle)
            if status == "confirmed":
                updated["confirmedGit"] = read_confirming_git(root)
                updated["confirmedAt"], updated["confirmedBy"] = updated["statusChangedAt"], actor
            evidence = list(evidence) or [entry["path"] for entry in record["evidence"]]
            for raw in evidence:
                if not safe_path(root, raw).is_file():
                    raise ValueError("交付记录文件不存在")
            updated["evidence"] = [{"path": raw} for raw in evidence]
            if not updated["evidence"]:
                raise ValueError("提交或确认必须提供实际证据")
        event = dict(eventId=f"{role}-{len(updated['history'])+1:04d}", **{
            "from": record["status"], "to": status, "at": updated["statusChangedAt"], "actor": actor,
            "record": {key: copy.deepcopy(value) for key, value in updated.items() if key != "history"},
        })
        updated["history"].append(event)
        validate_record(root, config, cycle, role, updated)
        data["cycles"][cycle]["roles"][role] = updated
        atomic_write(path, yaml.safe_dump(data, allow_unicode=True, sort_keys=False))


def initialize_cycle(root, config, cycle):
    if parse_cycle_identity(cycle) is None:
        raise ValueError("周期标识非法")
    path = safe_path(root, config.gate_file.as_posix())
    with exclusive(path.with_suffix(".yaml.lock")):
        if path.exists():
            errors = Result.empty()
            data = validate_ledger(root, config, errors)
            if errors.errors:
                raise ValueError("; ".join(errors.errors))
        else:
            data = dict(schemaVersion=2, projectId=config.project_id, timezone="Asia/Shanghai", cycles={})
        if cycle in data["cycles"]:
            raise ValueError("周期已存在，不能覆盖")
        validate_execution_protocol(root, config, cycle)
        manifest = safe_path(root, f"{config.demand_cycle_root.as_posix()}/{cycle}/manifest.yaml")
        errors = Result.empty()
        facts = validate_manifest(manifest, parse_cycle_identity(cycle).version, errors)
        if errors.errors or facts is None or facts.get("state") == "cancelled":
            raise ValueError("周期清单缺失、无效或已取消")
        data["cycles"][cycle] = {"roles": {role: blank_record() for role in ROLES}}
        atomic_write(path, yaml.safe_dump(data, allow_unicode=True, sort_keys=False))


def main():
    from core_validation import parse_config
    from local_paths import project_config_path
    parser = argparse.ArgumentParser(description="独立角色 Gate；confirm 仅用于记录实际负责人确认")
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--cycle", required=True)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--init", action="store_true")
    actions.add_argument("--capture-sources", action="store_true", help="列出当前产物路径及已登记变更范围，不生成快照")
    parser.add_argument("--role", choices=ROLES)
    parser.add_argument("--status", choices=sorted(STATES))
    parser.add_argument("--actor")
    parser.add_argument("--reason")
    parser.add_argument("--evidence", action="append", default=[])
    parser.add_argument("--expected-digest")
    args = parser.parse_args()
    root = args.project_root.resolve()
    result = Result.empty()
    config = parse_config(project_config_path(root), result)
    if config is None or config.schema_version != 20:
        parser.error("必须使用合法 Schema 20 配置")
    try:
        if args.init:
            initialize_cycle(root, config, args.cycle)
        elif args.capture_sources:
            print(json.dumps(capture_sources(root, config, args.cycle), ensure_ascii=False, indent=2))
        elif args.status:
            update_role(root, config, args.cycle, args.role, args.status, args.actor or "", args.reason or "", args.evidence, args.expected_digest)
        else:
            outcomes = validate_cycle(root / config.demand_cycle_root / args.cycle, config, root, result)
            print(json.dumps({key: {"confirmationRecorded": value.passed, "issues": value.failed_checks} for key, value in outcomes.items()}, ensure_ascii=False, indent=2))
            if result.errors:
                raise ValueError("; ".join(result.errors))
    except (ValueError, OSError, KeyError) as error:
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    main()
