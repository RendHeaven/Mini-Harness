#!/usr/bin/env python3
"""校验 Harness 生成的 TestHub Markdown v1 文档，不执行网络请求。"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ALLOWED_FUNCTIONS = {
    "query", "detail", "edit", "delete", "pagination", "create", "upload", "download", "share"
}
ALLOWED_PRIORITIES = {"P0", "P1", "P2", "P3"}
REQUIRED_CASE_FIELDS = ("模块", "页面", "功能", "优先级", "用例类型", "前置条件")
REQUIRED_SECTIONS = ("测试步骤", "预期结果", "断言", "测试数据", "备注")
CASE_HEADING = re.compile(r"^###\s+([^：:\s]+)[：:]\s*(.+?)\s*$", re.MULTILINE)
FIELD_LINE = re.compile(r"^-\s*([^：:]+)[：:]\s*(.+?)\s*$", re.MULTILINE)
SECTION_HEADING = re.compile(r"^####\s+(.+?)\s*$", re.MULTILINE)
VARIABLE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_.-]*)\}")
CASE_TABLE_COLUMNS = (
    "用例编号", "模块", "页面", "功能", "测试标题", "前置条件", "测试步骤", "预期结果",
    "优先级", "用例类型", "断言", "测试数据", "备注",
)
CASE_TABLE_HEADER = "| " + " | ".join(CASE_TABLE_COLUMNS) + " |"
TABLE_SEPARATOR_CELL = re.compile(r"^:?-{3,}:?$")


def _section(text: str, heading: str, level: int) -> str:
    marker = "#" * level
    match = re.search(
        rf"^{re.escape(marker)}\s+{re.escape(heading)}\s*$\r?\n(.*?)(?=^{re.escape(marker)}\s+|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    return match.group(1) if match else ""


def _case_blocks(text: str) -> list[tuple[str, str, str]]:
    matches = list(CASE_HEADING.finditer(text))
    blocks: list[tuple[str, str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        blocks.append((match.group(1), match.group(2), text[match.end():end]))
    return blocks


def _split_markdown_table_row(line: str) -> list[str] | None:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return None
    cells: list[str] = []
    current: list[str] = []
    index = 1
    while index < len(stripped) - 1:
        character = stripped[index]
        if character == "\\" and index + 1 < len(stripped) - 1 and stripped[index + 1] == "|":
            current.extend((character, "|"))
            index += 2
            continue
        if character == "|":
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(character)
        index += 1
    cells.append("".join(current).strip())
    return cells


def _case_table_rows(text: str) -> tuple[list[tuple[int, list[str]]], list[str]]:
    lines = text.splitlines()
    try:
        header_index = next(
            index for index, line in enumerate(lines) if line.strip() == CASE_TABLE_HEADER
        )
    except StopIteration:
        return [], []

    errors: list[str] = []
    separator_index = header_index + 1
    if separator_index >= len(lines):
        return [], ["TestHub 用例导入表缺少分隔行"]
    separator = _split_markdown_table_row(lines[separator_index])
    if (
        separator is None
        or len(separator) != len(CASE_TABLE_COLUMNS)
        or any(not TABLE_SEPARATOR_CELL.fullmatch(cell.replace(" ", "")) for cell in separator)
    ):
        errors.append(f"TestHub 用例导入表第 {separator_index + 1} 行必须是 13 列 Markdown 分隔行")

    rows: list[tuple[int, list[str]]] = []
    for index in range(separator_index + 1, len(lines)):
        raw = lines[index]
        if not raw.strip():
            if rows:
                break
            continue
        if not raw.lstrip().startswith("|"):
            break
        cells = _split_markdown_table_row(raw)
        if cells is None or len(cells) != len(CASE_TABLE_COLUMNS):
            actual = len(cells) if cells is not None else 0
            errors.append(
                f"TestHub 用例导入表第 {index + 1} 行必须包含 13 列，实际为 {actual} 列"
            )
            continue
        rows.append((index + 1, cells))
    return rows, errors


def _subsection(block: str, heading: str) -> str:
    match = re.search(
        rf"^####\s+{re.escape(heading)}\s*$\r?\n(.*?)(?=^####\s+|\Z)",
        block,
        re.MULTILINE | re.DOTALL,
    )
    return match.group(1).strip() if match else ""


def validate_document(path: Path) -> tuple[list[str], int]:
    errors: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return [f"无法读取文档：{exc}"], 0

    if not re.search(r"^#\s+TestHub AI UI 测试用例\s*$", text, re.MULTILINE):
        errors.append("缺少一级标题“TestHub AI UI 测试用例”")
    info = _section(text, "文档信息", 2)
    for label in ("文档标识", "协议版本", "Excel 字段基线", "需求版本", "Git 提交", "生成时间"):
        if not re.search(rf"^-\s*{re.escape(label)}[：:]\s*.+$", info, re.MULTILINE):
            errors.append(f"文档信息缺少“{label}”")
    if "external-harness-markdown-v1" not in info:
        errors.append("协议版本必须为 external-harness-markdown-v1")
    if "external-harness-excel-v3" not in info:
        errors.append("Excel 字段基线必须为 external-harness-excel-v3")

    context = _section(text, "参考上下文", 2)
    if not context or "| 类型 | 路径 | 状态 | SHA256 | 使用说明 |" not in context:
        errors.append("缺少完整的参考上下文表")
    if "## 测试用例" not in text:
        errors.append("缺少测试用例章节")

    seen: set[str] = set()
    cases = _case_blocks(text)
    table_rows, table_errors = _case_table_rows(text)
    errors.extend(table_errors)
    table_case_ids = [cells[0] for _line_number, cells in table_rows]
    if cases and CASE_TABLE_HEADER not in text:
        errors.append("缺少 TestHub Excel v3 用例导入表")
    if len(table_case_ids) != len(set(table_case_ids)):
        errors.append("TestHub 用例导入表存在重复用例编号")
    if set(table_case_ids) != {case_id for case_id, _title, _block in cases}:
        errors.append("TestHub 用例导入表与详情用例编号不一致")
    for line_number, cells in table_rows:
        row = dict(zip(CASE_TABLE_COLUMNS, cells))
        case_label = row["用例编号"] or f"第 {line_number} 行"
        for column in CASE_TABLE_COLUMNS:
            if not row[column]:
                errors.append(f"TestHub 用例导入表 {case_label} 的“{column}”不得为空")
        if row["功能"] and row["功能"] not in ALLOWED_FUNCTIONS:
            errors.append(f"TestHub 用例导入表 {case_label} 功能不在允许枚举中")
        if row["优先级"] and row["优先级"] not in ALLOWED_PRIORITIES:
            errors.append(f"TestHub 用例导入表 {case_label} 优先级不在允许枚举中")
    for case_id, _title, block in cases:
        if case_id in seen:
            errors.append(f"重复用例编号：{case_id}")
        seen.add(case_id)
        fields = {name.strip(): value.strip() for name, value in FIELD_LINE.findall(block)}
        for field in REQUIRED_CASE_FIELDS:
            if not fields.get(field):
                errors.append(f"{case_id} 缺少字段“{field}”")
        if fields.get("功能") not in ALLOWED_FUNCTIONS:
            errors.append(f"{case_id} 功能不在允许枚举中")
        if fields.get("优先级") not in ALLOWED_PRIORITIES:
            errors.append(f"{case_id} 优先级不在允许枚举中")
        for section in REQUIRED_SECTIONS:
            content = _subsection(block, section)
            if not content:
                errors.append(f"{case_id} 缺少“{section}”章节")
        data_section = _subsection(block, "测试数据")
        json_match = re.search(r"```json\s*\n(.*?)\n```", data_section, re.DOTALL)
        if not json_match:
            errors.append(f"{case_id} 测试数据必须为 JSON 代码块")
        else:
            try:
                payload = json.loads(json_match.group(1))
            except json.JSONDecodeError:
                errors.append(f"{case_id} 测试数据不是合法 JSON")
                payload = None
            if payload is not None and not isinstance(payload, dict):
                errors.append(f"{case_id} 测试数据必须是 JSON 对象")
        steps = _subsection(block, "测试步骤")
        expected = _subsection(block, "预期结果")
        assertions = _subsection(block, "断言")
        for variable in set(VARIABLE.findall(steps + expected + assertions)) - {"safe_data_prefix"}:
            if variable not in set(VARIABLE.findall(steps)) or variable not in set(VARIABLE.findall(expected)) or variable not in set(VARIABLE.findall(assertions)):
                errors.append(f"{case_id} 变量 ${{{variable}}} 未在步骤、预期和断言中闭环")
    return errors, len(cases)


def main() -> int:
    if len(sys.argv) != 2:
        print("用法：validate_testhub_markdown.py <cases.md>")
        return 2
    errors, count = validate_document(Path(sys.argv[1]))
    if errors:
        for error in errors:
            print(f"[ERROR] {error}")
        return 1
    print(f"[INFO] TestHub Markdown 校验通过：{count} 条用例")
    return 0


if __name__ == "__main__":
    sys.exit(main())
