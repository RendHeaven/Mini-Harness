# Atlas Core 使用导航

Atlas 的内容概括、角色路由、能力边界和目录职责见 [AGENTS.md](../AGENTS.md)。项目 AGENTS.md 指向该入口并说明项目结构。

## 按角色执行 workflow

按已选角色查看 [工作流路由](../AGENTS.md)，再读取对应 workflow 与阶段 skill。项目接入和跨仓操作见 [执行约定](rules/project-execution.md)。

## 主题定义入口

新增或修订定义时更新下表对应来源；workflow 负责阶段路由，skill 负责动作，模板保留字段、示例和填表提示。引用处不再维护第二套定义。

| 主题 | 定义位置 |
| --- | --- |
| 角色执行、原型写入权限、跨仓操作 | [项目执行约定](rules/project-execution.md) |
| 版本、稳定 ID、Manifest 状态 | [ID 与状态](rules/id-and-status-standard.md) |
| 产品事实、PRD 修订、派生与来源摘要 | [产品追溯](rules/product-semantics-and-traceability.md) |
| 项目原型、历史导入与资产摘要 | [项目资产](rules/project-assets.md) |
| 四角色 Gate、确认身份与变更范围引用 | [Gate 协议](rules/review-gates.md) |
| 文档时间与编辑记录 | [时间规范](rules/document-timestamps.md) |
| 后端模块编号、总览与详情、TASK 状态及追写 | [后端交付](rules/backend-delivery.md) |
| 接口文档 v5 结构、字段与特殊响应 | [接口文档](rules/api-document.md) |
| 前端页面 PLAN、TASK、复用与权限规划 | [UI Plan 决策](skills/frontend/01-ui-plan.md#decision-rules) |
| 前端 API 匹配、缺口与聚合判断 | [API Plan 决策](skills/frontend/03-api-plan.md#decision-rules) |
| TestHub 用例格式、安全、同步与回调 | [TestHub 协议](rules/testhub-markdown-v1.md) |
| 阶段根与产物路径 | 对应角色 workflow 的“阶段执行”；字段值取项目配置 |
| Hook 本地队列 | [Hook 说明](hooks/README.md)，运行行为由实现与测试验证 |

## 项目协议与工具

- Core 版本及 Schema 见 [harness.yaml](harness.yaml)，内容锁见 [version.lock](version.lock)。项目采用的 Schema 和目录以项目配置为准。
- 项目使用 Schema 20、`.harness/` 配置目录、根原型仓库与四角色独立 Gate。
- 项目接入见 [项目脚手架](../project-harness-template/README.md)，角色使用说明见 [手册导航](../使用手册/使用手册导航.md)。
- 校验入口为 `tools/validate_harness.py`；Gate、PRD 修订工具分别为 `role_gates.py`、`prd_revision.py`，用 `--help` 查看参数。
- Jenkins 为独立按需能力，见 [Jenkins skill](skills/delivery/jenkins.md)。
- Core 开发、验证和版本维护见 [维护约定](../docs/core-maintenance.md)；依赖见 [requirements.txt](tools/requirements.txt)。

- 已有工程缺少静态原型：使用 [原型补建 workflow](workflow/prototype-reconstruction-workflow.md) 与 [还原协议](rules/prototype-reconstruction.md)。
