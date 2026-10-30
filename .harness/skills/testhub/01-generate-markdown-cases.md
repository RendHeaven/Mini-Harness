---
name: generate-testhub-markdown-cases
description: 当研发 研发证据检查 检查完成后使用；读取当前需求版本可用上下文，生成可追溯的 TestHub Markdown 测试用例文档。缺少需求、Plan 或 Task 不阻断生成，但必须如实记录缺口。
---

# 生成 TestHub Markdown 用例

## Objective

从当前需求版本的真实上下文生成完整 `cases.md`，每个用例映射 TestHub Excel v3 的字段语义，并声明实际参考来源与信息缺口。

## Inputs

- 产物相对[工作流](../../workflow/testhub-workflow.md#阶段执行)指定的阶段根。
- 文档遵循[时间规范](../../rules/document-timestamps.md)。
- 当前版本的 PRD、Dev Guide、UI Handoff、前后端 Plan、Task、接口文档和 `develop/execution.yaml`。
- `change-impact-analysis.md`、`test-design.md` 与 `coverage-matrix.md`；三者定义代码影响范围、测试方法、风险、边界、可执行性和未覆盖原因。
- `.harness/projectContext/testhub.yaml` 中的非敏感稳定标识；若缺失，仍生成文档并在报告中标记待配置。
- `rules/testhub-markdown-v1.md` 与 `template/develop/testhub/cases-template.md`。

## Workflow

1. 在当前版本目录中查找并读取可用的需求、Plan、Task 与辅助上下文；对每个候选文件记录相对路径、SHA256、状态和使用目的。
2. 先读取变更影响分析、测试设计和覆盖矩阵。每个 `direct-change`、`indirect-impact`、`unchanged-regression` 的 `IMP-*` 必须生成或引用回归用例；无事实或不可执行时保留具名 GAP，不得为了满足覆盖数量而生成猜测用例。
3. 仅根据已读取事实提取模块、页面、可见字段、角色、权限、业务主键、正向/边界/异常场景和可观察断言。
4. 按 [TestHub 文档结构](../../rules/testhub-markdown-v1.md#文档结构)和模板生成完整 `cases.md`。
5. 按 [TestHub 字段与安全规则](../../rules/testhub-markdown-v1.md#字段与安全规则)写入影响、设计方法、来源及自动化缺口。
6. 对 Fixture、变量、清理和 Mock 使用 v3 契约；没有足够事实时在备注中说明缺口并避免生成依赖猜测的正式用例。
7. 生成 `generation-report.md`，记录状态、文档 SHA256、当前 Git revision、参考文件、缺失来源、用例数和未覆盖原因。

## Decision rules

- 稳定 ID、完整集合、Fixture/Mock、数据安全与正式用例适用性遵循 [TestHub 规则](../../rules/testhub-markdown-v1.md)。
- 不得因任一上下文缺失而停止文档生成；不得用虚构事实填充缺失上下文。

- 每个 REQ 在覆盖矩阵中至少声明功能、异常、权限和设计方法的覆盖状态；安全、性能、并发、SQL/指标按适用性声明，不适用必须给出事实依据。
- 未改功能的回归用例必须与直接改动用例一同进入完整 `cases.md`，不能以“未改”或“历史已有”作为省略当前文档的理由。

## Output contract

输出 `cases.md` 和 `generation-report.md`。文档必须列出实际参考和未参考上下文；无正式用例时仍输出结构完整的 `generated-with-gaps` 文档，供后续补充，不得伪造用例。
