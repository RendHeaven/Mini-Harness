from __future__ import annotations

import hashlib
import re
import subprocess
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from local_paths import resolve_service_path

from core_validation import (
    ALLOWED_EXECUTION_STATUSES,
    BACKEND_MULTI_PLAN_GATE_ITEMS,
    BACKEND_PLAN_CONFIRMER_LINE,
    BACKEND_PLAN_CONFIRM_DATE_LINE,
    BACKEND_PLAN_CONFIRM_LINE,
    BACKEND_PLAN_DEVELOPER_LINE,
    BACKEND_PLAN_ENDPOINT_HEADING,
    BACKEND_PLAN_MODE_LINE,
    BACKEND_PLAN_MODULE_REFERENCE,
    BACKEND_PLAN_OVERVIEW_REQ_ROW,
    BACKEND_PLAN_REQ_ROW,
    BACKEND_PLAN_RISK_LINE,
    BACKEND_PLAN_SERVICE_LINE,
    BACKEND_PLAN_STATUS_LINE,
    BACKEND_PLAN_TASK_HEADING,
    BACKEND_PLAN_VERSION_LINE,
    BACKEND_SINGLE_PLAN_GATE_ITEMS,
    HASH_PATTERN,
    HarnessConfig,
    PENDING_MARKER,
    PLACEHOLDER,
    REQ_REFERENCE,
    REVISION_PATTERN,
    Result,
    _exact_keys,
    _safe_service_path,
    load_yaml_mapping,
    read_text,
)

from product_ui_validation import _git, _git_is_ancestor, _normalized_repository
from validate_testhub_markdown import validate_document as validate_testhub_markdown


def _development_service(
    project_root: Path,
    config: HarnessConfig,
    identifier: str,
    expected_type: str,
    result: Result,
) -> tuple[Mapping[str, Any], Path] | None:
    catalog_path = project_root / config.service_catalog
    data = load_yaml_mapping(catalog_path, result)
    services = data.get("services") if data else None
    if not isinstance(services, Mapping):
        result.error(f"{catalog_path} services 必须是映射")
        return None
    service = services.get(identifier)
    if not isinstance(service, Mapping):
        result.error(f"execution 引用了不存在的服务: {identifier}")
        return None
    if service.get("type") != expected_type:
        result.error(f"execution 服务类型不一致: {identifier} 不是 {expected_type}")
        return None
    local_path = service.get("localPath")
    if not isinstance(local_path, str) or not local_path.strip():
        result.error(f"服务缺少 localPath: {identifier}")
        return None
    service_root = resolve_service_path(project_root, identifier, local_path)
    if not service_root.is_dir():
        result.error(f"服务本地目录不存在: {service_root}")
        return None
    return service, service_root


def _git_blob_sha256(service_root: Path, revision: str, path: str, result: Result) -> str:
    try:
        completed = subprocess.run(
            ["git", "show", f"{revision}:{path.replace(chr(92), '/') }"],
            cwd=service_root,
            check=False,
            capture_output=True,
        )
    except OSError as exc:
        result.error(f"无法读取契约 Git 对象: {exc}")
        return ""
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        result.error(f"契约不存在于 {revision}: {path}: {detail}")
        return ""
    return hashlib.sha256(completed.stdout).hexdigest()


def _artifact_ready(path: Path, result: Result) -> bool:
    if not path.is_file():
        return False
    text = read_text(path, result)
    return bool(text.strip()) and not PLACEHOLDER.search(text) and not PENDING_MARKER.search(text)


API_DOCUMENT_V5_MARKER = "接口文档协议：`v5`"
API_DOCUMENT_ENDPOINT_HEADING = re.compile(r"^#{3,4} \[API-[A-Za-z0-9_-]+\][^\r\n]*$", re.MULTILINE)
API_PLAN_PAGE_DEMAND_V3_MARKER = "API Plan 方式：`page-demand-v3`"
API_PLAN_PAGE_HEADING = re.compile(r"^### .+", re.MULTILINE)
API_PLAN_PAGE_PLAN_HEADING = "## 页面 API 计划"
API_PLAN_SHARED_CAPABILITIES_HEADING = "## 跨页面共享能力索引"
API_PLAN_BLOCKS_HEADING = "## 阻塞项"
API_PLAN_CONSUMPTION_INDEX_HEADING = "## 接口消费索引（附录）"
API_PLAN_GAP_CATEGORIES = {
    "none",
    "missing_endpoint",
    "missing_request_field",
    "missing_response_field",
    "missing_semantics",
    "external_contract",
}


def _api_document_section_has_table(section: str, heading: str) -> bool:
    """确认接口段落拥有带至少一行数据的 Markdown 字段表。"""
    heading_match = re.search(rf"^#{{4,5}} {re.escape(heading)}\s*$", section, re.MULTILINE)
    if heading_match is None:
        return False
    remainder = section[heading_match.end():]
    next_heading = re.search(r"^#{1,5} ", remainder, re.MULTILINE)
    body = remainder[: next_heading.start()] if next_heading else remainder
    rows = [line.strip() for line in body.splitlines() if line.strip().startswith("|")]
    return len(rows) >= 3


def _validate_api_document_v5(text: str, service: str, result: Result) -> bool:
    """校验 v5：无请求模型、逐字段表和每接口 JSON 样式串。"""
    if API_DOCUMENT_V5_MARKER not in text:
        result.error(f"backend {service} 仅支持接口文档协议 v5")
        return False
    if "## 接口总览" not in text or "## 具体接口" not in text:
        result.error(f"backend {service} 接口文档协议 v5 必须包含接口总览和具体接口两章节")
        return False
    overview_start = text.find("## 接口总览")
    detail_start = text.find("## 具体接口")
    overview = text[overview_start:detail_start] if detail_start > overview_start else ""
    if "来源 Plan" not in overview:
        result.error(f"backend {service} 接口文档协议 v5 的接口总览缺少来源 Plan 列")
        return False
    matches = list(API_DOCUMENT_ENDPOINT_HEADING.finditer(text))
    if not matches:
        result.error(f"backend {service} 接口文档协议 v5 未包含 API 端点")
        return False
    valid = True
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        section = text[match.start():end]
        endpoint = match.group(0)
        for required in ("- 来源 Plan：`", "- 接口地址：`", "- 功能说明："):
            if required not in section:
                result.error(f"backend {service} {endpoint} 协议 v5 缺少 {required.removeprefix('- ').removesuffix('`')}")
                valid = False
        for heading in ("请求体", "响应体", "成功状态", "错误状态"):
            if not _api_document_section_has_table(section, heading):
                result.error(f"backend {service} {endpoint} 协议 v5 缺少 {heading} 表")
                valid = False
        if not re.search(r"^#### JSON 示例\s*\n\s*```json\s*\n[\s\S]*?\n```", section, re.MULTILINE):
            result.error(f"backend {service} {endpoint} 协议 v5 缺少 JSON 示例")
            valid = False
        if "请求模型" in section:
            result.error(f"backend {service} {endpoint} 协议 v5 不应出现请求模型")
            valid = False
        for heading in ("请求体", "响应体"):
            heading_match = re.search(rf"^#### {heading}\s*$", section, re.MULTILINE)
            if heading_match is None:
                continue
            remainder = section[heading_match.end():]
            next_heading = re.search(r"^#### ", remainder, re.MULTILINE)
            table = remainder[:next_heading.start()] if next_heading else remainder
            for line in table.splitlines():
                if not line.startswith("| `"):
                    continue
                field = line.split("|", 2)[1]
                if "、" in field:
                    result.error(f"backend {service} {endpoint} 协议 v5 的{heading}必须逐字段一行")
                    valid = False
                    break
    return valid


def _api_plan_page_demand_rows(section: str) -> list[list[str]]:
    """返回 Markdown 表的数据行，忽略表头和分隔行。"""
    rows: list[list[str]] = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [item.strip() for item in stripped.strip("|").split("|")]
        if not cells or all(re.fullmatch(r":?-{3,}:?", item.replace(" ", "")) for item in cells):
            continue
        if cells[0].upper() == "TASK":
            continue
        rows.append(cells)
    return rows


def _api_plan_sections(section: str) -> list[tuple[str, str]]:
    """按三级页面标题拆出 v3 API Plan 的页面章节。"""
    matches = list(API_PLAN_PAGE_HEADING.finditer(section))
    return [
        (
            match.group(0).removeprefix("### ").strip(),
            section[match.end() : matches[index + 1].start() if index + 1 < len(matches) else len(section)],
        )
        for index, match in enumerate(matches)
    ]


def _validate_frontend_api_plan_page_demand_v3(text: str, service: str, result: Result) -> bool:
    """校验页面唯一分组、同表匹配和缺口分类的 API Plan v3。"""
    if API_PLAN_PAGE_DEMAND_V3_MARKER not in text:
        result.error(f"frontend {service} 仅支持 API Plan page-demand-v3")
        return False
    required_headings = (
        "## 总览",
        API_PLAN_PAGE_PLAN_HEADING,
        API_PLAN_SHARED_CAPABILITIES_HEADING,
        API_PLAN_BLOCKS_HEADING,
        API_PLAN_CONSUMPTION_INDEX_HEADING,
    )
    if any(heading not in text for heading in required_headings):
        result.error(f"frontend {service} 页面 API Plan v3 缺少固定章节")
        return False
    page_start = text.find(API_PLAN_PAGE_PLAN_HEADING)
    shared_start = text.find(API_PLAN_SHARED_CAPABILITIES_HEADING)
    blocks_start = text.find(API_PLAN_BLOCKS_HEADING)
    index_start = text.find(API_PLAN_CONSUMPTION_INDEX_HEADING)
    if not (page_start < shared_start < blocks_start < index_start):
        result.error(f"frontend {service} 页面 API Plan v3 固定章节顺序错误")
        return False
    page_sections = _api_plan_sections(text[page_start:shared_start])
    valid = bool(page_sections)
    if not page_sections:
        result.error(f"frontend {service} 页面 API Plan v3 至少需要一个路由页面")
        return False

    page_tasks: set[str] = set()
    has_blocked = False
    for page_name, page_section in page_sections:
        if not re.search(r"^- 路由：`[^`]+`\s*$", page_section, re.MULTILINE):
            result.error(f"frontend {service} 页面 API Plan v3 页面 {page_name} 缺少路由；共享组件不得作为页面章节")
            valid = False
        table_match = re.search(
            r"^(\| TASK \| REQ \| 用户动作/场景 \| 页面消费点 \| 所需能力与消费字段 \| 匹配接口与证据 \| 缺口分类 \| Owner \| decision \| API Exec 验收 \|)\r?\n(\|[^\r\n]+\|)$",
            page_section,
            re.MULTILINE,
        )
        if table_match is None or table_match.group(1).count("|") != table_match.group(2).count("|"):
            result.error(f"frontend {service} 页面 API Plan v3 页面 {page_name} 的 TASK 表头与分隔行列数必须一致")
            valid = False
        rows = _api_plan_page_demand_rows(page_section)
        task_rows = [row for row in rows if len(row) >= 10 and re.fullmatch(r"TASK-FE-\d+", row[0])]
        if not task_rows:
            result.error(f"frontend {service} 页面 API Plan v3 页面 {page_name} 缺少 TASK-FE 页面动作行")
            valid = False
            continue
        for row in task_rows:
            task, evidence, gap_category, owner, decision = row[0], row[5], row[6], row[7], row[8]
            if task in page_tasks:
                result.error(f"frontend {service} 页面 API Plan v3 TASK 不能跨页面重复: {task}")
                valid = False
            page_tasks.add(task)
            if decision not in {"contract", "implementation", "blocked"}:
                result.error(f"frontend {service} {task} 接口匹配 decision 必须是 contract、implementation 或 blocked")
                valid = False
                continue
            if gap_category not in API_PLAN_GAP_CATEGORIES:
                result.error(f"frontend {service} {task} 缺口分类非法: {gap_category}")
                valid = False
            if not owner or owner == "-":
                result.error(f"frontend {service} {task} 缺少接口或补齐 Owner")
                valid = False
            if decision in {"contract", "implementation"} and gap_category != "none":
                result.error(f"frontend {service} {task} {decision} 的缺口分类必须为 none")
                valid = False
            if decision == "contract" and ("API-" not in evidence or "正式接口文档未命中：" in evidence):
                result.error(f"frontend {service} {task} 标记 contract 但未给出正式接口文档匹配")
                valid = False
            if decision == "implementation":
                if "正式接口文档未命中：" not in evidence or not re.search(r"(?:\.java|\.ts|\.tsx|src/)", evidence):
                    result.error(f"frontend {service} {task} implementation 必须保留文档未命中和现有实现路径证据")
                    valid = False
            if decision == "blocked":
                has_blocked = True
                if gap_category == "none":
                    result.error(f"frontend {service} {task} blocked 必须使用具体缺口分类")
                    valid = False
                contract_gap = re.search(r"正式接口文档(?:未命中|字段缺口)：", evidence) is not None
                implementation_gap = re.search(r"现有实现(?:未命中|字段缺口)：", evidence) is not None
                if not contract_gap or not implementation_gap:
                    result.error(f"frontend {service} {task} blocked 必须同时记录接口文档与现有实现的未命中或字段缺口证据")
                    valid = False

    shared = text[shared_start:blocks_start]
    blocks = text[blocks_start:index_start]
    for label, section in (("共享能力索引", shared), ("阻塞项", blocks)):
        referenced = set(re.findall(r"\bTASK-FE-\d+\b", section))
        unknown = referenced - page_tasks
        if unknown:
            result.error(f"frontend {service} 页面 API Plan v3 {label} 引用了未在页面章节创建的 TASK: {', '.join(sorted(unknown))}")
            valid = False
    blocked_tasks = {
        row[0]
        for _, page_section in page_sections
        for row in _api_plan_page_demand_rows(page_section)
        if len(row) >= 10 and re.fullmatch(r"TASK-FE-\d+", row[0]) and row[8] == "blocked"
    }
    block_references = set(re.findall(r"\bTASK-FE-\d+\b", blocks))
    if blocked_tasks != block_references:
        result.error(
            f"frontend {service} 页面 API Plan v3 阻塞项必须覆盖且仅覆盖 blocked TASK："
            f"blocked {', '.join(sorted(blocked_tasks)) or '无'}；阻塞项 {', '.join(sorted(block_references)) or '无'}"
        )
        valid = False
    if has_blocked and re.search(r"^- 状态：`?ready`?\s*$", text, re.MULTILINE):
        result.error(f"frontend {service} 存在 blocked 页面接口需求时 API Plan 状态不能为 ready")
        valid = False
    return valid


