"""Append-only PRD change notes; full versions belong to normal Git history."""
import argparse
import difflib
import hashlib
import json
import re
from pathlib import Path

import yaml

from asset_io import atomic_write, exclusive, file_hash, now, safe_path
from core_validation import Result, load_yaml_mapping

LOG_PATH = "prd-changes/revisions.yaml"
INDEX_PATH = "prd-changelog.md"
JOURNAL_PATH = "pending-revision.json"
LOG_FIELDS = {"schemaVersion", "prd", "createdAt", "createdBy", "changes"}
CHANGE_FIELDS = {"id", "at", "actor", "reason", "impact", "document"}


def load_log(product):
    result = Result.empty()
    data = load_yaml_mapping(safe_path(product, LOG_PATH), result)
    if result.errors or data is None:
        raise ValueError("PRD 修订索引缺失或损坏")
    return data


def required_text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"PRD 修订{label}必填")


def valid_digest(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("PRD 临时事务摘要非法")


def validate_log(data):
    """Check record identities and paths without consulting any PRD snapshots."""
    from role_gates import timestamp
    if not isinstance(data, dict) or type(data.get("schemaVersion")) is not int or data["schemaVersion"] != 2:
        raise ValueError("PRD 修订索引仅支持 schemaVersion: 2")
    if set(data) != LOG_FIELDS:
        raise ValueError("PRD 修订索引字段错误，不保存基线或正文摘要")
    required_text(data.get("prd"), "文件名")
    if Path(data["prd"]).name != data["prd"] or any(char in data["prd"] for char in "/\\:"):
        raise ValueError("PRD 修订索引身份错误")
    created = timestamp(data["createdAt"])
    required_text(data["createdBy"], "创建主体")
    changes = data.get("changes")
    if not isinstance(changes, list):
        raise ValueError("PRD 修订必须为列表")
    previous_at = created
    for number, entry in enumerate(changes, 1):
        identifier = f"CHG-{number:03d}"
        if not isinstance(entry, dict) or entry.get("id") != identifier:
            raise ValueError("PRD 修订编号必须连续且不可重复")
        if set(entry) != CHANGE_FIELDS or entry["document"] != f"prd-changes/{identifier}.md":
            raise ValueError("PRD 修订文档路径或字段非法")
        at = timestamp(entry["at"])
        if at < previous_at:
            raise ValueError("PRD 修订时间不可倒退")
        previous_at = at
        for key, label in (("actor", "主体"), ("reason", "原因"), ("impact", "影响")):
            required_text(entry[key], label)


def validate_revisions(product, prd, result):
    """Validate current change notes without binding the live PRD content."""
    try:
        product, prd = checked_paths(product, prd)
        if safe_path(product, JOURNAL_PATH).exists():
            raise ValueError("存在 incomplete PRD 修订，请先恢复")
        data = load_log(product)
        validate_log(data)
        if data["prd"] != prd.name:
            raise ValueError("PRD 修订索引身份错误")
        expected = set()
        for entry in data["changes"]:
            relative = f"prd-changes/{entry['id']}.md"
            document = safe_path(product, relative)
            if not document.is_file() or not document.read_bytes():
                raise ValueError("PRD 追踪文档缺失或为空")
            expected.add(document.name)
        # Unindexed notes must never be silently overwritten by the next writer.
        for candidate in safe_path(product, "prd-changes").glob("CHG-*.md"):
            if re.fullmatch(r"CHG-\d+\.md", candidate.name) and candidate.name not in expected:
                raise ValueError(f"存在未登记 PRD 修订文档：{candidate.name}")
        if safe_path(product, INDEX_PATH).read_text(encoding="utf-8") != render_index(data):
            raise ValueError("PRD 修订 Markdown 索引与记录不符")
    except (ValueError, OSError, KeyError, TypeError) as error:
        result.error(str(error))


def render_index(log):
    validate_log(log)
    created_at = log["createdAt"]
    lines = [
        "# PRD 修订记录", "", f"- 创建时间：{created_at}",
        f"- 最后编辑时间：{log['changes'][-1]['at'] if log['changes'] else created_at}",
        "- 时区：Asia/Shanghai",
    ]
    lines.append(f"- 创建主体：{log['createdBy']}")
    lines.extend(["", "| 修订 | 时间 | 原因 | 影响 |", "| --- | --- | --- | --- |"])
    for change in log["changes"]:
        clean = lambda value: str(value).replace("|", "\\|").replace("\n", " ")
        lines.append(f"| [{change['id']}](prd-changes/{change['id']}.md) | {change['at']} | {clean(change['reason'])} | {clean(change['impact'])} |")
    return "\n".join(lines) + "\n"


def checked_paths(product, prd):
    product = Path(product).resolve()
    prd = Path(prd)
    if prd.parent.resolve() != product:
        raise ValueError("PRD 必须位于产品目录内")
    prd = safe_path(product, prd.name)
    if not prd.is_file():
        raise ValueError("当前 PRD 不存在")
    return product, prd


def checked_log(product, prd):
    errors = Result.empty()
    validate_revisions(product, prd, errors)
    if errors.errors:
        raise ValueError("; ".join(errors.errors))
    return load_log(product)


def log_changes(product):
    """Return ordered CHG IDs for role confirmation coverage."""
    data = load_log(product)
    prd = safe_path(product, data.get("prd"))
    return [entry["id"] for entry in checked_log(product, prd)["changes"]]


def index_files(log):
    return {LOG_PATH: yaml.safe_dump(log, allow_unicode=True, sort_keys=False), INDEX_PATH: render_index(log)}


def current_digest(path):
    return file_hash(path) if path.exists() else None


def write_transaction(product, prd, operation, files, before_hash, expected):
    journal = safe_path(product, JOURNAL_PATH)
    if journal.exists():
        raise ValueError("存在 incomplete PRD 修订，请先恢复")
    job = dict(
        schemaVersion=2, operation=operation, prd=prd.name, beforeSha256=before_hash,
        afterSha256=hashlib.sha256(files[prd.name].encode("utf-8")).hexdigest() if prd.name in files else before_hash,
        files=files, expected=expected,
    )
    atomic_write(journal, json.dumps(job, ensure_ascii=False))
    complete_pending(product)


def initialize(product, prd, actor):
    product, prd = checked_paths(product, prd)
    required_text(actor, "创建主体")
    with exclusive(safe_path(product, ".prd-revision.lock")):
        target = safe_path(product, LOG_PATH)
        if target.exists() or safe_path(product, INDEX_PATH).exists():
            raise ValueError("已有修订记录，不允许覆盖初始化")
        changes = safe_path(product, "prd-changes")
        if changes.exists() and any(changes.iterdir()):
            raise ValueError("已存在修订文件，需核对中断现场")
        log = dict(schemaVersion=2, prd=prd.name, createdAt=now(), createdBy=actor, changes=[])
        write_transaction(product, prd, "initialize", index_files(log), file_hash(prd), {LOG_PATH: None, INDEX_PATH: None})


def complete_pending(product):
    """Recover only if every target is still the old or planned new value."""
    product = Path(product).resolve()
    journal = safe_path(product, JOURNAL_PATH)
    job = json.loads(journal.read_text(encoding="utf-8"))
    if not isinstance(job, dict) or type(job.get("schemaVersion")) is not int or job["schemaVersion"] != 2:
        raise ValueError("PRD 中断事务仅支持 schemaVersion: 2")
    if set(job) != {"schemaVersion", "operation", "prd", "beforeSha256", "afterSha256", "files", "expected"}:
        raise ValueError("PRD 中断事务字段非法")
    prd = safe_path(product, job["prd"])
    checked_paths(product, prd)
    for key in ("beforeSha256", "afterSha256"):
        valid_digest(job[key])
    files, expected = job["files"], job["expected"]
    if not isinstance(files, dict) or not isinstance(expected, dict) or set(files) != set(expected):
        raise ValueError("PRD 中断事务文件清单非法")
    allowed = {LOG_PATH, INDEX_PATH}
    operation = job.get("operation")
    if operation == "revise":
        changes = [relative for relative in files if re.fullmatch(r"prd-changes/CHG-\d{3,}\.md", relative)]
        if len(changes) != 1:
            raise ValueError("PRD 中断事务修订文档非法")
        allowed.update((prd.name, changes[0]))
    elif operation != "initialize":
        raise ValueError("PRD 中断事务仅支持 initialize 或 revise 操作")
    if set(files) != allowed:
        raise ValueError("PRD 中断事务禁止写入清单外文件")
    if any(not isinstance(content, str) for content in files.values()):
        raise ValueError("PRD 中断事务正文非法")
    try:
        planned_log = yaml.safe_load(files[LOG_PATH])
    except yaml.YAMLError as error:
        raise ValueError("PRD 中断事务修订索引非法") from error
    validate_log(planned_log)
    if planned_log["prd"] != prd.name or files[INDEX_PATH] != render_index(planned_log):
        raise ValueError("PRD 中断事务索引与记录不符")
    if operation == "initialize" and planned_log["changes"]:
        raise ValueError("PRD 初始化事务不能包含修订记录")
    if operation == "revise" and (not planned_log["changes"] or planned_log["changes"][-1]["document"] != changes[0]):
        raise ValueError("PRD 中断事务修订文档与末条记录不符")
    if file_hash(prd) not in {job["beforeSha256"], job["afterSha256"]}:
        raise ValueError("中断后 PRD 被第三方修改，保留现场，不能自动覆盖")
    # Preflight every file before the first write to preserve external edits.
    for relative, content in files.items():
        if expected[relative] is not None:
            valid_digest(expected[relative])
        target = safe_path(product, relative)
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if current_digest(target) not in {expected[relative], digest}:
            raise ValueError(f"PRD 修订文件存在冲突，不能覆盖：{relative}")
    for relative, content in files.items():
        atomic_write(safe_path(product, relative), content)
    journal.unlink()


def revise(product, prd, content, actor, reason, impact):
    product, prd = checked_paths(product, prd)
    for value, label in ((actor, "主体"), (reason, "原因"), (impact, "影响")):
        required_text(value, label)
    content = content.replace("\r\n", "\n")
    with exclusive(safe_path(product, ".prd-revision.lock")):
        expected = {relative: current_digest(safe_path(product, relative)) for relative in (LOG_PATH, INDEX_PATH)}
        log = checked_log(product, prd)
        before_bytes = prd.read_bytes()
        before = before_bytes.decode("utf-8")
        if before_bytes == content.encode("utf-8"):
            return None
        identifier, at = f"CHG-{len(log['changes'])+1:03d}", now()
        before_hash = hashlib.sha256(before_bytes).hexdigest()
        diff_lines = difflib.unified_diff(before.splitlines(True), content.splitlines(True), fromfile=prd.name + ":before", tofile=prd.name + ":after", n=3)
        diff = "".join(line if line.endswith("\n") else line + "\n\\ No newline at end of file\n" for line in diff_lines)
        document = (
            f"# {identifier} PRD 修订追踪\n\n- 创建时间：{at}\n- 最后编辑时间：{at}\n"
            f"- 时区：Asia/Shanghai\n- 操作主体：{actor}\n- 原因：{reason}\n- 影响：{impact}\n"
            f"- 派生资产同步：pending；由各角色独立复核。\n\n## 内容差异\n\n~~~~diff\n{diff}\n~~~~\n"
        )
        relative = f"prd-changes/{identifier}.md"
        if safe_path(product, relative).exists():
            raise ValueError("PRD 修订文档已存在，不能覆盖")
        log["changes"].append(dict(id=identifier, at=at, actor=actor, reason=reason, impact=impact, document=relative))
        validate_log(log)
        files = {relative: document, prd.name: content, **index_files(log)}
        expected.update({relative: None, prd.name: before_hash})
        write_transaction(product, prd, "revise", files, before_hash, expected)
        return identifier


def main():
    parser = argparse.ArgumentParser(description="PRD 原位修订及逐次变更记录；先在独立文件准备修订正文")
    parser.add_argument("--prd", type=Path, required=True)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--init", action="store_true")
    action.add_argument("--content", type=Path)
    action.add_argument("--recover", action="store_true")
    parser.add_argument("--actor", default="")
    parser.add_argument("--reason", default="")
    parser.add_argument("--impact", default="")
    args = parser.parse_args()
    prd = args.prd.absolute()
    try:
        if args.init:
            initialize(prd.parent, prd, args.actor)
        elif args.recover:
            with exclusive(safe_path(prd.parent, ".prd-revision.lock")):
                complete_pending(prd.parent)
        else:
            print(revise(prd.parent, prd, args.content.read_text(encoding="utf-8"), args.actor, args.reason, args.impact) or "无修改")
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    main()
