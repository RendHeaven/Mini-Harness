# PRD 修订索引

通过 prd_revision.py 开始追踪并追加记录，保存实际创建/编辑时间、时区和 CHG 文档链接。
机器索引位于 prd-changes/revisions.yaml（Schema 2），每次保存改动原因、影响和局部 diff，不保存 baseline/before/after 全文副本。首次追踪不表示定稿、封板或 Gate 确认。
