---
name: publish-structured-api-document
description: 当后端 Plan、TDD、Exec 已形成当前模块事实时使用。从三类研发产物归纳新增、编辑、删除的 HTTP 接口，并以最终 Controller、请求/响应模型及固定响应键逐字段核对，只生成一个供前端直接消费的 api-document.md；本阶段不读取 LocalTest，也不表达阻塞、通过或 verified 状态。
---

# 生成结构化接口文档

## Objective

根据当前 Plan、TDD、Exec 和最终代码，生成符合[接口文档 v5](../../rules/api-document.md)的单一前端调用文档。

## Inputs

- 产物相对[工作流](../../workflow/backend-workflow.md#阶段执行)指定的阶段根。
- 正文结构、字段表、特殊响应和信息边界遵循[接口文档 v5](../../rules/api-document.md)。
- 文档遵循[时间规范](../../rules/document-timestamps.md)。
- 当前版本对应模块的 Plan、TDD 与 Exec；三者决定本期接口范围、业务语义与最终实现取舍。
- Owner 服务当前工作区中与已完成 Exec 对应的 Controller、请求 DTO、响应 DTO/VO、序列化注解，以及 `Map`/`Object` 响应的固定键写入位置；它们仅用于字段级契约核对，不能自行扩大本期接口范围或补造产品语义。
- 项目 Harness 当前服务的 `6-interface-document/` 目录，以及 Plan 已确认的前端服务、页面或组件消费点。
- LocalTest、服务 revision、文档 SHA256、测试通过率和环境可用性不属于本阶段输入，也不得写入接口文档状态。

## Workflow

1. 建立 Plan、TDD、Exec 的模块对应关系；按接口锚点合并三份来源，不把相邻模块或历史版本的接口混入本次文档。
2. 按接口文档规则识别新增、编辑、删除或无 HTTP 变化。
3. 从 Plan 提取业务含义、调用方和前端消费位置；从 TDD 提取方法、路径、参数位置、字段、校验和包装；从 Exec 提取最终实现取舍、兼容处理和实际落地范围。
4. 按[字段与特殊响应](../../rules/api-document.md#字段与特殊响应)逐端点对账真实 Controller、DTO/VO 和固定键写入位置。
5. 用[接口文档模板](../../template/develop/backend/interface-document-template.md)生成 `6-interface-document/api-document.md`，按 v5 规则核对结构、字段和示例。
6. 若 Plan/TDD/Exec 与最终实现的路径、字段、枚举、默认值或响应形状冲突，先回流正确的 Plan、TDD 或 Exec 并修正实现，再重生成文档；不得为了文档完整而静默选择任一版本。

## Decision rules

- 产品语义或 UI 事实变化先记录并询问用户按哪个角色处理；已明确属于后端的技术细化更新接口正文，记录受影响 consumers，不自动启动其他角色流程。

## Output contract

输出唯一文件 `6-interface-document/api-document.md`；按接口文档 v5 核对每个端点的来源与完整定义。
