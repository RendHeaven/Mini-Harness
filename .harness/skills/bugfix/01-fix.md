---
name: fix-confirmed-bug
description: 当 Bug 根因已经确认时使用；在受影响服务仓库修复并形成测试、提交和跨仓验证证据。
---

# Bug 修复与验证

## Objective

以最小变更修复已确认根因，并固定每个受影响服务的实现 revision。

## Inputs

- 必需：已确认 Bug 记录、服务目录、服务上下文和基础 revision。
- 条件输入：接口契约、发布顺序和跨服务测试环境。

## Workflow

1. 在服务仓库补充失败测试或可重复验证。
2. 实施最小修复并运行定向与回归测试。
3. 记录最终 commit、契约影响、发布顺序和证据。

## Decision rules

- 产品语义变化先记录并询问用户按哪个角色处理，不自动切换或修改 PRD。
- 契约变化同步通知所有调用方。
- 未提交工作区不能标记修复完成。

## Output contract

服务仓库形成可追溯提交，项目 Bug 记录包含 revision 和验证结论。
