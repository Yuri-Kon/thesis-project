# Inspector 卡片拖拽重排 — 设计规格

**SID:** `interface.web_workspace.inspector_reorder`
**Issue:** #317
**日期:** 2026-05-02
**状态:** revised

## 审查结论

原方案的方向是对的: Inspector 面板内的辅助卡片应该允许用户按页面调整顺序，并且该偏好只属于前端显示层。但原稿直接采用 HTML5 Drag and Drop API、事件委派和拖拽期 DOM transform，和当前 React 页面结构贴合不足，且会把移动端、键盘无障碍和状态一致性风险留给实现阶段。

本规格改为:

- 页面不再向 `InspectorPanel` 传裸 `ReactNode`，而是传稳定 key 的 `InspectorCardDescriptor[]`。
- 重排状态由 React 的 `order: string[]` 驱动；指针拖动期间只把临时拖动状态保存在 ref，释放后一次性提交。
- 指针拖动使用 Pointer Events，不使用 native HTML5 Drag and Drop 作为排序主路径。
- 每张卡片提供可聚焦的拖动手柄和显式上移/下移按钮，保证不能或不想拖动的用户也能完成同一操作。
- localStorage 只保存 key 顺序，不保存卡片内容、状态文本、任务 ID 或用户输入。

## 外部参考

- MDN HTML Drag and Drop API: HTML DnD 事件继承自 mouse events，`dragover` 会高频触发，drop 需要取消 `dragover` 才能成为有效目标；它更适合跨应用/文件拖放，不适合作为本场景唯一交互基础。参考: https://developer.mozilla.org/en-US/docs/Web/API/HTML_Drag_and_Drop_API
- MDN Pointer Events: Pointer Events 为 mouse、pen、touch 提供统一事件模型，并支持 pointer capture，适合本地可拖动 UI。参考: https://developer.mozilla.org/en-US/docs/Web/API/Pointer_events
- dnd-kit Sortable: sortable 列表需要让排序数组和实际渲染顺序保持一致，并通过 pointer/keyboard sensor 支持不同输入方式。参考: https://dndkit.com/legacy/presets/sortable/overview/
- dnd-kit Accessibility: 拖拽交互需要键盘支持、屏幕阅读器说明和 live region 公告。参考: https://dndkit.com/legacy/guides/accessibility
- Atlassian Pragmatic drag and drop accessibility guidelines: 必须提供拖拽之外的等效操作，例如按钮或菜单。参考: https://atlassian.design/components/pragmatic-drag-and-drop/accessibility-guidelines
- React Rendering Lists / Updating Arrays in State: 可重排列表必须使用稳定 key，并以新数组更新顺序状态。参考: https://react.dev/learn/rendering-lists 与 https://react.dev/learn/updating-arrays-in-state

## 目标

Inspector 面板内卡片支持用户自定义排序，排序按页面独立持久化到 localStorage。该能力只改变前端信息排列，不改变 API 请求、任务状态、人工确认流程或任何后端契约。

## 非目标

- 不同步到后端，不跨设备同步。
- 不允许用户隐藏卡片或编辑卡片内容。
- 不把主工作区、Sidebar、Pending Review 列表纳入同一套排序能力。
- 不引入 `@dnd-kit`、Pragmatic drag and drop 或其他第三方拖拽库；这些库只作为行为设计参考。

## 当前系统贴合点

当前页面结构是:

```text
main.tsx
  ├─ useState<ReactNode>(null)
  ├─ Page → useEffect → onInspectorChange(<>{...cards}</>)
  └─ InspectorPanel({ children })
```

这意味着重排不是 `InspectorPanel` 内部加事件就能完整解决的事。必须先把 Inspector 内容从“任意 JSX children”迁移到“稳定描述符数组”，否则无法可靠保存顺序、过滤已删除卡片、追加新增卡片，也无法给每张卡片生成一致的拖动/键盘控制。

迁移后的结构:

