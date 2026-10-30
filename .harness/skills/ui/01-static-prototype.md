---
name: adjust-static-prototype
description: 在已确定的 UI 角色中调整项目静态原型时使用；职责模糊或涉及业务含义时先询问角色归属，不自动切换。
---

# 调整静态原型

## Objective

调整静态原型，保留实际来源和操作证据。

## Inputs

PRD、项目原型与 rules/ui-standard.md。

## Workflow

1. 读取现有原型及 UI 规则。
2. 在 ui/adjustment-log.md 追加本轮编号、实际时间、页面、原因、修改文件、影响及规则依据，不覆盖旧改动；进入文档阶段后关联本轮独立 UI-ADJ 路径。
3. 直接调整共用原型的布局、组件、样式与交互表现。
4. 浏览器验证并记录差异、状态、问题；业务含义变化先记录，并询问用户本次按哪个角色处理，不自行修改业务定义。

## Decision rules

写入范围见[原型边界](../../rules/project-execution.md#原型写入边界)，文档遵循[时间规范](../../rules/document-timestamps.md)。

## Output contract

原型修改与逐轮调整记录，随后生成调整文档。

不得读取 `rules/frontend-engineering.md`。
