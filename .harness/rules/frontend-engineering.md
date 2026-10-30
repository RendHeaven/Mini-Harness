# 前端工程规则

本文件约束**真实前端仓库**里的实现边界。

项目的组件库、图标库、工具包、样式 Token、API 前缀来源和参考源码由项目 Harness 的 `.harness/projectContext/frontend-stack.md` 声明；存在时必须读取并按其执行，缺失时只以目标工程实际依赖和邻近实现为准。仍须先读目标工程实际依赖和邻近实现，不因为仓库安装了某个新组件库就替换稳定使用中的旧栈。下文“项目组件库”“项目工具包”均指该文件声明的对应项。

下文代码块是写法示例，不是第二套规则；约束以条目为准。

产品探索和静态 UI 原型阶段禁止读取本规则：`skills/product/discovery.md`、`skills/ui/01-static-prototype.md` 只读取 `rules/ui-standard.md`，不进入真实前端工程实现。

## 1. 邻近实现与改动边界

- 先读取邻近目录的写法、命名、导入顺序、组件组织和样式方案，再做最小改动。
- 复用 `src/components`、`src/utils`、`src/services`、`src/store` 中已有能力；不因需求狭窄而新增全局抽象。
- 修改公共组件、公共逻辑、请求封装、store 或发布依赖前，先说明影响范围和验证方式，经用户确认后再写入。
- 配置文件包括 `package.json`、锁文件、`tsconfig*`、构建配置、`.npmrc`、`.env*`、Tailwind/PostCSS/ESLint/Prettier、workspace 和 CI；新增、修改或删除前必须先说明拟改文件、原因、影响和可替代方案并取得确认。只读取配置不需要确认。
- 不为与需求无关的文件做大范围格式化或重构。
- 工作对象是可独立发布的 npm 包时，禁止写入 `workspace:*`、`link:`、`file:` 等只能在本地 monorepo 解析的依赖；临时 link 必须先确认且不得作为发布内容。



## 2. 类型、文案与组件组织

- 组件和页面目录使用 PascalCase，hooks 与工具文件使用 camelCase；邻近目录已有不同约定时邻近优先。
- 组件 props 使用明确接口类型，接口名优先使用 `I` 前缀或邻近文件既有风格。
- 事件、请求参数和响应数据避免无意义 `any`；无法确定时先局部收窄。未使用但因接口约束保留的参数使用 `_` 前缀。
- 复杂 JSX 逻辑提取为命名函数、hooks 或子组件；副作用放在 `useEffect` 并维护准确依赖。
- 用户可见文案使用中文简体，并与同页面已有文案风格一致。
- 非自解释的重要业务逻辑和关键状态流转补充中文简体注释。
- 组件库选择必须邻近实现优先：同模块已用哪套组件库就继续用哪套，系统管理等 `antd` 页面继续用 `antd`。
- 新模块且邻近没有历史约束时，按 `frontend-stack.md` 声明的组件库优先级选择；未声明时沿用目标工程主依赖。
- 图标优先项目声明的图标库或项目已有 Iconfont/SVG，不直接新增其他图标库，也不新增本地图标适配层，除非项目已有同类机制。
- 不重新封装目标工程已有的基础 Button、Modal、Table、Form 或图表容器，除非已有二次封装规范或存在明确复用价值。



## 3. 请求、状态、路由与权限

- API 请求优先放在 `src/services/`，使用 `src/utils/request.ts` 或当前项目统一 request，不在页面散写 URL。
- API 前缀必须读取当前项目已有 `apiPrefix`、request 配置或邻近 service；`frontend-stack.md` 列出的前缀仅作为线索，新增接口必须以当前项目实际配置为准，不得按示例生成不存在的 key。
- service 函数命名优先沿用 `getDataAsync`、`queryListAsync` 等项目既有风格。
- 请求和响应类型与 service 同文件或相邻类型文件维护。
- Zustand store 放在 `src/store/` 或邻近既有位置；state 与 action 分开命名；不把一次性页面局部状态塞进 store。
- 路由改动优先落在 `src/router/index.tsx` 或邻近路由模块。
- 权限判断优先使用 `useCheckPermission`。无权限时不渲染入口的可见规则见 `rules/ui-standard.md`。
- micro-app 相关逻辑优先沿用 `window.microApp` 和 `src/App.tsx` 中既有通信方式。



