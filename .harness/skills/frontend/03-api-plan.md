---
name: plan-frontend-api-integration
description: 当页面需要读取或写入服务数据时使用。以页面为一级结构、页面动作为 TASK，逐接口核对正式文档、HTTP 方法、业务路径与前端调用位置；缺口必须区分接口、字段、语义和外部契约。
---

# 前端 API 计划

## Objective

以真实页面动作形成 API TASK，规划消费字段、接口匹配、缺口和 API Exec 验收。

## Inputs

- 产物相对[工作流](../../workflow/frontend-workflow.md#阶段执行)指定的阶段根。
- 文档遵循[时间规范](../../rules/document-timestamps.md)。
- 必需：PRD、项目根静态原型及实际来源路径、变更记录、真实页面/组件/状态/API 封装、目标后端的结构化接口文档（存在时）和 `rules/frontend-engineering.md`。空值与 `0` 的展示口径见 `rules/ui-standard.md`。
- 可选：Dev Guide、UI Handoff；存在时交叉核对，不作为 API 计划前置条件。
- 查找现有实现时读取目标服务的 Controller、请求/响应 DTO/VO、固定 Map 键和前端既有 service/type；它们是候选实现证据，不会自动升级为正式接口契约。
- 路径、字段、错误语义或前端调用位置不清时反馈 backend 修订接口文档；不以 revision、SHA256 或测试状态替代接口定义。
- 读取当前周期登记的文档路径及 Owner，并核对本次选定的前后端分支与来源版本。多份同名文档、旧执行记录或不同版本的契约并存时，先确认本次引用的正文；无法确认时记录歧义与 Owner，不自行选择或拼合。来源版本记在 Plan 中，不向接口文档正文添加发布或测试状态。

## Workflow

1. 建立页面总览，为每个真实路由页面创建三级标题。
2. 从页面用户动作、组件状态和 PRD 提取 TASK 所需数据与操作。
3. 在同一 TASK 行写清页面消费点、所需请求/响应字段、加载/空/错误/权限/副作用和 API Exec 验收；在结构化接口文档中查找可完整满足需求的端点，记录 API 锚点、字段路径和错误语义。
4. 按下述匹配优先级查正式文档，再查候选实现；记录来源证据与待确认归属。
5. 无可满足来源时，按下述缺口分类登记 blocked TASK 及补齐 Owner。
6. 对字段或语义不足的接口继续检查现有实现，仍不能满足时按对应缺口分类记录；不在前端发明字段。
7. 页面章节完成后，仅以“跨页面共享能力索引”汇总可复用能力及其关联 TASK；索引不得产生新的 TASK。在“接口消费索引（附录）”建立逐接口对照表：每个 TASK 的每个接口调用位置各一行，列出 TASK、Owner、文档路径与 API 编号、HTTP 方法、文档业务路径、前端调用位置、当前请求定义、decision、差异与下一步。一个 TASK 调用多个接口时拆成多行；同一接口被多个 TASK 消费时分别关联，不能只写 API 范围或“接口已匹配”。
8. 在独立阻塞项表中汇总所有 blocked TASK，按缺口分类、Owner 和补齐内容说明处理边界。设计分页、筛选、排序、取消/竞态、加载、空、异常和权限处理；空值与 `0` 按 UI 规则 §5。

## Decision rules

- 页面是 API Plan 的唯一一级工作结构；每个 `TASK-FE-*` 只描述一个页面动作/场景，不从 API 清单、Service 文件或组件名反向创建。一个端点可服务多个 TASK，一个 TASK 也可组合多个端点。
- 组件、弹窗、抽屉和附件写在所属页面的消费点中。无独立路由的共享组件不建页面章节或独立 TASK；共享索引只引用既有页面 TASK，不以“通用 Service”“后端接口分组”等无路由对象分组。
- 匹配优先级固定为：结构化接口文档 `contract` → 现有实现 `implementation` → `blocked`。不得因当前 Mock、候选 type 或历史 API 名称而跳过检索。
- `contract` 和 `implementation` 的缺口分类为 `none`；`blocked` 必须使用固定缺口分类，不能用笼统的“接口不清楚”。
- TDD baseline 不能替代结构化接口文档；现有实现只能作为文档未命中时的证据来源。
- PRD 决定产品目标，页面决定需求，接口文档决定正式传输契约；无 backend 改动也必须检索并固定现有接口文档或现有实现证据。
- 文档引用使用 Owner、实际文档路径与 API 编号共同定位，不能仅凭 `API-001` 在跨文档检索中认定命中。逐项读取正文确认 HTTP 方法、业务路径和参数位置；路径参数保留占位符，query 不混入业务路径。
- 当前请求定义必须从调用函数及实际封装读取，记录方法和路径表达式；尚未实现时写“待新增”，不得凭页面名、函数名、Mock 或邻近 service 推测 URL。文档业务路径与完整 URL 分开记录，前缀、代理和运行场景由 API Exec 核对。
- `implementation` 行在文档引用处明确“未命中”，方法与路径注明来自候选实现并引用源码，标记“待正式接口文档确认”，不编造正式 API 编号。仅缺端点时保留 blocked TASK 与检索证据，不为凑齐对照表虚构接口。
- 路径、方法或文档归属存在未解决的歧义时，以 `missing_semantics` 记录受影响 TASK 的阻塞与 Owner；接口不存在时使用 `missing_endpoint`。旧实现与明确契约不同但修正方案已确定时，记录待改差异即可，不把所有待实现工作判成 blocked。
- `blocked` 缺口分类只允许 `missing_endpoint`、`missing_request_field`、`missing_response_field`、`missing_semantics`、`external_contract`；同一行保留接口文档与现有实现的未命中或字段缺口证据及补齐 Owner。
- 混合来源或部分接口阻塞时，页面行保留全部来源并按最弱状态汇总：任一接口 blocked 则 TASK blocked，其次为 implementation，全部正式命中才为 contract。
- 仅当每个页面动作均有 `contract` 或有可接受的 `implementation` 证据、且页面处理方式明确时标记 ready；存在任一 `blocked` 时状态必须为 blocked。implementation 不得作为真实联调通过或后端正式契约的证据。

## Output contract

输出 `3-api-plan/plan.md`，首行标记为：`API Plan 方式：page-demand-v3`。固定结构为“总览 → 页面 API 计划 → 跨页面共享能力索引 → 阻塞项 → 接口消费索引（附录）”。

逐接口对照表必须覆盖页面 TASK 中所有已定位的调用，并与页面行的 decision、Owner 和阻塞项一致。使用 `template/develop/frontend/api-plan-template.md`，保持页面为主、接口附录为追溯索引。
