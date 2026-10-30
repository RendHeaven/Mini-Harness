# 四角色独立 Gate

项目根 Gate.yaml 是状态唯一权威，按周期保存 product、ui、frontend、backend。原型为根目录项目共用资产。四角色无 dependsOn，不规定确认先后；TestHub 不作为第五道 Gate。

状态为 not_started、in_progress、pending_confirmation、confirmed、changes_requested、not_applicable。角色内部阶段有顺序，但其他角色状态不阻止启动。不适用必须说明依据及决定人。

通过 role_gates.py 初始化、检查、更新；记录实际执行主体、秒级 +08:00 时间、原因和完整历史。一次只更新一个周期的一个角色，使用排他锁及原子替换，可附 expected-digest 防止旧副本覆盖。

产品确认 PRD、原型与修订追踪；UI 确认原型、调整及视觉验证；前后端各确认自身所有适用服务的工程、契约、Review 与测试。真实接口等工程依赖不改写为 Gate 前置。

产品角色进入确认阶段后先按[产品确认技能](../skills/product/gate-confirm.md)完成反问收束和必要修订。反问回答或仅确认共同理解不能自动产生 confirmed；当前交付未变时，可在一次明确答复中同时确认共同理解与最终交付。有修订时必须针对修订后的交付确认。此要求由产品工作流执行，不新增 Gate 状态或其他角色前置，也不把现有工具校验通过当作已执行反问的证据。

机器检查不能产生真实负责人确认。封板是一次确认记录，不冻结文件。confirmed 必须有 confirmedBy、confirmedAt、confirmedGit（name、email）、明确确认范围的 reason、实际证据路径和 PRD/原型的来源及变更引用；不复制 PRD、原型或证据正文。

Gate 使用 Schema 2。`sources.prd` 为 `{path, changes: [CHG-...]}`，`sources.prototype` 为 `{path, changes: [已有变更记录的项目相对引用...]}`，例如带实际周期前缀的 `product/mock-changelog.md#CHG-001`、`ui/adjustments/UI-ADJ-001.md` 或 `ui/reconstruction/<记录>.yaml#iteration-1`。changes 保存本次确认已覆盖的唯一记录；初次追踪尚无修改时为 `[]`，无法核实的范围为 `null`，二者不可混用。证据使用普通 `path` 引用。Execution Schema 7 及各工程轨道采用同一来源结构，分别记录实际已消费范围。

PRD/原型始终原位维护当前内容，历史确认及其来源引用保留。后续新增变更不属于旧确认；复核时展示上次确认后新增的 CHG、原型日志条目及影响，由各角色决定受影响部分的复核范围。原型每次修改在 Mock 日志追加唯一 CHG 锚点、生成独立 UI-ADJ 文档，或追加原型补建 iteration；不能仅以日志路径相同推定全部内容已确认。不得因整份 PRD/原型的 hash 变化自动使角色确认失效，也不自动重置其他 Gate。角色确认不自动代表测试、发布或周期完成。

Manifest phase 记录实际进展，不从 Gate 推导。取消周期不得新增交付。Execution 保存工程事实，不另存 Gate 权威。当前校验和写入只接受 Gate Schema 2。

## 确认者 Git 身份

四角色确认时，工具在项目 Harness 仓库根读取生效的 git config user.name 和 user.email，记录在 confirmedGit.name / confirmedGit.email，并同步保存到本次 history.record。仓库局部配置优先，缺省可使用 Git 的全局配置；缺少任意字段或读取失败时拒绝确认，Gate.yaml 保持原样。

confirmedBy 保留实际确认人的显示名称；confirmedGit 是该确认人当次使用的 Git 配置身份，不从最后一次提交作者、服务仓库或远端账号推断。执行确认前确保生效的 Git 身份属于实际确认者，代理代录不能把其他账号写成确认人。缺失时补齐真实身份后再确认，不自动修改 Git 配置。此信息是当次身份记录，不等于 Git 服务器认证或签名。

未确认状态的 confirmedGit 为 null；重新进入工作时仅清空当前确认字段，历史确认身份保持不变。只读校验验证保存的字段，不拿当前 Git 配置反向修改或否定历史。再次确认时重新捕获本次身份。

缺少真实 confirmedGit 等信息时，不能用当前 Git 配置补写过去的确认身份。

## 角色执行约定

角色沿用与切换见[执行约定](project-execution.md#角色执行)。确认角色不等于确认 Gate；只有实际负责人明确确认交付后才记录该角色 Gate，不能因角色选择而改变其他角色状态。

变更引用的比较仅覆盖当前周期已登记的条目，不证明整个共用原型的所有内容均获确认；跨周期改动按实际影响关联到本周期记录，确认范围以 reason 和具体变更引用为准。
