# <需求标题>（接口文档）

<!-- atlas:generated document-timestamps:start -->
- 创建时间：`<yyyy-MM-dd HH:mm:ss>`
- 最后编辑时间：`<yyyy-MM-dd HH:mm:ss>`
- 时区：`Asia/Shanghai`
- 编辑记录：
  - `<yyyy-MM-dd HH:mm:ss>`｜创建｜首次生成本文档。
<!-- 后续每次编辑在编辑记录末尾追加“时间｜操作｜摘要”，同步最后编辑时间；不得覆盖历史记录。 -->
<!-- atlas:generated document-timestamps:end -->

- Owner 服务：`<service-id>`
- 需求版本：`v<主版本>.<次版本>`
- Consumers：`<service-id>`
- 接口文档协议：`v5`

<!-- 使用模板前读取[接口文档 v5](../../../rules/api-document.md)，生成产物时移除此提示。 -->

## 接口总览

| 接口编号 | 来源 Plan | 接口地址 | 接口名称 |
| --- | --- | --- | --- |
| API-NNN | `plan-NN-<slug>.md` | `POST /resource/query` | <接口名称> |

## 具体接口

### [API-NNN] <接口名称>

- 来源 Plan：`plan-NN-<slug>.md`
- 接口地址：`POST /resource/query`
- 功能说明：<调用时机、业务作用和写入效果>

#### 请求体

| 字段 | 类型 | 是否必填 | 说明 |
| --- | --- | --- | --- |
| `body.keyword` | string | 否 | 最大 100 字符；检索关键字 |
| `body.page.current` | integer | 是 | 从 1 开始；页码 |

#### 响应体

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `data.records[]` | array<object> | 当前页数据 |
| `data.records[].id` | string | ID |
| `data.total` | integer | 总记录数 |

#### JSON 示例

```json
{
  "request": {
    "keyword": "示例",
    "page": { "current": 1 }
  },
  "response": {
    "data": {
      "records": [{ "id": "example-id" }],
      "total": 1
    }
  }
}
```

#### 成功状态

| HTTP 状态 | 业务状态 | 说明 |
| --- | --- | --- |
| 200 | `ResponseResult` 成功 | 请求已完成；业务数据位于 `data` |

#### 错误状态

| 触发条件 | HTTP / 业务码 | 说明 |
| --- | --- | --- |
| <条件> | <状态或业务码> | <错误原因> |
