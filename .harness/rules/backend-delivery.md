# 后端模块交付记录

适用于 TDD、Exec、LocalTest 和 Review。服务与阶段根从[后端工作流](../workflow/backend-workflow.md#阶段执行)解析；Plan 的业务设计仍由 Plan skill 持有。

## 模块与文件

多模块沿用 `plan-NN-*.md` 的 `NN`，单模块统一为 `01`。先登记总览，只为实际开始的模块建立同编号详情；未开始模块只在总览标记 `planned`，不得预先伪造契约、测试、执行或审查事实。

| 阶段 | 目录 | 总览 | 模块详情 |
| --- | --- | --- | --- |
| TDD | `3-tdd/` | `tdd-overview.md` | `tdd-NN.md` |
| Exec | `4-exec/` | `exec-overview.md` | `exec-NN.md` |
| LocalTest | `5-local-interface-test/` | `localTest-overview.md` | `localTest-NN.md` |
| Review | `7-review/` | `review-overview.md` | `review-NN.md` |

不得使用聚合 `task.md`、`exec.md` 替代 Exec 模块记录。已确认 `backend n/a` 的 Plan 仍保留同编号 Exec、LocalTest、Review，具体依据和外部责任方交接按各阶段 skill 填写，不伪造 TASK、接口通过或审查事实。

## 总览与详情

总览只保存索引和聚合摘要；具体证据写入所属模块。各阶段分工如下：

| 阶段 | 总览 | 模块详情 |
| --- | --- | --- |
| TDD | Plan/外部设计/TDD 路径、模块状态、契约路径及基线、共享验证、跨模块依赖、全局告警和阶段结论 | 契约字段、骨架、测试、失败诊断、消费者通知和追写 |
| Exec | 模块输入与状态、TASK 及外部变更摘要 | 结构化 TASK、实现与测试、偏差、外部执行、审批、风险、验证和回滚证据 |
| LocalTest | Plan/外部设计/TDD/Exec/LocalTest 路径、模块状态、跨模块依赖、共享环境、全局回流项和阶段结论 | 请求、响应、断言、数据证据、失败根因与复测记录 |
| Review | 模块输入路径、revision、状态、跨模块依赖、共享验证、全局发现索引、REQ 聚合、TestHub 测试盲区和阶段结论 | 具体代码位置、审查证据、模块 REQ 覆盖、影响分析、修复建议与复测记录 |

## 记录追加

后续修订、测试补充、失败诊断、消费者通知、修复和复测均追加至原模块记录，并更新总览摘要。不得重建平行文件或覆盖既有证据。历史周期产物保持只读，不纳入当前周期的阶段事实。时间遵循[文档时间规范](document-timestamps.md)。

## TASK 状态

以下状态仅定义后端 Exec 的 TASK，不替代 Manifest 或 Gate 状态：

- `planned`：尚未开始；获得输入或解除阻塞本身不改变为进行中。
- `in-progress`：已实际开始编码、配置或测试实现。
- `implement`：实现与实现级测试完成，但尚未完成规定验证。
- `blocked`：当前无法继续，需要外部状态变化；恢复后回到真实进行状态。
- `done`：已完成规定验证；适用 TASK 的 Exec 阶段退出条件。
- `n/a`：不适用，必须在风险/依据栏说明具体原因。

每个 Plan TASK 在模块 TASK 主表中必须且只能出现一次；阶段退出时全部适用 TASK 必须为 `done`。已确认 `backend n/a` 的模块按 Exec skill 写依据与交接，不生成虚假 TASK 表。

## Exec 追写

- 首次 Exec 后，只要同一 Plan 模块发生代码、测试、SQL/Nacos、权限、MinIO、审批、验证或回滚改动，必须回到原 `4-exec/exec-NN.md`，在对应 `TASK-BE-NNN` 的“变更追写（仅追加）”中新增一行。
- 不得新建第二个 Exec 文件、平行 TASK 表或以覆盖方式替换首次实现、测试和审批证据；TASK 主表只更新当前状态和最新摘要，完整时间线以对应 TASK 的追写表为准。
- 追写必须记录精确到秒的编辑时间、触发原因、变更文件/代码路径、测试或外部验证结果、审批/风险状态和消费者通知；外部文件新增或修订时，在同主体文件中按 Exec/TASK 追加记录，同时更新模块的“外部变更文件”表与 `exec-overview.md` 摘要。
- 若改动改变业务语义、契约、数据口径、权限边界或 Plan TASK，先回流 Plan/TDD；仅实现细化、缺陷修复和外部执行证据补充可直接追写原 TASK。

每个 TASK 在“变更追写（仅追加）”中使用唯一三级标题，后续行只追加。
