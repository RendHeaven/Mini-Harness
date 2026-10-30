---
name: senior-testhub-test-design
description: 在生成 TestHub Markdown 用例前执行；以资深测试工程师方法建立可追溯的测试设计、风险模型和覆盖矩阵。
---

# 资深测试设计分析

## Objective

以拥有 10 年以上经验的资深测试工程师视角工作，覆盖业务、技术和用户风险。测试设计必须高覆盖、可执行、可自动化；证据不足时如实标记，而不使用猜测替代事实。

## Inputs

- 产物相对[工作流](../../workflow/testhub-workflow.md#阶段执行)指定的阶段根。
- 文档遵循[时间规范](../../rules/document-timestamps.md)。
- 当前版本的 PRD、Dev Guide、UI Handoff、前后端 Plan、TDD、Task、接口文档和 Execution。
- `.harness/projectContext/services.yaml`、服务契约、代码证据和环境配置。
- Execution 中的 TDD baseline、结构化接口文档、对应 Exec 改动文件和可追溯调用关系；有历史测试用例时读取相关版本用例作为回归场景候选。
- `rules/testhub-markdown-v1.md`、`template/develop/testhub/change-impact-analysis-template.md`、`template/develop/testhub/test-design-template.md`、`template/develop/testhub/coverage-matrix-template.md`。

## Workflow

1. 记录每个上下文来源、SHA256、适用 REQ 和可用程度；区分产品事实、实现事实与待确认事项。
2. 以 Plan、TDD、Exec 和结构化接口文档的变更汇总建立 `change-impact-analysis.md`：定位改动文件、接口/数据/消息契约与前后端调用链；标出直接改动、间接受影响和未改但必须回归的功能。没有差异或调用链证据时记录 `blocked`，不得猜测影响范围。
3. 对每个 `IMP-*` 反查业务功能、页面、接口、权限、数据状态和外部依赖，并映射 REQ、历史回归场景或具名 GAP。共享 Service/Mapper、接口封装、路由、公共组件、权限拦截、数据表或消息消费者均须评估为潜在未改回归点。
4. 对每个 REQ 及受影响功能建立业务主流程、备选流程、异常流程、角色/资源权限、数据状态和外部依赖图。
5. 使用等价类划分、边界值分析、场景法、状态转换法、错误推测法；多条件业务规则使用判定表，多个独立因子使用正交组合。每种方法记录适用原因或不适用证据。
6. 覆盖功能、异常、权限；安全、性能、并发、SQL/指标口径按适用性分析。数值、长度、时间、分页、金额存在明确边界时记录 min、min+1、max-1、max、越界；未知边界不得虚构。
7. 对指标口径列出独立计算公式、输入数据、聚合范围、舍入方式和可观察输出。SQL 等价只可引用已确认 Mapper/SQL、只读 Fixture、对账公式或 `EXPLAIN` 证据。
8. 输出变更影响分析、测试设计和覆盖矩阵，并将正式用例候选、阻塞项、Fixture/Mock/环境需求交给用例生成阶段。

## Decision rules

- 有可切换测试账号和资源归属 Fixture 时，权限必须覆盖 A 用户访问 B 用户空间/资源、菜单/页面/接口三层和切换空间后的残留数据；没有该条件时记录为 `blocked` 的权限证据缺口，不得伪造越权结论。
- 大数据、超时、重试和并发必须有数据规模、SLO、超时、重试策略或锁/幂等证据；缺失时标记 `blocked`。
- 禁止把 UI 显示结果当成 SQL 等价或指标正确性的唯一证据。
- Fixture、Mock、权限角色、外部服务或数据库访问路径不明确时，生成可追踪的缺口，不伪造可执行用例。
- 每个 `direct-change`、`indirect-impact`、`unchanged-regression` 的 `IMP-*` 必须映射正式用例或具名 GAP；“未改动”本身不是不测理由。
- `not-applicable-with-evidence` 必须说明为什么该功能与改动文件、调用链、接口、数据、权限和消息均无关联；不能用缺少阅读证据代替独立性证明。
- 只创建当前版本目录下的 `change-impact-analysis.md`、`test-design.md` 和 `coverage-matrix.md`；不上传、不执行、不写入凭据。

## Output contract

- `change-impact-analysis.md`：变更证据、调用链、直接/间接/未改回归功能、影响理由、用例或缺口的映射。
- `test-design.md`：系统上下文、REQ 风险、测试方法、边界、数据与环境策略、指标/SQL 口径和缺口。
- `coverage-matrix.md`：REQ、影响类型与测试类型、设计方法、现有用例、待补充项、状态的映射。
