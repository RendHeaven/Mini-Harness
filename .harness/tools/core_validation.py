from __future__ import annotations

import hashlib
import re
import subprocess
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Mapping

import yaml

from local_paths import resolve_service_path, project_config_path

CONFIG_SCHEMA_VERSION = 20
MANIFEST_SCHEMA_VERSION = 8
SERVICE_CATALOG_SCHEMA_VERSION = 1
EXECUTION_SCHEMA_VERSION = 7

VERSION_PATTERN = re.compile(r"^v\d+\.\d+(?:\.\d+)?$")
REQ_REFERENCE = re.compile(r"\bREQ-\d{3}\b")
MARKDOWN_REQ_HEADING = re.compile(
    r"^#{2,3}[ \t]+(REQ-\d{3})(?:[ \t]+[^\r\n]*)?[ \t]*\r?$",
    re.MULTILINE,
)
DEC_REFERENCE = re.compile(r"\bDEC-\d{3}\b")
ACCEPTED_DECISION_ROW = re.compile(
    r"^\|\s*(DEC-\d{3})\s*\|\s*accepted\s*\|", re.MULTILINE | re.IGNORECASE
)
HISTORY_STATUS = re.compile(
    r"历史知识回溯\s*[：:]\s*`?(greenfield-skipped|completed)`?",
    re.IGNORECASE,
)
HISTORY_SOURCE = re.compile(
    r"^[ \t]*(?:[-*+][ \t]+)?历史来源[：:][ \t]*`?([^`\r\n]*?)`?[ \t]*\r?$",
    re.MULTILINE,
)
REQ_SOURCE_LINE = re.compile(
    r"^[ \t]*(?:[-*+][ \t]+)?来源[：:][ \t]*`?([^`\r\n]*?)`?[ \t]*\r?$",
    re.MULTILINE,
)
PENDING_MARKER = re.compile(r"【待确认】")
PLACEHOLDER = re.compile(r"<[^<>\r\n]+>|\{version\}|v<主版本>|<版本号>")
HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
REVISION_PATTERN = re.compile(r"^[0-9a-f]{40}$")
BACKEND_PLAN_STATUS_LINE = re.compile(
    r"^[ \t]*-[ \t]*状态[：:][ \t]*`?(draft|ready|blocked)`?[ \t]*$",
    re.MULTILINE | re.IGNORECASE,
)
BACKEND_PLAN_VERSION_LINE = re.compile(
    r"^[ \t]*-[ \t]*需求版本[：:][ \t]*`?(v\d+\.\d+(?:\.\d+)?)`?[ \t]*$",
    re.MULTILINE | re.IGNORECASE,
)
BACKEND_PLAN_SERVICE_LINE = re.compile(
    r"^[ \t]*-[ \t]*后端服务[：:][ \t]*`?([^`\r\n]+)`?[ \t]*$",
    re.MULTILINE | re.IGNORECASE,
)
BACKEND_PLAN_DEVELOPER_LINE = re.compile(
    r"^[ \t]*-[ \t]*开发者[：:][ \t]*`?([^`\r\n]+)`?[ \t]*$",
    re.MULTILINE | re.IGNORECASE,
)
BACKEND_PLAN_RISK_LINE = re.compile(
    r"^[ \t]*-[ \t]*风险等级[：:][ \t]*`?(low|medium|high)`?[ \t]*$",
    re.MULTILINE | re.IGNORECASE,
)
BACKEND_PLAN_MODE_LINE = re.compile(
    r"^[ \t]*-[ \t]*模块形态[：:][ \t]*`?(single|multi)`?[ \t]*$",
    re.MULTILINE | re.IGNORECASE,
)
BACKEND_PLAN_CONFIRM_LINE = re.compile(
    r"^[ \t]*-[ \t]*用户确认[：:][ \t]*`?(pending|confirmed)`?[ \t]*$",
    re.MULTILINE | re.IGNORECASE,
)
BACKEND_PLAN_CONFIRMER_LINE = re.compile(
    r"^[ \t]*-[ \t]*确认人[：:][ \t]*`?([^`\r\n]+)`?[ \t]*$",
    re.MULTILINE | re.IGNORECASE,
)
BACKEND_PLAN_CONFIRM_DATE_LINE = re.compile(
    r"^[ \t]*-[ \t]*确认日期[：:][ \t]*`?(\d{4}-\d{2}-\d{2})`?[ \t]*$",
    re.MULTILINE | re.IGNORECASE,
)
BACKEND_PLAN_REQ_ROW = re.compile(
    r"^\|\s*(REQ-\d{3})\s*\|\s*(applicable|n/a)\s*\|\s*([^|]+?)\s*\|[^\r\n]+\|\s*$",
    re.MULTILINE | re.IGNORECASE,
)
BACKEND_PLAN_OVERVIEW_REQ_ROW = re.compile(
    r"^\|\s*(REQ-\d{3})\s*\|\s*(applicable|n/a)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|[^\r\n]+\|\s*$",
    re.MULTILINE | re.IGNORECASE,
)
BACKEND_PLAN_TASK_HEADING = re.compile(
    r"^###\s+(TASK-BE-\d{3})\s*:",
    re.MULTILINE | re.IGNORECASE,
)
BACKEND_PLAN_MODULE_REFERENCE = re.compile(r"`(plan-\d{2}-[^`\s/\\]+\.md)`", re.IGNORECASE)
BACKEND_PLAN_ENDPOINT_HEADING = re.compile(
    r"^###\s+(?:GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+.+$",
    re.MULTILINE | re.IGNORECASE,
)
BACKEND_SINGLE_PLAN_GATE_ITEMS = (
    "范围、非目标、角色、依赖和验收已确认",
    "全部 REQ 已声明适用性，受影响链路、历史、数据对象和调用方有证据；性能或数据变更时已补充数据量、索引和适用 EXPLAIN",
    "接口/定时任务、数据、事务、权限、异常和回滚路径明确",
    "TASK 的业务逻辑、技术选型、estimate、radius、风险和业务验收可执行",
    "业务与技术决策已确认；未确认项已分别登记 DEC-ID/TDEC-ID，且其阻塞对象未被伪造成可实现范围",
    "用户确认已记录；ready 时确认值为 confirmed",
)
BACKEND_MULTI_PLAN_GATE_ITEMS = (
    "全部 REQ 已映射到 plan-NN、TASK 或真实不适用依据",
    "模块索引和跨 Plan TASK 依赖与详情完全一致",
    "每个 plan-NN 已独立记录自身业务、技术选型、风险与验收",
    "用户确认已记录；ready 时确认值为 confirmed",
)
ALLOWED_MANIFEST_PHASES = {
    "discovery",
    "defining",
    "planning",
    "development",
    "testing",
    "completed",
}
ALLOWED_MANIFEST_STATES = {"active", "blocked", "cancelled"}
ALLOWED_EXECUTION_STATUSES = {"planned", "in-progress", "blocked", "completed", "not-applicable"}

