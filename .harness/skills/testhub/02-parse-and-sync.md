---
name: parse-and-sync-testhub-markdown
description: 当需要校验或同步已有 TestHub Markdown 用例时使用；按任务范围保存同步回执，用户明确要求运行时才执行、查询或重试。
---

# 解析并同步 TestHub Markdown 用例

## Objective

校验 `cases.md`，生成 metadata 并将完整 Markdown 文件上传到 TestHub；保存可审计、脱敏的同步结果。

## Inputs

- 产物相对[工作流](../../workflow/testhub-workflow.md#阶段执行)指定的阶段根。
- 文档遵循[时间规范](../../rules/document-timestamps.md)。
- `cases.md` 与 `generation-report.md`。
- `.harness/projectContext/testhub.yaml` 的基地址、稳定 ID、环境与可选回调地址；Harness 生命周期接口无需 TestHub 账号、密码或 Token。
- `rules/testhub-markdown-v1.md`、`template/develop/testhub/sync-metadata-template.json` 和 `template/develop/testhub/sync-report-template.md`。

## Workflow

1. 将 Markdown 解析为文档级 metadata 和用例级字段；验证固定标题、case ID 唯一、JSON、变量闭环、Fixture、Mock 和清理策略。
2. 写入不含 Secret 的 `sync-metadata.json`。无正式用例时写入 `sync-report.md` 的 `skipped-no-cases`，停止上传。
3. 使用 `tools/sync_testhub_markdown.py sync --upload` 上传完整 `.md` 文件与 metadata JSON。
4. 按同步规则区分同次重试与新请求，记录幂等键及重放结果。
5. 写入 `sync-report.md`：文件 SHA256、幂等键、project/version/task/import/case-set/revision ID、数量、blocked 原因、changes 和脱敏错误摘要。
6. 使用 `query-import`、`query-projects` 查询导入与 Harness 项目；只在用例或页面证据变更后调用 `generate-assets`。用户明确要求执行时，使用回执中的 `case_set_id`、`case_set_revision_id` 调用 `run`；保存 `run_id`，以回调为主、`query-run` 为兜底查询。仅 `202` 不代表已启动，必须检查 `execution_started` 与运行状态。
7. Run 进入终态后记录汇总和 `case-executions` 明细；只对失败或阻塞用例调用 `retry-failed`。文档被删除时使用 `delete-document`，并为删除生成新的幂等键。

## Decision rules

文档完整性、匿名访问、幂等、回调与保密约束统一遵循 [TestHub 同步规则](../../rules/testhub-markdown-v1.md#同步规则)；工具调用按上述步骤执行。

## Output contract

输出 `sync-metadata.json` 和 `sync-report.md`；按同步规则分别记录导入统计、真实阻塞与按需执行的终态结论。
