# Atlas Core 维护约定

本文件用于维护 Atlas 自身。项目使用入口为 [AGENTS.md](../AGENTS.md)，Core 不保存具体项目的 PRD、需求版本、服务源码或工程事实。

## 入口职责

Atlas AGENTS.md 只负责内容概括、角色工作流路由、能力边界和目录说明；目录职责统一见该文件。项目 AGENTS.md 只指向 Atlas 入口并说明项目结构。通用执行细节放在 workflow、skill 与 rules，项目专项约束放项目上下文。

## 修改与发布

1. 按工作区 meta-harness change-policy 明确 Change、影响、实施与推广范围；不自动修改其他项目、绑定或发布。
2. 修改权威来源后同步引用；README 只保存简介、入口和使用说明。Core 维护要求不复制到项目入口。
3. 修改 Schema、模板字段或校验器时同步测试、版本锁和当前使用说明；文案变更也要核对内容锁覆盖范围。精确 pin 必须对应实际 Git revision 和内容哈希，不用未提交内容冒充已发布版本。
4. Core 仅维护当前协议、工具和使用说明；版本以 `.harness/harness.yaml`、`.harness/version.lock` 及真实 Git revision 为准。实施过程、采用记录与独立评估由工作区治理记录持有，不在 Core 增加版本日志或迁移档案。本地自测不代表正式发布、独立 Evaluation 或业务 Gate 确认。

## 模板公共片段

时间格式与编辑语义由[时间规范](../.harness/rules/document-timestamps.md)定义，模板的公共正文只维护[时间片段](../.harness/template/_fragments/document-timestamps.md)。已登记模板中的 `atlas:generated document-timestamps:start/end` 注释划定同步区域；其他正文仍在各模板中维护。新增适用模板时在[同步工具](../.harness/tools/sync_template_fragments.py)的 `TEMPLATE_PATHS` 登记并显式放置标记，不根据正文自动扩张写入范围。

从 Core 根目录执行：

```powershell
python .harness/tools/sync_template_fragments.py --check
python .harness/tools/sync_template_fragments.py --write
python .harness/tools/test_sync_template_fragments.py
```

无参数等同于 `--check`，只读检查通过返回 0、漂移返回 1、输入异常返回 2；`--write` 只更新已登记模板的生成区域，无差异时不写入。修改片段后同步并审查 diff，再运行契约测试。CI 只检查，不自动修复或提交。

工具从自身位置定位 Core，不接受项目根或任意输出路径；拒绝缺失、重复、未知或未闭合标记及路径重定向。全部输入预检后暂存，写入前复核内容；失败时回滚已写入文件，遇到后续编辑则保留该编辑并报告原文备份路径。进程或系统强制中断后先核对现场和 Git diff，不把多文件更新视为文件系统事务。

时间片段保留占位符，编译时不读取当前时间；项目文档的真实时间、历史编辑记录和修订链仍由实际阶段及专用工具维护。生成项目文档时移除这两个 Core 维护标记。TestHub 的时间块保持在“文档信息”内；本工具不生成用例、同步远端、改写项目周期或更新 Gate。

## 验证

在 Core 根目录执行，Python 依赖见 `.harness/tools/requirements.txt`。按变更范围触发，避免无关全量测试。

| 场景 | 验证 |
| --- | --- |
| 日常 workflow / skill / 规则文案 | `python .harness/tools/validate_harness.py --core-only`，可选 |
| Schema、模板字段或校验器 | 先相关契约测试，再 `--core-only` |
| 发版、项目 pin 或正式 Gate | `python .harness/tools/validate_harness.py --project-root <实际项目根>`，可附单个周期路径 |

`test_validate_harness.py` 检查既有契约，`test_role_protocol.py` 检查新角色协议。开发检查可用 `--allow-dirty-core`，不能作为正式锁定凭据。机器检查不替代浏览器、数据库、接口、部署验证或真实负责人确认。
