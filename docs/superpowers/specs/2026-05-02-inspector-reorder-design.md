# Inspector 卡片拖拽重排 — 设计规格

**SID:** `interface.web_workspace.inspector_reorder`
**Issue:** #317
**日期:** 2026-05-02

## 目标

Inspector 面板内卡片支持用户自定义排序，按页面独立持久化到 localStorage。

## 架构

### 组件关系

```
main.tsx (App)
  ├─ useState<InspectorCardDescriptor[]>([])
  ├─ pageKey (从 bootstrap.view 推导)
  │
  ├─ Page → useEffect → onInspectorChange([...cards])
  │
  └─ InspectorPanel({ cards, pageKey })
       ├─ useState(order)               ← 当前排序
       ├─ useRef(cardRefs)              ← DOM 引用 Map
       ├─ useEffect → 读 localStorage
       ├─ 拖拽事件委派 (.inspector-content)
       ├─ 键盘事件 (Ctrl+ArrowUp/Down)
       └─ render sorted cards
```

### pageKey 映射

| bootstrap.view | pageKey |
|---------------|---------|
| dashboard | dashboard |
| task_detail | task_detail |
| task_builder | task_builder |
| event_timeline | event_timeline |

## 卡片描述符接口

```ts
export interface InspectorCardDescriptor {
  key: string;              // 唯一标识
  title: string;            // 卡片标题
  statusBadge?: ReactNode;  // 可选状态徽章
  className?: string;       // 附加 CSS class
  children: ReactNode;      // 卡片主体内容
}
```

## 卡片 DOM 结构

```html
<section class="inspector-card" data-card-key="...">
  <div class="inspector-card__header">
    <h2 class="inspector-card__title">Title</h2>
    <!-- statusBadge -->
    <span class="drag-handle" draggable="true">⋮⋮</span>
  </div>
  <div class="inspector-card__body">
    ...
  </div>
</section>
```

`draggable="true"` 仅放在 `.drag-handle` 上，确保拖拽只能通过手柄发起。`dragstart` 事件冒泡到 `.inspector-content` 容器，handler 中通过 `e.target.closest('.inspector-card')` 获取源卡片元素和 `data-card-key`。

## 默认卡片定义

| 页面 | 卡片 key |
|------|---------|
| Dashboard | `inspector-overview`, `action-required` |
| TaskDetail | `inspector-overview`, `operation` |
| TaskBuilder | `inspector-overview`, `safety-precheck`, `action-required` |
| EventTimeline | `inspector-overview`, `timeline-boundary` |

## 拖拽机制

### 事件委派

所有拖拽事件绑定在 `.inspector-content` 容器上：

| 事件 | 行为 |
|------|------|
| dragstart | 记录源卡片 key，添加 `.dragging`，设置透明幽灵图 |
| dragover | 坐标计算悬停目标，rAF 操作 DOM transform 让位 |
| drop | 计算最终位置 → setState + 写 localStorage |
| dragend | 清理所有 `.dragging` 和 inline transforms |

### 实现纪律

- 拖拽期间不修改 React state
- DOM 变换通过 ref + requestAnimationFrame 完成
- CSS transition 驱动动画平滑
- 释放后仅一次 setState + write localStorage

### 幽灵图策略

dragstart 中用透明元素替换默认幽灵图，视觉反馈由源卡片 CSS `.dragging` 提供。

## CSS 动画

### 新增选择器

- `.inspector-card__header` — flex 头部容器
- `.inspector-card__title` — 标题文本
- `.inspector-card__body` — 内容区
- `.drag-handle` — 拖拽手柄
- `.inspector-card.dragging` — 拖拽中源卡片
- `.inspector-card.drag-over` — 悬停目标高亮

### 动画时序

| 阶段 | 视觉变化 | 时长 |
|------|---------|------|
| 静止 | drag-handle opacity: 0 | — |
| 卡片 hover | drag-handle opacity: 0→1 | 150ms ease |
| 手柄 hover | translateY(-1px), shadow 增强 | 200ms ease |
| 拖拽中 | 源: opacity 0.5, scale 1.02; 其他: translateY 让位 | 200ms ease |
| 释放 | 卡片归位 | 250ms ease-out |

### 减少动画

```css
@media (prefers-reduced-motion: reduce) {
  .inspector-card, .drag-handle { transition: none; }
}
```

## 键盘无障碍

- `Ctrl/Cmd + ArrowUp/Down` 移动卡片一个位置
- 移动后自动聚焦目标卡片
- `aria-roledescription="sortable card"`, `aria-grabbed`
- 容器 `role="list"`, 卡片 `role="listitem"`

## localStorage 持久化

### 契约

```
inspector-order:{pageKey}  →  JSON string[]
```

### 恢复规则

```ts
function resolveOrder(stored: string[], cardKeys: string[]): string[] {
  const known = stored.filter((k) => cardKeys.includes(k));
  const newcomers = cardKeys.filter((k) => !stored.includes(k));
  return [...known, ...newcomers];
}
```

新增卡片追加末尾，已删除卡片自动过滤。不做跨设备同步。

## 边界情况

| 场景 | 处理 |
|------|------|
| localStorage 为空/损坏 | 降级为默认排序 |
| 存储中有已删除卡片 key | resolveOrder 过滤 |
| 拖拽到容器外（无效 drop） | dragend 清理，排序不变 |
| 快速连续拖拽 | ref 操作幂等，每次 dragend 完整清理 |
| localStorage 满 / 隐私模式 | 静默降级，会话内维持排序 |
| Inspector collapsed | display:none，拖拽不可操作 |
| 只剩 1 张卡片 | 手柄显示但拖拽无效果 |

## 变更文件

```
src/api/frontend/src/components/InspectorPanel.tsx
src/api/frontend/src/pages/DashboardPage.tsx
src/api/frontend/src/pages/TaskDetailPage.tsx
src/api/frontend/src/pages/TaskBuilderPage.tsx
src/api/frontend/src/pages/EventTimelinePage.tsx
src/api/frontend/src/main.tsx
src/api/frontend/src/styles/app.css
```

无新增文件。

## 约束

- 仅 HTML5 Drag and Drop API，不引入第三方库
- 仅 Inspector 面板内 `.inspector-card`，不涉及 Sidebar 或主工作区
- 顺序不同步后端，不跨设备