CORE_HASH_DEFAULT_PATHS = (
    "README.md",
    "harness.yaml",
    "workflow",
    "skills",
    "rules",
    "template",
    "tools",
    "hooks",
    "../project-harness-template",
    "../AGENTS.md",
    "../docs/core-maintenance.md",
)

REQUIRED_ACTIVE_FILES = (
    "tools/sync_template_fragments.py",
    "template/_fragments/document-timestamps.md",
    "tools/role_gates.py",
    "tools/project_protocol.py",
    "tools/prd_revision.py",
    "skills/product/gate-confirm.md",
    "skills/ui/02-adjustment-document.md",
    "skills/ui/03-gate-confirm.md",
    "template/product/prd-change-template.md",
    "template/ui/adjustment-template.md",
    "../project-harness-template/Gate.yaml",
    "../project-harness-template/原型仓库/README.md",
    "skills/delivery/jenkins.md",
    "template/develop/delivery/jenkins-execution-template.md",
    "../project-harness-template/.harness/projectContext/jenkins.md",
    "../project-harness-template/.harness/tools/jenkins-mcp.md",
    "README.md",
    "harness.yaml",
    "workflow/product-design-workflow.md",
    "workflow/ui-design-workflow.md",
    "workflow/frontend-workflow.md",
    "workflow/frontend-mock-workflow.md",
    "workflow/backend-workflow.md",
    "workflow/testhub-workflow.md",
    "workflow/bugfix-workflow.md",
    "skills/product/discovery.md",
    "skills/product/prd-build.md",
    "skills/product/prd-review.md",
    "skills/product/dev-guide.md",
    "skills/product/export-word-prd.md",
    "skills/product/package-prototype.md",
    "tools/package_prototype.py",
    "tools/test_package_prototype.py",
    "skills/ui/01-static-prototype.md",
    "skills/frontend/01-ui-plan.md",
    "skills/frontend/02-ui-exec.md",
    "skills/frontend/03-api-plan.md",
    "skills/frontend/04-api-exec.md",
    "skills/frontend/05-review.md",
    "skills/frontend/06-test-feed.md",
    "skills/frontend-mock/01-assessment.md",
    "skills/frontend-mock/02-bootstrap.md",
    "skills/frontend-mock/03-data-source.md",
    "skills/frontend-mock/04-integration.md",
    "skills/frontend-mock/05-verification.md",
    "skills/backend/01-plan.md",
    "skills/backend/02-external-design.md",
    "skills/backend/03-tdd.md",
    "skills/backend/04-exec.md",
    "skills/backend/05-local-interface-test.md",
    "skills/backend/06-interface-document.md",
    "skills/backend/07-review.md",
    "skills/backend/08-checklist.md",
    "skills/testhub/00-senior-test-design.md",
    "skills/testhub/01-generate-markdown-cases.md",
    "skills/testhub/02-parse-and-sync.md",
    "skills/bugfix/00-record.md",
    "skills/bugfix/01-fix.md",
    "skills/bugfix/02-summary.md",
    "rules/id-and-status-standard.md",
    "rules/product-semantics-and-traceability.md",
    "rules/backend-delivery.md",
    "rules/api-document.md",
    "rules/review-gates.md",
    "rules/testhub-markdown-v1.md",
    "rules/ui-standard.md",
    "rules/frontend-engineering.md",
    "../project-harness-template/README.md",
    "../project-harness-template/AGENTS.md",
    "../project-harness-template/.gitignore",
    "../project-harness-template/.harness/harness.yaml",
    "../project-harness-template/.harness/projectContext/project-context.md",
    "../project-harness-template/.harness/projectContext/services.yaml",
    "../project-harness-template/.harness/projectContext/testhub.yaml",
    "../project-harness-template/.harness/projectContext/frontend-stack.md",
    "../project-harness-template/.harness/history/README.md",
    "../project-harness-template/.harness/hooks/usage_hook.py",
    "../project-harness-template/.harness/hooks/usage_hook.cmd",
    "../project-harness-template/.codex/hooks.json",
    "../project-harness-template/.harness/tools/README.md",
    "../project-harness-template/.harness/tools/db_tool.py",
    "../project-harness-template/.harness/tools/.env.example",
    "template/product/manifest-template.yaml",
    "template/product/discovery-template.md",
    "template/product/prd-template.md",
    "template/product/prd-word-template.docx",
    "template/product/prd-changelog-template.md",
    "template/product/dev-guide-template.md",
    "template/ui/ui-handoff-template.md",
    "template/develop/execution-template.yaml",
    "template/develop/frontend/ui-plan-template.md",
    "template/develop/frontend/api-plan-template.md",
    "template/develop/frontend/task-exec-template.md",
    "template/develop/frontend/review-template.md",
    "template/develop/frontend/test-feed-template.md",
    "template/develop/frontend-mock/mock-plan-template.md",
    "template/develop/frontend-mock/mock-source-matrix-template.md",
    "template/develop/frontend-mock/mock-verification-template.md",
    "template/develop/backend/plan-template.md",
    "template/develop/backend/plan-overview-template.md",
    "template/develop/backend/tdd-template.md",
    "template/develop/backend/tdd-overview-template.md",
    "template/develop/backend/exec-overview-template.md",
    "template/develop/backend/exec-module-template.md",
    "template/develop/backend/external-sql-template.md",
    "template/develop/backend/external-nacos-template.md",
    "template/develop/backend/external-permission-template.md",
    "template/develop/backend/external-minio-template.md",
    "template/develop/backend/interface-test-template.md",
    "template/develop/backend/interface-document-template.md",
    "template/develop/backend/review-template.md",
    "template/develop/backend/review-overview-template.md",
    "template/develop/testhub/cases-template.md",
    "template/develop/testhub/change-impact-analysis-template.md",
    "template/develop/testhub/test-design-template.md",
    "template/develop/testhub/coverage-matrix-template.md",
    "template/develop/testhub/testhub-config-template.yaml",
    "template/develop/testhub/sync-metadata-template.json",
    "template/develop/testhub/sync-report-template.md",
    "template/bugfix/bug-list-template.md",
    "hooks/README.md",
    "hooks/usage_hook.py",
    "hooks/test_usage_hook.py",
    "hooks/test_project_hook.py",
    "tools/validate_harness.py",
    "tools/core_validation.py",
    "tools/product_ui_validation.py",
    "tools/backend_validation.py",
    "tools/test_validate_harness.py",
    "tools/test_project_db_tool.py",
    "tools/validate_testhub_markdown.py",
    "tools/sync_testhub_markdown.py",
)