def _plan_value(section: str, label: str) -> str:
    match = re.search(
        rf"^[ \t]*-[ \t]*{re.escape(label)}[：:][ \t]*`?([^`\r\n]+)`?[ \t]*$",
        section,
        re.MULTILINE | re.IGNORECASE,
    )
    return match.group(1).strip() if match else ""


def _http_endpoint_identity(heading: str) -> str | None:
    """从 Plan 标题提取规范化的“METHOD /path”身份。"""
    match = re.search(
        r"\b(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+`?([^`\s]+)",
        heading,
        re.IGNORECASE,
    )
    return f"{match.group(1).upper()} {match.group(2)}" if match else None


def _plan_has_non_http_reason(section: str) -> bool:
    value = _plan_value(section, "接口设计")
    match = re.match(r"^n/a[：:，,]\s*(.+)$", value, re.IGNORECASE)
    return match is not None and _meaningful_plan_value(match.group(1))


def _meaningful_plan_value(value: str) -> bool:
    absence_values = {
        "none",
        "n/a",
        "na",
        "-",
        "无",
        "不适用",
    }
    blocking_values = {
        "pending",
        "待确认",
        "待定",
        "未定",
        "未确认",
        "未知",
        "tbd",
        "todo",
        "unknown",
    }
    normalized = value.strip().lower()
    if not normalized or normalized in absence_values or normalized in blocking_values:
        return False
    if re.match(
        r"^(?:pending|待确认|待定|未定|未确认|未知|tbd|todo|unknown)"
        r"(?:$|[\s：:，,（(\-—])",
        normalized,
    ):
        return False
    absence_prefix = re.match(
        r"^(?:none|n/a|na|无|不适用)"
        r"(?:[：:，,]\s*|\s*[-—]\s*|\s+|[（(]\s*)(.+?)[）)]?$",
        normalized,
    )
    if absence_prefix is None:
        return True
    reason = absence_prefix.group(1).strip()
    return (
        reason not in absence_values
        and reason not in blocking_values
        and re.match(
            r"^(?:pending|待确认|待定|未定|未确认|未知|tbd|todo|unknown)"
            r"(?:$|[\s：:，,（(\-—])",
            reason,
        )
        is None
    )


def _single_plan_match(
    pattern: re.Pattern[str],
    text: str,
    label: str,
    service: str,
    result: Result,
) -> re.Match[str] | None:
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        result.error(f"backend {service} Plan 必须且只能声明一个{label}")
        return None
    return matches[0]


def _plan_identity_valid(
    text: str,
    *,
    version: str,
    service: str,
    expected_mode: str,
    result: Result,
) -> bool:
    valid = True
    fields: tuple[tuple[re.Pattern[str], str, str | None], ...] = (
        (BACKEND_PLAN_VERSION_LINE, "需求版本", version),
        (BACKEND_PLAN_SERVICE_LINE, "后端服务", service),
        (BACKEND_PLAN_DEVELOPER_LINE, "开发者", None),
        (BACKEND_PLAN_RISK_LINE, "风险等级", None),
        (BACKEND_PLAN_MODE_LINE, "模块形态", expected_mode),
        (BACKEND_PLAN_STATUS_LINE, "状态", "ready"),
        (BACKEND_PLAN_CONFIRM_LINE, "用户确认", "confirmed"),
        (BACKEND_PLAN_CONFIRMER_LINE, "确认人", None),
        (BACKEND_PLAN_CONFIRM_DATE_LINE, "确认日期", None),
    )
    values: dict[str, str] = {}
    for pattern, label, expected in fields:
        match = _single_plan_match(pattern, text, label, service, result)
        if match is None:
            valid = False
            continue
        value = match.group(1).strip()
        values[label] = value
        if expected is not None and value.lower() != expected.lower():
            result.error(f"backend {service} Plan {label} 必须为 {expected}")
            valid = False
    for label in ("开发者", "确认人"):
        identity_value = values.get(label, "").strip().lower()
        if label in values and (
            not _meaningful_plan_value(identity_value)
            or re.match(
                r"^(?:none|n/a|na|无|不适用)(?:$|[\s：:，,（(\-—])",
                identity_value,
            )
        ):
            result.error(f"backend {service} Plan 必须记录真实{label}")
            valid = False
    if "确认日期" in values:
        try:
            date.fromisoformat(values["确认日期"])
        except ValueError:
            result.error(f"backend {service} Plan 确认日期不是有效日期")
            valid = False
    return valid


def _markdown_section(text: str, heading: str) -> str:
    match = re.search(
        rf"^{re.escape(heading)}\s*$",
        text,
        re.MULTILINE,
    )
    if match is None:
        return ""
    level = len(heading.split(maxsplit=1)[0])
    following = text[match.end():]
    next_heading = re.search(rf"^#{{1,{level}}}\s+", following, re.MULTILINE)
    return following[:next_heading.start()] if next_heading else following


def _markdown_table_rows(
    text: str,
    section_heading: str,
    expected_headers: tuple[str, ...],
) -> list[list[str]] | None:
    section = _markdown_section(text, section_heading)
    if not section:
        return None
    lines = section.splitlines()
    normalized_headers = tuple(header.lower() for header in expected_headers)
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        cells = tuple(cell.strip() for cell in stripped.strip("|").split("|"))
        if tuple(cell.lower() for cell in cells) != normalized_headers:
            continue
        if index + 1 >= len(lines):
            return None
        separator_cells = [
            cell.strip()
            for cell in lines[index + 1].strip().strip("|").split("|")
        ]
        if (
            len(separator_cells) != len(expected_headers)
            or any(re.fullmatch(r":?-{3,}:?", cell) is None for cell in separator_cells)
        ):
            return None
        rows: list[list[str]] = []
        for row_line in lines[index + 2:]:
            row = row_line.strip()
            if not row:
                if rows:
                    break
                continue
            if not row.startswith("|") or not row.endswith("|"):
                break
            row_cells = [cell.strip() for cell in row.strip("|").split("|")]
            if len(row_cells) != len(expected_headers):
                return None
            rows.append(row_cells)
        return rows
    return None


def _plan_row_has_content(cells: list[str]) -> bool:
    if not cells or any(not cell or PLACEHOLDER.search(cell) for cell in cells):
        return False
    return any(_meaningful_plan_value(cell.strip("` ")) for cell in cells[1:])


def _plan_table_has_content(
    text: str,
    section_heading: str,
    headers: tuple[str, ...],
    service: str,
    label: str,
    result: Result,
) -> bool:
    rows = _markdown_table_rows(text, section_heading, headers)
    if not rows or any(not _plan_row_has_content(row) for row in rows):
        result.error(
            f"backend {service} {label} {section_heading} 表缺少已填写的真实数据行"
        )
        return False
    return True


def _plan_named_values_have_content(
    section: str,
    labels: tuple[str, ...],
    *,
    allow_non_substantive: tuple[str, ...] = (),
) -> bool:
    for label in labels:
        matches = re.findall(
            rf"^[ \t]*-[ \t]*{re.escape(label)}[：:][ \t]*(.*?)[ \t]*$",
            section,
            re.MULTILINE,
        )
        if len(matches) != 1:
            return False
        value = matches[0].strip().strip("` ")
        if (
            not value
            or PLACEHOLDER.search(value)
            or (
                label not in allow_non_substantive
                and not _meaningful_plan_value(value)
            )
        ):
            return False
    return True


