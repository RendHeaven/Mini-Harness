---
name: reconstruction-source-assessment
description: 原型补建时定位项目、源码和运行来源，确定还原范围与模式。
---

# 来源评估

## Objective

固定还原来源、范围和可验证边界，为后续工作项循环建立基线。

## Inputs

项目、目标模块或页面、可用源码/运行地址/截图。

## Workflow

1. 按项目配置解析 Core、原型根、服务目录及周期；核对 meta binding，不凭目录推定归属。明确周期后再写 UI 记录；只读盘点无需新建虚构版本。
2. 读取目标仓库 AGENTS；没有时读取 README、路由、package 和启动配置。记录分支、HEAD、dirty 及源文件摘要；保留已有修改。
   核对远端跟踪引用及采集时间；本地分支名相同不代表已同步。有同步授权时先 fetch 并比较提交关系，按授权范围更新干净分支；不要为消除差异自动切分支、stash 或 reset。新发现版本差异须保留旧证据，重新执行状态盘点，旧版通过项不能继承给新版。
3. 盘点现有共用原型和历史候选，记录保留/补建范围。历史原型不自动作为当前工程事实。
4. 判断运行条件。可用且获授权时运行并采集；依赖缺失或无可用环境时采用 source-derived，继续源码工作，记录视觉核实缺口。不要启动数据库、生产构建或遥测来验证原型。
5. 输出来源模式、目标区域/状态、排除项、验证条件；有可确认的版本冲突先解决基线，不把不同版本拼接。按还原协议记录基线标识与摘要，固定本轮 requiredChecks；缺少运行基线不删除视觉检查。
6. 来源变更回流到本节点时，比较新旧基线并列出受影响工作项、规格与资产；使相关验证失效，保留历史结果和人工调整。只重排受影响项，不重置全部队列。

source 与 scope 是来源和范围的权威记录。基线可用时进入 02 建立或更新队列；来源冲突尚未解决时记录受阻范围，其余独立工作可继续。单阶段请求保存结果后结束。

## Decision rules

遵循 [还原协议](../../rules/prototype-reconstruction.md)；原型写入范围与角色衔接见 [专项 workflow](../../workflow/prototype-reconstruction-workflow.md)。

## Output contract

更新 source、scope、基线与必需检查。在现有 reconstruction 记录的 iterations 中追加本次执行：workItemId（全局动作可为 null）、node（'01'）、result（done/partial/blocked）、changedArtifacts、affectedWorkItems、evidence、nextAction（targetNode/workItemId/reason）。保存后按 workflow 路由；单阶段请求将 targetNode 置为 null，在 reason 中记录建议下一步，不自动推进。