ACTIVE_WORKFLOWS = (
    "workflow/product-design-workflow.md",
    "workflow/ui-design-workflow.md",
    "workflow/frontend-workflow.md",
    "workflow/frontend-mock-workflow.md",
    "workflow/backend-workflow.md",
    "workflow/testhub-workflow.md",
    "workflow/bugfix-workflow.md",
)

class UniqueKeyLoader(yaml.SafeLoader):
    """拒绝会被 PyYAML 静默覆盖的重复映射键。"""


def _construct_unique_mapping(loader: UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key: {key}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


@dataclass
class Result:
    infos: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @classmethod
    def empty(cls) -> "Result":
        return cls()

    def info(self, message: str) -> None:
        self.infos.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def error(self, message: str) -> None:
        self.errors.append(message)

    def _hard_error(self, message: str) -> None:
        self.errors.append(message)


@dataclass(frozen=True)
class CycleIdentity:
    product_line: str | None
    version: str


def parse_cycle_identity(name: str) -> CycleIdentity | None:
    if VERSION_PATTERN.fullmatch(name):
        return CycleIdentity(None, name)
    match = re.fullmatch(r"([A-Za-z0-9\u3400-\u9fff][A-Za-z0-9_\u3400-\u9fff-]*)-(v\d+\.\d+(?:\.\d+)?)", name)
    if match is None:
        return None
    return CycleIdentity(match[1], match[2])


@dataclass(frozen=True)
class HarnessConfig:
    schema_version: int
    kind: str
    core_local_path: Path
    core_version: str
    core_revision: str
    core_content_hash: str
    project_id: str
    project_name: str
    demand_cycle_root: Path
    history_root: Path
    service_catalog: Path
    cycle_manifest: PurePosixPath
    product_root: PurePosixPath
    product_discovery: PurePosixPath
    product_prd: str
    product_prd_review: PurePosixPath
    product_dev_guide: PurePosixPath
    ui_root: PurePosixPath
    ui_handoff: PurePosixPath
    development_root: PurePosixPath
    development_execution: PurePosixPath
    development_frontend: PurePosixPath
    development_backend: PurePosixPath
    development_testhub: PurePosixPath
    prototype_root: Path = Path("原型仓库")
    gate_file: Path = Path("Gate.yaml")


@dataclass(frozen=True)
class DiscoveryFacts:
    valid: bool
    text: str
    sources: Mapping[str, str]
    accepted_decisions: frozenset[str]


@dataclass(frozen=True)
class MarkdownPrdFacts:
    valid: bool
    text: str
    requirements: frozenset[str]
    requirement_sources: Mapping[str, str] = field(default_factory=dict)
    accepted_decisions: frozenset[str] = frozenset()


@dataclass(frozen=True)
class GateOutcome:
    passed: bool
    failed_checks: tuple[str, ...]


def read_text(path: Path, result: Result) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        result.error(f"无法读取文本文件 {path}: {exc}")
        return ""


def load_yaml_mapping(path: Path, result: Result) -> dict[str, Any] | None:
    try:
        data = yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueKeyLoader)
    except (OSError, UnicodeError, yaml.YAMLError, TypeError, ValueError) as exc:
        result._hard_error(f"无法读取 YAML {path}: {exc}")
        return None
    if not isinstance(data, Mapping):
        result._hard_error(f"YAML 根节点必须是映射: {path}")
        return None
    return dict(data)