```text
main.tsx
  ├─ useState<InspectorCardDescriptor[]>([])
  ├─ pageKey = bootstrap.view
  ├─ Page → useEffect → onInspectorChange([...cards])
  └─ InspectorPanel({ cards, pageKey })
       ├─ collapsed state
       ├─ order state
       ├─ refs: card elements, drag session, live region
       ├─ pointer handlers on handle buttons
       ├─ explicit move up/down handlers
       └─ render sorted descriptors
```

## pageKey 映射

`bootstrap.view` 目前已经是稳定枚举，可直接作为 pageKey。

| bootstrap.view | pageKey |
| -------------- | ------- |
| dashboard | dashboard |
| task_detail | task_detail |
| task_builder | task_builder |
| event_timeline | event_timeline |

如果未来出现按任务实例独立排序的需求，需要另起规格确认；本次不把 `taskId` 拼入 storage key，避免同一页面类型产生大量无用偏好。

## 卡片描述符接口

```ts
export interface InspectorCardDescriptor {
  key: string;
  title: string;
  tone?: "default" | "warning";
  statusBadge?: ReactNode;
  className?: string;
  children: ReactNode;
}
```

约束:

- `key` 必须在同一页面的 Inspector 卡片中唯一、稳定，不能使用数组下标、随机值或标题文本。
- `title` 是卡片可访问名称的一部分，不能只依赖视觉内容。
- `tone` 负责表达已有的 `warning-card` 语义；`className` 只用于局部兼容，不作为主扩展机制。
- `children` 允许包含现有按钮、链接、表单控件；拖动只能从手柄开始，不能抢占卡片内容里的交互。

## 默认卡片定义

| 页面 | 卡片 key |
| ---- | -------- |
| Dashboard | `inspector-overview`, `action-required` |
| TaskDetail | `inspector-overview`, `operation` |
| TaskBuilder | `inspector-overview`, `safety-precheck`, `action-required` |
| EventTimeline | `inspector-overview`, `timeline-boundary` |

迁移时保留现有文案、指标和按钮行为，只调整卡片包装方式。

## DOM 结构

```html
<aside class="workbench-inspector" aria-label="Inspector">
  <button class="inspector-toggle" />
  <div class="inspector-content" role="list" aria-describedby="inspector-reorder-help">
    <section class="inspector-card" role="listitem" data-card-key="inspector-overview">
      <div class="inspector-card__header">
        <h2 class="inspector-card__title">Inspector</h2>
        <!-- statusBadge -->
        <button class="inspector-card__move" aria-label="Move Inspector up">↑</button>
        <button class="inspector-card__move" aria-label="Move Inspector down">↓</button>
        <button class="drag-handle" aria-label="Reorder Inspector" aria-describedby="inspector-reorder-help">↕</button>
      </div>
      <div class="inspector-card__body">
        ...
      </div>
    </section>
  </div>
  <p id="inspector-reorder-help" class="sr-only">
    Drag cards by the reorder handle, or use the move up and move down buttons.
  </p>
  <p class="sr-only" aria-live="polite" />
</aside>
```

说明:

- 手柄必须是 `<button type="button">`，不能用不可聚焦的 `<span draggable="true">`。
- 上移/下移按钮在卡片数量小于 2 时隐藏或禁用；第一张禁用上移，最后一张禁用下移。
- 卡片内容区不设置 `draggable`，避免链接、按钮、文本选择和表单操作被拖拽机制截获。
- `.sr-only` 使用现有可访问隐藏样式；如果项目尚无该样式，在 `app.css` 中新增通用实现。

## 排序状态

`InspectorPanel` 内部维护当前页面的 key 顺序:

```ts
type InspectorOrder = string[];

function resolveOrder(stored: readonly string[], cardKeys: readonly string[]): string[] {
  const keySet = new Set(cardKeys);
  const seen = new Set<string>();
  const known = stored.filter((key) => {
    if (!keySet.has(key) || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
  const newcomers = cardKeys.filter((key) => !seen.has(key));
  return [...known, ...newcomers];
}
```

实现要求:

