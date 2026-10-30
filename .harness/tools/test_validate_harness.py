from __future__ import annotations

import hashlib
import importlib.util
import os
import re
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import yaml
import product_ui_validation as product_validator
import development_roles
from project_protocol import default_config
from asset_io import atomic_write
import prd_revision
import role_gates


VALIDATOR_PATH = Path(__file__).with_name("validate_harness.py")
SPEC = importlib.util.spec_from_file_location("validate_harness", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"无法加载 {VALIDATOR_PATH}")
validator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = validator
SPEC.loader.exec_module(validator)

BACKEND_VALIDATOR_PATH = Path(__file__).with_name("backend_validation.py")
BACKEND_SPEC = importlib.util.spec_from_file_location("backend_validation", BACKEND_VALIDATOR_PATH)
if BACKEND_SPEC is None or BACKEND_SPEC.loader is None:
    raise RuntimeError(f"无法加载 {BACKEND_VALIDATOR_PATH}")
backend_validator = importlib.util.module_from_spec(BACKEND_SPEC)
sys.modules[BACKEND_SPEC.name] = backend_validator
BACKEND_SPEC.loader.exec_module(backend_validator)


CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="png" ContentType="image/png"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
"""


def text_paragraph(text: str, style: str = "") -> str:
    style_xml = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    return f"<w:p>{style_xml}<w:r><w:t>{text}</w:t></w:r></w:p>"


def image_paragraph(relationship_id: str) -> str:
    return f"""<w:p><w:r><w:drawing><wp:inline xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"><a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:graphicData><a:blip r:embed="{relationship_id}"/></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>"""


def write_docx(
    path: Path,
    requirements: tuple[str, ...] = ("REQ-001",),
    *,
    history_status: str = "greenfield-skipped",
    history_reference: str = "",
    decision_reference: str = "DEC-001",
    missing_image_for: str = "",
    external_image: bool = False,
) -> None:
    paragraphs = [
        text_paragraph("测试需求 PRD"),
        text_paragraph(f"历史知识回溯：{history_status}"),
    ]
    if history_reference:
        paragraphs.append(text_paragraph(f"历史来源：{history_reference}"))
    if decision_reference:
        paragraphs.append(text_paragraph(f"探索来源：{decision_reference}"))
    relationships: list[str] = []
    image_names: list[str] = []
    for index, requirement in enumerate(requirements, start=1):
        paragraphs.append(text_paragraph(f"{requirement} 可验收需求", "Heading2"))
        paragraphs.append(text_paragraph("用户可以完成目标操作并看到明确结果。"))
        if requirement != missing_image_for:
            relationship_id = f"rId{index}"
            paragraphs.append(image_paragraph(relationship_id))
            target_mode = ' TargetMode="External"' if external_image else ""
            target = "https://example.test/screenshot.png" if external_image else f"media/image{index}.png"
            relationships.append(
                f'<Relationship Id="{relationship_id}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="{target}"{target_mode}/>'
            )
            if not external_image:
                image_names.append(f"word/media/image{index}.png")
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<w:body>{''.join(paragraphs)}<w:sectPr/></w:body></w:document>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f"{''.join(relationships)}</Relationships>"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", CONTENT_TYPES)
        archive.writestr("word/document.xml", document)
        archive.writestr("word/_rels/document.xml.rels", rels)
        for name in image_names:
            archive.writestr(name, b"\x89PNG\r\n\x1a\n")


def markdown_prd_text(
    version: str = "v1.2",
    requirements: tuple[str, ...] = ("REQ-001",),
    *,
    history_status: str = "greenfield-skipped",
    history_reference: str = "",
    decision_reference: str = "DEC-001",
) -> str:
    history_source = history_reference or "none"
    sections: list[str] = [
        f"""# {version} 产品需求文档

- 版本：`{version}`
- 历史知识回溯：`{history_status}`
- 历史来源：`{history_source}`

## 已确认目标

- 让用户完成文件列表查询。

## 本期范围

- 文件列表查询。

## 明确非目标

- 文件上传。
"""
    ]
    for requirement in requirements:
        sections.append(
            f"""## {requirement} 文件列表

- 来源：`{decision_reference}`
- 原始需求表述：用户需要查看自己可访问的文件列表。
- 明确约束：只返回当前用户有权访问的文件。
- 验收标准：登录用户可获得权限范围内的文件列表；无数据时返回空列表。
"""
        )
    sections.append(
        """## 待确认事项

- none
"""
    )
    return "\n".join(sections)


def write_markdown_prd(
    path: Path,
    requirements: tuple[str, ...] = ("REQ-001",),
    *,
    history_status: str = "greenfield-skipped",
    history_reference: str = "",
    decision_reference: str = "DEC-001",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        markdown_prd_text(
            path.name.removesuffix("-prd.md"),
            requirements,
            history_status=history_status,
            history_reference=history_reference,
            decision_reference=decision_reference,
        ),
        encoding="utf-8",
    )


def discovery_text() -> str:
    return """# 产品探索与 Mock 验证

- 需求版本：`v1.2`
- 探索目标：验证文件列表的浏览体验

## 1. 待验证假设

| HYP | 用户场景与页面想法 | 输入或背景 |
| --- | --- | --- |
| HYP-001 | 登录用户查看文件时，希望页面直接呈现可访问文件 | 产品负责人提出用户需要查看权限范围内文件 |

## 2. Mock 与反馈

| 轮次 | Mock | 验证的假设 | 真实反馈或观察 | 结果 |
| --- | --- | --- | --- | --- |
| 1 | 原型仓库/index.html | HYP-001 | 产品负责人认为列表更容易理解 | 带入 PRD |
"""


def strict_markdown_prd_text(version: str = "v1.2") -> str:
    return f"""# {version} 产品需求文档

- 需求版本：`{version}`
- 历史知识回溯：`greenfield-skipped`
- 历史来源：`none`
- 创建日期：2026-07-22
- 最近更新：2026-07-22

## 1. 为什么做

登录用户需要查看自己有权访问的文件，减少逐目录确认成本。

## 2. 历史知识回溯

当前没有真实历史文档，本环节按 greenfield 跳过。

| 历史文档 | 关联本期 REQ | 继承的事实或约束 | 冲突与处理 |
| --- | --- | --- | --- |
| none | none | none | none |

## 3. 本期边界

本期包含：

| 编号 | 功能 | 本期交付范围 |
| --- | --- | --- |
| F-001 | 文件列表 | 展示当前用户有权访问的文件 |

## 4. 功能需求

### REQ-001 文件列表

- 来源：`DEC-001`

#### 需求说明

| 维度 | 内容 |
| --- | --- |
| 用户 | 登录用户 |
| 触发场景 | 进入文件页面查看列表 |
| 当前问题 | 需要逐目录确认可访问文件，成本高 |
| 目标结果 | 展示权限范围内的文件列表 |
| 本期正向边界 | 仅展示当前用户有权访问的文件列表 |

#### 详细需求

##### 入口与交互

用户从文件菜单进入列表，页面展示加载结果和明确反馈。

##### 操作流程

| 步骤 | 操作者 | 动作 | 系统响应 | 结果/下一状态 |
| --- | --- | --- | --- | --- |
| 1 | 登录用户 | 打开文件菜单进入列表 | 发起文件查询 | 加载中 |
| 2 | 系统 | 返回权限范围内文件 | 展示列表或空态 | 成功结束 |

##### 权限与数据范围

列表只返回当前用户有权访问的文件，服务端执行相同权限控制。

##### 异常校验

| 场景/条件 | 校验或拦截规则 | 用户提示 | 恢复方式 |
| --- | --- | --- | --- |
| 查询失败 | 接口错误或超时 | 展示失败原因 | 允许用户重试 |

#### 影响范围

影响文件列表页面、查询流程和服务端权限校验。

#### 验收要点

- 登录用户可以看到权限范围内的文件，无数据时看到空态。
- 无权文件不出现在列表中，查询失败时可以看到错误并重试。

## 5. 影响与风险

- 影响范围：文件列表页面和查询接口。
- 主要风险：权限范围不一致可能导致越权展示。

## 6. 待确认事项

- `none`

## 7. 产品决策

| 决策 ID | 结论 | 决策摘要 | 探索依据 | 决策人/时间 |
| --- | --- | --- | --- | --- |
| DEC-001 | accepted | 仅展示当前用户有权访问的文件 | HYP-001；列表主路径反馈 | 产品负责人/2026-07-22 |
"""