## 4. 表格实现

可见的分页滚动、Tooltip 和空值占位见 `rules/ui-standard.md`。

- 表格组件必须邻近实现优先；已有 Pagination、QueryForm、StatusTag、Iconfont、`useTableHeight` 或业务 Table 封装时优先复用。
- `columns` 必须有明确类型；列宽、对齐、fixed、ellipsis、render 按邻近表格风格设置。
- `rowKey` 必须稳定且来自业务唯一字段；禁止在可变列表中使用 index 作为 `rowKey`。
- 只有用户明确要求处理长文本溢出并展示 Tooltip 时，才为长文本列增加 `OverflowTooltip`。项目组件库已提供且邻近不冲突时从项目组件库引入；否则复用本地封装。
- 项目组件库未安装且没有本地封装时，读取 `frontend-stack.md` 登记的参考源码后再沉淀本地兼容封装。若参考源码无法访问、没有权限或读到登录页，先中止并抛出网址让用户授权，不能臆造组件细节；未登记参考源码时按目标工程现有能力实现最小封装。
- 空兜底值不要再套无意义 Tooltip。
- 接口分页字段必须与后端约定一致；不明确时不得写死 `current/pageSize/total` 映射。
- 表格自带 pagination 和外置 Pagination 不能混用；按邻近页面保持一致。
- 页面存在查询区时，优先复用 `useTableHeight` 或邻近高度计算方式，并清理 resize / observer 监听。
- 禁止在 columns render 中直接发请求或修改全局状态。
- 禁止把复杂单元格编辑、上传、校验逻辑堆在一个 render 函数里。

示例（仅当用户明确要求溢出 Tooltip）：

```tsx
import { OverflowTooltip } from '<项目组件库>';

{
  title: '名称',
  dataIndex: 'name',
  ellipsis: { showTitle: false },
  render: (value?: string) => {
    const text = value?.trim() ? value : '-';
    return text === '-' ? text : (
      <OverflowTooltip tooltipContent={text}>{text}</OverflowTooltip>
    );
  },
}
```



## 5. 图表实现

可见的空态、色板和标签不重叠见 `rules/ui-standard.md`。option 中的单位、颜色和统计口径必须来自已确认事实，不得在配置里编造。

- 图表封装必须邻近实现优先；同模块已有项目组件库 ECharts、本地 `src/components/ECharts/` 或其他既有图表封装时继续沿用。
- option 使用 `EChartsOption`、`CustomEChartsOption` 或当前封装导出的类型。
- 图表封装支持由 `data` 生成默认 option 时，无特殊样式只传 `data`；需要覆盖时同时传 `data` 和 `option`，由组件用 `data` 生成默认 option 再与 `option` 深度合并，且 `option` 字段优先。不要为少量覆盖手写完整 option。

示例（以支持 `data` + `option` 的封装为例）：

```tsx
<ECharts
  data={{
    type: 'bar',
    xdatas: ['1月', '2月', '3月'],
    ydatas: { 产量: [1000, 200, 150] },
  }}
  option={{
    tooltip: { unit: ['km'] },
    series: [{ label: { show: true }, showBackground: true }],
  }}
/>
```

