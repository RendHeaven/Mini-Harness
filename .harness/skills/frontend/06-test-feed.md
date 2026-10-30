---
name: prepare-frontend-test-feed
description: 当前端 Review 检查完成后使用；Review 告警不阻止执行。汇总页面层级、交互、状态、权限、视觉与公共组件回归盲区，供 TestHub Workflow 生成最终用例。
---

# 前端测试养料

## Objective

把已 Review 的前端事实整理为可追溯 TestHub 输入，不直接替代测试用例或测试结论。

## Inputs

- 产物相对[工作流](../../workflow/frontend-workflow.md#阶段执行)指定的阶段根。
- 文档遵循[时间规范](../../rules/document-timestamps.md)。
- 必需：PRD、结构化接口文档、前端 plan/exec/review、真实页面、`rules/ui-standard.md` 和 `rules/frontend-engineering.md`。
- 可选：Dev Guide、UI Handoff；存在时补充测试线索，不作为测试养料前置条件。
- Review 结论为 blocked/failed 或来源失效时记录告警，基于可用真实事实继续生成测试养料，不补造覆盖或通过结论。

## Workflow

1. 按 REQ 汇总角色、入口、页面、弹层、返回路径和跨页面联动。
2. 记录条件渲染、权限、表单、加载、空、异常、刷新和恢复。
3. 按 UI 规则记录尺寸、滚动、分页可见性、图表空态和视觉盲区；按工程规则记录公共组件与实现回归风险。
4. 引用结构化接口文档的接口锚点和 Review 盲区，不复制后端内部实现。
5. 使用 front-feed 模板生成最终产物并核对 REQ 覆盖。

## Decision rules

- 不包含 SQL、Feign、缓存、消息等后端内部细节。
- 不把开发自测写成 TestHub 测试已通过。
- 页面或 Review 变化后标记旧养料失效并告警，应重新生成；告警不阻止后续 TestHub 检查。

## Output contract

输出 `6-test-feed/front-feed.md`；TestHub Workflow 可据此生成前端场景与回归风险的可追溯用例。