- `cardsByKey = new Map(cards.map((card) => [card.key, card]))`，渲染时按 `order` 映射回 descriptor。
- 当 `cards` 或 `pageKey` 变化时重新 resolve；不要复用上一个页面的排序状态。
- 如果开发模式发现重复 key，保留第一个并在 `console.warn` 中提示；不要因为重复 key 崩溃生产页面。
- 重排数组更新必须创建新数组，不能原地 `sort` / `splice` 当前 state 后再 `setState`。

## 指针拖动机制

### 为什么不用 HTML5 Drag and Drop

本场景是同一 React 列表内排序，不需要跨窗口、文件或外部应用传输数据。native DnD 需要 `dataTransfer`、drop target 取消 `dragover`，并且事件模型偏 mouse；它会带来移动端兼容性、默认幽灵图、文本选择和嵌套交互冲突。Pointer Events 更适合“按住手柄移动卡片”的本地 UI 行为。

### 行为流程

| 阶段 | 行为 |
| ---- | ---- |
| pointerdown | 只在 `.drag-handle` 上启动；忽略非主指针；记录 `activeKey`、初始坐标、卡片 rect；调用 `setPointerCapture` |
| pointermove | 超过 4px 阈值后进入 dragging；根据指针 Y 坐标和卡片中线计算目标位置；用 rAF 更新 `drop-indicator` 与源卡片样式 |
| pointerup | 如果位置变化，计算新 order，一次 `setOrder` 并写 localStorage；公告结果；释放 pointer capture |
| pointercancel / Escape | 清理拖动状态，不提交排序；公告取消 |

实现纪律:

- 拖动期间不在每个 `pointermove` 调用 `setState`。
- 临时状态放入 ref: `activeKey`, `pointerId`, `originY`, `latestClientY`, `dropIndex`, `frameId`。
- 只测量 `.inspector-card` 的 bounding rect；不修改 card children。
- 释放或取消时必须清理 class、inline transform、drop indicator、frameId 和 pointer capture。
- 拖动中禁用文本选择: 仅在 `workbench-inspector` 加 `.is-reordering`，不要全局改 `body`。

### 视觉反馈

不使用透明幽灵图。源卡片保留原位并降低透明度，目标位置显示细线 drop indicator；其他卡片不需要复杂让位动画。Inspector 每页只有 2 到 3 张卡片，简单 drop indicator 比全量 FLIP transform 更稳定、更易读。

## 键盘与替代操作

必须提供的非拖动路径:

- 上移/下移按钮: 默认可见但低对比，hover 和 focus-within 时提高强调；键盘可 Tab 到达，触发后保持焦点在被移动卡片的对应按钮或手柄上。

可选增强:

- 手柄键盘拖动: 聚焦手柄后按 Space/Enter 进入“拾起”状态；ArrowUp/ArrowDown 调整预览位置；Space/Enter 放下；Escape 取消。该模式贴近 dnd-kit keyboard sensor，但会引入 `idle -> picked -> idle` 的额外状态机；第一版不要求实现，除非上移/下移按钮已经完成且交互仍需要更接近拖动手柄的键盘体验。

屏幕阅读器要求:

- `aria-live="polite"` 公告移动结果，例如 `Inspector moved to position 2 of 3`。
- 公告使用 1-based position，不使用数组 index。
- 手柄 `aria-describedby` 指向简短说明。
- 不使用过时或支持不稳定的 `aria-grabbed` 作为核心语义；视觉状态通过 class，辅助说明通过 live region 和按钮 label。

## localStorage 持久化

### 契约

```text
inspector-order:v1:{pageKey} -> JSON string[]
```

使用 `v1` 前缀，为未来隐藏卡片、跨设备同步或分组排序留下迁移空间。

### 写入策略

- 只在用户完成一次有效排序后写入。
- 写入前调用 `resolveOrder(nextOrder, currentCardKeys)`，保证不会保存重复/未知 key。
- `JSON.stringify` 失败、quota exceeded、隐私模式异常都静默降级；当前会话内仍保留 React state。
- localStorage 中的值视为不可信输入，读取时验证为字符串数组，否则忽略。

## CSS 与可用性

