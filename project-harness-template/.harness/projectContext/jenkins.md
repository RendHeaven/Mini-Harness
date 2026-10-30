# 项目 Jenkins 映射

本文件仅为可选模板，所有占位符须根据实际工程核实后填写。它保存项目服务到 Jenkins 的索引和发布约束；Jenkinsfile、构建脚本及部署清单仍由服务仓库持有。连接 URL 与 Token 使用客户端本地配置，见 [接入说明](../tools/jenkins-mcp.md)。不要在 `services.yaml` 增加未定义的 Jenkins 字段。

从项目 `.harness/harness.yaml` 的 `core.localPath` 加载 Core，再读取其 `.harness/skills/delivery/jenkins.md`；不要复制通用技能到项目中。更新下列索引时记录核对时间、来源 revision 与负责人，防止静态映射代替当前事实。

## 服务与任务

| 服务 ID | 环境 | 完整 Job 路径 | 用途及是否含部署 | 定义来源与 Revision | 核对时间 | 维护人 |
| --- | --- | --- | --- | --- | --- | --- |
| <services.yaml 的真实 ID> | <真实环境> | <Folder/Job，保留中文及大小写> | <仅构建/构建并部署及影响范围> | <服务仓库 Jenkinsfile/Job 定义引用> | <yyyy-MM-dd HH:mm:ss，Asia/Shanghai> | <维护人> |

## 参数映射

每个 Job/环境分别记录。真实参数可能与其他项目不同；不默认使用 `BRANCH`、`DEPLOY_ENV`，不将 GitLab 地址天然视为可传参数。敏感值由 Jenkins 凭据机制处理，本文件仅写用途，不保存其值。

| 服务 ID / 环境 / Job | 业务含义 | 真实参数名 | 必填及允许值约束 | 取值来源 | 定义来源 |
| --- | --- | --- | --- | --- | --- |
| <对应映射> | <分支/提交/环境等> | <真实参数名；固定配置则 not-applicable> | <按真实 Job 定义> | <用户目标/服务事实> | <Job/Jenkinsfile 及 revision> |

## 发布与验证约束

| 服务 ID / 环境 | 发布前提 | 授权与生产审批来源 | 版本核对依据 | 健康/业务检查依据 | NodePort/访问地址来源 | 平台联系入口 |
| --- | --- | --- | --- | --- | --- | --- |
| <对应映射> | <真实要求及影响范围> | <实际流程/审批记录位置> | <检出提交与部署版本来源> | <检查方式与判定依据的引用> | <部署清单/本次日志/环境查询入口> | <负责人或工单入口> |

映射存在不代表本次操作已授权，也不保证 `ALLOWED_JOBS`、Jenkins 权限或 `ENABLE_BUILD` 已开放。服务端拒绝时申请相应权限，不修改索引伪造授权。

## 执行证据位置

- 需求周期内：项目配置的周期根下 `develop/delivery/<service-id>/jenkins-<yyyyMMdd-HHmmss>-<序号>.md`，每次触发独立记录。
- 无需求周期的运维任务：`<填写本项目约定的执行记录目录；未采用前不创建示例事实>`。
- 使用 Core `.harness/template/develop/delivery/jenkins-execution-template.md`，记录本次回执与构建编号关联、实际 revision、构建和部署验证的各自结果。
