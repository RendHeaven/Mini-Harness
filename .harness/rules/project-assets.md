# 项目共用原型与历史资产

## 项目原型与历史路径

Schema 20 的 `project.prototypeRoot` 指向项目根共用原型仓库，默认 `原型仓库/`；所有需求共同维护，不按周期建目录或登记消费者。代码写入权限见[原型写入边界](project-execution.md#原型写入边界)。

历史根使用 `project.historyRoot`，默认 `.harness/history/`。新归档按 `<版本号>/` 或 `<产品线>/<版本号>/` 分区；旧扁平历史与冻结原文保留，不批量重写。周期及产品线标识见 [ID 规范](id-and-status-standard.md#版本号)。

## 资产登记

项目可在 `project.serviceCatalog` 所在目录添加可选的 `asset-registry.yaml`，使用独立 `schemaVersion: 1`。`prototypes` 必须为空；`historyImports` 按本规则登记历史来源。

```yaml
schemaVersion: 1
prototypes: []
historyImports:
  - cycle: 产品A-v1.0
    path: .harness/history/产品B/v0.9-prd.md
    hashMode: text-lf
    sha256: <按hashMode计算的64位小写SHA256>
    rationale: 复用已有列表组件基础
    boundaries: 不继承其他产品的配置、页签编排或本期承诺
```

上例须替换为真实配置路径、周期和摘要。两个列表允许为空；所有列出的字段必填，不允许未知字段、重复 YAML 键、重复目录或重复消费周期/历史文件组合。

## 历史导入与摘要

历史导入只允许历史根内的 Markdown、PDF、DOCX 文件，授权绑定确切消费周期、确切文档和实际 SHA256。历史来源字段必须写登记中的完整项目相对路径；裸文件名、其他周期、第二个未登记文件、反斜杠或 `..` 别名不能获得共享许可。

有导入的 PRD，其“历史知识回溯”必须为 `completed` 并显式引用登记来源，即使本产品线没有历史文档也不能标为 `greenfield-skipped`。此处是历史回溯状态，不是 Manifest phase。登记不修改 PRD 产品边界，复用范围仍以 PRD 的真实来源和决策为准。

`hashMode: raw` 基于原始字节，换行变化也使摘要失效；`hashMode: text-lf` 仅用于有效 UTF-8 Markdown，将 CRLF 统一为 LF 后计算，内容、其他字符和独立 CR 均保持。PDF/DOCX 只能使用 raw。摘要语义必须显式声明，不自动选择模式或重算后宣称重新核实。

## 安全校验与维护

登记文件、父目录、原型目录、入口、子树及历史来源均拒绝路径重定向和越界。全项目发现与单周期 Gate 都验证登记；任一声明无效则整份登记不提供允许项并产生硬错误。没有登记的非周期目录和跨产品线历史引用继续报错。

新增或更新登记须记录真实来源、影响与治理 Change。先核实原型用途和适用的消费者、共享文档内容及复用边界，再更新登记；不能为消除错误自动放行目录或历史文档。导入历史原件须保存固定来源 revision 和字节摘要，当前 PRD 引用的修订按[产品修订规则](product-semantics-and-traceability.md#prd-修订)追加，不改写旧证据和审批状态。
