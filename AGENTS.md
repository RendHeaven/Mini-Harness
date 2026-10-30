# Atlas-Harness 项目入口

## 内容概括

Atlas 是团队通用 Harness Core，提供角色工作流、阶段技能、规则、产物模板、项目脚手架及校验工具。项目 Harness 通过配置锁定并引用 Core，具体执行步骤由对应 workflow、skill 和规则原文持有。

沿用用户明确选择或会话已确定的角色；职责不清或需越界时询问归属，只暂停争议及依赖答复的工作。仅在用户明确选择其他角色或流程后切换，已安排的多角色顺序不重复确认；同角色阶段推进和返工正常执行，“回流”“交接”不授权跨角色代行。


| 已选角色或流程           | 工作流入口                                                          | 能力范围              |
| ----------------- | -------------------------------------------------------------- | ----------------- |
| 产品                | [product-design](.harness/workflow/product-design-workflow.md) | 需求探索、原型、PRD 与产品确认 |
| UI                | [ui-design](.harness/workflow/ui-design-workflow.md)           | 原型调整、调整文档与 UI 确认  |
| 已有页面原型补建 | [prototype-reconstruction](.harness/workflow/prototype-reconstruction-workflow.md) | 源码/页面取证、静态原型补建与验证（UI 支线） |
| 前端                | [frontend](.harness/workflow/frontend-workflow.md)             | 前端设计、实现、接口接入与验证   |
| 后端                | [backend](.harness/workflow/backend-workflow.md)               | 后端设计、实现、契约与验证     |
| 前端明确选择 Mock       | [frontend-mock](.harness/workflow/frontend-mock-workflow.md)   | 服务内模拟运行与场景数据      |
| 明确选择 TestHub      | [testhub](.harness/workflow/testhub-workflow.md)               | 测试设计、用例、同步与按需执行   |
| 当前服务角色明确选择 Bugfix | [bugfix](.harness/workflow/bugfix-workflow.md)                 | 问题定位、修复、验证与复盘     |


进入工作流后按阶段读取 skill、规则和模板；资源路径相对实际 Core 的 `.harness/` 解析。能力描述不自动触发角色选择或流程切换。

## 能力边界

- Atlas 维护通用方法和协议；产品事实与需求交付由项目 Harness 持有，源码、长期契约及运行事实由服务仓库持有。
- 角色路由不扩大写入授权；机器校验、Hook 或模板存在不代表业务 Gate 确认、外部系统接通或发布许可。
- 项目使用时读取 [项目接入与执行约定](.harness/rules/project-execution.md)；资产路径和采用协议以项目配置为准，项目采用必须匹配当前协议和精确锁定，业务确认由项目实际负责人记录。



## 目录说明


| 目录                          | 作用                                                                 |
| --------------------------- | ------------------------------------------------------------------ |
| `.harness/`                 | Core 资源根；`harness.yaml` 与 `version.lock` 定义元数据、版本和内容锁              |
| `.harness/workflow/`        | 各角色与专项流程的阶段编排、输入和写入边界                                              |
| `.harness/skills/`          | 阶段执行方法及专项能力                                                        |
| `.harness/rules/`           | 通用执行约束、状态、追溯和工程规则                                                  |
| `.harness/template/`        | 需求与阶段交付物模板                                                         |
| `.harness/tools/`           | 配置与产物校验、Gate、PRD 修订等工具及测试                                              |
| `.harness/hooks/`           | 可由项目接入的通用采集器与 Hook 实现                                              |
| `project-harness-template/` | 新项目脚手架：`.harness/` 项目配置与上下文、`.codex/` Hook 接入、`原型仓库/` 及根 Gate 模板   |
| `使用手册/`                     | 按角色组织的使用说明与维护者手册                                                   |
| `docs/`                     | Core 维护说明；当前版本由 `.harness/version.lock` 持有 |


