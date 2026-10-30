---
name: ui-adjustment-document
description: 生成 UI 调整文档时使用。
---

# 生成 UI 调整文档

## Objective

生成 UI 调整文档，保留实际来源和操作证据。

## Inputs

原型差异、adjustment-log.md、PRD、template/ui/adjustment-template.md。

## Workflow

1. 新增 UI-ADJ 编号。
2. 汇总页面、REQ、前后内容、规则依据、文件、来源路径、已消费 CHG 和验证。
3. 写入 ui/adjustments/UI-ADJ-*.md，保留秒级创建及编辑记录；每次新的原型调整生成独立 UI-ADJ 文档，Gate 引用该轮具体路径。
4. 更新 ui/ui-handoff.md 最新入口、文档链接和问题，不覆盖历史事实。

## Decision rules

写入范围见[原型边界](../../rules/project-execution.md#原型写入边界)，文档遵循[时间规范](../../rules/document-timestamps.md)。

## Output contract

逐轮调整文档及最新 Handoff，随后进入 UI Gate 确认。