def write_strict_markdown_prd(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(strict_markdown_prd_text(path.name.removesuffix("-prd.md")), encoding="utf-8")


def markdown_prd_hash(path: Path) -> str:
    result = validator.Result.empty()
    digest = validator.file_sha256(path, result)
    if result.errors:
        raise AssertionError(f"无法计算测试 PRD 文件哈希: {result.errors}")
    return digest


VALID_V5_DOCUMENT = """# 接口文档

- 接口文档协议：`v5`

## 接口总览

| 接口编号 | 来源 Plan | 接口地址 | 接口名称 |
| --- | --- | --- | --- |
| API-001 | `plan-01-file.md` | `GET /file` | 查询文件 |

## 具体接口

### [API-001] 查询文件

- 来源 Plan：`plan-01-file.md`
- 接口地址：`GET /file`
- 功能说明：查询文件详情。

#### 请求体

| 字段 | 类型 | 是否必填 | 说明 |
| --- | --- | --- | --- |
| `query.id` | string | 是 | 非空；文件 ID |

#### 响应体

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `data.id` | string | 文件 ID |

#### JSON 示例

```json
{ "request": { "id": "file-001" }, "response": { "data": { "id": "file-001" } } }
```

#### 成功状态

| HTTP 状态 | 业务状态 | 说明 |
| --- | --- | --- |
| 200 | 成功 | 返回 `data` |

#### 错误状态

| 触发条件 | HTTP / 业务码 | 说明 |
| --- | --- | --- |
| 文件不存在 | 既有包装 | 请求失败 |
"""


VALID_V3_PLAN = '# API Plan\n\n- 状态：`ready`\n- API Plan 方式：`page-demand-v3`\n\n## 总览\n\n| 页面 | 路由 | TASK 数 | 可执行 | 阻塞 | 阻塞原因 |\n| --- | --- | ---: | ---: | ---: | --- |\n| 文件页面 | `/files` | 2 | 1 | 1 | 缺少预览接口 |\n\n## 页面 API 计划\n\n### 文件页面\n\n- 路由：`/files`\n- 页面职责：展示文件。\n\n| TASK | REQ | 用户动作/场景 | 页面消费点 | 所需能力与消费字段 | 匹配接口与证据 | 缺口分类 | Owner | decision | API Exec 验收 |\n| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n| TASK-FE-101 | REQ-001 | 加载列表 | 文件列表 | `data.records[]`、`data.count` | API-001 `GET /files`、API-002 `GET /files/counts`，消费列表与数量 | none | backend-app | contract | 空态与错误提示 |\n\n## 跨页面共享能力索引\n\n| 能力 | 关联页面 TASK | 接口或实现证据 | 状态 |\n| --- | --- | --- | --- |\n\n## 阻塞项\n\n| BLOCK | 关联页面 TASK | 缺口分类 | 接口文档与现有实现证据 | 缺失内容 | 补齐 Owner |\n| --- | --- | --- | --- | --- | --- |\n\n## 接口消费索引（附录）\n\n| TASK | Owner | 文档路径与 API 编号 | HTTP 方法 | 文档业务路径 | 前端调用位置 | 当前请求定义 | decision | 差异与下一步 |\n| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n| TASK-FE-101 | backend-app | docs/api.md#API-001 | GET | /files | src/services/files.ts:listFiles | GET /files | contract | 无差异 |\n| TASK-FE-101 | backend-app | docs/api.md#API-002 | GET | /files/counts | src/services/files.ts:countFiles | GET /files/counts | contract | 无差异 |\n'


class InterfaceDocumentV5ContractTest(unittest.TestCase):
    def test_v5_document_requires_unit_fields_and_json_sample(self) -> None:
        valid_document = VALID_V5_DOCUMENT
        result = validator.Result.empty()
        self.assertTrue(backend_validator._validate_api_document_v5(valid_document, "backend-app", result))
        self.assertEqual(result.errors, [])

        incomplete_document = valid_document.replace("#### 响应体", "#### 响应")
        result = validator.Result.empty()
        self.assertFalse(backend_validator._validate_api_document_v5(incomplete_document, "backend-app", result))
        self.assertTrue(result.errors)

        grouped_field_document = valid_document.replace("`query.id`", "`query.id`、`query.name`")
        result = validator.Result.empty()
        self.assertFalse(backend_validator._validate_api_document_v5(grouped_field_document, "backend-app", result))
        self.assertTrue(result.errors)


class FrontendApiPlanPageDemandV3Test(unittest.TestCase):
    def test_page_plan_requires_routes_and_classified_blocks(self) -> None:
        valid_plan = """# API Plan

- 状态：`blocked`
- API Plan 方式：`page-demand-v3`

## 总览

| 页面 | 路由 | TASK 数 | 可执行 | 阻塞 | 阻塞原因 |
| --- | --- | ---: | ---: | ---: | --- |
| 文件页面 | `/files` | 2 | 1 | 1 | 缺少预览接口 |

## 页面 API 计划

### 文件页面

- 路由：`/files`
- 页面职责：展示文件。

| TASK | REQ | 用户动作/场景 | 页面消费点 | 所需能力与消费字段 | 匹配接口与证据 | 缺口分类 | Owner | decision | API Exec 验收 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TASK-FE-101 | REQ-001 | 加载列表 | 文件列表 | `data.records[]`、`data.count` | API-001 `GET /files`、API-002 `GET /files/counts`，消费列表与数量 | none | backend-app | contract | 空态与错误提示 |
| TASK-FE-102 | REQ-001 | 预览文件 | 预览按钮 | `previewUrl` | 正式接口文档未命中：API-001；现有实现未命中：FileController、src/services/files | missing_endpoint | backend-app | blocked | 补齐前不可预览 |

## 跨页面共享能力索引

| 能力 | 关联页面 TASK | 接口或实现证据 | 状态 |
| --- | --- | --- | --- |
| 文件读取 | TASK-FE-101、TASK-FE-102 | API-001、API-002 | contract/blocked |

## 阻塞项

| BLOCK | 关联页面 TASK | 缺口分类 | 接口文档与现有实现证据 | 缺失内容 | 补齐 Owner |
| --- | --- | --- | --- | --- | --- |
| BLOCK-001 | TASK-FE-102 | missing_endpoint | 两类来源均未命中 | 预览接口 | backend-app |

## 接口消费索引（附录）

| TASK | Owner | 文档路径与 API 编号 | HTTP 方法 | 文档业务路径 | 前端调用位置 | 当前请求定义 | decision | 差异与下一步 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TASK-FE-101 | backend-app | docs/api.md#API-001 | GET | /files | src/services/files.ts:listFiles | GET /files | contract | 无差异 |
| TASK-FE-101 | backend-app | docs/api.md#API-002 | GET | /files/counts | src/services/files.ts:countFiles | GET /files/counts | contract | 无差异 |
"""
        result = validator.Result.empty()
        self.assertTrue(backend_validator._validate_frontend_api_plan_page_demand_v3(valid_plan, "frontend-app", result))
        self.assertEqual(result.errors, [])

        invalid_plan = valid_plan.replace("- 路由：`/files`\n- 页面职责", "- 页面职责")
        result = validator.Result.empty()
        self.assertFalse(backend_validator._validate_frontend_api_plan_page_demand_v3(invalid_plan, "frontend-app", result))
        self.assertTrue(result.errors)


class CoreContentIntegrityTest(unittest.TestCase):
    def test_committed_harness_tree_matches_workspace_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            rules = repository / ".harness" / "rules"
            rules.mkdir(parents=True)
            (rules / "sample.md").write_bytes(b"# Harness rule\n")
            other = repository / "other-harness" / "rules"
            other.mkdir(parents=True)
            (other / "sample.md").write_bytes(b"unrelated\n")
            project_template = repository / "project-harness-template/.harness/hooks/usage_hook.py"
            project_template.parent.mkdir(parents=True)
            project_template.write_bytes(b"# project hook\n")
            entry = repository / "AGENTS.md"
            entry.write_bytes(b"# Team entry\n")
            for args in (
                ("init",),
                ("config", "core.autocrlf", "false"),
                ("add", "."),
                ("-c", "user.name=Harness Test", "-c", "user.email=test@example.test",
                 "commit", "-m", "Core content fixture"),
            ):
                subprocess.run(
                    ["git", *args], cwd=repository, check=True, capture_output=True
                )
            result = validator.Result.empty()
            committed = validator.compute_git_content_hash(
                repository, "HEAD", ["rules"], result
            )
            self.assertEqual([], result.errors)
            self.assertEqual(
                validator.compute_content_hash(repository / ".harness", ["rules"]),
                committed,
            )
            entries = ["rules", "../project-harness-template", "../AGENTS.md"]
            with_template = validator.compute_git_content_hash(repository, "HEAD", entries, result)
            self.assertEqual([], result.errors)
            self.assertEqual(
                validator.compute_content_hash(repository / ".harness", entries), with_template
            )
            for document in (entry,):
                original = document.read_bytes()
                document.write_bytes(original + b"changed after commit\n")
                self.assertNotEqual(
                    validator.compute_content_hash(repository / ".harness", entries), with_template
                )
                self.assertEqual(
                    validator.compute_git_content_hash(repository, "HEAD", entries, result), with_template
                )
                document.write_bytes(original)
            local_config = repository / "project-harness-template/.harness/tools/.env.local"
            local_config.parent.mkdir(parents=True)
            local_config.write_text("DB_PASSWORD=local-test-value\n", encoding="utf-8")
            self.assertEqual(
                validator.compute_content_hash(repository / ".harness", entries), with_template
            )
            example = local_config.with_name(".env.example")
            example.write_text("DB_PASSWORD=\n", encoding="utf-8")
            self.assertNotEqual(
                validator.compute_content_hash(repository / ".harness", entries), with_template
            )
            project_template.write_bytes(b"# changed hook\n")
            self.assertNotEqual(
                validator.compute_content_hash(repository / ".harness", entries), with_template
            )
            self.assertEqual(
                validator.compute_content_hash(repository / ".harness", ["rules"]), committed
            )
            (rules / "sample.md").write_bytes(b"changed after commit\n")
            self.assertNotEqual(
                validator.compute_content_hash(repository / ".harness", ["rules"]),
                committed,
            )


class ProjectHarnessTemplateTest(unittest.TestCase):
    def test_project_template_has_one_canonical_location(self) -> None:
        harness_root = VALIDATOR_PATH.parent.parent
        self.assertFalse((harness_root / "template/project").exists())
        files = [path for path in validator.REQUIRED_ACTIVE_FILES if path.startswith("../project-harness-template/")]
        self.assertGreaterEqual(len(files), 10)
        for path in files:
            self.assertTrue((harness_root / path).is_file(), path)
        self.assertIn("../project-harness-template", validator.CORE_HASH_DEFAULT_PATHS)
        lock = yaml.safe_load((harness_root / "version.lock").read_text(encoding="utf-8"))
        self.assertIn("../project-harness-template", lock["contentHashPaths"])
        for entry in ("../AGENTS.md", "../docs/core-maintenance.md"):
            self.assertIn(entry, validator.CORE_HASH_DEFAULT_PATHS)
            self.assertIn(entry, lock["contentHashPaths"])


class JenkinsIntegrationContractTest(unittest.TestCase):
    skill = "skills/delivery/jenkins.md"
    template = "template/develop/delivery/jenkins-execution-template.md"
    mapping = "../project-harness-template/.harness/projectContext/jenkins.md"
    connection = "../project-harness-template/.harness/tools/jenkins-mcp.md"

    def test_assets_are_registered_and_skill_is_validated(self) -> None:
        root = VALIDATOR_PATH.parent.parent
        for relative in (self.skill, self.template, self.mapping, self.connection):
            self.assertIn(relative, validator.REQUIRED_ACTIVE_FILES)
            self.assertTrue((root / relative).is_file(), relative)
        core = sys.modules[validator.validate_core.__module__]
        with mock.patch.object(core, "validate_skill", wraps=core.validate_skill) as check:
            validator.validate_core(root, validator.Result.empty())
        self.assertIn(root / self.skill, [call.args[0] for call in check.call_args_list])
        result = validator.Result.empty()
        core.validate_skill(root / self.skill, result)
        self.assertEqual(result.errors, [])

    def test_independent_entry_without_workflow_routes(self) -> None:
        root = VALIDATOR_PATH.parent.parent
        for path in (root / "workflow").rglob("*.md"):
            self.assertNotIn("jenkins", path.read_text(encoding="utf-8").lower(), str(path))
        # Independent capabilities are indexed by README; AGENTS owns role routing.
        self.assertIn(self.skill, (root / "README.md").read_text(encoding="utf-8"))
        template_entry = (root.parent / "project-harness-template/AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("core.localPath", template_entry)
        self.assertIn("Core 根目录的 `AGENTS.md`", template_entry)
        for relative in (self.mapping, self.connection):
            path = root / relative
            for link in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
                if not link.startswith("https://"):
                    self.assertTrue((path.parent / link).is_file(), link)

    def test_execution_template_preserves_distinct_evidence_fields(self) -> None:
        root = VALIDATOR_PATH.parent.parent
        text = (root / self.template).read_text(encoding="utf-8")
        for label in (
            "授权依据", "生产审批", "触发回执", "Queue 标识", "构建编号", "关联证据",
            "实际 Revision 及来源", "日志范围", "构建结论", "部署验证状态",
        ):
            self.assertRegex(text, rf"(?m)^- {re.escape(label)}：")
        # 所有新增表格保持固定列数，防止状态枚举破坏 Markdown 证据表。
        for relative in (self.template, self.mapping, self.connection):
            columns = None
            for line in (root / relative).read_text(encoding="utf-8").splitlines():
                if line.startswith("|"):
                    current = line.count("|")
                    columns = current if columns is None else columns
                    self.assertEqual(current, columns, (relative, line))
                else:
                    columns = None

    def test_connection_example_uses_only_local_token_reference(self) -> None:
        root = VALIDATOR_PATH.parent.parent
        text = (root / self.connection).read_text(encoding="utf-8")
        blocks = re.findall(r"```toml\n(.*?)\n```", text, re.DOTALL)
        self.assertEqual(len(blocks), 1)
        lines = blocks[0].splitlines()
        self.assertEqual(lines[0], "[mcp_servers.jenkins]")
        self.assertEqual(dict(re.findall(r'^(\w+) = "([^"\n]+)"$', blocks[0], re.MULTILINE)), {
            "url": "https://jenkins-mcp.example.invalid/mcp",
            "bearer_token_env_var": "JENKINS_MCP_TOKEN",
        })
        self.assertFalse((root.parent / "project-harness-template/.codex/config.toml").exists())
        for relative in (self.skill, self.template, self.mapping, self.connection):
            content = (root / relative).read_text(encoding="utf-8")
            self.assertNotRegex(content, r"Bearer\s+[A-Za-z0-9._-]{20,}")


class DocumentTimestampContractTest(unittest.TestCase):
    def test_all_development_templates_include_timestamp_metadata(self) -> None:
        root = VALIDATOR_PATH.parent.parent
        templates = list((root / "template/develop").rglob("*.md"))
        self.assertTrue(templates)
        for path in templates:
            with self.subTest(template=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertIn("- 创建时间：`<yyyy-MM-dd HH:mm:ss>`", text)
                self.assertIn("- 最后编辑时间：`<yyyy-MM-dd HH:mm:ss>`", text)
                self.assertIn("- 时区：`Asia/Shanghai`", text)
                self.assertIn("- 编辑记录：", text)
                self.assertNotIn("| 日期 |", text)
                self.assertNotIn("<UTC", text)

    def test_independent_stages_load_timestamp_rule(self) -> None:
        root = VALIDATOR_PATH.parent.parent
        self.assertTrue((root / "rules/document-timestamps.md").is_file())
        for track in ("frontend", "frontend-mock", "backend", "testhub"):
            paths = [root / "workflow" / f"{track}-workflow.md"]
            paths.extend((root / "skills" / track).glob("*.md"))
            for path in paths:
                with self.subTest(stage=str(path)):
                    self.assertIn(
                        "rules/document-timestamps.md", path.read_text(encoding="utf-8")
                    )


class FrontendMockCoreAssetsTest(unittest.TestCase):
    workflow = "workflow/frontend-mock-workflow.md"
    skills = (
        "skills/frontend-mock/01-assessment.md",
        "skills/frontend-mock/02-bootstrap.md",
        "skills/frontend-mock/03-data-source.md",
        "skills/frontend-mock/04-integration.md",
        "skills/frontend-mock/05-verification.md",
    )
    templates = (
        "template/develop/frontend-mock/mock-plan-template.md",
        "template/develop/frontend-mock/mock-source-matrix-template.md",
        "template/develop/frontend-mock/mock-verification-template.md",
    )

    def test_frontend_mock_assets_are_registered(self) -> None:
        harness_root = VALIDATOR_PATH.parent.parent
        self.assertIn(self.workflow, validator.ACTIVE_WORKFLOWS)
        for relative in (self.workflow, *self.skills, *self.templates):
            self.assertIn(relative, validator.REQUIRED_ACTIVE_FILES)
            self.assertTrue((harness_root / relative).is_file(), relative)

    def test_validate_core_checks_frontend_mock_skill_contracts(self) -> None:
        harness_root = VALIDATOR_PATH.parent.parent
        validated: list[str] = []

        def remember(path: Path, _result: validator.Result) -> None:
            validated.append(path.relative_to(harness_root).as_posix())

        core_validator = sys.modules[validator.validate_core.__module__]
        with mock.patch.object(core_validator, "validate_skill", side_effect=remember):
            validator.validate_core(harness_root, validator.Result.empty())

        for relative in self.skills:
            self.assertIn(relative, validated)


class FrontendEngineeringRulesTest(unittest.TestCase):
    rule = "rules/frontend-engineering.md"
    ui_rule = "rules/ui-standard.md"
    forbidden_readers = (
        "skills/product/discovery.md",
        "skills/ui/01-static-prototype.md",
        "template/product/discovery-template.md",
    )
    required_readers = (
        "workflow/frontend-workflow.md",
        "workflow/frontend-mock-workflow.md",
        "skills/frontend/01-ui-plan.md",
        "skills/frontend/02-ui-exec.md",
        "skills/frontend/03-api-plan.md",
        "skills/frontend/04-api-exec.md",
        "skills/frontend/05-review.md",
        "skills/frontend/06-test-feed.md",
        "skills/frontend-mock/01-assessment.md",
        "skills/frontend-mock/03-data-source.md",
    )
    ui_rule_readers = (
        "workflow/frontend-workflow.md",
        "workflow/ui-design-workflow.md",
        "skills/frontend/01-ui-plan.md",
        "skills/frontend/02-ui-exec.md",
        "skills/frontend/03-api-plan.md",
        "skills/frontend/04-api-exec.md",
        "skills/frontend/05-review.md",
        "skills/frontend/06-test-feed.md",
    )

    def test_frontend_engineering_rule_is_registered(self) -> None:
        harness_root = VALIDATOR_PATH.parent.parent
        self.assertIn(self.rule, validator.REQUIRED_ACTIVE_FILES)
        self.assertIn(self.ui_rule, validator.REQUIRED_ACTIVE_FILES)
        self.assertTrue((harness_root / self.rule).is_file(), self.rule)

    def test_discovery_and_static_page_forbid_engineering_rule(self) -> None:
        harness_root = VALIDATOR_PATH.parent.parent
        for relative in self.forbidden_readers:
            text = (harness_root / relative).read_text(encoding="utf-8")
            self.assertIn("不得读取", text, relative)
            self.assertIn(self.rule, text, relative)
            self.assertNotRegex(
                text,
                r"(?<!不得读取 )`rules/frontend-engineering\.md`",
                relative,
            )

    def test_frontend_reads_engineering_rule(self) -> None:
        harness_root = VALIDATOR_PATH.parent.parent
        for relative in self.required_readers:
            text = (harness_root / relative).read_text(encoding="utf-8")
            self.assertIn(self.rule, text, relative)
        for relative in self.ui_rule_readers:
            text = (harness_root / relative).read_text(encoding="utf-8")
            self.assertIn(self.ui_rule, text, relative)

    def test_ui_standard_has_no_implementation_details(self) -> None:
        harness_root = VALIDATOR_PATH.parent.parent
        text = (harness_root / self.ui_rule).read_text(encoding="utf-8")
        for forbidden in ("rowKey", "request.ts", "Zustand", "value ||", "OverflowTooltip", "useTableHeight"):
            self.assertNotIn(forbidden, text, forbidden)

    def test_frontend_skills_do_not_restate_engineering_entries(self) -> None:
        harness_root = VALIDATOR_PATH.parent.parent
        skills = (
            "skills/frontend/01-ui-plan.md",
            "skills/frontend/02-ui-exec.md",
            "skills/frontend/03-api-plan.md",
            "skills/frontend/04-api-exec.md",
            "skills/frontend/05-review.md",
            "skills/frontend/06-test-feed.md",
        )
        for relative in skills:
            text = (harness_root / relative).read_text(encoding="utf-8")
            for forbidden in (
                "OverflowTooltip",
                "formatThousand",
                "useTableHeight",
                "value ||",
                "yarn test:visual",
                "frontend-stack.md",
            ):
                self.assertNotIn(forbidden, text, f"{relative}: {forbidden}")

    def test_engineering_rule_delegates_stack_to_project(self) -> None:
        harness_root = VALIDATOR_PATH.parent.parent
        text = (harness_root / self.rule).read_text(encoding="utf-8")
        self.assertIn("禁止读取", text)
        self.assertIn("skills/ui/01-static-prototype.md", text)
        for marker in (
            ".harness/projectContext/frontend-stack.md",
            "邻近实现优先",
            "apiPrefix",
            "OverflowTooltip",
            "useTableHeight",
            "formatThousand",
        ):
            self.assertIn(marker, text, marker)
        stack = harness_root.parent / "project-harness-template/.harness/projectContext/frontend-stack.md"
        self.assertTrue(stack.is_file())
        self.assertIn(f"../{stack.relative_to(harness_root.parent).as_posix()}", validator.REQUIRED_ACTIVE_FILES)

    def test_ui_standard_declares_default_visual_baseline(self) -> None:
        harness_root = VALIDATOR_PATH.parent.parent
        text = (harness_root / self.ui_rule).read_text(encoding="utf-8")
        for marker in ("#006DFF", "#298DFF", "#F3F8FE", "frontend-stack.md", "固定业务指标色由项目"):
            self.assertIn(marker, text, marker)


class OpenSourceSanitizationTest(unittest.TestCase):
    private_address = re.compile(r"\b(?:10\.\d{1,3}|192\.168|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}\b")
    text_suffixes = {".md", ".py", ".yaml", ".yml", ".json", ".cmd", ".txt", ".toml", ".lock", ".example", ""}

    def published_texts(self):
        repository_root = VALIDATOR_PATH.parent.parent.parent
        for path in repository_root.rglob("*"):
            if not path.is_file() or ".git" in path.parts or "__pycache__" in path.parts:
                continue
            if path.suffix.lower() in self.text_suffixes:
                yield path.relative_to(repository_root), path.read_text(encoding="utf-8", errors="ignore")

    def test_published_tree_has_no_private_addresses(self) -> None:
        for relative, text in self.published_texts():
            match = self.private_address.search(text)
            self.assertIsNone(match, f"{relative}: {match and match.group(0)}")

    def test_published_tree_has_no_local_private_markers(self) -> None:
        # 私有关键词只放在维护者本机文件中，不能随开源仓库发布。
        configured = os.environ.get("ATLAS_PRIVATE_MARKERS_FILE", "")
        if not configured:
            self.skipTest("未设置 ATLAS_PRIVATE_MARKERS_FILE")
        markers_file = Path(configured).resolve()
        markers = [
            line.strip().lower()
            for line in markers_file.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        for relative, text in self.published_texts():
            if (VALIDATOR_PATH.parent.parent.parent / relative).resolve() == markers_file:
                continue
            lowered = text.lower()
            for marker in markers:
                self.assertNotIn(marker, lowered, f"{relative}: {marker}")


class FrontendUiPlanPermissionContractTest(unittest.TestCase):
    def test_reuse_plan_links_sources_decisions_and_regression_to_tasks(self) -> None:
        harness_root = VALIDATOR_PATH.parent.parent
        template_root = harness_root / "template/develop/frontend"
        page = (template_root / "ui-plan-module-template.md").read_text(encoding="utf-8")
        overview = (template_root / "ui-plan-template.md").read_text(encoding="utf-8")
        section = page.split("## 组件与逻辑复用方案\n", 1)[1].split("\n## ", 1)[0]
        rows = [
            [cell.strip() for cell in line.split("|")[1:-1]]
            for line in section.splitlines() if line.startswith("|")
        ]
        self.assertEqual(
            ["类别", "本页所需能力", "现有实现与调用方", "适配差异", "决策与理由", "改动边界", "受影响页面/回归", "关联 TASK"],
            rows[0],
        )
        self.assertEqual({"组件复用", "逻辑复用"}, {row[0] for row in rows[2:]})
        for row in rows[2:]:
            self.assertEqual(len(rows[0]), len(row))
            self.assertTrue(row[-1].startswith("TASK-"))
        for marker in ("检索范围", "状态归属", "兼容", "回流", "页面内部", "不单独拆 PLAN"):
            self.assertIn(marker, section)
        self.assertIn("- [ ] 每页已评估组件与逻辑复用", overview)

    def test_page_plan_has_four_design_sections_and_page_index(self) -> None:
        harness_root = VALIDATOR_PATH.parent.parent
        overview = (harness_root / "template/develop/frontend/ui-plan-template.md").read_text(encoding="utf-8")
        page = (harness_root / "template/develop/frontend/ui-plan-module-template.md").read_text(encoding="utf-8")
        skill = (harness_root / "skills/frontend/01-ui-plan.md").read_text(encoding="utf-8")
        for heading in ("## 页面样式", "## 交互逻辑", "## 路由设计", "## 权限设计（涉及时必填）"):
            self.assertIn(heading, page)
        self.assertIn("| Plan | 服务 ID | 页面 | 路由/承载入口 |", overview)
        self.assertIn("一个页面对应一个 PLAN 文件", skill)
        self.assertIn("负责的页面 PLAN/TASK", overview)
        self.assertIn("消费页面 PLAN", overview)
        for text in (overview, page):
            self.assertNotIn("大模块", text)
            self.assertNotIn("独立工程模块", text)

    def test_permission_planning_is_exposed_by_both_templates(self) -> None:
        harness_root = VALIDATOR_PATH.parent.parent
        overview = (harness_root / "template/develop/frontend/ui-plan-template.md").read_text(encoding="utf-8")
        module = (harness_root / "template/develop/frontend/ui-plan-module-template.md").read_text(encoding="utf-8")
        self.assertIn("## 权限范围与依赖", overview)
        self.assertIn("## 权限设计（涉及时必填）", module)
        for text in (overview, module):
            self.assertIn("not-applicable", text)
            self.assertIn("依据", text)
            self.assertIn("回流", text)
        headers = [line.split("|")[1:-1] for line in module.splitlines() if line.startswith("| REQ |") or line.startswith("| 关联 TASK |")]
        self.assertIn(
            ["REQ", "页面/路由/操作", "角色或授权条件", "权限标识与来源", "判断入口与工程位置", "数据/字段范围", "无权限表现", "关联 TASK"],
            [[cell.strip() for cell in row] for row in headers],
        )
        self.assertIn(
            ["关联 TASK", "验收场景", "身份/权限与数据前置条件", "预期页面/操作结果", "验证方式"],
            [[cell.strip() for cell in row] for row in headers],
        )
        for scenario in ("有权限", "无权限", "直接访问受限路由", "权限变化", "跨服务权限传递"):
            self.assertIn(scenario, module)


class GitCorePinTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.core = self.root / "core"
        self.rules = self.core / ".harness" / "rules" / "example.md"
        self.rules.parent.mkdir(parents=True)
        self.rules.write_text("Core rule\n", encoding="utf-8")
        content_hash = validator.compute_content_hash(self.core / ".harness", ["rules"])
        (self.core / ".harness" / "harness.yaml").write_text("kind: core\n", encoding="utf-8")
        (self.core / ".harness" / "version.lock").write_text(
            yaml.safe_dump({"version": "0.35.0", "contentHash": content_hash,
                            "contentHashPaths": ["rules"]}),
            encoding="utf-8",
        )
        self.git("init")
        self.git("add", ".")
        self.git("-c", "user.name=Atlas Test", "-c", "user.email=test@example.invalid",
                 "-c", "commit.gpgsign=false", "commit", "-m", "Core fixture")
        self.config = SimpleNamespace(
            core_local_path=Path("core"), core_version="0.35.0",
            core_revision=self.git("rev-parse", "HEAD"), core_content_hash=content_hash,
        )

    def git(self, *args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(self.core), *args], check=True,
            capture_output=True, text=True, encoding="utf-8",
        ).stdout.strip()

    def validate_pin(self):
        result = validator.Result.empty()
        validator.validate_core_pin(self.root, self.config, result)
        return result

    def test_clean_checkout_with_exact_pin_passes(self) -> None:
        self.assertEqual([], self.validate_pin().errors)

    def test_version_mismatch_is_rejected(self) -> None:
        self.config.core_version = "0.0.0"
        self.assertTrue(any("version 与" in error for error in self.validate_pin().errors))

    def test_revision_mismatch_is_rejected(self) -> None:
        self.config.core_revision = "0" * 40
        self.assertTrue(any("revision 与" in error for error in self.validate_pin().errors))

    def test_content_hash_mismatch_is_rejected(self) -> None:
        self.config.core_content_hash = "0" * 64
        self.assertTrue(any("contentHash 不一致" in error for error in self.validate_pin().errors))

    def test_dirty_checkout_is_rejected_for_formal_validation(self) -> None:
        self.rules.write_text("Changed rule\n", encoding="utf-8")
        self.assertTrue(any("工作区不干净" in error for error in self.validate_pin().errors))


class WordExportSkillContractTest(unittest.TestCase):
    def test_optional_word_skill_declares_one_way_equivalent_export_contract(self) -> None:
        harness_root = VALIDATOR_PATH.parent.parent
        text = (harness_root / "skills" / "product" / "export-word-prd.md").read_text(
            encoding="utf-8"
        )
        for marker in (
            "product/export/<版本号>-prd.docx",
            "源 PRD SHA256",
            "Markdown 文件原始字节",
            "render_docx.py",
            "逐页",
            "禁止从 Word 反向覆盖 Markdown",
            "不影响 产品内容检查～TestHub 检查",
        ):
            self.assertIn(marker, text)

    def test_word_template_is_a_display_shell_without_product_structure(self) -> None:
        harness_root = VALIDATOR_PATH.parent.parent
        template = harness_root / "template" / "product" / "prd-word-template.docx"
        with zipfile.ZipFile(template) as archive:
            self.assertIn("word/document.xml", archive.namelist())
            document = archive.read("word/document.xml").decode("utf-8")
            self.assertIn("源 PRD SHA256", document)
            self.assertIn("Markdown 文件原始字节 SHA256", document)
            self.assertIn("正文承载区", document)
            self.assertNotIn("引用图片", document)
            self.assertNotIn("REQ-001", document)
            self.assertFalse(any(name.startswith("word/media/") for name in archive.namelist()))


class PrdChangelogContractTest(unittest.TestCase):
    def test_prd_build_and_template_declare_finalize_revision_contract(self) -> None:
        harness_root = VALIDATOR_PATH.parent.parent
        skill = (harness_root / "skills" / "product" / "prd-build.md").read_text(
            encoding="utf-8"
        )
        template = (harness_root / "template" / "product" / "prd-changelog-template.md").read_text(
            encoding="utf-8"
        )
        for marker in (
            "prd_revision.py",
            "CHG",
        ):
            self.assertIn(marker, skill)
            self.assertIn(marker, template)
        self.assertIn("template/product/prd-changelog-template.md", validator.REQUIRED_ACTIVE_FILES)
        self.assertTrue(
            (harness_root / "template" / "product" / "prd-changelog-template.md").is_file()
        )


class MarkdownPrdValidationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def validate(self, path: Path) -> tuple[object, validator.Result]:
        result = validator.Result.empty()
        facts = product_validator.validate_markdown_prd(path, result)
        return facts, result

    def test_requirement_without_product_evidence_is_valid(self) -> None:
        path = self.root / "v1.2-prd.md"
        write_strict_markdown_prd(path)
        facts, result = self.validate(path)
        self.assertEqual([], result.errors)
        self.assertTrue(facts.valid)
        self.assertEqual({"REQ-001"}, set(facts.requirements))

    def test_markdown_images_are_not_product_evidence(self) -> None:
        path = self.root / "v1.2-prd.md"
        write_strict_markdown_prd(path)
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                "## 待确认事项",
                "![仅作说明](missing-image.png)\n\n## 待确认事项",
            ),
            encoding="utf-8",
        )
        facts, result = self.validate(path)
        self.assertEqual([], result.errors)
        self.assertTrue(facts.valid)

    def test_requirement_must_have_one_non_empty_source(self) -> None:
        path = self.root / "v1.2-prd.md"
        write_markdown_prd(path)
        path.write_text(
            path.read_text(encoding="utf-8").replace("- 来源：`DEC-001`\n", ""),
            encoding="utf-8",
        )
        facts, result = self.validate(path)
        self.assertFalse(facts.valid)
        self.assertTrue(any("来源" in error for error in result.errors))

    def test_prd_complete_structure_is_valid(self) -> None:
        path = self.root / "v1.2-prd.md"
        write_strict_markdown_prd(path)
        facts, result = self.validate(path)
        self.assertEqual([], result.errors)
        self.assertTrue(facts.valid)

    def test_prd_applicability_matrix_is_rejected(self) -> None:
        path = self.root / "v1.2-prd.md"
        write_strict_markdown_prd(path)
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                "#### 详细需求",
                "#### 适用性矩阵\n\n| 维度 | 结论 | 对应章节或不适用理由 |\n| --- | --- | --- |\n| interaction | applicable | 入口与交互 |\n\n#### 详细需求",
            ),
            encoding="utf-8",
        )
        facts, result = self.validate(path)
        self.assertFalse(facts.valid)
        self.assertTrue(any("不得包含适用性矩阵" in error for error in result.errors))

    def test_prd_detail_section_must_be_non_empty(self) -> None:
        path = self.root / "v1.2-prd.md"
        write_strict_markdown_prd(path)
        text = path.read_text(encoding="utf-8")
        start = text.index("#### 详细需求")
        end = text.index("#### 影响范围")
        path.write_text(
            text[:start] + "#### 详细需求\n\n\n" + text[end:],
            encoding="utf-8",
        )
        facts, result = self.validate(path)
        self.assertFalse(facts.valid)
        self.assertTrue(any("详细需求 缺少实质内容" in error for error in result.errors))

    def test_prd_empty_detail_heading_is_rejected(self) -> None:
        path = self.root / "v1.2-prd.md"
        write_strict_markdown_prd(path)
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                "用户从文件菜单进入列表，页面展示加载结果和明确反馈。",
                "",
            ),
            encoding="utf-8",
        )
        facts, result = self.validate(path)
        self.assertFalse(facts.valid)
        self.assertTrue(any("详细章节缺少实质内容: 入口与交互" in error for error in result.errors))

    def test_prd_missing_global_section_is_rejected(self) -> None:
        path = self.root / "v1.2-prd.md"
        write_strict_markdown_prd(path)
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                "## 5. 影响与风险", "## 5. 其他章节"
            ),
            encoding="utf-8",
        )
        facts, result = self.validate(path)
        self.assertFalse(facts.valid)
        self.assertTrue(any("缺少全局章节：影响与风险" in error for error in result.errors))

    def test_prd_missing_requirement_core_section_is_rejected(self) -> None:
        path = self.root / "v1.2-prd.md"
        write_strict_markdown_prd(path)
        path.write_text(
            path.read_text(encoding="utf-8").replace("#### 影响范围", "#### 其他影响"),
            encoding="utf-8",
        )
        facts, result = self.validate(path)
        self.assertFalse(facts.valid)
        self.assertTrue(any("缺少核心章节：影响范围" in error for error in result.errors))

    def test_prd_summary_must_use_dimension_table(self) -> None:
        path = self.root / "v1.2-prd.md"
        write_strict_markdown_prd(path)
        text = path.read_text(encoding="utf-8")
        start = text.index("#### 需求说明")
        end = text.index("#### 详细需求")
        path.write_text(
            text[:start]
            + "#### 需求说明\n\n登录用户进入文件页面后可以查看列表。\n\n"
            + text[end:],
            encoding="utf-8",
        )
        facts, result = self.validate(path)
        self.assertFalse(facts.valid)
        self.assertTrue(any("需求说明必须使用五维表" in error for error in result.errors))

    def test_prd_operation_flow_requires_table_columns(self) -> None:
        path = self.root / "v1.2-prd.md"
        write_strict_markdown_prd(path)
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                "| 步骤 | 操作者 | 动作 | 系统响应 | 结果/下一状态 |\n| --- | --- | --- | --- | --- |\n| 1 | 登录用户 | 打开文件菜单进入列表 | 发起文件查询 | 加载中 |\n| 2 | 系统 | 返回权限范围内文件 | 展示列表或空态 | 成功结束 |",
                "页面加载后查询文件；成功展示列表。",
            ),
            encoding="utf-8",
        )
        facts, result = self.validate(path)
        self.assertFalse(facts.valid)
        self.assertTrue(any("操作流程 必须使用 Markdown 表格" in error for error in result.errors))

    def test_prd_data_flow_requires_mermaid_flowchart(self) -> None:
        path = self.root / "v1.2-prd.md"
        write_strict_markdown_prd(path)
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                "##### 权限与数据范围",
                "##### 数据流转\n\n文件列表从服务查询后展示给用户。\n\n##### 权限与数据范围",
            ),
            encoding="utf-8",
        )
        facts, result = self.validate(path)
        self.assertFalse(facts.valid)
        self.assertTrue(any("数据流转必须包含 mermaid 代码块" in error for error in result.errors))

    def test_prd_data_flow_with_flowchart_is_valid(self) -> None:
        path = self.root / "v1.2-prd.md"
        write_strict_markdown_prd(path)
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                "##### 权限与数据范围",
                "##### 数据流转\n\n```mermaid\nflowchart LR\n  A[用户] --> B[文件服务]\n  B --> C[列表页]\n```\n\n##### 权限与数据范围",
            ),
            encoding="utf-8",
        )
        facts, result = self.validate(path)
        self.assertEqual([], result.errors)
        self.assertTrue(facts.valid)

    def test_invalid_utf8_is_rejected(self) -> None:
        path = self.root / "v1.2-prd.md"
        path.write_bytes(b"\xff\xfe\x00")
        facts, result = self.validate(path)
        self.assertFalse(facts.valid)
        self.assertTrue(any("UTF-8" in error for error in result.errors))

    def test_duplicate_requirement_is_rejected(self) -> None:
        path = self.root / "v1.2-prd.md"
        write_markdown_prd(path, ("REQ-001", "REQ-001"))
        facts, result = self.validate(path)
        self.assertFalse(facts.valid)
        self.assertTrue(any("重复 REQ" in error for error in result.errors))

    def test_missing_requirement_is_rejected(self) -> None:
        path = self.root / "v1.2-prd.md"
        path.write_text("# v1.2 产品需求文档\n\n- 历史知识回溯：`greenfield-skipped`\n", encoding="utf-8")
        facts, result = self.validate(path)
        self.assertFalse(facts.valid)
        self.assertTrue(any("至少需要一个 REQ-xxx" in error for error in result.errors))

    def test_prd_hash_is_markdown_file_hash(self) -> None:
        path = self.root / "v1.2-prd.md"
        write_markdown_prd(path)
        original = markdown_prd_hash(path)
        expected = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertEqual(expected, original)

        original_text = path.read_text(encoding="utf-8")
        path.write_text(
            original_text.replace("文件列表查询。", "按权限查询文件列表。", 1),
            encoding="utf-8",
        )
        body_changed = markdown_prd_hash(path)
        self.assertNotEqual(original, body_changed)

        path.write_text(original_text, encoding="utf-8")
        legacy_asset = self.root / "v1.2-prd-assets" / "REQ-001-main.png"
        legacy_asset.parent.mkdir()
        legacy_asset.write_bytes(b"\x89PNG\r\n\x1a\n")
        self.assertEqual(original, markdown_prd_hash(path))


class ProductCycleValidationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name)
        (self.project / ".harness" / "history").mkdir(parents=True)
        self.frontend = self.project / "frontend-app"
        self.remote = self.project / "frontend-remote.git"
        self.backend = self.project / "backend-app"
        self.backend_remote = self.project / "backend-remote.git"
        self.frontend.mkdir()
        self.git("init")
        self.git("config", "user.email", "test@example.test")
        self.git("config", "user.name", "Harness Test")
        (self.frontend / "src").mkdir()
        (self.frontend / "src" / "page.css").write_text("body { color: black; }\n", encoding="utf-8")
        (self.frontend / ".harness").mkdir()
        (self.frontend / ".harness" / "projectContext.md").write_text("# 前端上下文\n", encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-m", "initial")
        self.git("branch", "-M", "develop-v1.2")
        self.base_revision = self.git("rev-parse", "HEAD")
        self.backend.mkdir()
        self.git("init", cwd=self.backend)
        self.git("config", "user.email", "test@example.test", cwd=self.backend)
        self.git("config", "user.name", "Harness Test", cwd=self.backend)
        (self.backend / "src").mkdir()
        (self.backend / "src" / "Application.java").write_text("class Application {}\n", encoding="utf-8")
        (self.backend / "docs" / "interfaces").mkdir(parents=True)
        (self.backend / ".harness").mkdir()
        (self.backend / ".harness" / "projectContext.md").write_text("# 后端上下文\n", encoding="utf-8")
        self.git("add", ".", cwd=self.backend)
        self.git("commit", "-m", "initial backend", cwd=self.backend)
        self.git("branch", "-M", "develop-v1.2", cwd=self.backend)
        self.backend_base_revision = self.git("rev-parse", "HEAD", cwd=self.backend)
        catalog = self.project / ".harness" / "projectContext" / "services.yaml"
        catalog.parent.mkdir(parents=True)
        catalog.write_text(
            f"""schemaVersion: 1
services:
  frontend-app:
    type: frontend
    repository: {self.remote.as_posix()}
    localPath: frontend-app
    defaultBranch: develop
    responsibility: 测试前端
    contextPath: .harness/projectContext.md
    contractPaths: [docs/interfaces, src]
    dataOwnership: []
    dependsOn: [backend-app]
  backend-app:
    type: backend
    repository: {self.backend_remote.as_posix()}
    localPath: backend-app
    defaultBranch: develop
    responsibility: 测试后端
    contextPath: .harness/projectContext.md
    contractPaths: [docs/interfaces, src]
    dataOwnership: [test-db]
    dependsOn: []
""",
            encoding="utf-8",
        )
        self.config = validator.default_project_config()

    def git(self, *arguments: str, cwd: Path | None = None) -> str:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=cwd or self.frontend,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        return completed.stdout.strip()

    def tearDown(self) -> None:
        self.temp.cleanup()


    def test_service_catalog_id_must_be_nonempty_string(self) -> None:
        catalog = self.project / ".harness" / "projectContext" / "services.yaml"
        original = catalog.read_text(encoding="utf-8")
        for invalid_identifier in (1, ""):
            with self.subTest(identifier=invalid_identifier):
                data = yaml.safe_load(original)
                service = data["services"].pop("frontend-app")
                data["services"][invalid_identifier] = service
                catalog.write_text(
                    yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
                    encoding="utf-8",
                )
                result = validator.Result.empty()
                validator.validate_service_catalog(self.project, self.config, result)
                self.assertTrue(any("服务 ID 必须是非空字符串" in error for error in result.errors))
        catalog.write_text(original, encoding="utf-8")

    def create_cycle(self, version: str = "v1.2", history: str = "") -> Path:
        cycle = self.project / ".harness" / "demandCycle" / version
        product = cycle / "product"
        product.mkdir(parents=True)
        atomic_write(self.project / "原型仓库/index.html", "<html>产品原型</html>")
        (cycle / "manifest.yaml").write_text(
            f"""schemaVersion: 8
version: {version}
title: 测试需求
phase: planning
state: active
owners:
  product: 产品负责人
createdAt: 2026-07-22
updatedAt: 2026-07-22
blockedBy: []
""",
            encoding="utf-8",
        )
        (product / "discovery.md").write_text(discovery_text(), encoding="utf-8")
        status = "completed" if history else "greenfield-skipped"
        prd = product / f"{version}-prd.md"
        write_strict_markdown_prd(prd)
        if history:
            prd.write_text(
                prd.read_text(encoding="utf-8")
                .replace("`greenfield-skipped`", f"`{status}`", 1)
                .replace("`none`", f"`{history}`", 1),
                encoding="utf-8",
            )
        prd_revision.initialize(product, prd, "产品")
        atomic_write(product / "mock-changelog.md", "# 原型记录\n2026-09-22 10:00:00\n首次记录。\n")
        return cycle


    @staticmethod
    def write_artifact(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text.strip() + "\n", encoding="utf-8")

    @staticmethod
    def backend_plan_text() -> str:
        return """# 文件列表（Java 后端 Plan）

- 需求版本：`v1.2`
- 后端服务：`backend-app`
- 开发者：`Harness Test`
- 模块形态：`single`
- 模块编号：`single`
- 风险等级：`high`
- 状态：`ready`
- 用户确认：`confirmed`
- 确认人：`产品负责人`
- 确认日期：`2026-07-22`

## 1. 需求理解

- 核心目标：返回当前用户可见文件列表
- 用户角色：登录用户
- 本次范围：文件列表查询
- 非目标：文件上传
- 全局验收：权限过滤后的列表可验证
- UI/API 外部依赖：前端文件页

### 1.1 REQ 覆盖

| REQ | 适用性 | 业务目标或不适用依据 | 验收映射 |
| --- | --- | --- | --- |
| REQ-001 | applicable | 返回当前用户可见文件列表 | PRD 文件列表验收 |

## 2. 现状调研

### 2.1 历史需求与实现

| 历史来源 | Revision/产物 | 可复用设计 | 已知问题与当前适用性 |
| --- | --- | --- | --- |
| 服务 Git | initial | 现有查询链路 | 当前适用 |

### 2.2 代码、调用链与数据流

| REQ | 层/调用方 | 真实位置 | 当前职责与调用关系 | 本次影响/回归范围 |
| --- | --- | --- | --- | --- |
| REQ-001 | Service | src/Application.java | 文件查询 | GET /files |

### 2.3 数据对象与性能证据（按需）

| 表/数据源 | 数据量或 n/a：无性能/数据变更 | 索引或 n/a | 相关字段 | 只读证据与结论 |
| --- | ---: | --- | --- | --- |
| test-db.files | n/a：无性能或数据变更 | PRIMARY | id | 测试表结构已核对 |

### 2.4 现有接口与调用方

| 方法与真实路径 | 所在模块 | 调用方 | 兼容/影响半径 | 处理结论 |
| --- | --- | --- | --- | --- |
| GET /files | backend-app | frontend-app | 文件页 | modify |

### 2.5 待确认事项

#### 2.5.1 业务待确认事项

- 无待决业务语义：PRD:REQ-001 已完整定义当前只读查询的范围、权限与错误语义。

#### 2.5.2 技术待确认事项

- 无待确认技术事项：已核对代码:src/Application.java 的同步查询链路和运行环境:测试环境。

## 3. 技术方案

### 3.1 核心流程与异常路径

- 主路径：鉴权后查询文件
- 参数或权限失败：拒绝访问
- 外部依赖失败：返回业务错误
- 重复请求/并发：只读请求无副作用
- 数据一致性与回滚：只读请求无需回滚

### 3.2 模块职责与方案取舍

| 主题 | 候选方案 | 采用方案 | 真实约束与理由 | 影响范围 |
| --- | --- | --- | --- | --- |
| 查询复用 | 新增/复用 | 复用 | 保持兼容 | Service |

### 3.3 数据影响

| 变更 | 表/字段/索引 | 原因 | 数据量、锁与性能风险 | 关联 TASK 与外部设计要求 |
| --- | --- | --- | --- | --- |
| n/a | files | 只读 | 无锁变更 | n/a：无外部设计 |

### 3.4 缓存、消息、定时、幂等与外部依赖

- n/a：当前为同步只读查询。

## 4. 接口设计

### GET `/files`

- 关联 REQ：`REQ-001`
- 来源引用：`PRD:REQ-001`
- 角色/权限：登录用户
- 副作用：none

#### 请求字段

| 字段 | 位置 | 必填 | 业务语义 | 业务约束 |
| --- | --- | --- | --- | --- |
| page | query | no | 页码 | 大于零 |

#### 响应字段

| 字段 | 业务语义 | 空值约定 |
| --- | --- | --- |
| files | 可见文件 | 无数据为空列表 |

#### 错误场景

| 场景 | 业务错误语义 | 期望行为 |
| --- | --- | --- |
| 未登录 | 无权限 | 拒绝访问 |

## 5. TASK 与验收

### TASK-BE-001: GET `/files` 返回文件列表

- REQ：`REQ-001`
- 任务类型：`http`
- 接口设计：`GET /files`
- 定时任务：`n/a：HTTP TASK`
- 业务逻辑：在完成登录用户的数据范围过滤后，按请求页码查询其可见文件；无记录时返回空列表，不改变文件数据。
- 技术选型：`none`
- 可实现状态：`ready`
- 修改位置：`src/Application.java`
- risk：`high`
- estimate：`6h`
- radius：`GET /files、文件查询与前端调用方`
- human-review：`required`
- data-change：`no`
- 依赖：`none`
- acceptance：
  - 返回当前用户可见的文件列表；未登录访问被拒绝。

## 6. 风险与发布

| 风险 | 概率/影响 | 预防与人审 | 监控/验证 | 发布与回滚 |
| --- | --- | --- | --- | --- |
| 权限回归 | 中/高 | required | 权限用例 | 应用回滚 |

## 7. Plan Gate

- [x] 范围、非目标、角色、依赖和验收已确认
- [x] 全部 REQ 已声明适用性，受影响链路、历史、数据对象和调用方有证据；性能或数据变更时已补充数据量、索引和适用 EXPLAIN
- [x] 接口/定时任务、数据、事务、权限、异常和回滚路径明确
- [x] TASK 的业务逻辑、技术选型、estimate、radius、风险和业务验收可执行
- [x] 业务与技术决策已确认；未确认项已分别登记 DEC-ID/TDEC-ID，且其阻塞对象未被伪造成可实现范围
- [x] 用户确认已记录；ready 时确认值为 confirmed
"""

    def validate_engineering(self, cycle, result):
        outcomes = {}
        for role in ("frontend", "backend"):
            before = len(result.errors)
            development_roles.validate_development_role(self.project, self.config, cycle,
                validator.artifact_paths(cycle, self.config), role, result)
            outcomes[role] = validator.GateOutcome(len(result.errors) == before, ())
        return outcomes

    def create_development(self, cycle: Path, *, testhub: bool = False) -> Path:
        self.git("init", "--bare", str(self.remote), cwd=self.project)
        self.git("remote", "add", "origin", str(self.remote))
        frontend_before = self.git("rev-parse", "HEAD")
        (self.frontend / "src" / "api.ts").write_text("export const endpoint = '/files';\n", encoding="utf-8")
        self.git("add", "src/api.ts")
        self.git("commit", "-m", "integrate API")
        frontend_revision = self.git("rev-parse", "HEAD")
        self.git("push", "origin", f"develop-{cycle.name}")

        self.git("init", "--bare", str(self.backend_remote), cwd=self.project)
        self.git("remote", "add", "origin", str(self.backend_remote), cwd=self.backend)
        contract = self.backend / "docs" / "interfaces" / "files.md"
        contract.write_text(VALID_V5_DOCUMENT, encoding="utf-8")
        self.git("add", "docs/interfaces/files.md", cwd=self.backend)
        self.git("commit", "-m", "record current interface document", cwd=self.backend)
        baseline_revision = self.git("rev-parse", "HEAD", cwd=self.backend)
        baseline_hash = backend_validator._git_blob_sha256(self.backend, baseline_revision,
            "docs/interfaces/files.md", validator.Result.empty())
        self.git("push", "-u", "origin", f"develop-{cycle.name}", cwd=self.backend)

        develop = cycle / "develop"
        frontend = develop / "frontend" / "frontend-app"
        backend = develop / "backend" / "backend-app"
        self.write_artifact(
            frontend / "3-api-plan" / "plan.md",
            VALID_V3_PLAN + f"\n- 接口文档 SHA256：{baseline_hash}\n",
        )
        self.write_artifact(frontend / "4-api-exec" / "task.md", "# TASK\n\nTASK-FE-101 done")
        self.write_artifact(
            frontend / "4-api-exec" / "exec.md",
            f"# API Exec\n\n- 最终 Revision：{frontend_revision}\n- 联调：passed\n",
        )
        self.write_artifact(
            frontend / "5-review" / "review.md",
            f"# Frontend Review\n\n- 结论：`passed`\n- Final Revision：{frontend_revision}\n- 接口文档 SHA256：{baseline_hash}\n",
        )
        self.write_artifact(
            frontend / "6-test-feed" / "front-feed.md",
            f"# Front Feed\n\n- Final Revision：{frontend_revision}\n- 接口文档 SHA256：{baseline_hash}\n\n## REQ-001\n\n- 页面、状态、权限、视觉与回归盲区已记录。",
        )

        self.write_artifact(backend / "1-plan" / "plan-overview.md", self.backend_plan_text())
        self.write_artifact(
            backend / "2-external-design" / "external-design.md",
            "# Backend External Design\n\n## 外部设计项\n\nn/a：当前只读查询无 SQL、Nacos、定时任务或其他外部设计。\n",
        )
        self.write_artifact(
            backend / "3-tdd" / "tdd-01.md",
            f"# Backend TDD\n\n- Baseline Revision：{baseline_revision}\n- Baseline SHA256：{baseline_hash}\n- MockMvc：passed\n",
        )
        self.write_artifact(
            backend / "3-tdd" / "tdd-overview.md",
            f"""# Backend TDD Overview

## 模块矩阵

| 模块 | Plan | TDD | 契约路径 | Baseline Revision | Baseline SHA256 | 状态 | 当前结论 / 依赖 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 01 | `1-plan/plan-overview.md` | `tdd-01.md` | `docs/interfaces/files.md` | `{baseline_revision}` | `{baseline_hash}` | passed | MockMvc 已通过 |
""",
        )
        self.write_artifact(
            backend / "4-exec" / "exec-01.md",
            f"""# Backend Exec-01

## TASK

| TASK | 状态 | 修改位置 | 实现与测试 | 偏差/审批/风险 |
| --- | --- | --- | --- | --- |
| TASK-BE-001 | done | src/Application.java | JUnit 与 verify passed | 无偏差，高风险人审已完成 |

## 外部执行记录

n/a：本模块无 SQL、Nacos、权限或 MinIO 变更。

## 模块执行证据

- 最终 Revision：{baseline_revision}
- mvn verify：passed
""",
        )
        self.write_artifact(
            backend / "4-exec" / "exec-overview.md",
            """# Backend Exec Overview

## 模块索引

| Exec | Plan | TDD | TASK | 状态 | 外部变更文件 | 依赖/发布顺序 |
| --- | --- | --- | --- | --- | --- | --- |
| `exec-01.md` | `1-plan/plan-overview.md` | `3-tdd/tdd-01.md` | TASK-BE-001 | done | n/a：无外部执行 | 先发布后端 |
""",
        )
        self.write_artifact(
            backend / "5-local-interface-test" / "localTest-overview.md",
            "# LocalTest Overview\n\n"
            "| 模块 | LocalTest | 状态 |\n"
            "| --- | --- | --- |\n"
            "| 01 | localTest-01.md | pass |\n\n"
            "- 是否允许生成 verified 接口文档：`yes`\n",
        )
        self.write_artifact(
            backend / "5-local-interface-test" / "localTest-01.md",
            "# LocalTest-01\n\n- IT-001：Pass\n",
        )
        self.write_artifact(backend / "6-interface-document" / "api-document.md", VALID_V5_DOCUMENT)
        self.write_artifact(
            backend / "7-review" / "review-overview.md",
            f"""# Backend Review Overview

- 结论：`passed`
- Final Revision：{baseline_revision}
- 接口文档 SHA256：{baseline_hash}

## REQ 覆盖

| REQ | 结论 | 证据 |
| --- | --- | --- |
| REQ-001 | covered | Controller、JUnit 与接口测试 IT-001 |
""",
        )
        self.write_artifact(
            backend / "7-review" / "review-01.md",
            f"""# Review-01

- 服务与 Revision：backend-app@{baseline_revision}
- 状态：passed

## REQ 覆盖

| REQ | 结论 | 证据 |
| --- | --- | --- |
| REQ-001 | covered | Controller、JUnit 与接口测试 IT-001 |

## 发现

无 P0/P1/P2 发现。
""",
        )
        self.write_artifact(
            backend / "8-checklist" / "checklist.md",
            """# Backend External Configuration Checklist

## 待外部配置项

| ID | 来源与关联 Exec/TASK | 类型 | 外部系统/环境 | 配置或变更内容 | 执行/审批责任方 | 状态 | 外部变更记录 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EXT-001 | `4-exec/exec-01.md；TASK-BE-001` | permission | IAM 测试环境 | 配置测试身份的资源访问范围 | IAM 责任方 | pending | `4-exec/permission.md` |
""",
        )

        sources = role_gates.capture_sources(self.project, self.config, cycle.name)
        execution = develop / "execution.yaml"
        services = {}
        for role, name, remote, before, final in (
            ("frontend", "frontend-app", self.remote, frontend_before, frontend_revision),
            ("backend", "backend-app", self.backend_remote, self.backend_base_revision, baseline_revision),
        ):
            services[name] = dict(type=role, repository=remote.as_posix(), branch=f"develop-{cycle.name}",
                remote="origin", baseRevision=before, finalRevision=final, status="completed")
        tracks = {role: dict(applicable=True, services=[f"{role}-app"], status="completed", sources=sources)
                  for role in ("frontend", "backend")}
        tracks["frontend"].update(uiStages="not-applicable", uiScopeReason="仅接口接入")
        data = dict(schemaVersion=7, version=cycle.name, sources=sources, services=services, tracks=tracks,
            contracts=[dict(id="CONTRACT-001", ownerService="backend-app", consumers=["frontend-app"],
                path="docs/interfaces/files.md", baselineRevision=baseline_revision,
                baselineSha256=baseline_hash, status="baseline")], releaseOrder=["backend-app", "frontend-app"])
        atomic_write(execution, yaml.safe_dump(data, allow_unicode=True, sort_keys=False))
        manifest = cycle / "manifest.yaml"
        manifest_text = manifest.read_text(encoding="utf-8").replace(
            "phase: planning", "phase: completed" if testhub else "phase: testing"
        )
        manifest.write_text(manifest_text, encoding="utf-8")
        return execution


    def test_required_frontend_ui_stage_uses_page_artifacts(self) -> None:
        cycle = self.create_cycle()
        execution = self.create_development(cycle)
        frontend = cycle / "develop" / "frontend" / "frontend-app"
        self.write_artifact(
            frontend / "1-ui-plan" / "plan-overview.md",
            "# UI Plan Overview\n\n- 状态：ready\n\n## Plan 清单\n\n- PLAN-01：文件列表页面\n- PLAN-02：文件详情页面",
        )
        self.write_artifact(
            frontend / "1-ui-plan" / "plan-01.md",
            "# PLAN-01\n\n- 状态：ready\n\n## TASK\n\n- TASK-01.01：实现文件列表页面",
        )
        self.write_artifact(
            frontend / "2-ui-exec" / "exec-01.md",
            "# UI Exec-01\n\n- 状态：done\n\n## TASK\n\n- TASK-01.01：done",
        )
        self.write_artifact(
            frontend / "1-ui-plan" / "plan-02.md",
            "# PLAN-02：文件详情页面\n\n- 状态：ready\n\n## TASK\n\n- TASK-02.01：实现文件详情页面",
        )
        self.write_artifact(
            frontend / "2-ui-exec" / "exec-02.md",
            "# EXEC-02：文件详情页面\n\n- 状态：done\n\n## TASK\n\n- TASK-02.01：done",
        )
        execution.write_text(
            execution.read_text(encoding="utf-8").replace(
                "    uiStages: not-applicable\n",
                "    uiStages: required\n",
                1,
            ),
            encoding="utf-8",
        )

        result = validator.Result.empty()
        outcomes = self.validate_engineering(cycle, result)

        self.assertEqual([], result.errors)
        self.assertTrue(outcomes["backend"].passed)


    def test_backend_plan_requires_user_confirmation(self) -> None:
        cycle = self.create_cycle()
        self.create_development(cycle)
        plan = cycle / "develop" / "backend" / "backend-app" / "1-plan" / "plan-overview.md"
        plan.write_text(
            plan.read_text(encoding="utf-8").replace(
                "- 用户确认：`confirmed`",
                "- 用户确认：`pending`",
            ),
            encoding="utf-8",
        )
        result = validator.Result.empty()
        outcomes = self.validate_engineering(cycle, result)
        self.assertTrue(result.errors)
        self.assertTrue(
            any("用户确认" in message and "confirmed" in message for message in result.errors)
        )

    def test_backend_tdd_requires_current_module_record(self) -> None:
        cycle = self.create_cycle()
        self.create_development(cycle)
        tdd_root = cycle / "develop" / "backend" / "backend-app" / "3-tdd"
        (tdd_root / "tdd-01.md").rename(tdd_root / "tdd.md")

        result = validator.Result.empty()
        outcomes = self.validate_engineering(cycle, result)

        self.assertTrue(result.errors)
        self.assertTrue(any("TDD 文件必须与 Plan 模块一一对应" in message for message in result.errors))

    def test_backend_plan_write_endpoint_requires_confirmed_decision(self) -> None:
        cycle = self.create_cycle()
        self.create_development(cycle)
        plan = cycle / "develop" / "backend" / "backend-app" / "1-plan" / "plan-overview.md"
        plan.write_text(
            plan.read_text(encoding="utf-8").replace("### GET `/files`", "### POST `/files/draft`"),
            encoding="utf-8",
        )

        result = validator.Result.empty()
        outcomes = self.validate_engineering(cycle, result)

        self.assertTrue(result.errors)
        self.assertTrue(any("写接口" in message and "DEC-ID" in message for message in result.errors))

    def test_backend_plan_rejects_unknown_decision_reference(self) -> None:
        cycle = self.create_cycle()
        self.create_development(cycle)
        plan = cycle / "develop" / "backend" / "backend-app" / "1-plan" / "plan-overview.md"
        plan.write_text(
            plan.read_text(encoding="utf-8").replace(
                "- 来源引用：`PRD:REQ-001`",
                "- 来源引用：`PRD:REQ-001`；`DEC-001`",
            ),
            encoding="utf-8",
        )

        result = validator.Result.empty()
        outcomes = self.validate_engineering(cycle, result)

        self.assertTrue(result.errors)
        self.assertTrue(any("未确认或不存在的决策" in message for message in result.errors))

    def test_backend_plan_must_cover_prd_requirements(self) -> None:
        cycle = self.create_cycle()
        self.create_development(cycle)
        plan = cycle / "develop" / "backend" / "backend-app" / "1-plan" / "plan-overview.md"
        plan.write_text(
            plan.read_text(encoding="utf-8").replace(
                "| REQ-001 | applicable |",
                "| REQ-999 | applicable |",
            ),
            encoding="utf-8",
        )
        result = validator.Result.empty()
        outcomes = self.validate_engineering(cycle, result)
        self.assertTrue(result.errors)
        self.assertTrue(any("REQ 覆盖必须与 PRD 完全一致" in message for message in result.errors))

    def test_backend_plan_task_requires_task_metadata(self) -> None:
        cycle = self.create_cycle()
        self.create_development(cycle)
        plan = cycle / "develop" / "backend" / "backend-app" / "1-plan" / "plan-overview.md"
        plan.write_text(
            plan.read_text(encoding="utf-8").replace("- estimate：`6h`\n", ""),
            encoding="utf-8",
        )
        result = validator.Result.empty()
        outcomes = self.validate_engineering(cycle, result)
        self.assertTrue(result.errors)
        self.assertTrue(any("缺少 TASK 字段: estimate" in message for message in result.errors))

    def test_backend_plan_task_requires_business_logic(self) -> None:
        cycle = self.create_cycle()
        self.create_development(cycle)
        plan = cycle / "develop" / "backend" / "backend-app" / "1-plan" / "plan-overview.md"
        plan.write_text(
            plan.read_text(encoding="utf-8").replace(
                "- 业务逻辑：在完成登录用户的数据范围过滤后，按请求页码查询其可见文件；无记录时返回空列表，不改变文件数据。\n",
                "",
            ),
            encoding="utf-8",
        )
        result = validator.Result.empty()
        outcomes = self.validate_engineering(cycle, result)
        self.assertTrue(result.errors)
        self.assertTrue(any("必须补充真实业务逻辑" in message for message in result.errors))

    def test_backend_plan_unconfirmed_technical_selection_blocks_task(self) -> None:
        cycle = self.create_cycle()
        self.create_development(cycle)
        plan = cycle / "develop" / "backend" / "backend-app" / "1-plan" / "plan-overview.md"
        text = plan.read_text(encoding="utf-8")
        text = text.replace(
            "- 无待确认技术事项：已核对代码:src/Application.java 的同步查询链路和运行环境:测试环境。",
            """| TDEC-ID | 来源定位 | 待决问题 | 候选与推荐方案 | 影响 | Owner | 状态 | 阻塞对象 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| TDEC-001 | 代码:src/Application.java | 缓存策略 | 候选：直接查询/本地缓存；推荐：直接查询以保持现有一致性 | TASK-BE-001 | 架构负责人 | pending | TASK-BE-001 |""",
        ).replace("- 技术选型：`none`", "- 技术选型：`TDEC-001`")
        plan.write_text(text, encoding="utf-8")
        result = validator.Result.empty()
        outcomes = self.validate_engineering(cycle, result)
        self.assertTrue(result.errors)
        self.assertTrue(any("关联未确认 TDEC 时可实现状态必须为 blocked" in message for message in result.errors))

    def test_backend_plan_requires_detailed_structure(self) -> None:
        cycle = self.create_cycle()
        self.create_development(cycle)
        plan = cycle / "develop" / "backend" / "backend-app" / "1-plan" / "plan-overview.md"
        plan.write_text(
            plan.read_text(encoding="utf-8").replace(
                "### 2.1 历史需求与实现",
                "### 历史",
            ),
            encoding="utf-8",
        )
        result = validator.Result.empty()
        outcomes = self.validate_engineering(cycle, result)
        self.assertTrue(result.errors)
        self.assertTrue(any("缺少 Plan 详细结构" in message for message in result.errors))

    def test_backend_plan_detail_tables_require_real_rows(self) -> None:
        cycle = self.create_cycle()
        self.create_development(cycle)
        plan = cycle / "develop" / "backend" / "backend-app" / "1-plan" / "plan-overview.md"
        plan.write_text(
            plan.read_text(encoding="utf-8").replace(
                "| 服务 Git | initial | 现有查询链路 | 当前适用 |\n",
                "",
            ),
            encoding="utf-8",
        )
        result = validator.Result.empty()
        outcomes = self.validate_engineering(cycle, result)
        self.assertTrue(result.errors)
        self.assertTrue(any("表缺少已填写的真实数据行" in message for message in result.errors))

    def test_backend_plan_named_values_cannot_be_empty_semantics(self) -> None:
        cycle = self.create_cycle()
        self.create_development(cycle)
        plan = cycle / "develop" / "backend" / "backend-app" / "1-plan" / "plan-overview.md"
        plan.write_text(
            plan.read_text(encoding="utf-8").replace(
                "- 核心目标：返回当前用户可见文件列表",
                "- 核心目标：无",
            ),
            encoding="utf-8",
        )
        result = validator.Result.empty()
        outcomes = self.validate_engineering(cycle, result)
        self.assertTrue(result.errors)
        self.assertTrue(any("需求理解必须填写" in message for message in result.errors))

    def test_backend_plan_does_not_require_test_scenarios(self) -> None:
        cycle = self.create_cycle()
        self.create_development(cycle)
        plan = cycle / "develop" / "backend" / "backend-app" / "1-plan" / "plan-overview.md"
        plan.write_text(
            plan.read_text(encoding="utf-8").replace("- acceptance：\n  - 返回当前用户可见的文件列表；未登录访问被拒绝。\n", ""),
            encoding="utf-8",
        )
        result = validator.Result.empty()
        outcomes = self.validate_engineering(cycle, result)
        self.assertEqual([], result.errors)
        self.assertTrue(outcomes["backend"].passed)

    def test_non_http_backend_plan_accepts_explicit_reason(self) -> None:
        cycle = self.create_cycle()
        self.create_development(cycle)
        plan = cycle / "develop" / "backend" / "backend-app" / "1-plan" / "plan-overview.md"
        text = plan.read_text(encoding="utf-8")
        before_endpoint, endpoint_and_after = text.split("### GET `/files`", 1)
        _, after_endpoint = endpoint_and_after.split("## 5. TASK 与验收", 1)
        plan.write_text(
            (
                before_endpoint
                + "- 接口设计：n/a：本模块仅处理消息消费，不提供 HTTP 入口\n\n"
                + "## 5. TASK 与验收"
                + after_endpoint
            )
            .replace("### TASK-BE-001: GET `/files` 返回文件列表", "### TASK-BE-001: 处理文件消息消费")
            .replace("- 任务类型：`http`", "- 任务类型：`exception`")
            .replace("- 接口设计：`GET /files`", "- 接口设计：`n/a：仅消费文件变更消息`"),
            encoding="utf-8",
        )
        result = validator.Result.empty()
        outcomes = self.validate_engineering(cycle, result)
        self.assertEqual([], result.errors)
        self.assertTrue(outcomes["backend"].passed)

        plan.write_text(
            plan.read_text(encoding="utf-8").replace(
                "- 接口设计：n/a：本模块仅处理消息消费，不提供 HTTP 入口",
                "- 接口设计：n/a：待确认：产品回复",
            ),
            encoding="utf-8",
        )
        missing_reason_result = validator.Result.empty()
        self.validate_engineering(cycle, missing_reason_result)
        self.assertTrue(missing_reason_result.errors)
        self.assertTrue(
            any("无 HTTP 接口时必须记录" in message for message in missing_reason_result.errors)
        )

    def test_scheduled_backend_plan_uses_stable_identifier(self) -> None:
        cycle = self.create_cycle()
        self.create_development(cycle)
        plan = cycle / "develop" / "backend" / "backend-app" / "1-plan" / "plan-overview.md"
        text = plan.read_text(encoding="utf-8")
        before_endpoint, endpoint_and_after = text.split("### GET `/files`", 1)
        _, after_endpoint = endpoint_and_after.split("## 5. TASK 与验收", 1)
        text = (
            before_endpoint
            + "- 接口设计：n/a：本模块只执行归档定时任务，不提供 HTTP 入口\n\n"
            + "## 5. TASK 与验收"
            + after_endpoint
        ).replace(
            "### TASK-BE-001: GET `/files` 返回文件列表",
            "### TASK-BE-001: 执行文件归档定时任务",
        ).replace("- 任务类型：`http`", "- 任务类型：`scheduled`").replace(
            "- 接口设计：`GET /files`",
            "- 接口设计：`n/a：本任务没有 HTTP 入口`",
        ).replace(
            "- 定时任务：`n/a：HTTP TASK`",
            "- 定时任务：`FileArchiveJob.dailyArchive`",
        )
        plan.write_text(text, encoding="utf-8")
        result = validator.Result.empty()
        outcomes = self.validate_engineering(cycle, result)
        self.assertEqual([], result.errors)
        self.assertTrue(outcomes["backend"].passed)
        self.assertFalse([message for message in result.errors if "backend backend-app" in message])

    def test_backend_plan_rejects_open_pending_item_and_unchecked_gate(self) -> None:
        cycle = self.create_cycle()
        self.create_development(cycle)
        plan = cycle / "develop" / "backend" / "backend-app" / "1-plan" / "plan-overview.md"
        text = plan.read_text(encoding="utf-8")
        decision_start = text.index("#### 2.5.1 业务待确认事项")
        decision_end = text.index("#### 2.5.2 技术待确认事项", decision_start)
        heading_end = text.index("\n", decision_start) + 1
        decision_table = """| DEC-ID | 来源定位 | 待决问题 | 选项 | 影响 | Owner | 状态 | 阻塞对象 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DEC-001 | PRD:REQ-001 | 权限口径 | 方案A/方案B | GET /files | 产品 | blocked | GET /files |"""
        text = text[:heading_end] + "\n" + decision_table + "\n\n" + text[decision_end:]
        text = text.replace("- [x] 用户确认已记录", "- [ ] 用户确认已记录")
        plan.write_text(text, encoding="utf-8")
        result = validator.Result.empty()
        outcomes = self.validate_engineering(cycle, result)
        self.assertTrue(result.errors)
        self.assertTrue(any("未确认业务决策" in message for message in result.errors))
        self.assertTrue(any("Plan Gate 必须按模板逐项全部勾选" in message for message in result.errors))

    def test_backend_plan_gate_requires_exact_template_items(self) -> None:
        cycle = self.create_cycle()
        self.create_development(cycle)
        plan = cycle / "develop" / "backend" / "backend-app" / "1-plan" / "plan-overview.md"
        plan.write_text(
            plan.read_text(encoding="utf-8").replace(
                "- [x] 范围、非目标、角色、依赖和验收已确认",
                "- [x] 任意替代检查项",
            ),
            encoding="utf-8",
        )
        result = validator.Result.empty()
        outcomes = self.validate_engineering(cycle, result)
        self.assertTrue(result.errors)
        self.assertTrue(any("Plan Gate 必须按模板逐项全部勾选" in message for message in result.errors))

    def test_backend_plan_separates_business_and_technical_decisions(self) -> None:
        text = """### 2.5 待确认事项

#### 2.5.1 业务待确认事项

| DEC-ID | 来源定位 | 待决问题 | 选项 | 影响 | Owner | 状态 | 阻塞对象 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DEC-201 | 输入源缺失：PRD:REQ-001 | 默认排序规则 | 创建时间优先；风险优先 | GET /files | 产品负责人 | confirmed | TASK-BE-001 |

#### 2.5.2 技术待确认事项

| TDEC-ID | 来源定位 | 待决问题 | 候选与推荐方案 | 影响 | Owner | 状态 | 阻塞对象 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| TDEC-001 | DB:public.files | 索引创建窗口 | 候选：低峰执行/在线执行；推荐：低峰执行以降低锁风险 | 查询索引 | DBA | confirmed | TASK-BE-001 |
"""
        result = validator.Result.empty()
        self.assertTrue(backend_validator._plan_pending_items_closed(text, "backend-app", result))
        self.assertEqual([], result.errors)
        self.assertEqual({"DEC-201"}, backend_validator._plan_confirmed_decision_ids(text))

        pending = text.replace("| TDEC-001 |", "| TDEC-002 |", 1).replace(
            "| DBA | confirmed | TASK-BE-001 |",
            "| DBA | pending | TASK-BE-001 |",
            1,
        )
        pending_result = validator.Result.empty()
        self.assertFalse(backend_validator._plan_pending_items_closed(pending, "backend-app", pending_result))
        self.assertTrue(any("未确认技术决策: TDEC-002" in message for message in pending_result.errors))

    def test_backend_plan_identity_must_match_cycle_and_service(self) -> None:
        cycle = self.create_cycle()
        self.create_development(cycle)
        plan = cycle / "develop" / "backend" / "backend-app" / "1-plan" / "plan-overview.md"
        text = plan.read_text(encoding="utf-8")
        text = text.replace("- 需求版本：`v1.2`", "- 需求版本：`v9.9`")
        text = text.replace("- 后端服务：`backend-app`", "- 后端服务：`other-service`")
        plan.write_text(text, encoding="utf-8")
        result = validator.Result.empty()
        outcomes = self.validate_engineering(cycle, result)
        self.assertTrue(result.errors)
        self.assertTrue(
            any("需求版本" in message and "v1.2" in message for message in result.errors)
        )
        self.assertTrue(
            any("后端服务" in message and "backend-app" in message for message in result.errors)
        )

    def test_backend_plan_data_change_does_not_require_execution_controls(self) -> None:
        cycle = self.create_cycle()
        self.create_development(cycle)
        plan = cycle / "develop" / "backend" / "backend-app" / "1-plan" / "plan-overview.md"
        plan.write_text(
            plan.read_text(encoding="utf-8").replace(
                "- data-change：`no`",
                "- data-change：`yes`",
            ),
            encoding="utf-8",
        )
        result = validator.Result.empty()
        outcomes = self.validate_engineering(cycle, result)
        self.assertEqual([], result.errors)
        self.assertTrue(outcomes["backend"].passed)

    def test_backend_external_design_requires_task_reference(self) -> None:
        cycle = self.create_cycle()
        self.create_development(cycle)
        external = cycle / "develop" / "backend" / "backend-app" / "2-external-design" / "external-design.md"
        external.write_text(
            """# External Design

## 外部设计项

| ID | 类型 | 关联 TASK | 来源与目标对象 | 设计内容 | 兼容性、风险与状态 |
| --- | --- | --- | --- | --- | --- |
| EXT-DES-001 | nacos | TASK-BE-999 | 配置:feature.enabled | 功能开关 | 兼容 |
""",
            encoding="utf-8",
        )
        result = validator.Result.empty()
        outcomes = self.validate_engineering(cycle, result)
        self.assertTrue(result.errors)
        self.assertTrue(any("外部设计必须关联已登记的 Plan TASK" in message for message in result.errors))

    def test_backend_plan_rejects_invalid_dependency_syntax(self) -> None:
        cycle = self.create_cycle()
        self.create_development(cycle)
        plan = cycle / "develop" / "backend" / "backend-app" / "1-plan" / "plan-overview.md"
        plan.write_text(
            plan.read_text(encoding="utf-8").replace(
                "- 依赖：`none`",
                "- 依赖：`TASK-BE-ABC`",
            ),
            encoding="utf-8",
        )
        result = validator.Result.empty()
        outcomes = self.validate_engineering(cycle, result)
        self.assertTrue(result.errors)
        self.assertTrue(any("依赖格式非法" in message for message in result.errors))

    def test_backend_exec_task_set_must_match_plan(self) -> None:
        cycle = self.create_cycle()
        self.create_development(cycle)
        task = cycle / "develop" / "backend" / "backend-app" / "4-exec" / "exec-01.md"
        task.write_text(
            """# Backend Exec-01

## TASK

| TASK | 状态 | 修改位置 | 实现与测试 | 偏差/审批/风险 |
| --- | --- | --- | --- | --- |
| TASK-BE-999 | done | src/Application.java | JUnit 与 verify passed | 无偏差 |

## 外部执行记录

n/a：本模块无 SQL、Nacos、权限或 MinIO 变更。
""",
            encoding="utf-8",
        )
        result = validator.Result.empty()
        outcomes = self.validate_engineering(cycle, result)
        self.assertTrue(result.errors)
        self.assertTrue(any("Exec TASK 集必须与 Plan 完全一致" in message for message in result.errors))

    def test_backend_exec_task_status_must_be_allowed(self) -> None:
        cycle = self.create_cycle()
        self.create_development(cycle)
        task = cycle / "develop" / "backend" / "backend-app" / "4-exec" / "exec-01.md"
        task.write_text(
            task.read_text(encoding="utf-8").replace(
                "| TASK-BE-001 | done |",
                "| TASK-BE-001 | waiting |",
            ),
            encoding="utf-8",
        )
        result = validator.Result.empty()
        outcomes = self.validate_engineering(cycle, result)
        self.assertTrue(result.errors)
        self.assertTrue(any("TASK-BE-001 状态非法" in message for message in result.errors))

    def test_backend_exec_external_change_requires_generated_file(self) -> None:
        cycle = self.create_cycle()
        self.create_development(cycle)
        exec_path = cycle / "develop" / "backend" / "backend-app" / "4-exec" / "exec-01.md"
        exec_path.write_text(
            exec_path.read_text(encoding="utf-8").replace(
                "n/a：本模块无 SQL、Nacos、权限或 MinIO 变更。",
                """| 类型 | 状态 | 文件 | 外部设计与目标系统/环境 | 执行、验证与回滚 |
| --- | --- | --- | --- | --- |
| nacos | done | `nacos.md` | 测试命名空间，配置管理员已审批 | 发布后健康检查；失败回退历史版本 |""",
            ),
            encoding="utf-8",
        )
        result = validator.Result.empty()
        outcomes = self.validate_engineering(cycle, result)
        self.assertTrue(result.errors)
        self.assertTrue(any("缺少有效外部变更文件" in message for message in result.errors))

        self.write_artifact(
            exec_path.parent / "nacos.md",
            "# Nacos 变更\n\n## Exec-01 / TASK-BE-001\n\n```yaml\nfeature:\n  enabled: true\n```\n",
        )
        result = validator.Result.empty()
        outcomes = self.validate_engineering(cycle, result)
        self.assertEqual([], result.errors)
        self.assertTrue(outcomes["backend"].passed)

    def test_backend_review_must_cover_plan_requirements(self) -> None:
        cycle = self.create_cycle()
        self.create_development(cycle)
        review = cycle / "develop" / "backend" / "backend-app" / "7-review" / "review-overview.md"
        review.write_text(
            review.read_text(encoding="utf-8").replace(
                "| REQ-001 | covered | Controller、JUnit 与接口测试 IT-001 |\n",
                "普通说明：REQ-001 已检查。\n",
            ),
            encoding="utf-8",
        )
        result = validator.Result.empty()
        outcomes = self.validate_engineering(cycle, result)
        self.assertTrue(result.errors)
        self.assertTrue(any("Review 的 REQ 覆盖必须与 Plan" in message for message in result.errors))

    def test_backend_external_checklist_requires_configuration_owner(self) -> None:
        cycle = self.create_cycle()
        self.create_development(cycle)
        checklist = cycle / "develop" / "backend" / "backend-app" / "8-checklist" / "checklist.md"
        checklist.write_text(
            checklist.read_text(encoding="utf-8").replace(
                "| IAM 责任方 |",
                "| n/a |",
            ),
            encoding="utf-8",
        )
        result = validator.Result.empty()
        outcomes = self.validate_engineering(cycle, result)
        self.assertTrue(result.errors)
        self.assertTrue(any("必须给出可识别的执行或审批责任方" in message for message in result.errors))

    def test_multi_backend_plan_uses_canonical_overview_and_modules(self) -> None:
        cycle = self.create_cycle()
        self.create_development(cycle)
        plan_root = cycle / "develop" / "backend" / "backend-app" / "1-plan"
        module_one = (
            self.backend_plan_text()
            .replace(
                "- 模块形态：`single`\n- 模块编号：`single`",
                "- 模块形态：`multi`\n- 模块编号：`plan-01`",
            )
            .replace("files 返回文件列表", "复用文件查询")
            .replace(
                "`GET /files、文件查询与前端调用方`",
                "`GET /files 与查询层`",
            )
        )
        module_two = (
            self.backend_plan_text()
            .replace(
                "- 模块形态：`single`\n- 模块编号：`single`",
                "- 模块形态：`multi`\n- 模块编号：`plan-02`",
            )
            .replace("TASK-BE-001", "TASK-BE-002")
            .replace("files 返回文件列表", "增加权限过滤")
            .replace(
                "`GET /files、文件查询与前端调用方`",
                "`权限层与前端调用方`",
            )
            .replace(
                "- 依赖：`none`",
                "- 依赖：`plan-01:TASK-BE-001`",
            )
        )
        self.write_artifact(plan_root / "plan-01-query.md", module_one)
        self.write_artifact(plan_root / "plan-02-permission.md", module_two)
        self.write_artifact(
            cycle / "develop" / "backend" / "backend-app" / "3-tdd" / "tdd-02.md",
            "# Backend TDD plan-02\n\n- Baseline Revision：沿用 plan-01 已登记 baseline\n- MockMvc：passed\n",
        )
        self.write_artifact(
            cycle / "develop" / "backend" / "backend-app" / "3-tdd" / "tdd-overview.md",
            """# Backend TDD Overview

## 模块矩阵

| 模块 | Plan | TDD | 契约路径 | Baseline Revision | Baseline SHA256 | 状态 | 当前结论 / 依赖 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 01 | `1-plan/plan-01-query.md` | `tdd-01.md` | `docs/interfaces/files.md` | `0000000000000000000000000000000000000000` | `0000000000000000000000000000000000000000000000000000000000000000` | passed | 查询契约 |
| 02 | `1-plan/plan-02-permission.md` | `tdd-02.md` | `docs/interfaces/files.md` | `0000000000000000000000000000000000000000` | `0000000000000000000000000000000000000000000000000000000000000000` | passed | 权限契约 |
""",
        )
        self.write_artifact(
            cycle / "develop" / "backend" / "backend-app" / "5-local-interface-test" / "localTest-02.md",
            "# LocalTest-02\n\n- IT-002：Pass\n",
        )
        local_overview = cycle / "develop" / "backend" / "backend-app" / "5-local-interface-test" / "localTest-overview.md"
        local_overview.write_text(
            local_overview.read_text(encoding="utf-8").replace(
                "| 01 | localTest-01.md | pass |",
                "| 01 | localTest-01.md | pass |\n| 02 | localTest-02.md | pass |",
            ),
            encoding="utf-8",
        )
        self.write_artifact(
            cycle / "develop" / "backend" / "backend-app" / "7-review" / "review-02.md",
            "# Review-02\n\n- 状态：passed\n\n## REQ 覆盖\n\n| REQ | 结论 | 证据 |\n| --- | --- | --- |\n| REQ-001 | covered | 权限模块代码与 JUnit |\n",
        )
        self.write_artifact(
            cycle / "develop" / "backend" / "backend-app" / "4-exec" / "exec-01.md",
            """# Backend Exec-01

## TASK

| TASK | 状态 | 修改位置 | 实现与测试 | 偏差/审批/风险 |
| --- | --- | --- | --- | --- |
| TASK-BE-001 | done | src/Application.java | JUnit 与 verify passed | 无偏差 |

## 外部执行记录

n/a：本模块无 SQL、Nacos、权限或 MinIO 变更。
""",
        )
        self.write_artifact(
            cycle / "develop" / "backend" / "backend-app" / "4-exec" / "exec-02.md",
            """# Backend Exec-02

## TASK

| TASK | 状态 | 修改位置 | 实现与测试 | 偏差/审批/风险 |
| --- | --- | --- | --- | --- |
| TASK-BE-002 | done | src/Application.java | JUnit 与 verify passed | 无偏差 |

## 外部执行记录

n/a：本模块无 SQL、Nacos、权限或 MinIO 变更。
""",
        )
        self.write_artifact(
            cycle / "develop" / "backend" / "backend-app" / "4-exec" / "exec-overview.md",
            """# Backend Exec Overview

## 模块索引

| Exec | Plan | TDD | TASK | 状态 | 外部变更文件 | 依赖/发布顺序 |
| --- | --- | --- | --- | --- | --- | --- |
| `exec-01.md` | `1-plan/plan-01-query.md` | `3-tdd/tdd-01.md` | TASK-BE-001 | done | n/a：无外部变更 | 先执行 |
| `exec-02.md` | `1-plan/plan-02-permission.md` | `3-tdd/tdd-02.md` | TASK-BE-002 | done | n/a：无外部变更 | 依赖 exec-01 |
""",
        )
        self.write_artifact(
            plan_root / "plan-overview.md",
            """# 文件列表（Java 后端多模块 Plan 总览）

- 需求版本：`v1.2`
- 后端服务：`backend-app`
- 开发者：`Harness Test`
- 模块形态：`multi`
- 风险等级：`high`
- 状态：`ready`
- 用户确认：`confirmed`
- 确认人：`产品负责人`
- 确认日期：`2026-07-22`

## 1. 需求理解

- 核心目标：返回当前用户可见文件列表并统一权限过滤
- 本次范围：查询链路与权限模块
- 非目标：文件上传与删除
- 全局验收：列表内容与用户数据范围均可验证
- UI/API 外部依赖：frontend-app 文件页

## 1. REQ 与模块索引

| REQ | 适用性 | 业务目标或不适用依据 | Plan | TASK | 验收映射 |
| --- | --- | --- | --- | --- | --- |
| REQ-001 | applicable | 返回可见文件并执行权限过滤 | `plan-01-query.md`、`plan-02-permission.md` | TASK-BE-001、TASK-BE-002 | PRD 文件列表验收 |

## 2. 文档拆分索引

| 编号 | Plan | 功能与边界 | 依赖 | Owner | 风险 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| 01 | `plan-01-query.md` | 文件查询 | none | Backend A | high | ready |
| 02 | `plan-02-permission.md` | 权限过滤 | plan-01:TASK-BE-001 | Backend B | high | ready |

## 3. 跨 Plan TASK 依赖

- plan-01 → plan-02

## 4. Plan Gate

- [x] 全部 REQ 已映射到 plan-NN、TASK 或真实不适用依据
- [x] 模块索引和跨 Plan TASK 依赖与详情完全一致
- [x] 每个 plan-NN 已独立记录自身业务、技术选型、风险与验收
- [x] 用户确认已记录；ready 时确认值为 confirmed
""",
        )
        result = validator.Result.empty()
        outcomes = self.validate_engineering(cycle, result)
        self.assertEqual([], result.errors)
        self.assertTrue(outcomes["backend"].passed)
        self.assertFalse([message for message in result.errors if "backend backend-app" in message])


    def test_open_frontend_review_fails_role_check(self) -> None:
        cycle = self.create_cycle()
        self.create_development(cycle)
        review = cycle / "develop" / "frontend" / "frontend-app" / "5-review" / "review.md"
        review.write_text(
            review.read_text(encoding="utf-8")
            + "\n| ID | 优先级 | 位置 | 状态 |\n| --- | --- | --- | --- |\n| FR-001 | P1 | src/api.ts | open |\n",
            encoding="utf-8",
        )
        result = validator.Result.empty()
        outcomes = self.validate_engineering(cycle, result)
        self.assertTrue(result.errors)
        self.assertFalse(outcomes["frontend"].passed)

    def test_missing_test_feed_fails_role_check(self) -> None:
        cycle = self.create_cycle()
        self.create_development(cycle)
        (cycle / "develop" / "frontend" / "frontend-app" / "6-test-feed" / "front-feed.md").unlink()
        result = validator.Result.empty()
        outcomes = self.validate_engineering(cycle, result)
        self.assertTrue(result.errors)
        self.assertFalse(outcomes["frontend"].passed)


    def test_current_engineering_rejects_old_schema_and_contract_fields(self):
        import copy
        cycle = self.create_cycle()
        execution = self.create_development(cycle)
        current = yaml.safe_load(execution.read_text(encoding="utf-8"))
        for label, schema, contract_changes in (
            ("旧 Execution", 6, {}),
            ("旧 verified", 7, {"status": "verified", "verifiedRevision": "a" * 40, "verifiedSha256": "b" * 64}),
            ("旧摘要字段", 7, {"verifiedRevision": "", "verifiedSha256": ""}),
            ("接口摘要不匹配", 7, {"baselineSha256": "0" * 64}),
        ):
            with self.subTest(case=label):
                data = copy.deepcopy(current)
                data["schemaVersion"] = schema
                data["contracts"][0].update(contract_changes)
                atomic_write(execution, yaml.safe_dump(data, allow_unicode=True))
                result = validator.Result.empty()
                self.validate_engineering(cycle, result)
                self.assertTrue(result.errors, label)
        atomic_write(execution, yaml.safe_dump(current, allow_unicode=True))
        result = validator.Result.empty()
        self.validate_engineering(cycle, result)
        self.assertEqual([], result.errors)

    def test_current_engineering_rejects_old_local_test_report(self):
        cycle = self.create_cycle()
        self.create_development(cycle)
        directory = cycle / "develop/backend/backend-app/5-local-interface-test"
        (directory / "localTest-overview.md").rename(directory / "report.md")
        result = validator.Result.empty()
        self.validate_engineering(cycle, result)
        self.assertTrue(any("缺少有效 LocalTest" in error for error in result.errors))


class ProductLineCycleTest(unittest.TestCase):
    def setUp(self):
        self.area = tempfile.TemporaryDirectory()
        self.project = Path(self.area.name)
        self.config = default_config()
        self.cycles = self.project / self.config.demand_cycle_root
        self.cycles.mkdir(parents=True)
        self.history = self.project / self.config.history_root
        self.history.mkdir(parents=True)

    def tearDown(self):
        self.area.cleanup()

    def test_identity_accepts_product_lines_without_changing_version_grammar(self):
        for name, line, version in [('v1.2', None, 'v1.2'), ('地质工作台-v1.2', '地质工作台', 'v1.2'), ('drill-test-v1.2.3', 'drill-test', 'v1.2.3')]:
            identity = validator.parse_cycle_identity(name)
            self.assertEqual((line, version), (identity.product_line, identity.version))
        for name in ('../v1.2', '..-v1.2', 'a/v1.2', 'a\\v1.2', '原型', 'a-v1', 'a-v1.2-extra', 'a v1.2'):
            self.assertIsNone(validator.parse_cycle_identity(name), name)
        self.assertIsNone(validator.VERSION_PATTERN.fullmatch('地质工作台-v1.2'))

    def test_discovery_preserves_all_lines_and_reports_non_cycles_and_missing_manifest(self):
        for name in ('v1.2', '地质工作台-v1.2', '钻完井工作台-v1.2'):
            path = self.cycles / name
            path.mkdir()
            (path / 'manifest.yaml').write_text('schemaVersion: 8\n', encoding='utf-8')
        (self.cycles / '地质工作台原型').mkdir()
        (self.cycles / '钻完井工作台-v1.1').mkdir()
        result = validator.Result.empty()
        found = validator.discover_demand_cycles(self.project, self.config, result)
        self.assertEqual({'v1.2', '地质工作台-v1.2', '钻完井工作台-v1.2'}, {p.name for p in found})
        self.assertTrue(any('非法版本目录' in e for e in result.errors))
        self.assertTrue(any('缺少 manifest' in e for e in result.errors))


    def test_manifest_alias_is_not_silently_accepted(self):
        path = self.cycles / '钻完井工作台-v1.0'
        path.mkdir()
        manifest = path / 'manifest.yaml'
        manifest.write_text('schemaVersion: 8\nversion: v1.2\nphase: development\nstate: active\n', encoding='utf-8')
        result = validator.Result.empty()
        validator.validate_manifest(manifest, 'v1.0', result)
        self.assertTrue(any('周期产品版本 v1.0' in e for e in result.errors))

    def test_explicit_cross_line_history_reference_cannot_match_same_basename(self):
        for line in ('地质工作台', '钻完井工作台'):
            root = self.history / line
            root.mkdir()
            (root / 'v1.0-prd.md').write_text('# historical product facts', encoding='utf-8')
        root = self.history / '地质工作台'
        for reference, accepted in [('v1.0-prd.md', True), ('.harness/history/地质工作台/v1.0-prd.md', True), ('.harness/history/钻完井工作台/v1.0-prd.md', False)]:
            result = validator.Result.empty()
            valid = product_validator.validate_history_review('历史知识回溯：completed\n历史来源：' + reference, root, result,
                                                      self.cycles / '地质工作台-v1.2/product/v1.2-prd.md',
                                                      project_root=self.project, strict_references=True)
            self.assertEqual(accepted, valid, result.errors)
            if not accepted:
                self.assertTrue(result.errors)


    def test_bare_cycles_in_mixed_layout_exclude_named_product_history(self):
        named = self.history / '地质工作台'
        named.mkdir()
        (named / 'v1.0-prd.md').write_text('# named line', encoding='utf-8')
        legacy = self.history / 'archive'
        legacy.mkdir()
        (legacy / 'v0.9-prd.md').write_text('# legacy history', encoding='utf-8')
        self.assertEqual(['v0.9-prd.md'], [p.name for p in product_validator.history_documents(self.history, (named,))])
        result = validator.Result.empty()
        valid = product_validator.validate_history_review('历史知识回溯：completed\n历史来源：harness/history/地质工作台/v1.0-prd.md',
                                                  self.history, result, self.cycles / 'v1.2/product/v1.2-prd.md',
                                                  project_root=self.project, excluded_roots=(named,), strict_references=True)
        self.assertFalse(valid)


class AssetRegistryTest(unittest.TestCase):
    setUp = ProductLineCycleTest.setUp
    tearDown = ProductLineCycleTest.tearDown

    def registry(self, **updates):
        self.a = self.cycles / 'A-v1.0'
        self.b = self.cycles / 'B-v1.0'
        self.a.mkdir(exist_ok=True)
        self.b.mkdir(exist_ok=True)
        self.doc = self.history / 'B/v0.9-prd.md'
        self.doc.parent.mkdir(exist_ok=True)
        self.doc.write_text('fixed source', encoding='utf-8')
        self.proto = self.cycles / 'shared-prototype'
        self.proto.mkdir(exist_ok=True)
        (self.proto / 'index.html').write_text('<html>prototype</html>', encoding='utf-8')
        data = {'schemaVersion': 1, 'prototypes': [],
            'historyImports': [{'cycle': 'A-v1.0', 'path': self.doc.relative_to(self.project).as_posix(),
                                'hashMode': 'raw', 'sha256': hashlib.sha256(self.doc.read_bytes()).hexdigest(),
                                'rationale': 'Reuse component structure', 'boundaries': 'No product scope inheritance'}]}
        data.update(updates)
        self.registration = self.project / self.config.service_catalog.parent / 'asset-registry.yaml'
        self.registration.parent.mkdir(parents=True, exist_ok=True)
        self.write_registry(data)
        return data

    def write_registry(self, data):
        self.registration.write_text(yaml.safe_dump(data), encoding='utf-8')

    def load(self):
        result = validator.Result.empty()
        return validator.load_asset_registry(self.project, self.config, result), result

    def review(self, reference, cycle='A-v1.0', status='completed'):
        assets, result = self.load()
        line = cycle.split('-')[0]
        valid = product_validator.validate_history_review(
            f'历史知识回溯：{status}\n历史来源：{reference}', self.history / line,
            result, self.cycles / cycle / 'product/v1.0-prd.md',
            project_root=self.project, strict_references=True,
            imported_documents=assets.history_imports.get(cycle, ()))
        return valid, result

    def test_optional_registry_preserves_default_discovery(self):
        self.registry()
        self.registration.unlink()
        result = validator.Result.empty()
        validator.discover_demand_cycles(self.project, self.config, result)
        self.assertTrue(any('shared-prototype' in e for e in result.errors))


    def test_only_exact_reference_gets_cycle_scoped_permission(self):
        self.registry()
        reference = self.doc.relative_to(self.project).as_posix()
        valid, result = self.review(reference)
        self.assertTrue(valid, result.errors)
        for ref in ('v0.9-prd.md', reference.replace('/B/', '/B/../B/'), reference.replace('/', '\\')):
            with self.subTest(ref=ref):
                valid, result = self.review(ref)
                self.assertFalse(valid)
                self.assertTrue(result.errors)
        (self.cycles / 'C-v1.0').mkdir()
        valid, result = self.review(reference, 'C-v1.0')
        self.assertFalse(valid)
        self.assertTrue(result.errors)
        other = self.doc.with_name('v0.8-prd.md')
        other.write_text('other', encoding='utf-8')
        self.assertFalse(self.review(other.relative_to(self.project).as_posix())[0])

    def test_import_without_local_history_requires_completed_explicit_source(self):
        self.registry()
        valid, result = self.review('none', status='greenfield-skipped')
        self.assertFalse(valid)
        self.assertTrue(result.errors)

    def test_unknown_schema_keys_duplicate_yaml_and_duplicate_items_fail_closed(self):
        for change in ({'schemaVersion': 2}, {'schemaVersion': True}, {'extra': []}):
            self.registry(**change)
            assets, result = self.load()
            self.assertFalse(assets.valid)
            self.assertTrue(result.errors)
        data = self.registry()
        data['historyImports'] *= 2
        self.write_registry(data)
        self.assertFalse(self.load()[0].valid)
        data = self.registry()
        data['prototypes'] = [{'path': 'old-prototype'}]
        self.write_registry(data)
        self.assertFalse(self.load()[0].valid)
        self.registration.write_text('schemaVersion: 1\nschemaVersion: 1\nprototypes: []\nhistoryImports: []\n', encoding='utf-8')
        self.assertFalse(self.load()[0].valid)

    def test_invalid_import_paths_missing_files_and_hashes_are_hard_errors(self):
        for bad in ('../outside.md', '/absolute.md', 'C:/outside.md', '.harness/history/B/../B/v0.9-prd.md',
                    '.harness/history/B/missing.md', '.harness/history/B/v0.9-prd.md '):
            data = self.registry()
            data['historyImports'][0]['path'] = bad
            self.write_registry(data)
            self.assertFalse(self.load()[0].valid, bad)
        self.registry()
        self.doc.write_text('changed source', encoding='utf-8')
        self.assertFalse(self.load()[0].valid)
        data = self.registry()
        data['historyImports'][0]['cycle'] = 'unknown-v1.0'
        self.write_registry(data)
        self.assertFalse(self.load()[0].valid)


    def test_explicit_text_hash_accepts_only_utf8_markdown_line_endings(self):
        data = self.registry()
        item = data['historyImports'][0]
        item['hashMode'] = 'text-lf'
        item['sha256'] = hashlib.sha256(b'line one\nline two\n').hexdigest()
        self.write_registry(data)
        for content in (b'line one\nline two\n', b'line one\r\nline two\r\n'):
            self.doc.write_bytes(content)
            self.assertTrue(self.load()[0].valid)
        for changed in (b'changed line\nline two\n', b'line one\nline two', b'\xef\xbb\xbfline one\nline two\n', b'line one\rline two\n'):
            self.doc.write_bytes(changed)
            self.assertFalse(self.load()[0].valid)
        self.doc.write_bytes(b'\xff\n')
        self.assertFalse(self.load()[0].valid)

    def test_raw_hash_rejects_line_ending_changes_and_binary_text_mode(self):
        data = self.registry()
        item = data['historyImports'][0]
        self.doc.write_bytes(b'raw\n')
        item['sha256'] = hashlib.sha256(self.doc.read_bytes()).hexdigest()
        self.write_registry(data)
        self.doc.write_bytes(b'raw\r\n')
        self.assertFalse(self.load()[0].valid)
        pdf = self.doc.with_suffix('.pdf')
        pdf.write_bytes(b'raw\n')
        item.update(path=pdf.relative_to(self.project).as_posix(), hashMode='text-lf')
        self.write_registry(data)
        self.assertFalse(self.load()[0].valid)
        item['hashMode'] = 'unknown'
        self.write_registry(data)
        self.assertFalse(self.load()[0].valid)
        del item['hashMode']
        self.write_registry(data)
        self.assertFalse(self.load()[0].valid)


class CurrentProtocolBoundaryTest(unittest.TestCase):
    def test_config_accepts_only_schema20_without_mutating_input(self):
        template = Path(__file__).parents[2] / "project-harness-template/.harness/harness.yaml"
        data = yaml.safe_load(template.read_text(encoding="utf-8"))
        data["core"].update(revision="a" * 40, contentHash="b" * 64)
        data["project"].update(id="example", name="示例")
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "harness.yaml"
            for schema in (20, 19, 18, True, "20"):
                with self.subTest(schema=schema):
                    data["schemaVersion"] = schema
                    original = yaml.safe_dump(data, allow_unicode=True).encode()
                    config_path.write_bytes(original)
                    result = validator.Result.empty()
                    parsed = validator.parse_config(config_path, result)
                    self.assertEqual(schema == 20 and type(schema) is int, parsed is not None)
                    self.assertEqual(original, config_path.read_bytes())
                    if parsed is None:
                        self.assertTrue(result.errors)
            data["schemaVersion"] = 20
            data["product"]["mock"] = "mock"
            config_path.write_text(yaml.safe_dump(data), encoding="utf-8")
            result = validator.Result.empty()
            self.assertIsNone(validator.parse_config(config_path, result))
            self.assertTrue(result.errors)

    def test_old_project_root_is_rejected(self):
        from local_paths import project_config_path
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            atomic_write(root / "harness/harness.yaml", "schemaVersion: 19")
            with self.assertRaisesRegex(ValueError, "只支持"):
                project_config_path(root)
            atomic_write(root / ".harness/harness.yaml", "schemaVersion: 20")
            with self.assertRaises(ValueError):
                project_config_path(root)

    def test_api_document_and_api_plan_reject_older_protocols(self):
        for version in ("v2", "v3", "v4", ""):
            result = validator.Result.empty()
            text = VALID_V5_DOCUMENT.replace("`v5`", f"`{version}`")
            self.assertFalse(backend_validator._validate_api_document_v5(text, "backend-app", result))
            self.assertTrue(any("仅支持" in error for error in result.errors))
        result = validator.Result.empty()
        self.assertFalse(backend_validator._validate_frontend_api_plan_page_demand_v3(
            VALID_V3_PLAN.replace("page-demand-v3", "page-demand-v2"), "frontend-app", result))
        self.assertTrue(result.errors)

    def test_discovery_rejects_old_cycle_mock_path(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "discovery.md"
            atomic_write(path, discovery_text().replace("原型仓库/index.html", "mock/a/index.html"))
            result = validator.Result.empty()
            self.assertFalse(product_validator.validate_discovery(path, result).valid)
            self.assertTrue(any("原型仓库" in error for error in result.errors))

    def test_backend_plan_rejects_combined_old_decision_section(self):
        text = "## 9. 待确认事项\n\n- 无待决业务语义：PRD:REQ-001 已确认。\n"
        result = validator.Result.empty()
        self.assertFalse(backend_validator._plan_pending_items_closed(text, "backend-app", result))
        self.assertTrue(result.errors)


if __name__ == "__main__":
    unittest.main()
