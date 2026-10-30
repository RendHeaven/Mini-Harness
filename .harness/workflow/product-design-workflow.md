---
name: product-design-workflow
description: 用户已选择产品角色时使用；按产品流程完成需求探索、静态原型、PRD 和产品确认，职责不清时询问角色归属，不自动切换。
---

# 产品工作流

## 触发条件

- 用户已选择产品角色，或会话中已确定当前为产品角色时，按本流程执行。
- 本角色内可处理需求探索、业务规则和验收条件、需求原型、PRD 生成与修订、产品交付确认。产品 Mock 是需求表达，不是服务内模拟运行。
- 角色沿用与切换遵循[角色执行约定](../rules/project-execution.md#角色执行)。

## 职责与输入

负责明确用户目标、业务规则和验收条件，通过原型探索并形成可追溯的 PRD。最低输入是需求描述与项目上下文；已有 PRD、原型和历史决策时必须读取。只有项目首次使用时初始化原型，不要求先有 PRD。

读取项目配置确定文档所属周期和[原型路径](../rules/project-assets.md#项目原型与历史路径)；事实归属、修订与派生遵循[产品追溯规则](../rules/product-semantics-and-traceability.md)，视觉表达遵循 [UI 规则](../rules/ui-standard.md)。

## 阶段执行

主线：Mock → 生成或修订 PRD → 产品 Gate 确认。单独修订或确认时，读取已有产物并进入对应阶段，不重复生成整条流程。

| 阶段 | Skill | 主要产物 | 完成标准 |
| --- | --- | --- | --- |
| Mock | `skills/product/discovery.md` | 项目原型、`product/discovery.md`、`product/mock-changelog.md` | 改动和 UI 规则依据已记录，主路径及适用状态已验证，假设与真实反馈分开 |
| 生成或修订 PRD | `skills/product/prd-build.md` | `product/<版本>-prd.md`、修订文档和索引 | PRD 结构、DEC/REQ 和历史回溯完整；后续修改原位更新并逐次追踪 |
| 产品 Gate 确认 | `skills/product/gate-confirm.md`，内置调用 `skills/product/prd-review.md` | 反问对话、必要的产品修订及 `Gate.yaml` 当前周期 product 记录 | 反问收束、自身交付检查完成，实际负责人明确确认最终内容；时间、Git 身份和来源证据完整 |

进入产品确认阶段后自动开展 grilling，按决策依赖分轮提问并逐题给出推荐答案；结论复用、增量追问、必要修订与最终确认遵循[产品确认技能](../skills/product/gate-confirm.md)。仅生成、修改或导出 PRD 不自动触发该阶段。

### 按需支线

以下支线可单独调用，完成指定任务后结束，不自动推进主线或 Gate。PRD 变更仍使用逐次修订工具。

| 支线 | Skill | 主要产物或结果 |
| --- | --- | --- |
| 产品反问 | `skills/product/prd-review.md` | 反问对话，不强制生成 PRD Review |
| PRD 增强 | `skills/product/dev-guide.md` | Dev Guide |
| Word 导出 | `skills/product/export-word-prd.md` | PRD 的 Word 展示副本 |
| 原型打包 | `skills/product/package-prototype.md` | 将原型目录内容打包为同级 ZIP；已有原型即可直接调用，无需 PRD 或产品确认 |

## 写入边界

代码权限遵循[原型写入边界](../rules/project-execution.md#原型写入边界)；产品文档写入当前周期配置的 `product.root`。不得调用前端 Skill 代行实现。

原型打包支线只读取源目录，并在该目录同级新增 ZIP 派生副本；具体路径与同名处理遵循[原型打包技能](../skills/product/package-prototype.md)。

只通过 Gate 工具更新本角色记录，记录确认范围、来源路径和截至本次确认的变更引用；不改其他角色状态。文档时间遵循 `rules/document-timestamps.md`，确认协议遵循 `rules/review-gates.md`。

## 问题处理与结束

- 反馈改变业务含义时，在产品角色内更新决策与 PRD 修订记录，列明受影响资产，不代其他角色执行。
- 工程或接口问题超出本角色范围时记录现象与影响，主动询问本次应以哪个角色处理，不自行启动研发流程。
- 单阶段请求完成相应产物后结束；完整主线在产品 Gate 明确确认后结束。不等待其他角色 Gate，不把机器校验当成人工确认。
