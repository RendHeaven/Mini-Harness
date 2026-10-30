---
name: reconstruction-spec
description: 将页面证据整理成可执行的原型规格，明确字段、交互、本地数据与已知偏差。
---

# 还原规格

## Objective

形成可执行的原型还原规格。

## Inputs

当前工作项、证据包、状态矩阵、目标工程视觉体系及已有规格。

## Workflow

逐区域记录布局、尺寸依据、组件、字段顺序/单位/格式、交互触发与结果；共用区域只定义一次。每条行为关联状态与证据，事实、源码推断、演示假设不混写。

明确实现策略：HTML/CSS/JS 为轻量默认；可复用展示组件时评估依赖成本；复杂图表可使用固定版本本地库。资源/组件不可复用时列出替代与视觉影响，不能把截图占位称作可交互图表。

准备确定性的合成数据，覆盖目标路径、零值和适用空值，固定日期/随机种子；标明演示数据。默认不保留远程业务调用、登录和平台运行依赖。所有按钮要对应行为、演示说明或排除原因。

按工作项明确可验证的预期结果、必需检查、允许差异及所依赖的共用规格和资产。规格记录版本或摘要；修订时说明依据与受影响项，使依赖旧规格的验证失效，保留历史。不得为了通过检查降低既定标准。

证据不足且可补采时回到 03；发现遗漏状态回到 02；来源变化回到 01。不可取得的证据保留缺口，不能用演示假设代替来源事实；其余规格足以实现时进入 05，否则停止该项并继续无依赖项。构建或验证回流时定向修正规格，不重写已确认且未受影响部分。

## Decision rules

遵循 [还原协议](../../rules/prototype-reconstruction.md)；原型写入范围与角色衔接见 [专项 workflow](../../workflow/prototype-reconstruction-workflow.md)。

## Output contract

更新 page-spec.md、本地数据设计、规格摘要与来源映射，遵循文档时间规则。在现有 reconstruction 记录的 iterations 中追加本次执行：workItemId、node（'04'）、result（done/partial/blocked）、changedArtifacts、affectedWorkItems、evidence、nextAction（targetNode/workItemId/reason）。保存后按 workflow 路由；单阶段请求将 targetNode 置为 null，在 reason 中记录建议下一步，不自动推进。
