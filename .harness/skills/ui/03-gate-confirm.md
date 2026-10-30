---
name: ui-gate-confirm
description: UI Gate 确认时使用。
---

# UI Gate 确认

## Objective

UI Gate 确认，保留实际来源和操作证据。

## Inputs

原型、调整文档、浏览器验证及真实 UI 负责人确认。

## Workflow

1. 检查自身证据，进入 pending_confirmation。
2. 负责人明确确认后，用 role_gates.py --role ui --status confirmed 记录。
3. 再次调整时重新进入工作，追加改动记录并保留旧确认及其已覆盖范围。

## Decision rules

确认遵循 [Gate 协议](../../rules/review-gates.md)（含确认者 Git 身份）；文档遵循[时间规范](../../rules/document-timestamps.md)。

## Output contract

ui Gate 独立记录；产品意见可作为证据，产品 Gate 不是确认条件。
