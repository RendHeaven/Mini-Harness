---
name: export-word-prd
description: 当用户明确要求把已校验的版本化 Markdown PRD 导出为便于阅读或流转的 Word 文件时使用；执行单向等义导出并逐页渲染检查。不要把 Word 作为事实源、反向覆盖 Markdown 或用于任何 Gate。
---

# 导出 Word PRD

## Objective

将当前 `product/<版本号>-prd.md` 单向等义导出为 `product/export/<版本号>-prd.docx`，保留全部产品文字和结构，并记录源 PRD SHA256。

## Inputs

- 必需：用户明确导出指令、已完成 validator 检查的当前 Markdown PRD、`prd-word-template.docx`。
- 来源：PRD SHA256 直接按 Markdown 文件原始字节计算。
- 告警：Markdown PRD 存在质量告警或待确认项时如实保留并允许导出，不得在 Word 中补造结论；无法读取源文件、计算文件哈希或完成 DOCX 渲染检查时记录真实失败，不宣称导出完成。

## Workflow

1. 确认用户显式选择本支线并要求 Word 导出；不得把导出作为产品主线或 产品内容检查 的默认步骤。
2. 校验当前 `product/<版本号>-prd.md`，并按 Markdown 文件原始字节计算源 PRD SHA256。
3. 使用展示模板生成 `product/export/<版本号>-prd.docx`；在文档中记录源 Markdown 相对路径和源 PRD SHA256。
4. 按原顺序转换标题、正文、列表、表格和代码样式；mermaid flowchart 等代码块保留为等义源码块展示，不得删图意、不得改写成与源不一致的叙述。
5. 逐项对照 Markdown，确认没有总结、润色、补充、删减、重排或改变产品语义；展示所需的分页和样式调整不得改变内容。
6. 使用 `render_docx.py` 渲染全部页面，逐页检查文字截断、表格溢出、分页异常和不可读内容；修复后重新渲染，直至检查通过。
7. 报告源 PRD SHA256、输出路径和逐页渲染结果；不修改 Markdown PRD、质检报告、Dev Guide、Manifest 或任何 Gate 状态。

## Decision rules

- Word 是当前 Markdown PRD 的可选展示副本；事实归属见 `rules/product-semantics-and-traceability.md`。
- Word 缺失、损坏、过期或被单独修改，均不影响 产品内容检查～TestHub 检查；只有重新导出才能恢复与当前 Markdown 的同源关系。
- 禁止从 Word 反向覆盖 Markdown，也不得只在 Word 中修正或新增产品内容；内容变化必须先更新 Markdown，再重新质检并重新导出。
- 导出路径固定为 `product/export/<版本号>-prd.docx`，不得写回产品目录根部或替代 `product.prd`。

## Output contract

交付 `product/export/<版本号>-prd.docx`，并说明它对应的源 Markdown、源 PRD SHA256 和逐页渲染检查结果。