- 没有既有图表封装且需要直接配置 echarts 时，优先读取 `frontend-stack.md` 登记的图表参考源码。无法访问时中止并抛出网址，不能臆造源文件细节。可抽离的默认风格通常包括：默认色板、深色半透明 tooltip、白边圆点 marker、统一坐标轴、圆形 legend、柱状图最大宽度和正负值圆角、折线默认隐藏 symbol 且 hover 显示圆点、饼图底部滚动 legend 和标签防重叠。
- 柱状图、折线图默认携带 `toolbox` 和 `inside` 类型 `dataZoom`；不展示底部滑块，除非业务明确需要或邻近页面已使用。
- `axisLine.onZero` 未被明确要求时设为 `false`。
- tooltip 多系列使用 `trigger: 'axis'`，系列顺序稳定。
- 数据转换放到 service、hooks、utils 或清晰命名函数中，不在 JSX 内临时拼复杂 option。
- 容器尺寸变化时必须触发 resize 并清理监听。dataZoom、toolbox、点击事件和图例选中要与页面状态同步。
- 图表没有跳转能力时鼠标为箭头；有点击跳转能力时鼠标为小手。
- 禁止把图表配置散落在多个副作用中导致状态难以追踪。



## 6. 格式化与空态实现

数字精度、千分位、日期格式、`0` 为有效值、空值占位和「暂无数据」见 `rules/ui-standard.md`。本文件只约束如何落到代码。

- 项目工具包已提供千分位函数（如 `formatThousand`）时直接引入；未提供时使用项目现有 formatter，避免重复实现千分位。
- 优先复用项目已有 format、math、dict、枚举和状态标签；缺少通用能力时只在当前模块新增局部工具，跨 3 处复用再提升到公共 utils。
- 表格、详情、图表 tooltip / axisLabel、导出前预览和表单只展示格式化后的稳定值。
- 日期优先 dayjs；历史文件已使用 moment 时沿用。
- 使用 antd 或兼容 antd 的 Empty 时，空态图片默认 `Empty.PRESENTED_IMAGE_SIMPLE`。空态描述优先按接口 `code` 从 `@/enums` 的 `ErrorCodeMessage` 取中文文案。
- 禁止用 `value || '-'` 或同类假值判断处理可能为 `0` 的数字字段。
- 禁止在多个表格 render、tooltip formatter、axisLabel 或详情 JSX 中重复写临时格式化逻辑。
- 禁止把空值写成空字符串。
- 禁止在 tooltip、axisLabel 或详情中直接拼接未格式化的 `null`、`undefined`、`NaN`。
- 接口失败提示不要和 request 全局错误重复弹出，除非业务需要局部错误说明。



## 7. 样式实现

- 目标工程已使用设计 Token + Tailwind 时：新增业务样式优先 Tailwind 工具类，文字、背景、边框、阴影、圆角和主按钮状态使用 `frontend-stack.md` 声明的 Token 类名，不硬编码色值。
- Tailwind 横向尺寸优先 `w-vw-[设计稿px]`、`px-vw-[设计稿px]`、`gap-vw-[设计稿px]`；纵向优先 `h-vh-[设计稿px]`、`py-vh-[设计稿px]`。全屏可用 `h-[calc(100vh_-_var(--app-header-height))]`。
- Tailwind 新页面不新增 `.less`，不恢复 Less 预处理；普通全局样式用 `.css` 和 PostCSS，CSS Module 用 `.module.css`。
- 老项目页面和组件样式优先沿用 Less + CSS Modules，通常为 `index.module.less`，className 通过 `styles.xxx` 引用。不要把 Tailwind 页面强行套回 Less，也不要把老页面强行改成 Tailwind。
- CSS Module 仅用于覆盖第三方 DOM、表达工具类难以描述的复杂选择器，或维护已有模块。
- 不随意变更公共组件样式、参数和结构。



## 8. 工程验证

- 目标工程已有 Playwright 视觉回归时优先跑视觉回归。视觉测试文件放在 `tests/visual`，使用 `toHaveScreenshot()`，视口 `1440 × 800`。
- 首次生成或确认设计稿变更后运行 `yarn test:visual:update`（或工程等价命令）；日常检查运行 `yarn test:visual`。工程没有这些脚本时记录为不可用，不伪造结果。
- 依赖接口的页面必须在视觉测试中 mock 接口，并覆盖标准兜底、空状态和加载状态。
- 涉及逻辑、状态、权限、请求或共享工具时补充或更新单元测试；无法补充时在交付说明中写明原因和剩余风险。

