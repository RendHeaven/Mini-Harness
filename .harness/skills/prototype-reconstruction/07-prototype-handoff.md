---
name: reconstruction-prototype-handoff
description: 准备补建原型交付资料，对最终累计改动执行必需open-code-review，闭环问题后汇总交付并衔接既有UI确认流程。
---

# 原型交付

## Objective

对最终候选完成open-code-review收尾审核，交付可维护原型及真实覆盖、审核和来源记录。

## Inputs

页面产物、工作队列终态、有效分项验证与跨状态回归、差异清单、节点执行历史、本轮开始基线及累计变更清单。

## Workflow

先准备入口/启动方式、当前来源基线、页面与状态覆盖、演示数据说明、资源来源、已知差异及维护映射，冻结待审候选摘要。

按[必需收尾审核协议](../../rules/prototype-reconstruction.md#必需收尾审核)调用open-code-review，对本轮累计原型变更的最终状态审核，保存完整报告、逐文件覆盖和摘要。常规模式或官方委托模式均可，必须实际调用工具；06中的过程评审不能代替本次收尾审核。未跟踪文件、删除和早轮产物同样核对，跳过文件或零可审文件不能直接当成通过。

核实问题并复用原issues/causeKey，按原因返回必要节点；修复后经06行为与关联回归，再回本节点按最终摘要复审。普通报告归档不触发自审，任何被审输入的实质变化使旧passed失效。OCR尝试计入全局执行与无进展上限，只有封包保存现场不受重试上限阻止。

最后核对必需检查与回归是否有效、OCR是否有效passed或有证据的not_applicable、是否有未解决阻断。全部满足才记录completed；工具不可用、审核覆盖不全、未核实必需项或停止问题都交付partial，写出审核实际结果和恢复条件。示例措辞：原型候选已交付，本地交互通过，收尾OCR通过；原页面视觉一致性待验证，整体partial。

按实际结果汇总每个节点 done/partial/blocked，保留 iterations 中每轮执行历史；交付尚未解决问题的根因、受影响工作项、停止原因及恢复节点。继续执行时先核对输入是否改变，再恢复对应项，不重新采集和构建全部页面，也不继承已失效的通过记录。保留本次来源索引、实际 revision、必要局部差异和独有验证证据；后续源变更先做差异分析，不能覆盖已经人工调整的原型。

需要 UI 调整文档时衔接 [调整文档](../ui/02-adjustment-document.md)；真实负责人确认才进入 [UI 确认](../ui/03-gate-confirm.md)。逆向结果不自动变成 PRD，不修改 product/frontend/backend Gate，不新增 Gate 类型或 Execution Track。

收尾审核按官方OCR技能处理工具依赖，工具缺失时如实partial，不要求安装外部页面克隆工具。

## Decision rules

遵循 [还原协议](../../rules/prototype-reconstruction.md)；原型写入范围与角色衔接见 [专项 workflow](../../workflow/prototype-reconstruction-workflow.md)。

## Output contract

更新交付入口、覆盖、finalReview（工具/模式、范围对账、输入摘要、报告与问题）、专项completed/partial状态及恢复待办。在iterations追加每次真实执行：workItemId（全局可为null）、node（'07'）、action（final-review或handoff）、result（done/partial/blocked）、changedArtifacts、affectedWorkItems、evidence、nextAction（targetNode/workItemId/reason）；需要返工时保留目标节点，单阶段请求只记录建议并结束。本轮最终交付结束时targetNode为null，reason说明结果与恢复条件。不自动确认Gate。