def _plan_detail_structure_valid(text: str, service: str, label: str, result: Result) -> bool:
    required_markers = (
        "## 1. 需求理解",
        "- 核心目标：",
        "- 用户角色：",
        "- 本次范围：",
        "- 非目标：",
        "- 全局验收：",
        "- UI/API 外部依赖：",
        "## 2. 现状调研",
        "### 2.1 历史需求与实现",
        "### 2.2 代码、调用链与数据流",
        "### 2.3 数据对象与性能证据（按需）",
        "### 2.4 现有接口与调用方",
        "### 2.5 待确认事项",
        "## 3. 技术方案",
        "### 3.1 核心流程与异常路径",
        "### 3.2 模块职责与方案取舍",
        "### 3.3 数据影响",
        "### 3.4 缓存、消息、定时、幂等与外部依赖",
        "## 4. 接口设计",
        "## 5. TASK 与验收",
        "## 6. 风险与发布",
        "## 7. Plan Gate",
    )
    missing = [marker for marker in required_markers if marker not in text]
    if missing:
        result.error(f"backend {service} {label} 缺少 Plan 详细结构: {', '.join(missing)}")
        return False

    valid = True
    if not _plan_named_values_have_content(
        _markdown_section(text, "## 1. 需求理解"),
        ("核心目标", "用户角色", "本次范围", "非目标", "全局验收", "UI/API 外部依赖"),
    ):
        result.error(f"backend {service} {label} 需求理解必须填写目标、角色、范围、非目标、验收和依赖")
        valid = False

    table_specs = (
        (
            "### 2.1 历史需求与实现",
            ("历史来源", "Revision/产物", "可复用设计", "已知问题与当前适用性"),
        ),
        (
            "### 2.2 代码、调用链与数据流",
            ("REQ", "层/调用方", "真实位置", "当前职责与调用关系", "本次影响/回归范围"),
        ),
        (
            "### 2.3 数据对象与性能证据（按需）",
            ("表/数据源", "数据量或 n/a：无性能/数据变更", "索引或 n/a", "相关字段", "只读证据与结论"),
        ),
        (
            "### 2.4 现有接口与调用方",
            ("方法与真实路径", "所在模块", "调用方", "兼容/影响半径", "处理结论"),
        ),
        (
            "### 3.2 模块职责与方案取舍",
            ("主题", "候选方案", "采用方案", "真实约束与理由", "影响范围"),
        ),
        (
            "### 3.3 数据影响",
            ("变更", "表/字段/索引", "原因", "数据量、锁与性能风险", "关联 TASK 与外部设计要求"),
        ),
        (
            "## 6. 风险与发布",
            ("风险", "概率/影响", "预防与人审", "监控/验证", "发布与回滚"),
        ),
    )
    for section_heading, headers in table_specs:
        valid = _plan_table_has_content(
            text,
            section_heading,
            headers,
            service,
            label,
            result,
        ) and valid

    flow_section = _markdown_section(text, "### 3.1 核心流程与异常路径")
    if not _plan_named_values_have_content(
        flow_section,
        ("主路径", "参数或权限失败", "外部依赖失败", "重复请求/并发", "数据一致性与回滚"),
    ):
        result.error(f"backend {service} {label} 必须填写主流程与四类异常/一致性路径")
        valid = False

    dependency_section = _markdown_section(
        text,
        "### 3.4 缓存、消息、定时、幂等与外部依赖",
    )
    dependency_lines = [
        line.strip().lstrip("-").strip()
        for line in dependency_section.splitlines()
        if line.strip()
    ]
    if (
        not dependency_lines
        or any(PLACEHOLDER.search(line) for line in dependency_lines)
        or not any(_meaningful_plan_value(line.strip("` ")) for line in dependency_lines)
    ):
        result.error(f"backend {service} {label} 必须填写缓存、消息、幂等与外部依赖结论")
        valid = False

    endpoint_matches = list(BACKEND_PLAN_ENDPOINT_HEADING.finditer(text))
    confirmed_decisions = _plan_confirmed_decision_ids(text)
    for endpoint_match in endpoint_matches:
        following = text[endpoint_match.start():]
        body_start = endpoint_match.end() - endpoint_match.start()
        next_heading = re.search(
            r"^#{2,3}\s+",
            following[body_start:],
            re.MULTILINE,
        )
        endpoint_section = (
            following[:body_start + next_heading.start()]
            if next_heading
            else following
        )
        endpoint_name = endpoint_match.group(0).removeprefix("###").strip()
        if not _plan_named_values_have_content(
            endpoint_section,
            ("关联 REQ", "来源引用", "角色/权限", "副作用"),
            allow_non_substantive=("副作用",),
        ):
            result.error(f"backend {service} {label} 接口 {endpoint_name} 缺少 REQ、来源、权限或副作用语义")
            valid = False
        source_match = re.search(
            r"^[ \t]*-[ \t]*来源引用[：:][ \t]*(.+?)[ \t]*$",
            endpoint_section,
            re.MULTILINE,
        )
        source_refs = source_match.group(1) if source_match else ""
        if not re.search(r"\bPRD:\S+|\bREQ-\d{3}\b", source_refs, re.IGNORECASE):
            result.error(f"backend {service} {label} 接口 {endpoint_name} 来源引用必须包含 PRD 或 REQ 定位")
            valid = False
        decision_refs = {item.upper() for item in re.findall(r"\bDEC-\d{3}\b", source_refs, re.IGNORECASE)}
        method = endpoint_match.group(0).split(maxsplit=2)[1].upper()
        if method in {"POST", "PUT", "PATCH", "DELETE"} and not decision_refs:
            result.error(f"backend {service} {label} 写接口 {endpoint_name} 必须引用已确认 DEC-ID")
            valid = False
        unknown_decisions = decision_refs - confirmed_decisions
        if unknown_decisions:
            result.error(
                f"backend {service} {label} 接口 {endpoint_name} 引用未确认或不存在的决策: "
                f"{', '.join(sorted(unknown_decisions))}"
            )
            valid = False
        endpoint_tables = (
            ("#### 请求字段", ("字段", "位置", "必填", "业务语义", "业务约束")),
            ("#### 响应字段", ("字段", "业务语义", "空值约定")),
            ("#### 错误场景", ("场景", "业务错误语义", "期望行为")),
        )
        for section_heading, headers in endpoint_tables:
            valid = _plan_table_has_content(
                endpoint_section,
                section_heading,
                headers,
                service,
                f"{label} 接口 {endpoint_name}",
                result,
            ) and valid
    if not endpoint_matches:
        interface_section = _markdown_section(text, "## 4. 接口设计")
        non_http_match = re.search(
            r"^[ \t]*-[ \t]*接口设计[：:][ \t]*`?n/a[：:，,][ \t]*([^`\r\n]+)`?[ \t]*$",
            interface_section,
            re.MULTILINE | re.IGNORECASE,
        )
        reason = non_http_match.group(1).strip() if non_http_match else ""
        if not _meaningful_plan_value(reason) or PLACEHOLDER.search(reason):
            result.error(
                f"backend {service} {label} 无 HTTP 接口时必须记录“接口设计：n/a：具体理由”"
            )
            valid = False
    return valid


def _plan_declares_no_change(value: str) -> bool:
    normalized = value.strip().strip("` ").lower()
    return bool(
        re.match(r"^(?:n/a|na|none|无|不适用)(?:$|[：:，,])", normalized)
        or any(
            marker in normalized
            for marker in ("不涉及数据", "不涉及结构", "无数据变更", "无迁移", "无脚本")
        )
    )


def _plan_has_explicit_no_change_reason(value: str) -> bool:
    normalized = value.strip().strip("` ")
    match = re.match(
        r"^(?:n/a|na|none|无|不适用|无变更)[：:，,]\s*(.+)$",
        normalized,
        re.IGNORECASE,
    )
    return match is not None and _meaningful_plan_value(match.group(1))


def _plan_overview_structure_valid(
    text: str,
    service: str,
    task_requirements: Mapping[str, str],
    task_modules: Mapping[str, str],
    module_risks: Mapping[str, str],
    task_metadata: Mapping[str, Mapping[str, str]],
    task_dependencies: Mapping[str, set[str]],
    dependency_qualifiers: Mapping[str, Mapping[str, str | None]],
    result: Result,
) -> bool:
    """校验多模块 Plan 的极简索引，业务详情只允许留在模块 Plan。"""
    del task_metadata, dependency_qualifiers
    valid = True
    req_headers = ("REQ", "适用性", "业务目标或不适用依据", "Plan", "TASK", "验收映射")
    index_headers = ("编号", "Plan", "功能与边界", "依赖", "Owner", "风险", "状态")
    for heading, headers in (
        ("## 1. REQ 与模块索引", req_headers),
        ("## 2. 文档拆分索引", index_headers),
    ):
        valid = _plan_table_has_content(text, heading, headers, service, "Plan 总览", result) and valid

    expected_by_requirement: dict[str, tuple[set[str], set[str]]] = {}
    for task, requirement in task_requirements.items():
        expected_by_requirement.setdefault(requirement, (set(), set()))
        expected_by_requirement[requirement][0].add(task_modules[task])
        expected_by_requirement[requirement][1].add(task)
    for row in _markdown_table_rows(text, "## 1. REQ 与模块索引", req_headers) or []:
        requirement = row[0].strip().upper()
        plans = set(BACKEND_PLAN_MODULE_REFERENCE.findall(row[3]))
        tasks = {item.upper() for item in re.findall(r"TASK-BE-\d{3}", row[4])}
        applicability = row[1].strip().lower()
        if applicability == "applicable" and (plans, tasks) != expected_by_requirement.get(requirement, (set(), set())):
            result.error(f"backend {service} Plan 总览 {requirement} 的 Plan/TASK 映射必须与模块详情完全一致")
            valid = False
        if applicability == "n/a" and (plans or tasks):
            result.error(f"backend {service} Plan 总览 {requirement} n/a 不得映射模块或 TASK")
            valid = False

    expected_dependencies: dict[str, set[str]] = {module[:7]: set() for module in task_modules.values()}
    expected_edges: set[tuple[str, str]] = set()
    for task, dependencies in task_dependencies.items():
        source = task_modules[task][:7]
        for dependency in dependencies:
            target = task_modules.get(dependency, "")[:7]
            if target and target != source:
                expected_dependencies[source].add(target)
                expected_edges.add((target, source))
    indexed: list[str] = []
    for row in _markdown_table_rows(text, "## 2. 文档拆分索引", index_headers) or []:
        refs = BACKEND_PLAN_MODULE_REFERENCE.findall(row[1])
        if len(refs) != 1:
            result.error(f"backend {service} Plan 总览拆分索引每行必须引用一个 plan-NN 文件")
            valid = False
            continue
        module = refs[0][:7].lower()
        indexed.append(module)
        dependencies = {item.lower() for item in re.findall(r"\bplan-\d{2}\b", row[3], re.IGNORECASE)}
        if dependencies != expected_dependencies.get(module, set()):
            result.error(f"backend {service} Plan 总览 {module} 的索引依赖必须与模块 TASK 一致")
            valid = False
        if row[5].strip().lower() != module_risks.get(module, "") or row[6].strip().lower() != "ready":
            result.error(f"backend {service} Plan 总览 {module} 的风险或状态必须与模块详情一致且为 ready")
            valid = False
    if len(indexed) != len(set(indexed)) or set(indexed) != set(expected_dependencies):
        result.error(f"backend {service} Plan 总览拆分索引必须唯一且覆盖全部模块")
        valid = False

    dependency_section = _markdown_section(text, "## 3. 跨 Plan TASK 依赖")
    edges = {
        (plans[0].lower(), plans[1].lower())
        for line in dependency_section.splitlines()
        if re.search(r"(?:-->|→)", line)
        for plans in [re.findall(r"\bplan-\d{2}\b", line, re.IGNORECASE)]
        if len(plans) == 2
    }
    if edges != expected_edges:
        result.error(f"backend {service} Plan 总览跨 Plan TASK 依赖必须与模块详情完全一致")
        valid = False
    if not expected_edges and not _plan_has_explicit_no_change_reason("n/a：" + dependency_section.strip()):
        result.error(f"backend {service} Plan 总览无跨 Plan 依赖时必须记录可并行依据")
        valid = False
    return valid


_PLAN_BUSINESS_DECISION_HEADERS = (
    "DEC-ID",
    "来源定位",
    "待决问题",
    "选项",
    "影响",
    "Owner",
    "状态",
    "阻塞对象",
)

_PLAN_TECHNICAL_DECISION_HEADERS = (
    "TDEC-ID",
    "来源定位",
    "待决问题",
    "候选与推荐方案",
    "影响",
    "Owner",
    "状态",
    "阻塞对象",
)


def _plan_decision_sections(text: str) -> list[tuple[str, str, str, tuple[str, ...]]]:
    specs = (
        ("#### 2.5.1 业务待确认事项", "业务", "DEC", _PLAN_BUSINESS_DECISION_HEADERS),
        ("#### 2.5.2 技术待确认事项", "技术", "TDEC", _PLAN_TECHNICAL_DECISION_HEADERS),
        ("### 9.1 业务待确认事项", "业务", "DEC", _PLAN_BUSINESS_DECISION_HEADERS),
        ("### 9.2 技术待确认事项", "技术", "TDEC", _PLAN_TECHNICAL_DECISION_HEADERS),
    )
    matched = [
        (heading, category, prefix, headers)
        for heading, category, prefix, headers in specs
        if _markdown_section(text, heading)
    ]
    return matched


