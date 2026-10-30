# <需求标题>（前端测试养料）

<!-- atlas:generated document-timestamps:start -->
- 创建时间：`<yyyy-MM-dd HH:mm:ss>`
- 最后编辑时间：`<yyyy-MM-dd HH:mm:ss>`
- 时区：`Asia/Shanghai`
- 编辑记录：
  - `<yyyy-MM-dd HH:mm:ss>`｜创建｜首次生成本文档。
<!-- 后续每次编辑在编辑记录末尾追加“时间｜操作｜摘要”，同步最后编辑时间；不得覆盖历史记录。 -->
<!-- atlas:generated document-timestamps:end -->

- 前端服务与 Revision：`<service-id>@<revision>`
- Review：`<路径>`
- 接口文档：`<owner:path>`

## REQ 与页面

| REQ | 角色 | 页面/入口 | 变更 | 风险 |
| --- | --- | --- | --- | --- |
| REQ-001 | <角色> | <页面> | <变更> | <风险> |

## TestHub 测试盲区

- 页面层级、返回和跨页面联动：<内容>
- 加载、空、异常、权限和恢复：<内容>
- 表单、重复点击、慢网和竞态：<内容>
- 尺寸、滚动、表体滚动与分页可见性：<内容>
- 图表空态与视觉回归：<内容>
- 公共组件回归：<内容>

## 工程边界盲区

| 维度 | 是否适用 | 残留风险 |
| --- | --- | --- |
| 表格 | yes/no | <rowKey、分页、权限入口或 none> |
| 图表 | yes/no | <空态、resize、口径或 none> |
| 数据格式化与空态 | yes/no | <0 值、占位符、精度或 none> |
| 代码与请求边界 | yes/no | <request、权限渲染或 none> |

