---
name: ui-design-workflow
description: 用户已选择 UI 角色时使用；按 UI 流程完成静态原型调整、调整文档和确认，职责不清时询问角色归属，不自动切换。
---

# UI 静态原型工作流

## 触发条件

- 用户已选择 UI 角色，或会话中已确定当前为 UI 角色时，按本流程执行。
- 本角色内可调整原型视觉、布局、样式和交互表现，生成调整文档并进行 UI 确认；不因请求中出现业务或前端词语自行切换角色。
- 角色沿用与切换遵循[角色执行约定](../rules/project-execution.md#角色执行)。

需要从已有前端补建缺失原型时，进入 [已有页面原型补建](prototype-reconstruction-workflow.md)；该支线允许从现状证据启动，不要求先有 PRD。常规调整仍遵循以下输入。

## 职责与输入

负责把已明确需求的静态原型调整到 UI 规则要求，并提供可复核的调整记录。输入为 PRD、项目根原型仓库和 `rules/ui-standard.md`。缺少业务定义时先记录并询问角色归属；不等待产品或研发 Gate。

## 阶段执行

唯一主线：调整 → 生成调整文档 → UI Gate 确认。可根据已有产物单独进入文档或确认阶段。

| 阶段 | Skill | 主要产物 | 完成标准 |
| --- | --- | --- | --- |
| 调整 | `skills/ui/01-static-prototype.md` | 项目原型、`ui/adjustment-log.md` | 修改依据 UI 规则，逐项记录改动，浏览器验证与实际结果完整 |
| 生成调整文档 | `skills/ui/02-adjustment-document.md` | `ui/adjustments/UI-ADJ-*.md`、`ui/ui-handoff.md` | 汇总前后差异、规则依据、影响文件、验证证据与遗留问题 |
| UI Gate 确认 | `skills/ui/03-gate-confirm.md` | `Gate.yaml` 当前周期 ui 记录 | 自身调整证据完整，实际负责人明确确认；时间、Git 身份和来源证据完整 |

## 写入边界

代码权限与原型共用方式见[原型写入边界](../rules/project-execution.md#原型写入边界)；UI 文档写入当前周期配置的 `ui.root`。

不读取前端工程实现规则。外部设计工具可选，以本地可预览原型为交付。仅更新自身 Gate 和来源证据，执行 `rules/review-gates.md`、`rules/document-timestamps.md`。

## 问题处理与结束

- 发现业务规则、权限语义或验收条件不明确时，记录问题并询问本次应以哪个角色处理；答复前不修改有争议的业务定义。
- 实际应用实现问题保留为缺口，不自动切换角色或修改服务代码。UI 角色内的样式和原型验证问题在本流程修正。
- 单阶段请求完成相应产物后结束；完整交付在 UI Gate 明确确认后结束。来源变化由本角色复核，不重置其他 Gate。