def _plan_confirmed_decision_ids(text: str) -> set[str]:
    confirmed: set[str] = set()
    sections = _plan_decision_sections(text)
    for heading, category, _, headers in sections:
        if category != "业务":
            continue
        rows = _markdown_table_rows(text, heading, headers) or []
        confirmed.update(
            row[0].strip().upper()
            for row in rows
            if len(row) == len(headers) and row[6].strip().lower() == "confirmed"
        )
    return confirmed


def _plan_technical_decision_statuses(text: str) -> dict[str, str]:
    statuses: dict[str, str] = {}
    sections = _plan_decision_sections(text)
    for heading, category, _, headers in sections:
        if category != "技术":
            continue
        for row in _markdown_table_rows(text, heading, headers) or []:
            if len(row) == len(headers):
                statuses[row[0].strip().upper()] = row[6].strip().lower()
    return statuses


def _plan_no_decision_declared(section: str, category: str) -> bool:
    if not any(line.strip().startswith("-") for line in section.splitlines()):
        return False
    if category == "业务":
        return "无待决业务语义" in section and "PRD:" in section
    return "无待确认技术事项" in section and not PLACEHOLDER.search(section)


def _plan_decision_rows_closed(
    rows: list[list[str]],
    *,
    service: str,
    category: str,
    prefix: str,
    headers: tuple[str, ...],
    result: Result,
) -> bool:
    if not rows:
        result.error(f"backend {service} Plan {category}待确认事项必须至少登记一项决策")
        return False
    valid = True
    identifiers: list[str] = []
    source_pattern = (
        r"(?:PRD|输入源缺失)[：:]\s*\S+|\bDEC-\d{3}\b"
        if category == "业务"
        else r"(?:PRD|代码|DB|配置|运行环境|外部系统)[：:]\s*\S+"
    )
    for row in rows:
        if any(not cell or PLACEHOLDER.search(cell) for cell in row):
            result.error(f"backend {service} Plan {category}决策表存在未填写字段")
            valid = False
            continue
        identifier = row[0].strip().upper()
        identifiers.append(identifier)
        if re.fullmatch(rf"{prefix}-\d{{3}}", identifier) is None:
            result.error(f"backend {service} Plan {category}决策 ID 非法: {row[0]}")
            valid = False
        if not re.search(source_pattern, row[1], re.IGNORECASE):
            result.error(f"backend {service} Plan {category}决策 {row[0]} 缺少有效来源定位")
            valid = False
        if category == "技术" and "推荐" not in row[3]:
            result.error(f"backend {service} Plan 技术决策 {row[0]} 必须写明候选方案与推荐方案")
            valid = False
        if any(cell.strip().lower() in {"none", "n/a", "na", "无", "不适用"} for cell in row[1:]):
            result.error(f"backend {service} Plan {category}决策 {row[0]} 不得使用 none/n-a 伪造关闭结论")
            valid = False
        status = row[6].strip().lower()
        if status not in {"pending", "blocked", "confirmed"}:
            result.error(f"backend {service} Plan {category}决策 {row[0]} 状态必须为 pending/blocked/confirmed")
            valid = False
        elif status != "confirmed":
            result.error(f"backend {service} Plan 仍有未确认{category}决策: {row[0]}")
            valid = False
    if len(identifiers) != len(set(identifiers)):
        result.error(f"backend {service} Plan {category}决策表存在重复 ID")
        valid = False
    return valid


def _plan_pending_items_closed(text: str, service: str, result: Result) -> bool:
    sections = _plan_decision_sections(text)
    if not sections:
        result.error(f"backend {service} Plan 缺少待确认事项章节")
        return False
    valid = True
    categories = {category for _, category, _, _ in sections}
    if categories != {"业务", "技术"}:
        result.error(f"backend {service} Plan 必须同时包含业务待确认事项与技术待确认事项")
        valid = False
    for heading, category, prefix, headers in sections:
        section = _markdown_section(text, heading)
        rows = _markdown_table_rows(text, heading, headers)
        if rows is None:
            if _plan_no_decision_declared(section, category):
                continue
            result.error(
                f"backend {service} Plan {category}待确认事项必须使用 {prefix}-ID 决策表，"
                f"或声明无待确认{category}事项的具体依据"
            )
            valid = False
            continue
        valid = _plan_decision_rows_closed(
            rows,
            service=service,
            category=category,
            prefix=prefix,
            headers=headers,
            result=result,
        ) and valid
    return valid


def _plan_gate_complete(
    text: str,
    service: str,
    expected_items: tuple[str, ...],
    label: str,
    result: Result,
) -> bool:
    gate_match = re.search(
        r"^##\s+\d+\.\s+Plan Gate\s*$([\s\S]*)",
        text,
        re.MULTILINE | re.IGNORECASE,
    )
    if gate_match is None:
        result.error(f"backend {service} {label} 缺少 Plan Gate")
        return False
    gate_text = gate_match.group(1)
    items = re.findall(
        r"^\s*-\s*\[([^\]])\]\s*(.+?)\s*$",
        gate_text,
        re.MULTILINE,
    )
    normalized_items = tuple(" ".join(value.split()) for _, value in items)
    if (
        len(items) != len(expected_items)
        or any(state.lower() != "x" for state, _ in items)
        or normalized_items != expected_items
    ):
        result.error(f"backend {service} {label} Plan Gate 必须按模板逐项全部勾选")
        return False
    return True


def _parse_task_dependencies(value: str) -> list[tuple[str | None, str]] | None:
    normalized = value.strip().strip("` ").strip()
    if normalized.lower() == "none":
        return []
    if not normalized:
        return None
    parts = re.split(r"\s*(?:,|，|、)\s*", normalized)
    if not parts or any(not part for part in parts):
        return None
    parsed: list[tuple[str | None, str]] = []
    for part in parts:
        match = re.fullmatch(
            r"(?:(plan-\d{2})\s*:\s*)?(TASK-BE-\d{3})",
            part,
            re.IGNORECASE,
        )
        if match is None:
            return None
        qualifier = match.group(1).lower() if match.group(1) else None
        parsed.append((qualifier, match.group(2).upper()))
    if len({task for _, task in parsed}) != len(parsed):
        return None
    return parsed


def _parse_technical_selections(value: str) -> list[tuple[str | None, str]] | None:
    normalized = value.strip().strip("` ")
    if normalized.lower() == "none":
        return []
    if not normalized:
        return None
    parts = re.split(r"\s*(?:,|，|、)\s*", normalized)
    parsed: list[tuple[str | None, str]] = []
    for part in parts:
        match = re.fullmatch(r"(?:(plan-\d{2})\s*:\s*)?(TDEC-\d{3})", part, re.IGNORECASE)
        if match is None:
            return None
        parsed.append((match.group(1).lower() if match.group(1) else None, match.group(2).upper()))
    return parsed if len(set(parsed)) == len(parsed) else None


def _task_dependencies_acyclic(dependencies: Mapping[str, set[str]]) -> bool:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(task: str) -> bool:
        if task in visiting:
            return False
        if task in visited:
            return True
        visiting.add(task)
        for dependency in dependencies.get(task, set()):
            if not visit(dependency):
                return False
        visiting.remove(task)
        visited.add(task)
        return True

    return all(visit(task) for task in dependencies)


