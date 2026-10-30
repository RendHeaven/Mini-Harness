from __future__ import annotations

import re
import subprocess
from pathlib import Path


from core_validation import (
    ACCEPTED_DECISION_ROW,
    DEC_REFERENCE,
    DiscoveryFacts,
    HISTORY_SOURCE,
    HISTORY_STATUS,
    MARKDOWN_REQ_HEADING,
    MarkdownPrdFacts,
    PLACEHOLDER,
    REQ_SOURCE_LINE,
    Result,
    read_text,
)

def _heading_section(text: str, heading: str, level: int = 2) -> str:
    match = re.search(
        rf"^{'#' * level}\s+(?:\d+\.\s+)?{re.escape(heading)}\s*$\r?\n"
        rf"(.*?)(?=^{'#' * level}\s+|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    return match.group(1) if match else ""


def _table_rows(section: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for raw in section.splitlines():
        line = raw.strip()
        if not line.startswith("|") or not line.endswith("|"):
            continue
        cells = [cell.strip().strip("`").strip() for cell in line[1:-1].split("|")]
        if cells and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            continue
        rows.append(cells)
    return rows


def _meaningful_markdown(section: str) -> bool:
    stripped = re.sub(r"(?m)^#{1,6}\s+.*$", "", section)
    stripped = re.sub(r"(?m)^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*$", "", stripped)
    stripped = stripped.strip().strip("-").strip()
    return bool(stripped) and stripped.lower() not in {"none", "n/a"}


REQ_SUMMARY_DIMENSIONS = ("用户", "触发场景", "当前问题", "目标结果", "本期正向边界")
STRUCTURED_DETAIL_TABLES = {
    "操作流程": ("步骤", "操作者", "动作", "系统响应", "结果/下一状态"),
    "字段定义": ("字段名", "含义", "必填", "类型/格式", "默认/示例"),
    "字段校验": ("字段名", "校验条件", "错误提示", "触发时机"),
    "异常校验": ("场景/条件", "校验或拦截规则", "用户提示", "恢复方式"),
}


def _header_contains(header: list[str], required: str) -> bool:
    joined = " ".join(header)
    if required in joined:
        return True
    # Allow splitting compound headers such as 结果/下一状态 across cells or wording.
    parts = [part for part in re.split(r"[/／]", required) if part]
    return bool(parts) and all(any(part in cell for cell in header) for part in parts)


def _validate_requirement_summary(
    path: Path,
    identifier: str,
    summary: str,
    result: Result,
) -> bool:
    rows = _table_rows(summary)
    if len(rows) < 2:
        result.error(f"{path} 的 {identifier} 需求说明必须使用五维表（维度|内容）")
        return False
    header = rows[0]
    if not (_header_contains(header, "维度") and _header_contains(header, "内容")):
        result.error(f"{path} 的 {identifier} 需求说明表头必须包含「维度」「内容」")
        return False
    dim_index = next((i for i, cell in enumerate(header) if "维度" in cell), 0)
    present = {row[dim_index].strip() for row in rows[1:] if len(row) > dim_index}
    missing = [dim for dim in REQ_SUMMARY_DIMENSIONS if dim not in present]
    if missing:
        result.error(
            f"{path} 的 {identifier} 需求说明缺少维度: {', '.join(missing)}"
        )
        return False
    return True


def _validate_structured_detail_section(
    path: Path,
    identifier: str,
    heading: str,
    body: str,
    result: Result,
) -> bool:
    ok = True
    if heading == "数据流转":
        if not re.search(r"```\s*mermaid\b", body, re.IGNORECASE):
            result.error(f"{path} 的 {identifier} 数据流转必须包含 mermaid 代码块")
            ok = False
        elif not re.search(r"\bflowchart\b", body, re.IGNORECASE):
            result.error(f"{path} 的 {identifier} 数据流转 mermaid 必须使用 flowchart")
            ok = False
        return ok

    required_columns = STRUCTURED_DETAIL_TABLES.get(heading)
    if required_columns is None:
        return True
    rows = _table_rows(body)
    if not rows:
        result.error(f"{path} 的 {identifier} {heading} 必须使用 Markdown 表格")
        return False
    header = rows[0]
    missing = [col for col in required_columns if not _header_contains(header, col)]
    if missing:
        result.error(
            f"{path} 的 {identifier} {heading} 表头缺少列: {', '.join(missing)}"
        )
        ok = False
    if len(rows) < 2:
        result.error(f"{path} 的 {identifier} {heading} 表格缺少数据行")
        ok = False
    return ok


def validate_discovery(path: Path, result: Result) -> DiscoveryFacts:
    if not path.is_file():
        return DiscoveryFacts(False, "", {}, frozenset())
    text = read_text(path, result)
    valid = bool(text.strip()) and not PLACEHOLDER.search(text)
    hypothesis_rows = _table_rows(_heading_section(text, "待验证假设"))
    data_rows = [row for row in hypothesis_rows if row and row[0] != "HYP"]
    hypothesis_ids: set[str] = set()
    if not data_rows:
        result.error(f"{path} Discovery 必须登记至少一个待验证假设")
        valid = False
    for index, row in enumerate(data_rows, start=1):
        if len(row) != 3:
            result.error(f"{path} 待验证假设第 {index} 行必须为 3 列")
            valid = False
            continue
        identifier, page_idea, context = row
        identifier = identifier.upper()
        if not re.fullmatch(r"HYP-\d{3}", identifier):
            result.error(f"{path} 包含非法 HYP ID: {identifier}")
            valid = False
            continue
        if identifier in hypothesis_ids:
            result.error(f"{path} 存在重复 HYP ID: {identifier}")
            valid = False
        hypothesis_ids.add(identifier)
        if any(not value or value.lower() == "none" for value in (page_idea, context)):
            result.error(f"{path} 的 {identifier} 缺少页面想法或输入背景")
            valid = False
    feedback_rows = _table_rows(_heading_section(text, "Mock 与反馈"))
    feedback_data = [row for row in feedback_rows if row and row[0] != "轮次"]
    if not feedback_data:
        result.error(f"{path} Discovery 必须登记至少一条 Mock 与反馈记录")
        valid = False
    for index, row in enumerate(feedback_data, start=1):
        if len(row) != 5:
            result.error(f"{path} 的 Mock 与反馈第 {index} 行必须为 5 列")
            valid = False
            continue
        round_number, mock_path, hypotheses, feedback, outcome = row
        if any(not value or value.lower() == "none" for value in row):
            result.error(f"{path} 的 Mock 与反馈第 {index} 行不得为空")
            valid = False
        if not round_number.isdigit() or int(round_number) < 1:
            result.error(f"{path} 的 Mock 与反馈第 {index} 行轮次必须为正整数")
            valid = False
        if (not mock_path.startswith("原型仓库/") or not mock_path.endswith("index.html")
                or any(part in {"", ".", ".."} for part in mock_path.split("/")) or "\\" in mock_path):
            result.error(f"{path} 的 Mock 与反馈第 {index} 行 Mock 必须指向项目原型仓库中的 index.html")
            valid = False
        if not re.search(r"\bHYP-\d{3}\b", hypotheses, re.IGNORECASE):
            result.error(f"{path} 的 Mock 与反馈第 {index} 行必须关联 HYP")
            valid = False
    return DiscoveryFacts(valid, text, {}, frozenset())


def _validate_markdown_prd(
    path: Path,
    text: str,
    req_matches: list[re.Match[str]],
    result: Result,
) -> tuple[bool, dict[str, str]]:
    valid = True
    required_global = (
        "为什么做",
        "历史知识回溯",
        "本期边界",
        "功能需求",
        "影响与风险",
        "待确认事项",
    )
    positions: list[int] = []
    for heading in required_global:
        match = re.search(rf"^##\s+\d+\.\s+{re.escape(heading)}\s*$", text, re.MULTILINE)
        if match is None:
            result.error(f"{path} PRD 缺少全局章节：{heading}")
            valid = False
        else:
            positions.append(match.start())
    if len(positions) == len(required_global) and positions != sorted(positions):
        result.error(f"{path} PRD 六个全局章节顺序非法")
        valid = False

    requirement_sources: dict[str, str] = {}
    required_req_sections = ("需求说明", "详细需求", "影响范围", "验收要点")
    for index, req_match in enumerate(req_matches):
        identifier = req_match.group(1)
        if not req_match.group(0).lstrip().startswith("### "):
            result.error(f"{path} 的 {identifier} 必须使用三级标题")
            valid = False
        if index + 1 < len(req_matches):
            section_end = req_matches[index + 1].start()
        else:
            following = text[req_match.end():]
            next_global = re.search(r"^##\s+5\.\s+", following, re.MULTILINE)
            section_end = (
                req_match.end() + next_global.start() if next_global else len(text)
            )
        section = text[req_match.end():section_end]
        if re.search(r"^####\s+适用性矩阵\s*$", section, re.MULTILINE):
            result.error(f"{path} 的 {identifier} 不得包含适用性矩阵")
            valid = False
        source_lines = REQ_SOURCE_LINE.findall(section)
        if len(source_lines) == 1:
            requirement_sources[identifier] = source_lines[0].strip()
            if not DEC_REFERENCE.search(source_lines[0]):
                result.error(f"{path} 的 {identifier} 来源必须引用 accepted DEC")
                valid = False

        section_positions: list[int] = []
        req_parts: dict[str, str] = {}
        for heading in required_req_sections:
            match = re.search(
                rf"^####\s+{re.escape(heading)}\s*$\r?\n(.*?)(?=^####\s+|\Z)",
                section,
                re.MULTILINE | re.DOTALL,
            )
            if match is None:
                result.error(f"{path} 的 {identifier} 缺少核心章节：{heading}")
                valid = False
                continue
            section_positions.append(match.start())
            req_parts[heading] = match.group(1)
        if len(section_positions) == len(required_req_sections) and section_positions != sorted(section_positions):
            result.error(f"{path} 的 {identifier} 核心章节顺序非法")
            valid = False
        for heading in ("需求说明", "详细需求", "影响范围", "验收要点"):
            if heading in req_parts and not _meaningful_markdown(req_parts[heading]):
                result.error(f"{path} 的 {identifier} {heading} 缺少实质内容")
                valid = False
        if "需求说明" in req_parts and req_parts["需求说明"].strip():
            if not _validate_requirement_summary(
                path, identifier, req_parts["需求说明"], result
            ):
                valid = False
        if "验收要点" in req_parts and not re.search(r"(?m)^\s*[-*+]\s+\S+", req_parts["验收要点"]):
            result.error(f"{path} 的 {identifier} 验收要点必须使用可检查的列表项")
            valid = False

        detail = req_parts.get("详细需求", "")
        detail_heading_matches = list(re.finditer(r"^#####\s+(.+?)\s*$", detail, re.MULTILINE))
        for heading_index, heading_match in enumerate(detail_heading_matches):
            following = detail[heading_match.end():]
            next_heading = (
                detail_heading_matches[heading_index + 1]
                if heading_index + 1 < len(detail_heading_matches)
                else None
            )
            body = following[: next_heading.start() - heading_match.end()] if next_heading else following
            heading_name = heading_match.group(1).strip()
            if not _meaningful_markdown(body):
                result.error(
                    f"{path} 的 {identifier} 详细章节缺少实质内容: {heading_name}"
                )
                valid = False
            if not _validate_structured_detail_section(
                path, identifier, heading_name, body, result
            ):
                valid = False
    decision_rows = _table_rows(_heading_section(text, "产品决策"))
    for row in decision_rows:
        if not row or row[0] == "决策 ID" or row[1].lower() != "accepted":
            continue
        decision = row[0].upper()
        evidence = row[3] if len(row) >= 4 else ""
        if not evidence or evidence.lower() == "none":
            result.error(f"{path} 的 accepted 决策 {decision} 必须记录探索依据")
            valid = False
    return valid, requirement_sources


def validate_markdown_prd(path: Path, result: Result) -> MarkdownPrdFacts:
    if not path.is_file():
        result.error(f"缺少 Markdown PRD: {path}")
        return MarkdownPrdFacts(False, "", frozenset())
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
    except (OSError, UnicodeError) as exc:
        result.error(f"Markdown PRD 必须是可读取的 UTF-8 文件 {path}: {exc}")
        return MarkdownPrdFacts(False, "", frozenset())

    req_matches = list(MARKDOWN_REQ_HEADING.finditer(text))
    requirements: set[str] = set()
    duplicates: set[str] = set()
    for match in req_matches:
        identifier = match.group(1)
        if identifier in requirements:
            duplicates.add(identifier)
        requirements.add(identifier)
    if duplicates:
        result.error(f"{path} 存在重复 REQ: {', '.join(sorted(duplicates))}")
    if not req_matches:
        result.error(f"{path} 至少需要一个 REQ-xxx 二级或三级标题")

    structure_valid = bool(req_matches) and not duplicates
    requirement_sources: dict[str, str] = {}
    for index, req_match in enumerate(req_matches):
        identifier = req_match.group(1)
        section_end = req_matches[index + 1].start() if index + 1 < len(req_matches) else len(text)
        section = text[req_match.end():section_end]
        source_lines = REQ_SOURCE_LINE.findall(section)
        if len(source_lines) != 1 or not source_lines[0].strip():
            result.error(f"{path} 的 {identifier} 必须且只能记录一个非空“来源”字段")
            structure_valid = False
        elif source_lines:
            requirement_sources[identifier] = source_lines[0].strip()
    strict_valid, strict_sources = _validate_markdown_prd(path, text, req_matches, result)
    structure_valid = strict_valid and structure_valid
    requirement_sources.update(strict_sources)
    accepted_decisions = {
        match.upper() for match in ACCEPTED_DECISION_ROW.findall(text)
    }
    return MarkdownPrdFacts(
        structure_valid,
        text,
        frozenset(requirements),
        requirement_sources,
        frozenset(accepted_decisions),
    )


def markdown_req_decision_references(text: str) -> set[str]:
    """只从各 REQ 的“来源”字段提取 PRD 正式决策引用。"""
    matches = list(MARKDOWN_REQ_HEADING.finditer(text))
    references: set[str] = set()
    for index, match in enumerate(matches):
        section_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        section = text[match.end():section_end]
        for source in REQ_SOURCE_LINE.findall(section):
            references.update(reference.upper() for reference in DEC_REFERENCE.findall(source))
    return references


def history_documents(history_root: Path, excluded_roots: tuple[Path, ...] = ()) -> list[Path]:
    if not history_root.is_dir():
        return []
    allowed = {".docx", ".pdf", ".md"}
    return sorted(
        path
        for path in history_root.rglob("*")
        if path.is_file() and path.suffix.lower() in allowed and path.name.lower() != "readme.md"
        and path.resolve().is_relative_to(history_root.resolve())
        and not any(path.resolve().is_relative_to(root.resolve()) for root in excluded_roots)
    )


def validate_history_review(prd_text: str, history_root: Path, result: Result, prd_path: Path,
                            *, project_root: Path | None = None,
                            excluded_roots: tuple[Path, ...] = (), strict_references: bool = False,
                            imported_documents: tuple[Path, ...] = ()) -> bool:
    matches = HISTORY_STATUS.findall(prd_text)
    if len(matches) != 1:
        result.error(f"{prd_path} 必须且只能记录一个历史知识回溯状态")
        return False
    status = matches[0].lower()
    source_matches = HISTORY_SOURCE.findall(prd_text)
    if len(source_matches) != 1 or not source_matches[0].strip():
        result.error(f"{prd_path} 必须且只能记录一个非空历史来源字段")
        return False
    source = source_matches[0].strip()
    documents = history_documents(history_root, excluded_roots)
    imports = {path.relative_to(project_root.resolve()).as_posix(): path for path in imported_documents} if project_root else {}
    imported_reference = False
    if strict_references or imports:
        references = re.findall(r"[^\s`|<>()[\]，；;,]+?\.(?:md|pdf|docx)", source, re.IGNORECASE)
        allowed = {path.resolve() for path in documents}
        for reference in references:
            reference_path = Path(reference.replace("\\", "/"))
            if len(reference_path.parts) == 1:
                valid_reference = any(path.name == reference for path in documents)
            else:
                candidates = [reference_path] if reference_path.is_absolute() else [
                    base / reference_path for base in (prd_path.parent, history_root, project_root) if base is not None
                ]
                valid_reference = any(path.resolve() in allowed for path in candidates)
            # Cross-line permission requires the exact registered project-relative spelling.
            if reference in imports:
                valid_reference = True
                imported_reference = True
            if not valid_reference:
                result._hard_error(f"{prd_path} 历史来源不在本周期产品线范围: {reference}")
                return False
    if imports and (status != "completed" or not imported_reference):
        result._hard_error(f"{prd_path} 已登记历史导入时必须 completed 并显式引用登记路径")
        return False
    if documents or imports:
        referenced = imported_reference or any(path.name in source for path in documents)
        if status != "completed" or not referenced:
            result.error(
                f"{prd_path} 存在历史文档时必须标记 completed，"
                "并在历史来源字段引用真实文件名"
            )
            return False
    elif status != "greenfield-skipped" or source.lower() != "none":
        result.error(
            f"{prd_path} 没有历史文档时必须标记 greenfield-skipped，"
            "且历史来源必须为 none"
        )
        return False
    return True


def _git(service_root: Path, arguments: list[str], result: Result, description: str) -> str:
    try:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=service_root,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        result.error(f"无法执行 Git {description}: {exc}")
        return ""
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        result.error(f"Git {description} 失败: {detail}")
        return ""
    return completed.stdout.strip()


def _git_is_ancestor(service_root: Path, ancestor: str, descendant: str) -> bool:
    try:
        completed = subprocess.run(
            ["git", "merge-base", "--is-ancestor", ancestor, descendant],
            cwd=service_root,
            check=False,
            capture_output=True,
        )
    except OSError:
        return False
    return completed.returncode == 0


def _normalized_repository(value: str) -> str:
    normalized = value.strip().replace("\\", "/").rstrip("/")
    return normalized[:-4] if normalized.lower().endswith(".git") else normalized
