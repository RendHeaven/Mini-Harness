---
name: summarize-bug-cycle
description: 当一轮 Bug 修复结束时使用；汇总状态、共性根因、漏检原因和可执行改进措施。
---

# Bug 汇总与漏检复盘

## Objective

确认修复闭环，并把可复用改进返回测试、规则或服务工程实践。

## Inputs

- 必需：本轮 Bug 记录、最终服务 revisions 和验证证据。
- 可选：Review、TestHub 同步记录和线上反馈。

## Workflow

1. 汇总数量、状态和跨服务影响。
2. 分类共性根因与此前漏检原因。
3. 形成有负责人和验证方式的改进措施。

## Decision rules

- 未验证或没有最终 revision 的 Bug 不得关闭。
- 通用改进进入 Core，服务专有改进留在服务仓库。

## Output contract

更新本轮汇总，列明关闭项、遗留风险和后续动作。