def _backend_plan_valid(
    service_root: Path,
    requirements: set[str],
    version: str,
    result: Result,
) -> tuple[bool, set[str], set[str]]:
    plan_root = service_root / "1-plan"
    main_path = plan_root / "plan-overview.md"
    if not _artifact_ready(main_path, result):
        result.error(f"backend {service_root.name} 缺少有效且已关闭待确认项的 Plan: 1-plan/plan-overview.md")
        return False, set(), set()

    valid = True
    main_text = read_text(main_path, result)
    mode_matches = list(BACKEND_PLAN_MODE_LINE.finditer(main_text))
    plan_mode = mode_matches[0].group(1).lower() if len(mode_matches) == 1 else ""
    valid = _plan_identity_valid(
        main_text,
        version=version,
        service=service_root.name,
        expected_mode=plan_mode or "single",
        result=result,
    ) and valid
    module_paths = sorted(plan_root.glob("plan-[0-9][0-9]-*.md"))
    index_match = re.search(
        r"^##\s+2\.\s+文档拆分索引\s*$([\s\S]*?)^##\s+3\.",
        main_text,
        re.MULTILINE,
    )
    referenced_modules = (
        set(BACKEND_PLAN_MODULE_REFERENCE.findall(index_match.group(1)))
        if index_match
        else set()
    )
    actual_modules = {path.name for path in module_paths}
    module_numbers = [
        match.group(1)
        for path in module_paths
        if (match := re.match(r"plan-(\d{2})-", path.name, re.IGNORECASE))
    ]
    if len(module_numbers) != len(set(module_numbers)):
        result.error(f"backend {service_root.name} 多模块 Plan 编号不得复用")
        valid = False
    if plan_mode == "single" and module_paths:
        result.error(f"backend {service_root.name} 单模块 Plan 不得遗留 plan-NN 文件")
        valid = False
    if plan_mode == "single" and _plan_value(main_text, "模块编号").lower() != "single":
        result.error(f"backend {service_root.name} 单模块 Plan 的模块编号必须为 single")
        valid = False
    if plan_mode == "multi":
        if len(module_paths) < 2:
            result.error(f"backend {service_root.name} 多模块 Plan 至少需要两个 plan-NN 文件")
            valid = False
        if referenced_modules != actual_modules:
            result.error(f"backend {service_root.name} Plan 总览索引必须与 plan-NN 文件完全一致")
            valid = False

    module_documents: list[tuple[Path, str]] = []
    module_risks: dict[str, str] = {}
    for module_path in module_paths:
        if not _artifact_ready(module_path, result):
            result.error(f"backend {service_root.name} 存在无效模块 Plan: {module_path.name}")
            valid = False
            continue
        module_text = read_text(module_path, result)
        valid = _plan_identity_valid(
            module_text,
            version=version,
            service=service_root.name,
            expected_mode="multi",
            result=result,
        ) and valid
        expected_module = module_path.name[:7]
        risk_match = BACKEND_PLAN_RISK_LINE.search(module_text)
        if risk_match is not None:
            module_risks[expected_module] = risk_match.group(1).lower()
        module_number = _plan_value(module_text, "模块编号").lower()
        if module_number != expected_module:
            result.error(
                f"backend {service_root.name} 模块 Plan 编号必须与文件一致: "
                f"{module_path.name} -> {expected_module}"
            )
            valid = False
        valid = _plan_detail_structure_valid(
            module_text,
            service_root.name,
            module_path.name,
            result,
        ) and valid
        valid = _plan_pending_items_closed(module_text, service_root.name, result) and valid
        valid = _plan_gate_complete(
            module_text,
            service_root.name,
            BACKEND_SINGLE_PLAN_GATE_ITEMS,
            module_path.name,
            result,
        ) and valid
        module_documents.append((module_path, module_text))

    overview_mappings: dict[str, tuple[set[str], set[str]]] = {}
    if plan_mode == "multi":
        overview_rows = BACKEND_PLAN_OVERVIEW_REQ_ROW.findall(main_text)
        coverage_rows = [
            (identifier, raw_applicability, rationale)
            for identifier, raw_applicability, rationale, _, _ in overview_rows
        ]
        for identifier, raw_applicability, _, plan_cell, task_cell in overview_rows:
            requirement = identifier.upper()
            referenced_plans = set(BACKEND_PLAN_MODULE_REFERENCE.findall(plan_cell))
            referenced_tasks = {
                item.upper() for item in re.findall(r"TASK-BE-\d{3}", task_cell)
            }
            overview_mappings[requirement] = (referenced_plans, referenced_tasks)
            if raw_applicability.lower() == "applicable" and (
                not referenced_plans or not referenced_tasks
            ):
                result.error(
                    f"backend {service_root.name} Plan 总览 {requirement} "
                    "必须映射 plan-NN 与 TASK-BE"
                )
                valid = False
            if raw_applicability.lower() == "n/a" and (
                referenced_plans or referenced_tasks
            ):
                result.error(
                    f"backend {service_root.name} Plan 总览 {requirement} n/a 不得映射模块或 TASK"
                )
                valid = False
    else:
        coverage_rows = BACKEND_PLAN_REQ_ROW.findall(main_text)
    coverage_ids = [identifier.upper() for identifier, _, _ in coverage_rows]
    if len(coverage_ids) != len(set(coverage_ids)):
        result.error(f"backend {service_root.name} Plan REQ 覆盖表存在重复 ID")
        valid = False
    if set(coverage_ids) != requirements:
        result.error(f"backend {service_root.name} Plan REQ 覆盖必须与 PRD 完全一致")
        valid = False
    applicability: dict[str, str] = {}
    for identifier, raw_applicability, rationale in coverage_rows:
        requirement = identifier.upper()
        applicability[requirement] = raw_applicability.lower()
        if not _meaningful_plan_value(rationale):
            result.error(f"backend {service_root.name} Plan {requirement} 缺少业务目标或不适用依据")
            valid = False
    applicable_requirements = {
        identifier for identifier, value in applicability.items() if value == "applicable"
    }
    if not applicable_requirements:
        result.error(f"backend {service_root.name} Plan 至少需要一个 applicable REQ")
        valid = False

    detail_documents = (
        [(main_path, main_text)]
        if plan_mode == "single"
        else module_documents
    )
    task_sections: list[tuple[str, str, str]] = []
    for document_path, document_text in detail_documents:
        matches = list(BACKEND_PLAN_TASK_HEADING.finditer(document_text))
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(document_text)
            task_sections.append(
                (
                    match.group(1).upper(),
                    document_text[match.start():end],
                    document_path.name,
                )
            )
    task_ids = [task for task, _, _ in task_sections]
    if not task_ids:
        result.error(f"backend {service_root.name} Plan 缺少 TASK-BE")
        valid = False
    if len(task_ids) != len(set(task_ids)):
        result.error(f"backend {service_root.name} Plan TASK-BE ID 必须唯一")
        valid = False

    # HTTP 接口、定时任务和显式非 HTTP 例外均以一个 TASK 为最小可追溯单位。
    for document_path, document_text in detail_documents:
        document_endpoints = {
            endpoint
            for match in BACKEND_PLAN_ENDPOINT_HEADING.finditer(document_text)
            if (endpoint := _http_endpoint_identity(match.group(0))) is not None
        }
        document_tasks = [
            (task, section)
            for task, section, module_name in task_sections
            if module_name == document_path.name
        ]
        task_endpoints: dict[str, str | None] = {}
        scheduled_identifiers: dict[str, str] = {}
        for task, section in document_tasks:
            title = section.splitlines()[0] if section.splitlines() else ""
            identity = _http_endpoint_identity(title)
            task_kind = _plan_value(section, "任务类型").lower()
            task_endpoints[task] = identity if task_kind == "http" else None
            if task_kind == "http":
                declared = _http_endpoint_identity(_plan_value(section, "接口设计"))
                if identity is None or declared != identity:
                    result.error(f"backend {service_root.name} Plan {task} HTTP TASK 标题和接口设计必须使用同一 METHOD /path")
                    valid = False
            elif task_kind == "scheduled":
                identifier = _plan_value(section, "定时任务")
                if identity is not None or not _meaningful_plan_value(identifier) or _plan_declares_no_change(identifier):
                    result.error(f"backend {service_root.name} Plan {task} scheduled TASK 必须填写唯一的定时任务标识且不得声明 HTTP 接口")
                    valid = False
                elif identifier in scheduled_identifiers:
                    result.error(f"backend {service_root.name} Plan 定时任务 {identifier} 必须且只能映射一个 TASK-BE")
                    valid = False
                else:
                    scheduled_identifiers[identifier] = task
                if not _plan_has_non_http_reason(section):
                    result.error(f"backend {service_root.name} Plan {task} scheduled TASK 必须记录“接口设计：n/a：具体理由”")
                    valid = False
            elif task_kind == "exception":
                if identity is not None or not _plan_has_non_http_reason(section):
                    result.error(f"backend {service_root.name} Plan {task} exception TASK 必须无 HTTP 接口并记录“接口设计：n/a：具体理由”")
                    valid = False
        for endpoint in document_endpoints:
            mapped = [task for task, identity in task_endpoints.items() if identity == endpoint]
            if len(mapped) != 1:
                result.error(
                    f"backend {service_root.name} Plan 接口 {endpoint} 必须且只能映射一个 TASK-BE，当前: {', '.join(mapped) or 'none'}"
                )
                valid = False
        for task, identity in task_endpoints.items():
            if identity is not None and identity not in document_endpoints:
                result.error(
                    f"backend {service_root.name} Plan {task} 声明的接口 {identity} 未出现在接口设计章节"
                )
                valid = False

    task_requirements: dict[str, str] = {}
    task_modules: dict[str, str] = {}
    task_metadata: dict[str, dict[str, str]] = {}
    dependency_qualifiers: dict[str, dict[str, str | None]] = {}
    dependencies: dict[str, set[str]] = {}
    technical_decision_statuses = {
        path.name: _plan_technical_decision_statuses(document_text)
        for path, document_text in detail_documents
    }
    for task, section, module_name in task_sections:
        task_modules[task] = module_name
        title_match = re.match(
            rf"^###\s+{re.escape(task)}\s*:\s*(.+?)[ \t]*$",
            section,
            re.IGNORECASE | re.MULTILINE,
        )
        task_title = title_match.group(1).strip() if title_match else ""
        if not _meaningful_plan_value(task_title) or PLACEHOLDER.search(task_title):
            result.error(f"backend {service_root.name} Plan {task} 必须填写真实目标")
            valid = False
        requirement_match = re.search(
            r"^[ \t]*-[ \t]*REQ[：:][ \t]*`?(REQ-\d{3})`?[ \t]*$",
            section,
            re.MULTILINE | re.IGNORECASE,
        )
        requirement = requirement_match.group(1).upper() if requirement_match else ""
        task_requirements[task] = requirement
        if not requirement or applicability.get(requirement) != "applicable":
            result.error(f"backend {service_root.name} Plan {task} 必须绑定 applicable REQ")
            valid = False

        required_values = {
            "任务类型": _plan_value(section, "任务类型"),
            "接口设计": _plan_value(section, "接口设计"),
            "定时任务": _plan_value(section, "定时任务"),
            "业务逻辑": _plan_value(section, "业务逻辑"),
            "技术选型": _plan_value(section, "技术选型"),
            "可实现状态": _plan_value(section, "可实现状态"),
            "修改位置": _plan_value(section, "修改位置"),
            "risk": _plan_value(section, "risk"),
            "estimate": _plan_value(section, "estimate"),
            "radius": _plan_value(section, "radius"),
            "human-review": _plan_value(section, "human-review"),
            "data-change": _plan_value(section, "data-change"),
            "依赖": _plan_value(section, "依赖"),
        }
        missing = [label for label, value in required_values.items() if not value]
        if missing:
            result.error(
                f"backend {service_root.name} Plan {task} 缺少 TASK 字段: {', '.join(missing)}"
            )
            valid = False
        task_kind = required_values["任务类型"].lower()
        if task_kind not in {"http", "scheduled", "exception"}:
            result.error(f"backend {service_root.name} Plan {task} 任务类型必须为 http/scheduled/exception")
            valid = False
        if not _meaningful_plan_value(required_values["业务逻辑"]) or PLACEHOLDER.search(required_values["业务逻辑"]):
            result.error(f"backend {service_root.name} Plan {task} 必须补充真实业务逻辑")
            valid = False
        technical_selections = _parse_technical_selections(required_values["技术选型"])
        if technical_selections is None:
            result.error(f"backend {service_root.name} Plan {task} 技术选型只能填写 none、TDEC-ID 或 plan-NN:TDEC-ID")
            valid = False
            technical_selections = []
        unresolved_technical: list[str] = []
        unconfirmed_technical: list[str] = []
        for qualifier, identifier in technical_selections:
            target_prefix = qualifier or module_name[:7].lower()
            target_document = next(
                (name for name in technical_decision_statuses if name[:7].lower() == target_prefix),
                "",
            )
            status = technical_decision_statuses.get(target_document, {}).get(identifier)
            display = f"{qualifier}:{identifier}" if qualifier else identifier
            if not status:
                unresolved_technical.append(display)
            elif status != "confirmed":
                unconfirmed_technical.append(display)
        if unresolved_technical:
            result.error(
                f"backend {service_root.name} Plan {task} 引用了不存在的技术选型: {', '.join(unresolved_technical)}"
            )
            valid = False
        implementability = required_values["可实现状态"].lower()
        if implementability not in {"ready", "blocked"}:
            result.error(f"backend {service_root.name} Plan {task} 可实现状态必须为 ready/blocked")
            valid = False
        if unconfirmed_technical and implementability != "blocked":
            result.error(f"backend {service_root.name} Plan {task} 关联未确认 TDEC 时可实现状态必须为 blocked")
            valid = False
        risk = required_values["risk"].lower()
        human_review = required_values["human-review"].lower()
        if risk not in {"low", "medium", "high"}:
            result.error(f"backend {service_root.name} Plan {task} risk 必须为 low/medium/high")
            valid = False
        estimate_match = re.fullmatch(
            r"(\d+(?:\.\d+)?)h",
            required_values["estimate"],
            re.IGNORECASE,
        )
        if estimate_match is None or float(estimate_match.group(1)) <= 0:
            result.error(f"backend {service_root.name} Plan {task} estimate 必须为正数小时，如 6h")
            valid = False
        if not _meaningful_plan_value(required_values["radius"]):
            result.error(f"backend {service_root.name} Plan {task} radius 必须记录真实影响范围")
            valid = False
        if human_review not in {"required", "optional"}:
            result.error(f"backend {service_root.name} Plan {task} human-review 值非法")
            valid = False
        data_change = required_values["data-change"].lower()
        if data_change not in {"yes", "no"}:
            result.error(f"backend {service_root.name} Plan {task} data-change 必须为 yes/no")
            valid = False
        if risk == "high" and human_review != "required":
            result.error(f"backend {service_root.name} Plan {task} high risk 必须 human-review required")
            valid = False
        task_metadata[task] = {
            "目标": task_title,
            "risk": required_values["risk"].lower(),
            "estimate": required_values["estimate"].lower(),
            "radius": required_values["radius"],
            "human-review": required_values["human-review"].lower(),
            "data-change": required_values["data-change"].lower(),
        }

        dependency_value = required_values["依赖"]
        parsed_dependencies = _parse_task_dependencies(dependency_value)
        if parsed_dependencies is None:
            result.error(
                f"backend {service_root.name} Plan {task} 依赖格式非法；"
                "仅允许 none、TASK-BE-NNN 或 plan-NN:TASK-BE-NNN，多个值用逗号分隔"
            )
            valid = False
            parsed_dependencies = []
        dependency_ids = {identifier for _, identifier in parsed_dependencies}
        dependency_qualifiers[task] = {
            identifier: qualifier
            for qualifier, identifier in parsed_dependencies
        }
        if task in dependency_ids:
            result.error(f"backend {service_root.name} Plan {task} 不得依赖自身")
            valid = False
        dependencies[task] = dependency_ids

    for requirement in applicable_requirements:
        if requirement not in set(task_requirements.values()):
            result.error(f"backend {service_root.name} Plan {requirement} 缺少 TASK-BE")
            valid = False
    known_tasks = set(task_ids)
    for task, task_dependencies in dependencies.items():
        missing_dependencies = task_dependencies - known_tasks
        if missing_dependencies:
            result.error(
                f"backend {service_root.name} Plan {task} 依赖不存在: "
                f"{', '.join(sorted(missing_dependencies))}"
            )
            valid = False
        for dependency in task_dependencies & known_tasks:
            source_module = task_modules.get(task, "")
            target_module = task_modules.get(dependency, "")
            expected_prefix = target_module[:7]
            qualifier = dependency_qualifiers.get(task, {}).get(dependency)
            if qualifier is not None and qualifier != expected_prefix:
                result.error(
                    f"backend {service_root.name} Plan {task} 依赖 {dependency} "
                    f"的模块限定必须为 {expected_prefix}"
                )
                valid = False
            elif source_module != target_module and qualifier != expected_prefix:
                result.error(
                    f"backend {service_root.name} Plan {task} 跨模块依赖必须写为 "
                    f"{expected_prefix}:{dependency}"
                )
                valid = False
    if not _task_dependencies_acyclic(dependencies):
        result.error(f"backend {service_root.name} Plan TASK 依赖不得成环")
        valid = False

    if plan_mode == "multi":
        tasks_by_requirement: dict[str, set[str]] = {}
        for task, requirement in task_requirements.items():
            tasks_by_requirement.setdefault(requirement, set()).add(task)
        for requirement in applicable_requirements:
            mapped_plans, mapped_tasks = overview_mappings.get(requirement, (set(), set()))
            expected_tasks = tasks_by_requirement.get(requirement, set())
            expected_plans = {
                task_modules[task]
                for task in expected_tasks
                if task in task_modules
            }
            if mapped_tasks != expected_tasks or mapped_plans != expected_plans:
                result.error(
                    f"backend {service_root.name} Plan 总览 {requirement} "
                    "的 Plan/TASK 映射必须与模块详情完全一致"
                )
                valid = False
        valid = _plan_overview_structure_valid(
            main_text,
            service_root.name,
            task_requirements,
            task_modules,
            module_risks,
            task_metadata,
            dependencies,
            dependency_qualifiers,
            result,
        ) and valid

    if plan_mode == "single":
        valid = _plan_detail_structure_valid(
            main_text,
            service_root.name,
            "Plan",
            result,
        ) and valid
        required_sections: tuple[str, ...] = ()
        required_gate_items = BACKEND_SINGLE_PLAN_GATE_ITEMS
    else:
        required_sections = (
            "## 1. REQ 与模块索引",
            "## 2. 文档拆分索引",
            "## 3. 跨 Plan TASK 依赖",
            "## 4. Plan Gate",
        )
        required_gate_items = BACKEND_MULTI_PLAN_GATE_ITEMS
    missing_sections = [heading for heading in required_sections if heading not in main_text]
    if missing_sections:
        result.error(
            f"backend {service_root.name} Plan 缺少章节: {', '.join(missing_sections)}"
        )
        valid = False
    if plan_mode == "single":
        valid = _plan_pending_items_closed(main_text, service_root.name, result) and valid
    valid = _plan_gate_complete(
        main_text,
        service_root.name,
        required_gate_items,
        "Plan",
        result,
    ) and valid
    return valid, applicable_requirements, known_tasks


