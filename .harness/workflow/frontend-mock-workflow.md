---
name: frontend-mock-workflow
description: 用户在前端角色下明确选择 Mock 流程时使用；完成模拟运行与场景数据，保持当前角色，职责不清时先询问。
---

# 前端 Mock 工作流

## 触发条件

- 用户在前端角色下明确选择 Mock 流程，或会话已确定该流程时进入；“Mock”关键词本身不触发角色或流程切换。
- 本流程处理真实前端的模拟接口、独立启动方式和场景数据；需要其他能力时先记录职责问题。
- 角色沿用与切换遵循[角色执行约定](../rules/project-execution.md#角色执行)。

## 职责与输入

负责前端服务内可显式启动、可维护且与生产隔离的 Mock 运行能力。输入为目标服务 AGENTS、启动脚本、构建与请求配置、目标页面、可用接口契约和场景需求；既有 Mock 必须先盘点。

按阶段 Skill 读取 `rules/frontend-engineering.md`。缺少契约时明确区分已知事实和展示假设；运行时技术选择、启动命令及拦截方式由 Skill 根据工程决定。

## 阶段执行

所有产物属于目标前端服务仓库。每个阶段均可单独进入或复跑，先核对并复用已有产物。

| 阶段 | Skill | 主要产物 | 完成标准 |
| --- | --- | --- | --- |
| 盘点与方案 | `skills/frontend-mock/01-assessment.md` | `docs/mock/mock-plan.md` | 页面、接口范围、运行模式、来源和不模拟的能力明确 |
| 启动基建 | `skills/frontend-mock/02-bootstrap.md` | 显式启动脚本、配置和入口 | Mock 可独立启动，生产模式不加载 |
| 数据源 | `skills/frontend-mock/03-data-source.md` | `src/mocks/` 等工程约定目录内的数据和处理器 | 正常、空、加载、错误及关键边界场景有来源和假设说明 |
| 集成与隔离 | `skills/frontend-mock/04-integration.md` | 拦截、切换守卫和迁移说明 | Mock 与真实 API 显式切换，不静默回落真实环境 |
| 验证与交接 | `skills/frontend-mock/05-verification.md` | `docs/mock/mock-verification.md` | 启动、场景、构建及关闭 Mock 的证据可复核 |

## 写入边界

方案、数据、Runtime 和验证记录写入前端服务；Harness 仅引用服务 revision 和必要摘要，不新增需求周期目录、Execution Track 或第五道 Gate。

不得为了 Mock 修改真实后端、生产网关、正式契约或生产环境。涉及共享配置时按目标项目规则核对影响和已有授权；超出授权范围不继续写入。具体隔离和脱敏规则由阶段 Skill 执行，文档遵循 `rules/document-timestamps.md`。

## 问题处理与结束

- 契约变化或隔离问题，在本流程的数据源、集成与验证阶段处理；Mock 失败不能写成真实联调通过。
- 需求涉及本流程之外的业务实现或其他角色资产时，记录差异并询问本次以哪个角色、哪个流程处理，不自行切换。
- 单阶段请求完成相应产物后结束；完整请求以验证记录和交接材料完成为结束，不新增 Gate，不自动发布或执行远程测试。
