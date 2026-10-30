---
name: backend-workflow
description: 用户已选择后端角色时使用；按后端流程完成设计、实现、测试、接口文档和确认，职责不清时询问角色归属，不自动切换。
---

# Java 后端研发工作流

## 触发条件

- 用户已选择后端角色，或会话中已确定当前为后端角色时，按本流程执行。
- 本角色内可设计和实现接口、业务逻辑、数据处理，完成测试、文档和交付确认。本链路按 Java 工程编排，其他语言不能伪造 Java 工具执行证据。
- 角色沿用与切换遵循[角色执行约定](../rules/project-execution.md#角色执行)。

## 职责与输入

负责后端技术方案、实现、测试、接口文档、Review 和外部配置交接。需求输入为 PRD 与项目静态原型；读取目标服务 AGENTS、工程上下文、现有契约和数据所有权。静态数据不代替接口契约。

Execution 的 backend.sources 记录本角色已消费的来源路径和变更引用。Plan 定义业务与实现方案，外部设计独立产出，实际外部执行证据由 Exec 保留；不等待其他角色 Gate。

## 阶段执行

当前周期由项目配置 `project.demandCycleRoot` 与完整周期标识定位；下述目录字段取自同一配置。

按适用服务执行，产物相对当前周期 `<development.root>/<development.backend>/<service-id>/`（默认 `develop/backend/<service-id>/`），Gate 除外。单独进入阶段时先核对已有事实，不要求机械重跑前序；缺失依赖不能被写成已完成。

| 阶段 | Skill | 主要产物 | 完成标准 |
| --- | --- | --- | --- |
| Plan | `skills/backend/01-plan.md` | `1-plan/plan-overview.md`、适用的模块计划 | 范围、非目标、链路、技术取舍、TASK 和业务验收明确 |
| 外部设计 | `skills/backend/02-external-design.md` | `2-external-design/external-design.md`、设计资产 | 适用外部系统设计齐全，与执行审批和执行证据分开 |
| TDD | `skills/backend/03-tdd.md` | `3-tdd/tdd-overview.md`、`tdd-NN.md`、服务内测试和契约基线 | 与 Plan、外部设计可追溯，基线与测试结果真实 |
| Exec | `skills/backend/04-exec.md` | `4-exec/exec-overview.md`、`exec-NN.md`、服务代码 | TASK 集合与计划一致，完成状态、实现和外部执行事实有证据 |
| 本地接口测试 | `skills/backend/05-local-interface-test.md` | `5-local-interface-test/localTest-overview.md`、模块记录 | 真实接口、边界、权限、异常和数据结果已验证 |
| 接口文档 | `skills/backend/06-interface-document.md` | `6-interface-document/api-document.md`、服务契约记录 | 按阶段 Skill 指定协议生成正文，与最终实现对账 |
| 独立 Review | `skills/backend/07-review.md` | `7-review/review-overview.md`、模块记录 | 适用 REQ 有结构化证据，开放风险按 Review 规则处理 |
| 外部配置清单 | `skills/backend/08-checklist.md` | `8-checklist/checklist.md` | 剩余外部执行或审批事项、责任方和关联 TASK 明确 |
| 后端 Gate 确认 | `skills/backend/09-gate-confirm.md` | `Gate.yaml` 当前周期 backend 记录 | 自身适用服务检查完成，负责人明确确认，时间、Git 身份和来源证据完整 |

## 写入边界

服务代码、长期契约、数据和运行事实由后端服务持有；Harness 保存阶段交付与跨仓引用。各服务分别操作 Git，跨仓写入先读取目标规则，不能凭目录推定服务归属。

外部设计不等于外部系统执行授权；实际执行遵循已有任务授权、项目规则及相应 Skill。接口正文、测试记录和发布事实各自保存，不互相伪装。仅更新自身 Gate，执行 `rules/review-gates.md`、`rules/document-timestamps.md`。

## 问题处理与结束

- Plan、TDD、Exec 与接口定义冲突时，在当前后端流程内修正相应阶段；实现错误在 Exec 修复，契约基线问题在 TDD 修复，外部设计变化由 Plan 复核。
- 产品语义、原型或其他服务角色的职责问题，记录影响并主动询问本次应以哪个角色处理，不自行切换或代改其资产。
- 未闭环失败不能写成通过，不受影响工作可继续。技术细化记录受影响消费者与待办，不因此启动其他角色流程。
- 单阶段请求完成相应产物后结束；完整交付在后端 Gate 明确确认后结束。外部待办不伪称已执行，确认不代表发布或部署。
