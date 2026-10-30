---
name: product-mock
description: 在已确定的产品角色中开展需求探索和静态原型制作时使用；职责模糊时询问用户角色归属，不自动切换。
---

# 产品 Mock

## Objective

产品 Mock，保留实际来源和操作证据。

## Inputs

需求、项目上下文、既有 PRD、项目原型与 template/product/discovery-template.md。

## Workflow

1. 定位需求文档所属周期，读取项目根原型仓库，仅项目首次使用时初始化。
2. 读取 rules/ui-standard.md，在 product/mock-changelog.md 追加唯一 CHG 条目与同名可引用锚点（如 CHG-001），记录时间、页面、改动计划和 UI 规则依据；完成后补齐原因、实际修改文件、影响与验证，不覆盖旧条目。
3. 生成或修改 HTML/CSS/JavaScript、资源和 Mock 数据，不依赖真实后端。
4. 浏览器检查主路径和适用的加载、空、失败、权限、禁用状态，补齐实际变更和证据。
5. Discovery 记录 HYP、真实反馈及待确认事项，不把假设写成产品承诺。

## Decision rules

写入范围见[原型边界](../../rules/project-execution.md#原型写入边界)，文档遵循[时间规范](../../rules/document-timestamps.md)。

## Output contract

项目原型、discovery.md、mock-changelog.md。周期只组织文档，不组织原型代码。

不得读取 `rules/frontend-engineering.md`。
