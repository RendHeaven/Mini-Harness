---
name: build-prd
description: 当需要从已记录的产品事实生成 PRD，或因业务规则、流程与验收条件变化修订原 PRD 时使用；每次修改追加时间戳追踪。
---

# 生成或修订 PRD

## Objective

生成或修订 PRD，保留实际来源和操作证据。

## Inputs

Discovery、项目原型、真实反馈、历史知识、[产品事实与修订规则](../../rules/product-semantics-and-traceability.md)和 [PRD 模板](../../template/product/prd-template.md)。

## Workflow

1. 按[PRD 模板](../../template/product/prd-template.md)组织 Markdown 正文。
2. 保留 HYP/反馈 → accepted DEC → REQ；每个 REQ 含五维需求说明表、适用的结构化详细需求、影响和验收。不造事实。
3. 首次完成后调用 tools/prd_revision.py --prd <绝对路径> --init --actor <实际主体> 开始追踪并建立索引，不复制正文，不表示定稿、封板或产品已确认。
4. 后续先在独立临时文件准备新正文，再使用 --prd <路径> --content <新正文> --actor <主体> --reason <原因> --impact <REQ与影响>。修订证据按[PRD 修订规则](../../rules/product-semantics-and-traceability.md#prd-修订)保存。
5. pending-revision.json 表示 incomplete；检查现场后用 --recover 恢复，第三方已改正文时不得覆盖。
6. 更新受影响原型和派生文档，记录待同步事项。完整产品流程继续进入[产品确认](gate-confirm.md)并自动开展反问；若用户只要求生成或修订 PRD，则交付当前结果后结束，不自动进入确认或反问。

## Decision rules

写入范围见[原型边界](../../rules/project-execution.md#原型写入边界)，文档遵循[时间规范](../../rules/document-timestamps.md)。

## Output contract

当前 PRD、prd-changelog.md、prd-changes/revisions.yaml（Schema 2）和每次 CHG 的说明及局部 diff；不生成 baseline/before/after 全文副本。证据维护遵循上述修订规则。
