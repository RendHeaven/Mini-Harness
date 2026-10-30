---
name: record-bug-root-cause
description: 当项目出现可复现缺陷时使用；定位受影响服务和根因并维护项目级 Bug 记录，不提前修改实现。
---

# Bug 记录与根因定位

## Objective

把错误信息转换为可复现、可追溯到服务和 revision 的根因记录。

## Inputs

- 阶段根按 [Bugfix 工作流](../../workflow/bugfix-workflow.md#阶段执行)解析。
- 必需：错误信息、预期行为依据、完整周期标识（纯版本或产品线加版本）、服务目录和相关服务上下文。
- 条件输入：日志、截图、接口响应和可复现环境。

## Workflow

1. 复现或用代码与证据证实问题。
2. 记录受影响服务、基础 revision、根因、产品影响和拟验证范围。
3. 未确认根因时保持记录状态为 investigating。

## Decision rules

- 不把猜测写成根因。
- 跨服务问题分别记录所有者和调用方。
- 不复制服务实现事实到项目 Harness。

## Output contract

更新 阶段根下的 `bug-list.md`，包含稳定 Bug ID、复现、根因、服务和 revision。
