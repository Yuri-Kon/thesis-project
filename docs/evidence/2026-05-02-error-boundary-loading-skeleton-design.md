# Frontend Error Boundary 与 Loading Skeleton 工程设计

日期: 2026-05-02 | 状态: draft

## 1. 背景与目标

当前前端工作台（React 19 + TypeScript + Vite）缺少两类关键基础设施：

1. **Error Boundary** — 任一组件渲染错误导致整个 React root 崩溃白屏，且用户无法恢复
2. **Loading Skeleton** — API 加载期间仅显示 "Loading workspace data..." 纯文本，无视觉层次

本设计为三栏控制台架构提供分层的错误隔离和平滑的加载过渡。

### 非目标

- 不引入新路由方案（React Router）
- 不拆解 CSS 单体文件
- 不改变 WorkspaceState 数据流
- 不修改现有组件逻辑

## 2. Error Boundary 架构

### 2.1 层级结构

```
<AppErrorBoundary>                          ← 兜底：整个 React root 的崩溃保护
  <main className="app-shell">
    <ColumnErrorBoundary name="sidebar">    ← 侧边栏独立隔离
      <WorkbenchSidebar />
    </ColumnErrorBoundary>
    <ColumnErrorBoundary name="main">       ← 主工作区独立隔离
      <section className="workbench-main">
        {content}
      </section>
    </ColumnErrorBoundary>
    <ColumnErrorBoundary name="inspector">  ← Inspector 独立隔离
      <InspectorPanel />
    </ColumnErrorBoundary>
  </main>
</AppErrorBoundary>
```

### 2.2 降级行为

| 层级 | 崩溃时渲染 | 恢复方式 |
|------|-----------|---------|
| `ColumnErrorBoundary` | 列内 compact 降级卡片，含错误摘要 + Retry 按钮 | 点击 Retry → setState 重新渲染子组件 |
| `AppErrorBoundary` | 全屏居中错误提示 + 错误详情折叠 + Reload Page | 需手动刷新 |

### 2.3 降级卡片规格

```
┌─ column-error-card ──────────────────────┐
│  ⚠  {column name} 不可用                   │
│  {error.message 前 120 字符}               │
│                                 [Retry]   │
└───────────────────────────────────────────┘
```

- `border-left: 4px solid var(--danger)`
- 入场动画: `opacity 0→1` + `translateY(-4px→0)`，200ms ease-out
- Retry 按钮通过重置 ErrorBoundary 内部 `error` state 触发子组件重新挂载

### 2.4 实现要点

- 使用 React class component（Error Boundary 必须为 class）
- `componentDidCatch(error, errorInfo)` 捕获错误并设置 state
- `render()` 检查 `hasError`，为 true 时渲染降级 UI
- ColumnErrorBoundary 接收 `name: "sidebar" | "main" | "inspector"` prop

## 3. Loading Skeleton 设计

### 3.1 触发时机

`WorkspaceState.loading === true` 时渲染对应页面的骨架布局。当前纯文本 "Loading workspace data..." 替换。

### 3.2 骨架卡片类型

| 骨架组件 | 对应真实卡片 | 高度 |
|---------|------------|------|
| `SkeletonMetricCard` | MetricCard（3 列横排） | 80px |
| `SkeletonListRow` | PendingActionList 单行 | 56px，渲染 4-6 行叠加 |
| `SkeletonInspectorCard` | inspector-card | 120px |
| `SkeletonPanel` | 通用 panel | 200px |
| `SkeletonHero` | workspace-hero | 90px |

### 3.3 视觉规格

```
┌─ skeleton-card ───────────────────────────┐
│  ████████████████░░░░░░  ← 标题区 60%       │
│  ██████████████░░░░░░░░  ← 内容区 50%       │
│  ████████████░░░░░░░░░░  ← 内容区 40%       │
└────────────────────────────────────────────┘
```

- 色条：`linear-gradient(90deg, var(--line) 25%, rgba(255,255,255,0.6) 50%, var(--line) 75%)`，`background-size: 200% 100%`
- CSS 动画：`@keyframes shimmer` → `background-position: -200% 0 → 200% 0`，周期 1.5s，ease-in-out 无限循环
- 每个色条 `animation-delay` 递增 0.1s，产生波浪推进效果
- 卡片：`border-radius: var(--radius)`，`border: 1px solid rgba(0,0,0,0.05)`

### 3.4 各页面骨架布局

**Dashboard**:
```
SkeletonHero → 3×SkeletonMetricCard → SkeletonListRow×5 + side-stack{2×SkeletonInspectorCard}
```

**TaskDetail**:
```
SkeletonHero → 3×SkeletonMetricCard → SkeletonPanel + SkeletonInspectorCard
```

**EventTimeline**:
```
SkeletonHero → 3×SkeletonMetricCard → SkeletonPanel
```

**TaskBuilder**:
```
SkeletonHero → SkeletonPanel
```

## 4. 文件结构

```
src/api/frontend/src/
  components/
    ErrorBoundary.tsx         ← ColumnErrorBoundary + AppErrorBoundary
    SkeletonCard.tsx          ← SkeletonMetricCard / SkeletonListRow / SkeletonInspectorCard / SkeletonPanel / SkeletonHero
    styles/
      error-boundary.css      ← ~30 行
      skeleton.css            ← ~50 行
```

在 `main.tsx` 的 JSX 中包裹 Error Boundary。

## 5. 与现有代码的关系

- `WorkspaceState.loading` 逻辑不变
- 三栏 CSS 布局不变（`.app-shell` 等选择器不动）
- 各 Page 组件在 `state.loading` 为 true 时渲染骨架（替换 `<p className="muted">Loading...</p>`）
- 不产生新的 API 调用或依赖

## 6. 不影响

- API 契约
- FSM / PendingAction / Decision 语义
- 后端路由或模板
- CLI 行为
