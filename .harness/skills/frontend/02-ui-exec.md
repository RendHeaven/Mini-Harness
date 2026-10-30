---
name: execute-frontend-ui-engineering
description: 当 ui-plan 检查完成时使用；plan 的 draft、blocked 或其他告警不阻止执行可行部分。把已确认页面方案落入真实前端工程并记录测试、生产构建和浏览器验证的真实结果；不依赖 UI Handoff 或 Dev Guide。
---

# 前端 UI 工程实现

## Objective

按 ui-plan 的页面 PLAN 完成页面样式、交互逻辑、路由和权限实现，并逐页提供可复核工程证据；一个页面 PLAN 对应一个 EXEC 文件。

## Inputs

- 产物相对[工作流](../../workflow/frontend-workflow.md#阶段执行)指定的阶段根。
- 文档遵循[时间规范](../../rules/document-timestamps.md)。
- 必需：当前 `1-ui-plan/plan-overview.md` 和全部 `plan-编号.md`、PRD、项目共用原型、目标前端源码、版本分支、工程命令、`rules/ui-standard.md` 和 `rules/frontend-engineering.md`。
- 可选：UI Handoff、Dev Guide；存在时用于交叉核对，缺失时以 PRD 和 UI Plan 为准。
- 读取项目共用静态原型；来源失效或工程不可运行时记录告警和真实 `blocked` 状态并继续可执行内容。分支错误涉及写入边界时不得擅自切换或在错误分支实现。

## Workflow

1. 按 PLAN 顺序读取其内部 TASK。每开始执行一个 PLAN，先以 `template/develop/frontend/ui-exec-template.md` 创建 `2-ui-exec/exec-编号.md`，并在同一文件内持续追写该 PLAN 的 TASK 状态、实际变更与验证；保护用户已有改动。按 `rules/frontend-engineering.md` §1 做聚焦改动，公共或配置写入前先确认。
2. 复用现有组件、路由、权限、请求层和状态设施完成最小实现。
3. 本页有表格则按工程规则 §4 落地，可见表现按 UI 规则 §4；有图表则按工程规则 §5 与 UI 规则 §4；格式化与空态按工程规则 §6 与 UI 规则 §5。
4. 集中管理临时 Mock，保留生产禁用和后续 API 替换边界。
5. 按真实页面重判对照栏，上游错误的 `not-applicable` 必须推翻。
6. 按 UI 规则的[布局](../../rules/ui-standard.md#2-布局与响应式)、[交互](../../rules/ui-standard.md#3-组件与交互)、[表格与图表](../../rules/ui-standard.md#4-表单表格与图表)及[数据展示](../../rules/ui-standard.md#5-数据展示)要求验证页面；按工程规则 §8 运行聚焦测试，并完成 lint、production build 和真实浏览器检查。
7. 使用 `ui-exec-template.md` 记录变更、偏差、证据和遗留风险。执行证据不得回写 `1-ui-plan/plan-编号.md`，以免计划基线与执行事实混合。

## Decision rules

- 不重新设计已确认页面方案；偏差在当前前端角色内修正 ui-plan；已有 UI Handoff 受影响时记录差异并询问角色归属，不代改其他角色产物。
- Mock、开发服务器或截图不能替代 production build 和真实页面验证。
- 公共组件变化必须扩大调用方回归。

## Output contract

对每个实际开始执行的 PLAN 输出并持续追写 `2-ui-exec/exec-编号.md`（例如 `exec-01.md` 对应 `plan-01.md`），以及真实代码 revision。一个 EXEC 文件只对应一个 PLAN；不得生成全局 `task.md`、`exec.md`，也不得将多个 PLAN 的执行事实混写到同一 EXEC 文件。适用检查未满足时保留失败或 blocked 状态并告警，不伪造通过，且不阻止后续阶段继续检查。
