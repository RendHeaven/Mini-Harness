---
name: review-frontend-delivery
description: 当前端 ui/api 实现与自测完成检查时使用；上游未完成项或失败形成告警但不阻止 Review。独立审查 PRD、结构化接口文档、实现和测试的一致性；Dev Guide、UI Handoff 仅在存在时纳入交叉核对。
---

# 前端独立 Review

## Objective

以独立视角检查页面、状态、权限、接口、竞态、视觉、可维护性和构建质量，形成可定位发现。

## Inputs

- 产物相对[工作流](../../workflow/frontend-workflow.md#阶段执行)指定的阶段根。
- 文档遵循[时间规范](../../rules/document-timestamps.md)。
- 当前来源哈希、适用 plan/exec、结构化接口文档、代码 diff/revision、验证证据、`rules/ui-standard.md` 和 `rules/frontend-engineering.md`。
- 输入缺失或 revision 不一致时记录告警并在真实可见范围内审查，不审猜测内容，也不阻止 Review 检查完成。

## Workflow

1. 建立页面、组件、API、状态、权限和公共调用方索引。
2. 检查实现与 PRD、结构化接口文档的一致性；已有 Dev Guide、UI Handoff 时追加交叉核对。
3. 检查加载/空/异常、竞态、错误恢复、可访问性、视觉和生产构建。
4. 对照 `rules/ui-standard.md` 与 `rules/frontend-engineering.md` 全文审查；对照栏按真实页面重判，上游错误的 `not-applicable` 记为 `issue`。
5. 按 P0/P1/P2 记录位置、证据、影响、修复和验证方法。
6. 修复后重跑聚焦测试、完整构建与相关浏览器场景。

## Decision rules

- P0/P1 未修复或未由真实负责人接受风险时保留真实状态并告警，不伪造接受风险；Review 检查仍完成并允许进入后续阶段。
- Review 不静默改变产品、UI 或接口文档。
- 同一发现保留原记录和复测结论，不删除历史。

## Output contract

输出 `5-review/review.md`；高优发现或回归未闭环时告警并保留真实结论，不阻止进入 test-feed。
