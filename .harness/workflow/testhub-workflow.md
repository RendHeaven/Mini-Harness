---
name: testhub-workflow
description: 用户明确选择 TestHub 测试流程时使用；完成测试设计、用例生成、同步和按需执行，职责不清时询问，不自动接手产品或研发职责。
---

# TestHub 测试设计、用例同步与按需执行工作流

## 触发条件

- 用户明确选择 TestHub 测试流程，或会话已确定该流程时进入；当前角色不因发现实现问题自动变化。
- 本流程可分析回归范围、生成用例、按任务范围同步及查询结果；只要求生成文档时到文档交付结束，远程运行须有用户明确要求。
- 角色沿用与切换遵循[角色执行约定](../rules/project-execution.md#角色执行)。

## 职责与输入

负责测试影响分析、测试设计、完整用例文档、同步回执和按需执行结果。读取当前周期可用的 PRD、计划、任务、Execution，以及项目根静态原型、服务目录、正式契约和真实代码证据；历史用例仅作为回归候选。

有可比较 revision 时分析直接、间接及未改功能的回归影响。来源缺失、不可解析或过期时记录缺口，只生成有事实依据的内容，不虚构字段、阈值或自动化条件。不以其他角色 Gate 为前置。

## 阶段执行

当前周期由项目配置 `project.demandCycleRoot` 与完整周期标识定位；下述目录字段取自同一配置。

产物相对当前周期 `<development.root>/<development.testhub>/`（默认 `develop/testhub/`）。独立进入同步或执行时复用已校验的文档或回执，不重做无关阶段。

| 阶段 | Skill | 主要产物 | 完成标准 |
| --- | --- | --- | --- |
| 测试设计 | `skills/testhub/00-senior-test-design.md` | `change-impact-analysis.md`、`test-design.md`、`coverage-matrix.md` | 影响、风险、设计方法与覆盖关系明确；缺失证据有具名缺口 |
| 用例生成 | `skills/testhub/01-generate-markdown-cases.md` | `cases.md`、`generation-report.md` | 完整当前用例集可追溯到来源、影响和设计，实际缺口未被掩盖 |
| 本地校验与同步 | `skills/testhub/02-parse-and-sync.md` 的校验和同步步骤 | `sync-metadata.json`、`sync-report.md` | 文档和稳定身份校验通过，按任务范围同步并保存脱敏回执 |
| 按需执行与查询 | `skills/testhub/02-parse-and-sync.md` 的执行、查询和重试步骤 | 同步报告中的 run 引用和执行结果 | 使用实际导入回执启动，依据真实终态记录结果，重试有独立运行记录 |

## 写入边界

项目 Harness 持有测试文档、覆盖矩阵和回执；正式用例同步到配置指定的 TestHub Harness 项目。测试设计和影响分析文档不上传，不修改业务源码、产品定义或其他角色 Gate。

TestHub 是需由团队自建或适配的外部测试服务，Atlas 不提供其服务端；对接接口以 `tools/sync_testhub_markdown.py` 使用的 `/api/ai-ui-testing/` 路径为准，项目 `testhub.yaml` 未配置真实地址前只能生成文档，不能同步或执行。同步字段、稳定 ID、完整文档上传、幂等、回调、脱敏与运行协议统一由 [TestHub 规则](../rules/testhub-markdown-v1.md)定义，按实际项目配置执行。生成不授予远程写入或运行权限，删除也不能被默认为生成步骤。文档时间遵循 `rules/document-timestamps.md`。

## 问题处理与结束

- 信息不足记录 generated-with-gaps；结构或安全校验失败记录 invalid-for-sync，不上传；无正式用例时记录 skipped-no-cases。
- 来源变化在本流程内重新分析影响、设计并修订完整用例集，保持稳定身份。
- 导入成功只表示同步成功，执行以真实启动和终态为准；失败、阻塞或取消不能写成通过。环境、需求或实现问题先记录，职责不清或需超出当前范围时询问本次以哪个角色处理，不自动进入修复流程。
- 到用户要求的阶段交付结果即结束。不新增 Gate；四角色状态不作为测试开始条件，也不能代替测试结果。