def file_sha256(path: Path, result: Result) -> str:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()
    except OSError as exc:
        result.error(f"无法计算 SHA256 {path}: {exc}")
        return ""


def _unsafe_relative_reference(value: str) -> bool:
    normalized = value.replace("\\", "/")
    posix = PurePosixPath(normalized)
    windows = PureWindowsPath(value)
    return (
        posix.is_absolute()
        or bool(windows.drive)
        or ".." in posix.parts
        or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", normalized) is not None
    )


def _relative_path(value: Any, location: str, result: Result) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        result._hard_error(f"{location} 必须是非空相对路径")
        return None
    normalized = PurePosixPath(value.replace("\\", "/"))
    if _unsafe_relative_reference(value):
        result._hard_error(f"{location} 必须位于项目仓库内: {value}")
        return None
    return Path(*normalized.parts)


def _safe_service_path(service_root: Path, raw: Any, location: str, result: Result) -> Path | None:
    relative = _relative_path(raw, location, result)
    if relative is None:
        return None
    candidate = (service_root / relative).resolve()
    try:
        candidate.relative_to(service_root.resolve())
    except ValueError:
        result._hard_error(f"{location} 越出服务仓库: {raw}")
        return None
    return candidate


def _exact_keys(data: Mapping[str, Any], expected: set[str], location: str, result: Result) -> None:
    actual = set(data)
    missing = expected - actual
    extra = actual - expected
    if any(not isinstance(key, str) for key in actual):
        result._hard_error(f"{location} 的字段名必须是字符串")
    if missing:
        result._hard_error(f"{location} 缺少字段: {', '.join(sorted(map(str, missing)))}")
    if extra:
        result._hard_error(f"{location} 包含未定义字段: {', '.join(sorted(map(str, extra)))}")


