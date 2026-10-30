# <需求标题>（前端 API Plan）

<!-- atlas:generated document-timestamps:start -->
- 创建时间：`<yyyy-MM-dd HH:mm:ss>`
- 最后编辑时间：`<yyyy-MM-dd HH:mm:ss>`
- 时区：`Asia/Shanghai`
- 编辑记录：
  - `<yyyy-MM-dd HH:mm:ss>`｜创建｜首次生成本文档。
<!-- 后续每次编辑在编辑记录末尾追加“时间｜操作｜摘要”，同步最后编辑时间；不得覆盖历史记录。 -->
<!-- atlas:generated document-timestamps:end -->

- 需求版本：`v<主版本>.<次版本>`
- 前端服务：`<service-id>`
- 状态：`draft|ready|blocked`
- 接口文档：`<owner:path>`
- 前后端来源：`<服务、选定分支与源码版本>`
- 文档选择依据：<当前周期登记的引用；多份文档时说明本次正文与差异处置>
- API Plan 方式：`page-demand-v3`

## 总览

| 页面 | 路由 | TASK 数 | 可执行 | 阻塞 | 阻塞原因 |
| --- | --- | ---: | ---: | ---: | --- |
| <页面名称> | `<路由>` | 1 | 1 | 0 | 无 |

## 页面 API 计划

按 [API Plan 决策规则](../../../skills/frontend/03-api-plan.md#decision-rules)填写页面、动作和消费点。

### <页面名称>

- 路由：`<路由>`
- 页面职责：<业务目标与用户可触发动作>

| TASK | REQ | 用户动作/场景 | 页面消费点 | 所需能力与消费字段 | 匹配接口与证据 | 缺口分类 | Owner | decision | API Exec 验收 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TASK-FE-101 | REQ-001 | <加载、提交或操作动作> | <页面/组件/状态> | <请求字段、响应字段、副作用> | <API 锚点、字段路径和错误语义；implementation 时附源码路径> | none | <接口 Owner> | contract | <加载/空/错误/权限/并发与验收> |
| TASK-FE-102 | REQ-001 | <动作> | <消费点> | <能力与字段> | 正式接口文档未命中：<检索范围>；现有实现未命中：<检索范围> | missing_endpoint | <补齐 Owner> | blocked | <阻塞前不能进入的验收项> |

## 跨页面共享能力索引

填写已存在的页面 TASK 引用；索引边界见上述决策规则。

| 能力 | 关联页面 TASK | 接口或实现证据 | 状态 |
| --- | --- | --- | --- |
| <共享能力> | TASK-FE-101、TASK-FE-102 | API-001 / <源码路径> | contract/implementation/blocked |

## 阻塞项

无阻塞时写“无”。存在阻塞时必须覆盖所有 decision 为 `blocked` 的 TASK。

| BLOCK | 关联页面 TASK | 缺口分类 | 接口文档与现有实现证据 | 缺失内容 | 补齐 Owner |
| --- | --- | --- | --- | --- | --- |
| BLOCK-001 | TASK-FE-102 | missing_endpoint | <两类来源均未命中的证据> | <端点、字段或语义> | <Owner> |

## 接口消费索引（附录）

按 [API Plan 步骤](../../../skills/frontend/03-api-plan.md#workflow)逐调用位置填写；方法、文档业务路径和当前请求定义分列。

| TASK | Owner | 文档路径与 API 编号 | HTTP 方法 | 文档业务路径 | 前端调用位置 | 当前请求定义 | decision | 差异与下一步 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TASK-FE-101 | <接口 Owner> | <实际文档路径>#API-001 | <方法> | <业务路径，保留路径参数> | <文件与函数；或待新增> | <当前方法与路径表达式；或待新增> | contract | <无差异或确定的改造方式> |

候选实现、缺端点和多接口聚合按 [API Plan 决策规则](../../../skills/frontend/03-api-plan.md#decision-rules)处理。

## Gate 检查（未满足项告警）

- [ ] 有路由页面是唯一一级工作结构；所有 TASK 均由页面动作创建，共享组件只在页面消费点或共享索引出现
- [ ] 每个 TASK 已先检索结构化接口文档，再检索现有实现；无可满足来源时明确为 blocked
- [ ] 每个 TASK 在同一页面行同时记录消费字段、匹配证据、缺口分类、Owner、decision 与 API Exec 验收
- [ ] 逐接口对照覆盖每个 TASK 已定位的全部调用位置；正文中的方法、业务路径与当前请求定义已分别记录，多接口调用没有合并成 API 范围
- [ ] 文档来源唯一且可定位；地址歧义、候选实现和待改差异已区分，不以 Mock 或旧 service 推测正式 URL
- [ ] implementation 行含 Controller/DTO/VO 或前端 service 的真实路径，并标记待正式接口文档确认
- [ ] blocked 行使用固定缺口分类，并同时保留接口文档与现有实现的未命中或字段缺口证据、Owner 和所需补齐内容
- [ ] 共享能力索引和阻塞项只引用页面 TASK，不产生新的 TASK
- [ ] 请求落点、分页字段按工程规则；空值与 `0` 按 UI 规则
- [ ] 分页、竞态、权限、空态和错误恢复明确