新增/调整选择器:

- `.inspector-card__header`
- `.inspector-card__title`
- `.inspector-card__body`
- `.inspector-card__move`
- `.drag-handle`
- `.inspector-card.is-dragging`
- `.workbench-inspector.is-reordering`
- `.inspector-drop-indicator`
- `.sr-only`

视觉原则:

- `.inspector-card__header` 使用 flex 布局，`.inspector-card__title` 用 `flex: 1` 或 `margin-right: auto` 推开状态徽章与操作按钮；不要为纯布局间距增加 spacer DOM。
- 手柄默认可见但低对比，不要 `opacity: 0` 完全隐藏；hover/focus 时提高对比。
- 手柄和移动按钮点击区域至少 32px，高度与卡片标题行对齐。
- `.drag-handle` 设置 `touch-action: none`，只限制手柄本身，不阻断 Inspector 内其他内容滚动。
- 不使用大幅 scale 或阴影跳变；拖动中源卡片 `opacity: 0.62` 足够。
- drop indicator 使用 2px 实线和当前 accent 色，不给整张目标卡片染色，避免误读为警告状态。
- `prefers-reduced-motion: reduce` 下关闭 transform/transition。

## 边界情况

| 场景 | 处理 |
| ---- | ---- |
| localStorage 为空/损坏 | 使用默认 descriptor 顺序 |
| 存储中有已删除 key | `resolveOrder` 过滤 |
| 存储中有重复 key | 只保留第一次出现 |
| 新增卡片 | 追加到已知卡片后 |
| 页面切换 | 按新 `pageKey` 重新读取排序 |
| 拖动到 Inspector 外 | pointer capture 仍收到 pointerup；如果无有效位置则取消 |
| pointercancel / Escape | 清理状态，排序不变 |
| Inspector collapsed | 内容 `display: none`，不启动拖动；collapse 时取消进行中的拖动 |
| 只剩 1 张卡片 | 隐藏或禁用重排控件 |
| 卡片内按钮/链接 | 不受拖动影响，只有手柄启动拖动 |
| localStorage 满 / 隐私模式 | 静默降级，会话内排序保留 |

## 变更文件

```text
src/api/frontend/src/components/InspectorPanel.tsx
src/api/frontend/src/pages/DashboardPage.tsx
src/api/frontend/src/pages/TaskDetailPage.tsx
src/api/frontend/src/pages/TaskBuilderPage.tsx
src/api/frontend/src/pages/EventTimelinePage.tsx
src/api/frontend/src/main.tsx
src/api/frontend/src/styles/app.css
```

无新增运行时代码文件。若测试环境已有前端测试框架，可补充 focused tests；当前仓库前端未配置测试框架时，至少运行:

```text
npm run build:ui
```

## 实施顺序

1. 在 `InspectorPanel.tsx` 导出 `InspectorCardDescriptor`，把 props 从 `children` 改为 `cards` 和 `pageKey`。
2. 在 `main.tsx` 把 `inspector` state 改为 `InspectorCardDescriptor[]`，并传入 `pageKey={bootstrap.view}`。
3. 逐页把 `onInspectorChange(<>{...}</>)` 改为 `onInspectorChange([{ key, title, tone, statusBadge, children }, ...])`。
4. 在 `InspectorPanel` 实现 `resolveOrder`、localStorage 读取/写入和 move up/down。
5. 实现 Pointer Events 拖动和 live region 公告；手柄键盘拖动作为可选增强，不阻塞第一版交付。
6. 调整 CSS，确认 collapsed、hover、focus、reduced motion 和 warning card 均正常。
7. 运行 `npm run build:ui`，手动验证四个页面的排序恢复、上移/下移按钮、拖动取消和 localStorage 损坏降级。

## 约束

- 不引入第三方拖拽库。
- 不使用 native HTML5 Drag and Drop 作为排序主路径。
- 不把排序偏好写入后端。
- 不改变 Inspector 卡片内已有操作的业务含义。
- 不让拖拽或重排触发任务状态、人工确认、恢复流程等系统行为。