def parse_config(path: Path, result: Result) -> HarnessConfig | None:
    data = load_yaml_mapping(path, result)
    if data is None:
        return None
    if type(data.get("schemaVersion")) is not int or data["schemaVersion"] != CONFIG_SCHEMA_VERSION:
        result.error(f"harness.yaml.schemaVersion 必须为 {CONFIG_SCHEMA_VERSION}，不支持其他协议")
        return None
    from project_protocol import parse_project_config
    return parse_project_config(path, data, result)


def default_project_config() -> HarnessConfig:
    return HarnessConfig(
        20,
        "project",
        Path("../Mini-Harness"),
        "0.35.0",
        "0" * 40,
        "0" * 64,
        "project",
        "项目",
        Path(".harness/demandCycle"),
        Path(".harness/history"),
        Path(".harness/projectContext/services.yaml"),
        PurePosixPath("manifest.yaml"),
        PurePosixPath("product"),
        PurePosixPath("discovery.md"),
        "{version}-prd.md",
        PurePosixPath("prd-review.md"),
        PurePosixPath("dev-guide.md"),
        PurePosixPath("ui"),
        PurePosixPath("ui-handoff.md"),
        PurePosixPath("develop"),
        PurePosixPath("execution.yaml"),
        PurePosixPath("frontend"),
        PurePosixPath("backend"),
        PurePosixPath("testhub"),
    )


def excluded_hash_file(path: Path | PurePosixPath) -> bool:
    return "__pycache__" in path.parts or (
        "project-harness-template" in path.parts and path.name == ".env.local"
    )


def iter_hash_files(harness_root: Path, entries: list[str] | tuple[str, ...]) -> list[Path]:
    files: list[Path] = []
    for entry in entries:
        path = harness_root / entry
        if path.is_file():
            if not excluded_hash_file(path):
                files.append(path)
        elif path.is_dir():
            files.extend(candidate for candidate in path.rglob("*") if candidate.is_file() and not excluded_hash_file(candidate))
    return sorted(set(files), key=lambda item: item.relative_to(harness_root).as_posix())


def compute_content_hash(harness_root: Path, entries: list[str] | tuple[str, ...]) -> str:
    digest = hashlib.sha256()
    for path in iter_hash_files(harness_root, entries):
        relative = path.relative_to(harness_root).as_posix().encode("utf-8")
        content = path.read_bytes()
        # Git 在 Windows 的 text=auto/CRLF 工作区中会把文本规范化为 LF 后
        # 写入对象库。发布锁必须同时匹配当前工作区和指定 revision，因此对
        # 无 NUL 的文本采用相同规范化；二进制内容保持原字节。
        if b"\0" not in content:
            content = content.replace(b"\r\n", b"\n")
        digest.update(relative + b"\0" + content + b"\0")
    return digest.hexdigest()


def compute_git_content_hash(
    core_root: Path,
    revision: str,
    entries: list[str] | tuple[str, ...],
    result: Result,
) -> str:
    """从指定 revision 读取 Core 和项目模板，避免把脏工作区伪装成已发布 revision。"""
    folder = ".harness"
    if not _git_output(core_root, "ls-tree", revision, "--", folder) or _git_output(core_root, "ls-tree", revision, "--", "harness"):
        result.error("Core revision 必须仅使用 .harness 配置根")
        return ""
    prefixes = [
        entry[3:] if entry.startswith("../")
        else f"{folder}/{entry.strip('/')}"
        for entry in entries
    ]
    try:
        listed = subprocess.run(
            ["git", "-c", "core.quotepath=false", "ls-tree", "-r", "--name-only", revision, "--", *prefixes],
            cwd=core_root,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        ).stdout.splitlines()
    except (OSError, subprocess.CalledProcessError) as exc:
        result.error(f"无法读取 Core revision {revision} 的内容树: {exc}")
        return ""
    digest = hashlib.sha256()
    def relative_hash_path(repository_path: str) -> str:
        if repository_path.startswith(folder + "/"):
            return PurePosixPath(repository_path).relative_to(folder).as_posix()
        return "../" + repository_path

    for repository_path in sorted(set(listed), key=relative_hash_path):
        if excluded_hash_file(PurePosixPath(repository_path)):
            continue
        try:
            blob = subprocess.run(
                ["git", "show", f"{revision}:{repository_path}"],
                cwd=core_root,
                check=True,
                capture_output=True,
            ).stdout
        except (OSError, subprocess.CalledProcessError) as exc:
            result.error(f"无法读取 Core revision 文件 {repository_path}: {exc}")
            return ""
        relative = relative_hash_path(repository_path).encode("utf-8")
        digest.update(relative + b"\0" + blob + b"\0")
    return digest.hexdigest()