def _backend_external_design_valid(
    service_root: Path,
    service: str,
    plan_tasks: set[str],
    result: Result,
) -> bool:
    path = service_root / "2-external-design" / "external-design.md"
    if not _artifact_ready(path, result):
        result.error(f"backend {service} 缺少有效外部设计产物: 2-external-design/external-design.md")
        return False
    text = read_text(path, result)
    section = _markdown_section(text, "## 外部设计项")
    if re.search(r"\bn/a[：:].+", section, re.IGNORECASE):
        return True
    rows = _markdown_table_rows(
        text,
        "## 外部设计项",
        ("ID", "类型", "关联 TASK", "来源与目标对象", "设计内容", "兼容性、风险与状态"),
    )
    if not rows:
        result.error(f"backend {service} 外部设计必须声明 n/a 理由或使用设计项表")
        return False
    valid = True
    identifiers: set[str] = set()
    for row in rows:
        if any(not cell or PLACEHOLDER.search(cell) for cell in row):
            result.error(f"backend {service} 外部设计项存在未填写字段")
            valid = False
            continue
        identifier = row[0].strip().upper()
        if not re.fullmatch(r"EXT-DES-\d{3}", identifier) or identifier in identifiers:
            result.error(f"backend {service} 外部设计 ID 必须唯一且符合 EXT-DES-NNN")
            valid = False
        identifiers.add(identifier)
        if row[1].strip().lower() not in {"sql", "nacos", "scheduled", "permission", "minio", "message", "client"}:
            result.error(f"backend {service} 外部设计类型非法: {row[1]}")
            valid = False
        task_ids = {item.upper() for item in re.findall(r"TASK-BE-\d{3}", row[2])}
        if not task_ids or not task_ids <= plan_tasks:
            result.error(f"backend {service} 外部设计必须关联已登记的 Plan TASK")
            valid = False
    return valid


def _review_passed(
    path: Path,
    result: Result,
    *,
    expected_revision: str = "",
    required_hashes: set[str] | None = None,
) -> bool:
    if not _artifact_ready(path, result):
        return False
    text = read_text(path, result)
    conclusion = re.search(r"结论[：:]\s*`?passed`?", text, re.IGNORECASE)
    open_high = re.search(
        r"^\|[^\n]*\|\s*P[01]\s*\|[^\n]*\|\s*open\s*\|\s*$",
        text,
        re.MULTILINE | re.IGNORECASE,
    )
    hashes = required_hashes or set()
    return (
        bool(conclusion)
        and open_high is None
        and (not expected_revision or expected_revision in text)
        and all(value in text for value in hashes)
    )


def _validate_service_git(
    identifier: str,
    raw: Mapping[str, Any],
    catalog: Mapping[str, Any],
    service_root: Path,
    version: str,
    result: Result,
) -> bool:
    expected_keys = {
        "type",
        "repository",
        "branch",
        "remote",
        "baseRevision",
        "finalRevision",
        "status",
    }
    _exact_keys(raw, expected_keys, f"execution.services.{identifier}", result)
    expected_branch = f"develop-{version}"
    repository = raw.get("repository")
    remote = raw.get("remote")
    final_revision = raw.get("finalRevision")
    status = raw.get("status")
    final_text = str(final_revision or "")
    final_valid = (
        REVISION_PATTERN.fullmatch(final_text) is not None
        if status == "completed"
        else final_text == "" or REVISION_PATTERN.fullmatch(final_text) is not None
    )
    valid = (
        raw.get("type") == catalog.get("type")
        and isinstance(repository, str)
        and _normalized_repository(repository) == _normalized_repository(str(catalog.get("repository", "")))
        and raw.get("branch") == expected_branch
        and isinstance(remote, str)
        and bool(remote)
        and REVISION_PATTERN.fullmatch(str(raw.get("baseRevision", ""))) is not None
        and final_valid
        and status in ALLOWED_EXECUTION_STATUSES - {"not-applicable"}
    )
    if not valid:
        result.error(f"execution.services.{identifier} 的类型、仓库、分支、revision 或状态无效")
        return False
    if status != "completed":
        return True
    current_branch = _git(service_root, ["branch", "--show-current"], result, f"读取 {identifier} 分支")
    head = _git(service_root, ["rev-parse", "HEAD"], result, f"读取 {identifier} HEAD")
    worktree = _git(service_root, ["status", "--porcelain"], result, f"读取 {identifier} 工作区")
    remote_revision = _git(
        service_root,
        ["rev-parse", f"{remote}/{expected_branch}"],
        result,
        f"读取 {identifier} 远端版本分支",
    )
    remote_url = _git(service_root, ["remote", "get-url", str(remote)], result, f"读取 {identifier} 远端")
    git_valid = (
        current_branch == expected_branch
        and head == final_revision
        and not worktree
        and remote_revision == final_revision
        and _normalized_repository(remote_url) == _normalized_repository(str(repository))
        and _git_is_ancestor(service_root, str(raw.get("baseRevision")), str(final_revision))
    )
    if not git_valid:
        result.error(f"{identifier} 的版本分支、最终提交、工作区或远端状态无效")
    return git_valid


def _validate_contracts(
    contracts: Any,
    service_roots: Mapping[str, Path],
    service_catalogs: Mapping[str, Mapping[str, Any]],
    execution_services: Mapping[str, Any],
    project_root: Path,
    config: HarnessConfig,
    result: Result,
) -> tuple[bool, dict[str, list[Mapping[str, Any]]]]:
    by_consumer: dict[str, list[Mapping[str, Any]]] = {}
    if not isinstance(contracts, list) or not contracts:
        result.error("execution.contracts 必须包含至少一个接口文档引用")
        return False, by_consumer
    valid = True
    identifiers: set[str] = set()
    for index, item in enumerate(contracts):
        location = f"execution.contracts[{index}]"
        if not isinstance(item, Mapping):
            result.error(f"{location} 必须是映射")
            valid = False
            continue
        expected = {
            "id",
            "ownerService",
            "consumers",
            "path",
            "baselineRevision",
            "baselineSha256",
            "status",
        }
        _exact_keys(item, expected, location, result)
        identifier = item.get("id")
        owner = item.get("ownerService")
        consumers = item.get("consumers")
        path = item.get("path")
        if not isinstance(identifier, str) or not re.fullmatch(r"CONTRACT-\d{3}", identifier) or identifier in identifiers:
            result.error(f"{location}.id 必须是唯一 CONTRACT-xxx")
            valid = False
        else:
            identifiers.add(identifier)
        if not isinstance(owner, str):
            result.error(f"{location}.ownerService 必须引用 backend 服务")
            valid = False
            continue
        if (
            not isinstance(consumers, list)
            or any(not isinstance(value, str) for value in consumers)
            or len(consumers) != len(set(consumers))
            or owner in consumers
        ):
            result.error(f"{location}.consumers 必须是无重复且不含 owner 的服务 ID 列表")
            valid = False
            consumers = []
        for consumer in consumers:
            if consumer not in service_roots:
                result.error(f"{location}.consumers 引用了 execution 外服务: {consumer}")
                valid = False
            by_consumer.setdefault(consumer, []).append(item)
        baseline_revision = str(item.get("baselineRevision", ""))
        baseline_hash = str(item.get("baselineSha256", ""))
        path_text = str(path or "")
        fields_valid = (
            REVISION_PATTERN.fullmatch(baseline_revision) is not None
            and HASH_PATTERN.fullmatch(baseline_hash) is not None
            and item.get("status") == "baseline"
        )
        if not fields_valid:
            result.error(f"{location} 必须记录有效 baselineRevision、baselineSha256 且 status 为 baseline")
            valid = False
            continue
        if owner in service_roots:
            service_root = service_roots[owner]
            owner_catalog = service_catalogs.get(owner, {})
            if owner_catalog.get("type") != "backend":
                result.error(f"{location}.ownerService 必须引用 backend 服务")
                valid = False
                continue
        else:
            owner_info = _development_service(project_root, config, owner, "backend", result)
            if owner_info is None:
                valid = False
                continue
            owner_catalog, service_root = owner_info
        allowed_paths = owner_catalog.get("contractPaths", [])
        normalized_contract = PurePosixPath(path_text.replace("\\", "/"))
        allowed = any(
            tuple(normalized_contract.parts[: len(PurePosixPath(str(prefix).replace("\\", "/")).parts)])
            == PurePosixPath(str(prefix).replace("\\", "/")).parts
            for prefix in allowed_paths
            if isinstance(prefix, str) and prefix
        )
        if not allowed:
            result.error(f"{location}.path 不在 owner 服务 contractPaths 内")
            valid = False
        document = _safe_service_path(service_root, path, f"{location}.path", result)
        baseline_actual = _git_blob_sha256(service_root, baseline_revision, path_text, result)
        if document is None or not document.is_file() or baseline_actual != baseline_hash:
            result.error(f"{location} 的契约文档或 baseline SHA256 无效")
            valid = False
    return valid, by_consumer


