---
name: backend-gate-confirm
description: backend Gate 确认时使用。
---

# backend Gate 确认

## Objective

backend Gate 确认，保留实际来源和操作证据。

## Inputs

PRD、项目原型和自身全部适用服务的实现、Review、测试证据。

## Workflow

1. 核对 backend.sources 和自身服务 finalRevision、契约及阶段产物。
2. 进入 pending_confirmation，记录证据。
3. 真实负责人确认后记录 confirmed、确认人和时间，不读取其他角色 Gate。

## Decision rules

确认遵循 [Gate 协议](../../rules/review-gates.md)（含确认者 Git 身份）；文档遵循[时间规范](../../rules/document-timestamps.md)。

## Output contract

Gate.yaml 中 backend 确认记录及已覆盖变更引用。
