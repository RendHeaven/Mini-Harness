---
name: frontend-workflow
description: 用户已选择前端角色时使用；按前端流程完成真实页面、接口接入、Review 和确认，职责不清时询问角色归属，不自动切换。
---

# 前端研发工作流

## 触发条件

- 用户已选择前端角色，或会话中已确定当前为前端角色时，按本流程执行。
- 本角色内可实现实际应用页面、接入接口、审查代码和确认交付。出现缺陷、Mock 或原型相关内容时，仍按当前角色判断可执行范围，不自动改用其他 workflow。
- 角色沿用与切换遵循[角色执行约定](../rules/project-execution.md#角色执行)。

## 职责与输入

负责页面工程化、接口接入、前端质量检查和测试交接。必需需求输入为 PRD 与项目静态原型；同时读取目标服务的 AGENTS、真实工程、服务目录和可用的结构化接口文档。Dev Guide、UI Handoff 为可选补充，不替代两项需求输入。

`execution.yaml` 的 frontend.sources 记录本角色已消费的来源路径和变更引用。实现要求由阶段 Skill 读取 `rules/frontend-engineering.md`，可见性要求读取 `rules/ui-standard.md`；不等待其他角色 Gate。

## 阶段执行

当前周期由项目配置 `project.demandCycleRoot` 与完整周期标识定位；下述目录字段取自同一配置。

按服务分别执行；表中产物相对当前周期 `<development.root>/<development.frontend>/<service-id>/`（默认 `develop/frontend/<service-id>/`），Gate 除外。可从指定阶段进入，先核对已有输入；缺口不阻止无依赖工作，但不得伪报完成。

| 阶段 | Skill | 主要产物 | 完成标准 |
| --- | --- | --- | --- |
| UI 计划 | `skills/frontend/01-ui-plan.md` | `1-ui-plan/plan-overview.md`、`plan-编号.md` | 按页面明确样式、交互、路由、权限、复用与 TASK 验收 |
| UI 实现 | `skills/frontend/02-ui-exec.md` | `2-ui-exec/exec-编号.md`、服务代码 | 每个已执行 PLAN 有记录，实际构建和浏览器验证结果完整 |
| API 计划 | `skills/frontend/03-api-plan.md` | `3-api-plan/plan.md` | 页面动作与结构化接口逐项对应，接口、字段、语义和外部契约缺口已分类 |
| API 实现 | `skills/frontend/04-api-exec.md` | `4-api-exec/task.md`、`exec.md`、服务代码 | 真实联调覆盖状态、权限、异常，TASK 与证据可追溯 |
| 独立 Review | `skills/frontend/05-review.md` | `5-review/review.md` | 实现和测试经独立审查，开放风险按 Review 规则处理 |
| 测试养料 | `skills/frontend/06-test-feed.md` | `6-test-feed/front-feed.md` | 页面、状态、权限、视觉与回归盲区已交接 |
| 前端 Gate 确认 | `skills/frontend/07-gate-confirm.md` | `Gate.yaml` 当前周期 frontend 记录 | 自身适用服务交付检查完成，负责人明确确认，时间、Git 身份和来源证据完整 |

只有范围确实无页面改动时，UI 阶段可标记不适用并填写 uiScopeReason；不能以产品或 UI 已写真实前端代码为跳过依据。

## 写入边界

业务代码、长期接口消费定义和构建事实写入已定位的前端服务；跨仓前先读取目标仓库规则。阶段记录和 Execution 的本角色事实写回项目 Harness，不将服务源码放入原型仓库或 Harness。

后端持有的正式接口契约只读取和反馈，不自行篡改；Harness 保存契约引用。Mock 不能替代真实联调或生产构建证据。仅更新自身 Gate；执行 `rules/review-gates.md`、`rules/document-timestamps.md`。

## 问题处理与结束

- 页面实现、计划和 TASK 的偏差在当前前端流程内修正。涉及业务定义、原型事实或后端契约的职责问题，记录差异并主动询问本次应以哪个角色处理。
- 正式接口未匹配时可读取真实实现证据，但不虚构字段、不把 TDD 基线当成最终接口文档，也不自行改写其他角色持有的事实。
- 来源变化时复核受影响产物，可继续不受影响工作；不一致的联调不得写成通过。
- 单阶段请求完成相应产物后结束；完整交付在前端 Gate 明确确认后结束。测试养料作为本角色产物保存，不自动进入测试流程、同步远程用例或发布。