def _frontend_artifacts_valid(
    root: Path,
    services: list[str],
    ui_stages: str,
    skip_evidence: Any,
    paths: Mapping[str, Path],
    contracts_by_consumer: Mapping[str, list[Mapping[str, Any]]],
    requirements: set[str],
    service_revisions: Mapping[str, str],
    result: Result,
) -> bool:
    valid = True
    if ui_stages == "not-applicable":
        if not isinstance(skip_evidence, Mapping) or set(skip_evidence) != {"scopeReason"}:
            result.error("无页面改动必须仅提供 scopeReason")
            return False
        if not isinstance(skip_evidence["scopeReason"], str) or not skip_evidence["scopeReason"].strip():
            result.error("无页面改动必须提供范围依据")
            return False
    elif ui_stages != "required":
        result.error("execution.tracks.frontend.uiStages 只能为 required 或 not-applicable")
        valid = False

    for service in services:
        service_root = root / service
        if ui_stages == "required":
            ui_plan_root = service_root / "1-ui-plan"
            ui_exec_root = service_root / "2-ui-exec"
            ui_plan_overview = ui_plan_root / "plan-overview.md"
            if not _artifact_ready(ui_plan_overview, result):
                result.error(f"frontend {service} 缺少有效阶段产物: 1-ui-plan/plan-overview.md")
                valid = False
            ui_plans = sorted(ui_plan_root.glob("plan-[0-9][0-9].md")) if ui_plan_root.is_dir() else []
            if not ui_plans:
                result.error(f"frontend {service} UI Plan 至少需要一个模块文件: 1-ui-plan/plan-NN.md")
                valid = False
            expected_ui_exec_names = {f"exec-{path.name[5:7]}.md" for path in ui_plans}
            actual_ui_exec = sorted(ui_exec_root.glob("exec-[0-9][0-9].md")) if ui_exec_root.is_dir() else []
            actual_ui_exec_names = {path.name for path in actual_ui_exec}
            if actual_ui_exec_names != expected_ui_exec_names:
                result.error(
                    f"frontend {service} UI Exec 文件必须与 UI Plan 模块一一对应："
                    f"期望 {', '.join(sorted(expected_ui_exec_names)) or '无'}，"
                    f"实际 {', '.join(sorted(actual_ui_exec_names)) or '无'}"
                )
                valid = False
            for path in actual_ui_exec:
                if not _artifact_ready(path, result):
                    result.error(f"frontend {service} 缺少有效阶段产物: 2-ui-exec/{path.name}")
                    valid = False
        else:
            for relative in ("1-ui-plan", "2-ui-exec"):
                if (service_root / relative).exists():
                    result.error(f"frontend {service} 跳过 UI 阶段时禁止创建空产物: {relative}")
                    valid = False
        required = (
            "3-api-plan/plan.md",
            "4-api-exec/task.md",
            "4-api-exec/exec.md",
            "5-review/review.md",
            "6-test-feed/front-feed.md",
        )
        for relative in required:
            if not _artifact_ready(service_root / relative, result):
                result.error(f"frontend {service} 缺少有效阶段产物: {relative}")
                valid = False
        review = service_root / "5-review" / "review.md"
        contract_hashes = {
            str(item.get("baselineSha256", ""))
            for item in contracts_by_consumer.get(service, [])
            if item.get("baselineSha256")
        }
        if review.is_file() and not _review_passed(
            review,
            result,
            expected_revision=service_revisions.get(service, ""),
            required_hashes=contract_hashes,
        ):
            result.error(f"frontend {service} Review 未绑定 finalRevision/契约、未通过或存在开放 P0/P1")
            valid = False
        api_plan = service_root / "3-api-plan" / "plan.md"
        api_text = read_text(api_plan, result) if api_plan.is_file() else ""
        if api_text and not _validate_frontend_api_plan_page_demand_v3(api_text, service, result):
            valid = False
        consumer_contracts = contracts_by_consumer.get(service, [])
        if not consumer_contracts:
            result.error(f"frontend {service} 缺少后端接口文档归属")
            valid = False
        if consumer_contracts and "接口文档" not in api_text:
            result.error(f"frontend {service} api-plan 未引用结构化接口文档")
            valid = False
        feed = service_root / "6-test-feed" / "front-feed.md"
        feed_text = read_text(feed, result) if feed.is_file() else ""
        feed_requirements = set(REQ_REFERENCE.findall(feed_text))
        if feed_requirements != requirements:
            result.error(f"frontend {service} front-feed 的 REQ 覆盖必须与 PRD 一致")
            valid = False
        if service_revisions.get(service, "") not in feed_text or any(value not in feed_text for value in contract_hashes):
            result.error(f"frontend {service} front-feed 未绑定 finalRevision 或 接口契约")
            valid = False
    return valid


def _backend_exec_tasks_valid(
    text: str,
    service: str,
    result: Result,
    *,
    allow_empty: bool = False,
) -> tuple[bool, set[str]]:
    rows = _markdown_table_rows(
        text,
        "## TASK",
        ("TASK", "状态", "修改位置", "实现与测试", "偏差/审批/风险"),
    )
    if not rows:
        section = _markdown_section(text, "## TASK")
        if allow_empty and re.search(r"\bn/a[：:].+", section, re.IGNORECASE):
            return True, set()
        result.error(f"backend {service} Exec 必须使用 TASK 表记录执行结果")
        return False, set()
    valid = True
    task_ids: list[str] = []
    for row in rows:
        if any(not cell or PLACEHOLDER.search(cell) for cell in row):
            result.error(f"backend {service} Exec TASK 表存在未填写字段")
            valid = False
        identifier = row[0].strip().upper()
        if re.fullmatch(r"TASK-BE-\d{3}", identifier) is None:
            result.error(f"backend {service} Exec TASK ID 非法: {row[0]}")
            valid = False
            continue
        task_ids.append(identifier)
        if row[1].strip().lower() not in {"planned", "in-progress", "implement", "blocked", "done", "n/a"}:
            result.error(f"backend {service} Exec {identifier} 状态非法")
            valid = False
    if len(task_ids) != len(set(task_ids)):
        result.error(f"backend {service} Exec TASK 表存在重复 ID")
        valid = False
    return valid, set(task_ids)


def _backend_exec_external_changes_valid(
    text: str,
    exec_path: Path,
    service: str,
    result: Result,
) -> bool:
    section = _markdown_section(text, "## 外部执行记录")
    if not section:
        result.error(f"backend {service} {exec_path.name} 缺少外部执行记录章节")
        return False
    if re.search(r"\bn/a[：:].+", section, re.IGNORECASE):
        return True
    rows = _markdown_table_rows(
        text,
        "## 外部执行记录",
        ("类型", "状态", "文件", "外部设计与目标系统/环境", "执行、验证与回滚"),
    )
    if not rows:
        result.error(f"backend {service} {exec_path.name} 外部执行必须写 n/a 理由或使用结构化表")
        return False
    valid = True
    filenames = {
        "sql": "sql.md",
        "nacos": "nacos.md",
        "permission": "permission.md",
        "minio": "minio.md",
    }
    for row in rows:
        if any(not cell or PLACEHOLDER.search(cell) for cell in row):
            result.error(f"backend {service} {exec_path.name} 外部变更表存在未填写字段")
            valid = False
            continue
        change_type = row[0].strip().lower()
        if change_type not in filenames:
            result.error(f"backend {service} {exec_path.name} 外部变更类型非法: {row[0]}")
            valid = False
        if row[1].strip().lower() not in {"done", "blocked"}:
            result.error(f"backend {service} {exec_path.name} 外部变更状态必须为 done/blocked")
            valid = False
        relative = row[2].strip().strip("` ").replace("\\", "/")
        expected_filename = filenames.get(change_type)
        if relative != expected_filename:
            result.error(
                f"backend {service} {exec_path.name} {change_type} 变更文件必须为 "
                f"4-exec/{expected_filename}"
            )
            valid = False
            continue
        external_path = exec_path.parent / relative
        if not _artifact_ready(external_path, result):
            result.error(f"backend {service} {exec_path.name} 缺少有效外部变更文件: {relative}")
            valid = False
    return valid


def _backend_exec_overview_valid(
    text: str,
    expected_exec_names: set[str],
    service: str,
    result: Result,
) -> bool:
    rows = _markdown_table_rows(
        text,
        "## 模块索引",
        ("Exec", "Plan", "TDD", "TASK", "状态", "外部变更文件", "依赖/发布顺序"),
    )
    if not rows:
        result.error(f"backend {service} Exec 总览必须使用模块索引表")
        return False
    valid = True
    actual_names: list[str] = []
    for row in rows:
        if any(not cell or PLACEHOLDER.search(cell) for cell in row):
            result.error(f"backend {service} Exec 总览模块索引存在未填写字段")
            valid = False
            continue
        name = row[0].strip().strip("` ")
        if re.fullmatch(r"exec-\d{2}\.md", name, re.IGNORECASE) is None:
            result.error(f"backend {service} Exec 总览模块文件名非法: {row[0]}")
            valid = False
            continue
        actual_names.append(name.lower())
    if set(actual_names) != {name.lower() for name in expected_exec_names}:
        result.error(f"backend {service} Exec 总览必须与 Plan 模块一一对应")
        valid = False
    if len(actual_names) != len(set(actual_names)):
        result.error(f"backend {service} Exec 总览不得重复引用模块文件")
        valid = False
    return valid


def _backend_tdd_overview_valid(
    text: str,
    expected_tdd_names: set[str],
    service: str,
    result: Result,
) -> bool:
    rows = _markdown_table_rows(
        text,
        "## 模块矩阵",
        ("模块", "Plan", "TDD", "契约路径", "Baseline Revision", "Baseline SHA256", "状态", "当前结论 / 依赖"),
    )
    if not rows:
        result.error(f"backend {service} TDD 总览必须使用模块矩阵表")
        return False
    valid = True
    actual_names: list[str] = []
    for row in rows:
        if any(not cell or PLACEHOLDER.search(cell) for cell in row):
            result.error(f"backend {service} TDD 总览模块矩阵存在未填写字段")
            valid = False
            continue
        name = row[2].strip().strip("` ")
        if re.fullmatch(r"tdd-\d{2}\.md", name, re.IGNORECASE) is None:
            result.error(f"backend {service} TDD 总览模块文件名非法: {row[2]}")
            valid = False
            continue
        actual_names.append(name.lower())
    if set(actual_names) != {name.lower() for name in expected_tdd_names}:
        result.error(f"backend {service} TDD 总览必须与 Plan 模块一一对应")
        valid = False
    if len(actual_names) != len(set(actual_names)):
        result.error(f"backend {service} TDD 总览不得重复引用模块文件")
        valid = False
    return valid


