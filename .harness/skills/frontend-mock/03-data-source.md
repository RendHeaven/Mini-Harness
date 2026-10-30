---
name: create-frontend-mock-data-source
description: 为前端 Mock 建立集中、可追溯、场景化且可随契约演进的数据源与请求处理器。
---

# 前端 Mock 数据源

## Objective

将 Mock 数据、接口处理器和场景选择集中管理，使页面在不依赖远端服务时仍可重复验证正常、空、错误和边界状态。

## Inputs

- 文档遵循[时间规范](../../rules/document-timestamps.md)。
- Mock 方案、接口契约或已标记的假设、页面状态要求、脱敏约束和 `rules/frontend-engineering.md`。
- 现有类型定义、真实样例（可用时）和目标前端仓库的数据组织规范。

## Workflow

1. 按业务域建立 `src/mocks/`（或工程等价目录），拆分 fixtures、handlers、scenarios 与公共辅助函数。
2. 为每个接口建立与真实路径和方法一致的处理器；响应结构复用真实 TypeScript 类型或单独声明的契约类型。
3. 定义至少正常、空数据、业务错误和网络错误场景；需要时加入分页、权限、加载延迟、上传失败和边界值。
4. 使用查询参数、请求头或仅限 Mock 模式的场景选择器切换场景；请求组织遵循 `rules/frontend-engineering.md` §3，不得在页面组件中散落判断。
5. 使用 `template/develop/frontend-mock/mock-source-matrix-template.md` 维护接口—场景—数据来源矩阵，并标明真实、脱敏、合成或假设来源。

## Decision rules

- 不提交个人信息、令牌、真实客户数据或未经允许的生产数据；样例必须脱敏或合成。
- Mock 响应必须包含产品需要的异常和空态，不能只提供“永远成功”的演示数据。
- API 契约发生变更时，同时更新数据、处理器、矩阵和验证记录。

## Output contract

输出集中 Mock 数据与处理器，以及 `docs/mock/mock-source-matrix.md`。矩阵须能从接口定位到场景、数据来源、假设、负责模块和对应验证。
