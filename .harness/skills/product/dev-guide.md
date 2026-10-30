---
name: enhance-prd-with-development-guide
description: 当需要把当前版本化 Markdown PRD 派生为开发指导时使用；生成与 Markdown PRD 同源的 dev-guide.md。不要决定产品事实、依赖代码质检报告、推进 Manifest phase 或进入研发实现。
---

# 开发指导

## Objective

将 `product/<版本号>-prd.md` 派生为 `product/dev-guide.md`，保持完全相同的 `REQ-*` 集合并记录当前 Markdown 文件 SHA256。

## Inputs

- 必需：有效 Manifest、按真实状态保留待确认项和占位符检查结果的版本化 Markdown PRD、开发指导模板。
- 默认：只展开 PRD 中真实适用的规则；不适用内容写 `none`。PRD Review 存在时仅作风险参考，不写成新的产品事实。
- 告警：历史回溯无结论或仍有待确认项时保留真实状态并继续可执行内容，不得补造产品事实。PRD 编码或文件名等结构错误仍需先修正。

## Workflow

1. 校验 Markdown PRD 的 UTF-8 编码、版本化文件名、REQ、历史回溯、accepted 决策追溯和待确认项。
2. 按 REQ 完整整理 PRD 已写明的结构化详细需求（五维需求说明与已有操作流程/数据流转/字段/校验/异常等表或图）与逐条验收映射；只重组正向产品事实，不补造排除项，不把表拆成散文。
3. 计算当前 Markdown 文件 SHA256，写入 `product/dev-guide.md`。
4. 确认开发指导与 PRD 的 REQ 集合完全一致，并引用 `<版本号>-prd.md（REQ-*）`。
5. 运行 validator 验证同源关系；PRD 变化时重新执行本支线。本支线不执行 产品内容检查，也不修改 Manifest phase。

## Decision rules

- 开发指导只重组产品事实，不决定框架、接口、数据库、模块拆分或排期。
- 产品内容检查 在生成 PRD 主线完成；本支线只提供下游 UI、研发与 TestHub 所需的同源派生产物。
- Word 导出不是本步骤输入；同源、失效与回流见 `rules/product-semantics-and-traceability.md`。

## Output contract

交付 `product/dev-guide.md`、覆盖的 REQ、PRD SHA256 与同源检查结果，并确认 Manifest phase 未被本支线改变。