def _backend_review_requirements_valid(
    text: str,
    service: str,
    result: Result,
) -> tuple[bool, set[str]]:
    rows = _markdown_table_rows(
        text,
        "## REQ 覆盖",
        ("REQ", "结论", "证据"),
    )
    if not rows:
        result.error(f"backend {service} Review 必须使用 REQ 覆盖表记录结论")
        return False, set()
    valid = True
    requirement_ids: list[str] = []
    for row in rows:
        identifier = row[0].strip().upper()
        if re.fullmatch(r"REQ-\d{3}", identifier) is None:
            result.error(f"backend {service} Review REQ ID 非法: {row[0]}")
            valid = False
            continue
        requirement_ids.append(identifier)
        if row[1].strip().lower() != "covered":
            result.error(f"backend {service} Review {identifier} 结论必须为 covered")
            valid = False
        evidence = row[2].strip().strip("` ")
        if not _meaningful_plan_value(evidence) or PLACEHOLDER.search(evidence):
            result.error(f"backend {service} Review {identifier} 缺少真实覆盖证据")
            valid = False
    if len(requirement_ids) != len(set(requirement_ids)):
        result.error(f"backend {service} Review REQ 覆盖表存在重复 ID")
        valid = False
    return valid, set(requirement_ids)


def _backend_external_configuration_checklist_valid(
    service_root: Path,
    service: str,
    result: Result,
) -> bool:
    """校验只包含未完成外部配置变更的 Review 后清单。"""
    path = service_root / "8-checklist" / "checklist.md"
    if not _artifact_ready(path, result):
        result.error(f"backend {service} 缺少有效外部配置清单: 8-checklist/checklist.md")
        return False

    text = read_text(path, result)
    rows = _markdown_table_rows(
        text,
        "## 待外部配置项",
        (
            "ID",
            "来源与关联 Exec/TASK",
            "类型",
            "外部系统/环境",
            "配置或变更内容",
            "执行/审批责任方",
            "状态",
            "外部变更记录",
        ),
    )
    if not rows:
        if "无待外部配置项" in text:
            return True
        result.error(f"backend {service} 外部配置清单必须使用待配置项表，或明确写无待外部配置项")
        return False

    valid = True
    identifiers: list[str] = []
    for row in rows:
        if any(not cell or PLACEHOLDER.search(cell) for cell in row):
            result.error(f"backend {service} 待外部配置项表存在未填写字段")
            valid = False
            continue
        identifier = row[0].strip().upper()
        identifiers.append(identifier)
        if re.fullmatch(r"EXT-\d{3}", identifier) is None:
            result.error(f"backend {service} 待外部配置项 ID 非法: {row[0]}")
            valid = False
        if row[2].strip().lower() not in {"sql", "nacos", "permission", "minio"}:
            result.error(f"backend {service} 待外部配置项类型必须为 sql/nacos/permission/minio")
            valid = False
        if not _meaningful_plan_value(row[5].strip().strip("` ")) or row[5].strip().lower() == "n/a":
            result.error(f"backend {service} 待外部配置项必须给出可识别的执行或审批责任方")
            valid = False
        if row[6].strip().lower() not in {"pending", "blocked"}:
            result.error(f"backend {service} 待外部配置项状态必须为 pending/blocked")
            valid = False
    if len(identifiers) != len(set(identifiers)):
        result.error(f"backend {service} 待外部配置项表存在重复 ID")
        valid = False
    return valid


def _backend_artifacts_valid(
    root: Path,
    services: list[str],
    contracts: list[Mapping[str, Any]],
    service_revisions: Mapping[str, str],
    requirements: set[str],
    version: str,
    result: Result,
) -> bool:
    valid = True
    for service in services:
        service_root = root / service
        plan_valid, applicable_requirements, plan_tasks = _backend_plan_valid(
            service_root,
            requirements,
            version,
            result,
        )
        valid = plan_valid and valid
        valid = _backend_external_design_valid(service_root, service, plan_tasks, result) and valid
        tdd_root = service_root / "3-tdd"
        module_plans = sorted((service_root / "1-plan").glob("plan-[0-9][0-9]-*.md"))
        expected_tdd = (
            [tdd_root / f"tdd-{path.name[5:7]}.md" for path in module_plans]
            if module_plans
            else [tdd_root / "tdd-01.md"]
        )
        actual_tdd = sorted(tdd_root.glob("tdd-[0-9][0-9].md")) if tdd_root.is_dir() else []
        expected_tdd_names = {path.name for path in expected_tdd}
        actual_tdd_names = {path.name for path in actual_tdd}
        if actual_tdd_names != expected_tdd_names:
            result.error(
                f"backend {service} TDD 文件必须与 Plan 模块一一对应："
                f"期望 {', '.join(sorted(expected_tdd_names))}，"
                f"实际 {', '.join(sorted(actual_tdd_names)) or '无'}"
            )
            valid = False
        for tdd_path in expected_tdd:
            if not _artifact_ready(tdd_path, result):
                result.error(
                    f"backend {service} 缺少有效模块 TDD 产物: "
                    f"3-tdd/{tdd_path.name}"
                )
                valid = False
        tdd_overview = tdd_root / "tdd-overview.md"
        if not _artifact_ready(tdd_overview, result):
            result.error(f"backend {service} 缺少有效 TDD 总览产物: 3-tdd/tdd-overview.md")
            valid = False
        elif not _backend_tdd_overview_valid(
            read_text(tdd_overview, result),
            expected_tdd_names,
            service,
            result,
        ):
            valid = False
        api_document = service_root / "6-interface-document" / "api-document.md"
        api_document_text = read_text(api_document, result) if _artifact_ready(api_document, result) else ""
        required = (
            "4-exec/exec-overview.md",
            "7-review/review-overview.md",
        )
        for relative in required:
            if not _artifact_ready(service_root / relative, result):
                result.error(f"backend {service} 缺少有效阶段产物: {relative}")
                valid = False
        exec_root = service_root / "4-exec"
        review_root = service_root / "7-review"
        expected_reviews = (
            {f"review-{path.name[5:7]}.md" for path in module_plans}
            if module_plans
            else {"review-01.md"}
        )
        actual_reviews = (
            {path.name for path in review_root.glob("review-[0-9][0-9].md")}
            if review_root.is_dir()
            else set()
        )
        if actual_reviews != expected_reviews:
            result.error(
                f"backend {service} Review 文件必须与 Plan 模块一一对应："
                f"期望 {', '.join(sorted(expected_reviews))}，"
                f"实际 {', '.join(sorted(actual_reviews)) or '无'}"
            )
            valid = False
        for review_name in expected_reviews:
            if not _artifact_ready(review_root / review_name, result):
                result.error(
                    f"backend {service} 缺少有效模块 Review 产物: "
                    f"7-review/{review_name}"
                )
                valid = False
        expected_exec_tasks: dict[str, set[str]] = {}
        if module_plans:
            for plan_path in module_plans:
                number = plan_path.name[5:7]
                expected_exec_tasks[f"exec-{number}.md"] = {
                    match.group(1).upper()
                    for match in BACKEND_PLAN_TASK_HEADING.finditer(read_text(plan_path, result))
                }
        else:
            plan_path = service_root / "1-plan" / "plan-overview.md"
            expected_exec_tasks["exec-01.md"] = {
                match.group(1).upper()
                for match in BACKEND_PLAN_TASK_HEADING.finditer(read_text(plan_path, result))
            }
        expected_exec_names = set(expected_exec_tasks)
        actual_exec = sorted(exec_root.glob("exec-[0-9][0-9].md")) if exec_root.is_dir() else []
        actual_exec_names = {path.name for path in actual_exec}
        unexpected_exec_names = actual_exec_names - expected_exec_names
        if unexpected_exec_names:
            result.error(
                f"backend {service} Exec 文件必须对应已登记 Plan 模块："
                f"非法 {', '.join(sorted(unexpected_exec_names))}"
            )
            valid = False
        all_exec_tasks: set[str] = set()
        for exec_path in actual_exec:
            exec_text = read_text(exec_path, result)
            exec_tasks_valid, exec_tasks = _backend_exec_tasks_valid(
                exec_text,
                service,
                result,
                allow_empty=not expected_exec_tasks.get(exec_path.name, set()),
            )
            external_valid = _backend_exec_external_changes_valid(exec_text, exec_path, service, result)
            valid = exec_tasks_valid and external_valid and valid
            if exec_tasks != expected_exec_tasks.get(exec_path.name, set()):
                result.error(
                    f"backend {service} {exec_path.name} TASK 集必须与对应 Plan 模块完全一致"
                )
                valid = False
            all_exec_tasks.update(exec_tasks)
        if all_exec_tasks != plan_tasks:
            result.error(f"backend {service} Exec TASK 集必须与 Plan 完全一致")
            valid = False
        overview_path = exec_root / "exec-overview.md"
        overview_text = read_text(overview_path, result) if overview_path.is_file() else ""
        valid = _backend_exec_overview_valid(
            overview_text,
            actual_exec_names,
            service,
            result,
        ) and valid
        local_test_root = service_root / "5-local-interface-test"
        local_test_overview = local_test_root / "localTest-overview.md"
        expected_local_test_names = {
            f"localTest-{name[5:7]}.md" for name in expected_exec_names
        }
        actual_local_tests = (
            sorted(local_test_root.glob("localTest-[0-9][0-9].md"))
            if local_test_root.is_dir()
            else []
        )
        actual_local_test_names = {path.name for path in actual_local_tests}
        if local_test_overview.is_file():
            if actual_local_test_names != expected_local_test_names:
                result.error(
                    f"backend {service} LocalTest 文件必须与 Plan 模块一一对应："
                    f"期望 {', '.join(sorted(expected_local_test_names))}，"
                    f"实际 {', '.join(sorted(actual_local_test_names)) or '无'}"
                )
                valid = False
            local_test_overview_text = read_text(local_test_overview, result)
            for path in actual_local_tests:
                if path.name not in local_test_overview_text:
                    result.error(
                        f"backend {service} LocalTest 总览未引用模块文件: "
                        f"5-local-interface-test/{path.name}"
                    )
                    valid = False
        else:
            result.error(
                f"backend {service} 缺少有效 LocalTest 产物："
                "5-local-interface-test/localTest-overview.md"
            )
            valid = False
        owned = [item for item in contracts if item.get("ownerService") == service]
        if not owned:
            result.error(f"backend {service} 缺少接口文档引用")
            valid = False
        tdd_text = "\n".join(
            read_text(path, result)
            for path in expected_tdd
            if path.is_file()
        )
        if not _validate_api_document_v5(api_document_text, service, result):
            valid = False
        for contract in owned:
            if str(contract.get("baselineSha256", "")) not in tdd_text:
                result.error(f"backend {service} TDD 未引用 baseline SHA256")
                valid = False
        review = service_root / "7-review" / "review-overview.md"
        review_text = read_text(review, result) if review.is_file() else ""
        review_requirements_valid, review_requirements = _backend_review_requirements_valid(
            review_text,
            service,
            result,
        )
        valid = review_requirements_valid and valid
        if review_requirements != applicable_requirements:
            result.error(f"backend {service} Review 的 REQ 覆盖必须与 Plan applicable REQ 一致")
            valid = False
        contract_hashes = {
            str(item.get("baselineSha256", ""))
            for item in owned
            if item.get("baselineSha256")
        }
        if review.is_file() and not _review_passed(
            review,
            result,
            expected_revision=service_revisions.get(service, ""),
            required_hashes=contract_hashes,
        ):
            result.error(f"backend {service} Review 未绑定 finalRevision/契约、未通过或存在开放 P0/P1")
            valid = False
        valid = _backend_external_configuration_checklist_valid(service_root, service, result) and valid
    return valid


def _validate_testhub_artifact(path: Path, result: Result) -> bool:
    if not _artifact_ready(path, result):
        return False
    errors, case_count = validate_testhub_markdown(path)
    for error in errors:
        result.error(f"{path}：{error}")
    if case_count == 0:
        result.error(f"{path} 不含可同步的正式用例")
    return not errors and case_count > 0
