---
name: reconstruction-page-evidence-capture
description: 按页面状态采集运行或源码证据，固定采集条件与真实覆盖范围。
---

# 页面证据采集

## Objective

收集可复核的运行或源码证据。

## Inputs

当前工作项及其 stateIds、状态矩阵、固定来源基线和本轮待补证据。

## Workflow

- 能运行时按关键路径导航，记录视口、浏览器、角色、版本、时间与数据条件；采集页面/区域截图、可见 DOM、计算样式、资源与操作前后变化。使用环境允许的浏览器工具；工具能力缺失不得伪造截图或采集成功。
- 只读源码时采集准确路径、符号、行号范围和文件 SHA256，提取布局、字段、枚举、事件、可移植资产。不要将代码推断标成浏览器观察。
- 图表、Canvas、虚拟列表、懒加载和遮罩层需要单独操作与区域证据，首屏截图不代表全部数据或状态。
- 操作运行页前辨别副作用：筛选、图例、颜色等表面展示控件也可能保存用户配置；结合源码和已知接口判定，只读取证不执行真实持久化。未知行为留缺口，原型本地模拟通过不能授权操作原系统。
- 只在确有需要时记录接口样本，遵循还原协议的凭据与数据边界。HAR 回放仅是采集/测试手段，不等于交付原型拥有离线 Runtime。
- 首次采集按当前工作项执行；回流时只补缺失或失效证据，可复用仍匹配当前基线和采集条件的既有证据。每次保存成功与失败结果，不能覆盖前次采集事实。

发现遗漏状态回到 02 更新矩阵；来源变化回到 01。证据可用时进入 04；确实无法获取的证据记录原因、受影响检查与恢复条件，不无限回采。其余依据足够时允许携带缺口进入 04，受影响结论保持未核实；缺口阻止构建时停止该项并继续无依赖项。

## Decision rules

遵循 [还原协议](../../rules/prototype-reconstruction.md)；原型写入范围与角色衔接见 [专项 workflow](../../workflow/prototype-reconstruction-workflow.md)。

## Output contract

更新 evidence 索引、独有截图和缺口，不复制整份产品或源码。在现有 reconstruction 记录的 iterations 中追加本次执行：workItemId、node（'03'）、result（done/partial/blocked）、changedArtifacts、affectedWorkItems、evidence、nextAction（targetNode/workItemId/reason）。保存后按 workflow 路由；单阶段请求将 targetNode 置为 null，在 reason 中记录建议下一步，不自动推进。
