---
name: reconstruction-static-prototype-build
description: 按证据规格在项目共用原型内构建脱离真实服务的页面和必要交互。
---

# 静态原型构建

## Objective

构建可独立预览的静态原型。

## Inputs

当前工作项、固定版本的页面规格、本地数据和资产索引；修复轮次还需问题编号与复现证据。

## Workflow

先核对原型目录现有文件，增量实现共用布局、区域和状态，不覆盖其他需求的原型。功能按 pages/assets/mock-data 组织，入口沿用项目约定。

移植展示层与资源，业务请求换成本地数据与状态变化；不从原型反向 import 服务目录。图表库等放本地并附来源、版本和许可证。原型控制区与产品界面区分，演示数据清楚标注。

按规格实现选择/搜索/弹层/图例等行为，保证切换后字段、图表、选择态同步。危险动作只模拟；不挂回真实 endpoint。缺少可验证业务定义的操作保留说明，不能自创流程。

回流修复只处理已核实的问题及必要关联处，记录根因、修复尝试和实际变更。原工程继承行为列为差异，不能自动作为原型缺陷修正；规格含糊或矛盾回到 04，发现遗漏状态回到 02，来源变化回到 01。构建节点不得修改验收标准、删除失败状态或更新视觉基线来获得通过。

保存变更文件摘要与 affectedWorkItems。共享样式、组件、数据或资产变更必须沿依赖关系使受影响验证失效，追加回归任务；不能只重测当前状态。保留历史证据与用户已有改动。

提供从任意工作目录可复现的静态服务器启动说明；相对路径资源无需业务服务器。候选构建可用时进入 06，代码写完不代表验证通过；遇到已达到停止条件的问题时按 workflow 停止该项，继续其他独立项。

## Decision rules

遵循 [还原协议](../../rules/prototype-reconstruction.md)；原型写入范围与角色衔接见 [专项 workflow](../../workflow/prototype-reconstruction-workflow.md)。

## Output contract

更新原型文件、启动说明、产物摘要及修复记录。在现有 reconstruction 记录的 iterations 中追加本次执行：workItemId、node（'05'）、result（done/partial/blocked）、changedArtifacts、affectedWorkItems、evidence、nextAction（targetNode/workItemId/reason）。每次实际原型改动均有独立 iteration，Gate 按记录路径#iteration-序号引用，不另建重叠日志。保存后按 workflow 路由；单阶段请求将 targetNode 置为 null，在 reason 中记录建议下一步，不自动推进。
