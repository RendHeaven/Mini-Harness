---
name: reconstruction-page-state-inventory
description: 从实际路由引用链与运行入口建立页面—状态矩阵，排除未接入的历史组件。
---

# 页面与状态盘点

## Objective

建立可追溯的页面—状态清单和可逐项推进的工作队列。

## Inputs

来源评估、路由/菜单/页面、已有证据。

## Workflow

追踪入口至页面和组件，区分可达、条件可达、未接入、待核实。记录页面或区域 ID、状态 ID、前置条件、触发动作、显示变化及来源分类。

重点检查列表选择/搜索、详情联动、页签、弹层、图表图例/筛选，以及有证据的空、加载、失败与权限分支。完整业务路径优先；复杂组合选择代表用例，并记录不覆盖项及理由。

未接入组件不能因名称像某功能就放入导航。动态权限和服务端菜单不能只凭静态路由判断覆盖完整。

states 是页面状态的权威矩阵；每项标明 planned/implemented/verified/deferred。`verified` 必须链接当前有效的原型行为验证结果，并与来源类型分开，不代表线上已验证。

以范围内的“页面或区域 × 状态”建立稳定 workItemId，workItems 通过 stateIds 引用 states，不复制前置条件、动作和预期结果。记录 dependsOn、所需规格和共享资产引用；按关键路径优先、依赖先行的顺序选择可运行项。不得为追求覆盖数量拆出没有独立验证意义的工作项。

其他节点发现遗漏状态回流时，先核对是否属于 scope，再补状态和队列；超出范围的发现进入 unresolved，不自动扩大还原范围。来源改变回到 01；状态事实或依赖变更时使相关旧验证失效。受阻项的依赖项保持等待，选择其他独立项；无可运行项时按 workflow 进入跨状态回归和交付判断，不把队列阻塞视作全部通过。

## Decision rules

遵循 [还原协议](../../rules/prototype-reconstruction.md)；原型写入范围与角色衔接见 [专项 workflow](../../workflow/prototype-reconstruction-workflow.md)。

## Output contract

更新 states、workItems、队列与 unresolved。在现有 reconstruction 记录的 iterations 中追加本次执行：workItemId（全局动作可为 null）、node（'02'）、result（done/partial/blocked）、changedArtifacts、affectedWorkItems、evidence、nextAction（targetNode/workItemId/reason）。选中可运行项后通常进入 03；其他去向按 workflow 路由。单阶段请求将 targetNode 置为 null，在 reason 中记录建议下一步，不自动推进。