def validate_core_manifest(harness_root: Path, result: Result) -> str:
    data = load_yaml_mapping(harness_root / "harness.yaml", result)
    if data is None:
        return ""
    _exact_keys(data, {"schemaVersion", "kind", "core"}, "Core harness.yaml", result)
    if data.get("schemaVersion") != CONFIG_SCHEMA_VERSION:
        result.error(f"Core schemaVersion 必须为 {CONFIG_SCHEMA_VERSION}")
    if data.get("kind") != "core":
        result.error("Core kind 必须为 core")
    core = data.get("core")
    if not isinstance(core, Mapping):
        result.error("Core core 必须是映射")
        return ""
    _exact_keys(
        core,
        {"version", "manifestSchemaVersion", "serviceCatalogSchemaVersion", "executionSchemaVersion"},
        "Core core",
        result,
    )
    if core.get("manifestSchemaVersion") != MANIFEST_SCHEMA_VERSION:
        result.error(f"Core manifestSchemaVersion 必须为 {MANIFEST_SCHEMA_VERSION}")
    if core.get("serviceCatalogSchemaVersion") != SERVICE_CATALOG_SCHEMA_VERSION:
        result.error(f"Core serviceCatalogSchemaVersion 必须为 {SERVICE_CATALOG_SCHEMA_VERSION}")
    if core.get("executionSchemaVersion") != EXECUTION_SCHEMA_VERSION:
        result.error(f"Core executionSchemaVersion 必须为 {EXECUTION_SCHEMA_VERSION}")
    return str(core.get("version", ""))


def validate_version_lock(harness_root: Path, core_version: str, result: Result) -> None:
    path = harness_root / "version.lock"
    data = load_yaml_mapping(path, result)
    if data is None:
        return
    if data.get("version") != core_version:
        result.error("version.lock.version 与 Core version 不一致")
    if data.get("configSchemaVersion") != CONFIG_SCHEMA_VERSION:
        result.error(f"version.lock.configSchemaVersion 必须为 {CONFIG_SCHEMA_VERSION}")
    entries = data.get("contentHashPaths")
    if isinstance(entries, list) and all(isinstance(item, str) for item in entries):
        current = compute_content_hash(harness_root, entries)
        if current != data.get("contentHash"):
            result.error("当前 Core 内容与 version.lock 不一致；必须刷新发布锁")
    else:
        result.error("version.lock.contentHashPaths 必须是字符串列表")


def validate_skill(path: Path, result: Result) -> None:
    text = read_text(path, result)
    if not text.startswith("---\n") or text.count("---") < 2:
        result.error(f"Skill 缺少 YAML frontmatter: {path}")
    for heading in ("## Objective", "## Inputs", "## Workflow", "## Decision rules", "## Output contract"):
        if heading not in text:
            result.error(f"Skill 缺少章节 {heading}: {path}")


def validate_workflow_references(harness_root: Path, result: Result) -> None:
    reference = re.compile(r"`((?:skills|rules|template)/[^`]+)`")
    roots = (harness_root / "workflow", harness_root / "skills", harness_root / "rules")
    for path in sorted(
        candidate
        for root in roots
        for candidate in root.rglob("*.md")
    ):
        text = read_text(path, result)
        for raw in reference.findall(text):
            target = harness_root / raw
            if not target.exists():
                result.error(f"有效 Workflow 引用了不存在的路径 {raw}: {path}")


def validate_core(harness_root: Path, result: Result) -> HarnessConfig:
    for relative in REQUIRED_ACTIVE_FILES:
        if not (harness_root / relative).is_file():
            result.error(f"Core 有效基线缺少文件: {relative}")
    for path in sorted((harness_root / "skills").rglob("*.md")):
        validate_skill(path, result)
    validate_workflow_references(harness_root, result)
    core_version = validate_core_manifest(harness_root, result)
    validate_version_lock(harness_root, core_version, result)
    template_result = Result.empty()
    parse_config(harness_root.parent / "project-harness-template/.harness/harness.yaml", template_result)
    for message in template_result.errors:
        if "<" not in message and "40 位" not in message and "64 位" not in message:
            result.error(f"项目配置模板无效: {message}")
    from project_protocol import default_config
    return default_config()


def _git_output(repo: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo), *args],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        return completed.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def validate_core_pin(
    project_root: Path,
    config: HarnessConfig,
    result: Result,
    *,
    allow_dirty_core: bool = False,
) -> None:
    core_root = (project_root / config.core_local_path).resolve()
    try:
        core_config = project_config_path(core_root)
    except ValueError as error:
        result.error(str(error))
        return
    lock_path = core_config.parent / "version.lock"
    data = load_yaml_mapping(lock_path, result)
    if data is None:
        return
    if data.get("version") != config.core_version:
        result.error("项目 Core version 与 version.lock 不一致")
    if data.get("contentHash") != config.core_content_hash:
        result.error("项目 Core contentHash 与 version.lock 不一致")
    revision = _git_output(core_root, "rev-parse", "HEAD")
    if revision and revision != config.core_revision:
        result.error("项目 Core revision 与 Mini-Harness HEAD 不一致")
    dirty = _git_output(core_root, "status", "--porcelain")
    if dirty and not allow_dirty_core:
        result.error("Mini-Harness 工作区不干净，不能作为正式项目锁定 Core")
    elif dirty:
        result.warn("Mini-Harness 工作区不干净；仅按开发模式校验，结果不可作为发布锁")
    entries = data.get("contentHashPaths")
    if isinstance(entries, list) and all(isinstance(item, str) for item in entries):
        current = (
            compute_content_hash(core_config.parent, entries)
            if allow_dirty_core and dirty
            else compute_git_content_hash(core_root, config.core_revision, entries, result)
        )
        if current != config.core_content_hash:
            result.error("Mini-Harness 指定 revision 内容与项目锁定 contentHash 不一致")


def validate_service_catalog(project_root: Path, config: HarnessConfig, result: Result) -> None:
    path = project_root / config.service_catalog
    data = load_yaml_mapping(path, result)
    if data is None:
        return
    if data.get("schemaVersion") != SERVICE_CATALOG_SCHEMA_VERSION:
        result.error(f"services.yaml.schemaVersion 必须为 {SERVICE_CATALOG_SCHEMA_VERSION}")
    services = data.get("services")
    if not isinstance(services, Mapping):
        result.error("services.yaml.services 必须是映射")
        return
    identifiers = set(services)
    dependency_graph: dict[str, list[str]] = {}
    for identifier, raw in services.items():
        location = f"services.yaml.services.{identifier}"
        if not isinstance(identifier, str) or not identifier.strip():
            result.error("services.yaml.services 的服务 ID 必须是非空字符串")
            continue
        if not isinstance(raw, Mapping):
            result.error(f"{location} 必须是映射")
            continue
        _exact_keys(
            raw,
            {
                "type", "repository", "localPath", "defaultBranch", "responsibility",
                "contextPath", "contractPaths", "dataOwnership", "dependsOn",
            },
            location,
            result,
        )
        local_path = raw.get("localPath")
        context_path = raw.get("contextPath")
        service_type = raw.get("type")
        repository = raw.get("repository")
        contract_paths = raw.get("contractPaths")
        if not isinstance(service_type, str) or service_type not in {"frontend", "backend"}:
            result.error(f"{location}.type 必须为 frontend 或 backend")
        if not isinstance(repository, str) or not repository.strip():
            result.error(f"{location}.repository 必须是非空字符串")
        if not isinstance(raw.get("defaultBranch"), str) or not raw.get("defaultBranch", "").strip():
            result.error(f"{location}.defaultBranch 必须是非空字符串")
        if not isinstance(raw.get("responsibility"), str) or not raw.get("responsibility", "").strip():
            result.error(f"{location}.responsibility 必须是非空字符串")
        data_ownership = raw.get("dataOwnership")
        if not isinstance(data_ownership, list) or any(
            not isinstance(item, str) or not item.strip() for item in data_ownership
        ):
            result.error(f"{location}.dataOwnership 必须是字符串列表")
        if not isinstance(contract_paths, list) or not contract_paths or any(
            not isinstance(item, str) or not item.strip() for item in contract_paths
        ):
            result.error(f"{location}.contractPaths 必须是非空路径列表")
        if not isinstance(local_path, str) or not local_path:
            result.error(f"{location}.localPath 必须是非空字符串")
            continue
        service_root = resolve_service_path(project_root, identifier, local_path)
        if not service_root.is_dir():
            result.warn(f"{location}.localPath 不存在: {local_path}")
        if not isinstance(context_path, str) or not context_path.strip():
            result.error(f"{location}.contextPath 必须是非空字符串")
        else:
            context_file = _safe_service_path(
                service_root,
                context_path,
                f"{location}.contextPath",
                result,
            )
            if context_file is not None and not context_file.is_file():
                result.warn(f"{location}.contextPath 不存在: {context_path}")
        if isinstance(contract_paths, list):
            for index, contract_path in enumerate(contract_paths):
                if isinstance(contract_path, str) and contract_path.strip():
                    _safe_service_path(
                        service_root,
                        contract_path,
                        f"{location}.contractPaths[{index}]",
                        result,
                    )
        depends_on = raw.get("dependsOn", [])
        if (
            not isinstance(depends_on, list)
            or any(not isinstance(item, str) or item not in identifiers for item in depends_on)
            or len(depends_on) != len(set(depends_on))
            or identifier in depends_on
        ):
            result.error(f"{location}.dependsOn 包含不存在、重复或自依赖")
        else:
            dependency_graph[str(identifier)] = list(depends_on)

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(identifier: str) -> bool:
        if identifier in visiting:
            return False
        if identifier in visited:
            return True
        visiting.add(identifier)
        valid = all(visit(dependency) for dependency in dependency_graph.get(identifier, []))
        visiting.remove(identifier)
        visited.add(identifier)
        return valid

    if any(not visit(identifier) for identifier in dependency_graph):
        result.error("services.yaml.dependsOn 存在循环依赖")


def validate_manifest(path: Path, version: str, result: Result) -> dict[str, Any] | None:
    data = load_yaml_mapping(path, result)
    if data is None:
        return None
    expected = {
        "schemaVersion",
        "version",
        "title",
        "phase",
        "state",
        "owners",
        "createdAt",
        "updatedAt",
        "blockedBy",
    }
    _exact_keys(data, expected, str(path), result)
    if data.get("schemaVersion") != MANIFEST_SCHEMA_VERSION:
        result.error(f"{path} schemaVersion 必须为 {MANIFEST_SCHEMA_VERSION}")
    if data.get("version") != version:
        result.error(f"{path} version 必须与周期产品版本 {version} 一致")
    if not VERSION_PATTERN.fullmatch(str(data.get("version", ""))):
        result.error(f"{path} version 格式非法")
    phase = data.get("phase")
    state = data.get("state")
    if not isinstance(phase, str) or phase not in ALLOWED_MANIFEST_PHASES:
        result.error(f"{path} phase 非法: {phase}")
    if not isinstance(state, str) or state not in ALLOWED_MANIFEST_STATES:
        result.error(f"{path} state 非法: {state}")
    if phase == "completed" and state != "active":
        result.error(f"{path} phase=completed 时 state 必须为 active")
    owners = data.get("owners")
    if not isinstance(owners, Mapping) or not isinstance(owners.get("product"), str) or not owners.get("product", "").strip():
        result.error(f"{path} owners.product 必须是非空字符串")
    elif set(owners) - {"product", "ui", "frontend", "backend", "testhub"}:
        result.error(f"{path} owners 包含未定义角色")
    for key in ("createdAt", "updatedAt"):
        value = data.get(key)
        if not isinstance(value, (date, str)):
            result.error(f"{path} {key} 必须是 YYYY-MM-DD")
        else:
            try:
                date.fromisoformat(str(value))
            except ValueError:
                result.error(f"{path} {key} 必须是 YYYY-MM-DD")
    blocked_by = data.get("blockedBy")
    if not isinstance(blocked_by, list) or any(not isinstance(item, str) or not item.strip() for item in blocked_by):
        result.error(f"{path} blockedBy 必须是字符串列表")
    elif state == "blocked" and not blocked_by:
        result.error(f"{path} state=blocked 时 blockedBy 不得为空")
    elif state != "blocked" and blocked_by:
        result.error(f"{path} 仅 state=blocked 时允许 blockedBy 非空")
    return data
