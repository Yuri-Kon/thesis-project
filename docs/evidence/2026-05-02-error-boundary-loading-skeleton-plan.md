# Frontend Error Boundary 与 Loading Skeleton 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为三栏控制台添加分层 Error Boundary 和 Loading Skeleton，实现组件崩溃隔离和加载态视觉平滑过渡

**Architecture:** 在 `main.tsx` 中用 `AppErrorBoundary`（兜底）+ 三个 `ColumnErrorBoundary`（sidebar/main/inspector）包裹三栏；各 Page 在 `state.loading` 时渲染页面骨架屏替代纯文本 Loading 提示

**Tech Stack:** React 19 + TypeScript 5.9 + Vite 7，CSS animation keyframes，无新依赖

---

## 文件结构一览

| 操作 | 文件 | 职责 |
|------|------|------|
| 新建 | `src/api/frontend/src/components/ErrorBoundary.tsx` | AppErrorBoundary + ColumnErrorBoundary 类组件 |
| 新建 | `src/api/frontend/src/components/SkeletonCard.tsx` | 5 种骨架屏函数组件 |
| 新建 | `src/api/frontend/src/styles/error-boundary.css` | 错误降级卡片样式 |
| 新建 | `src/api/frontend/src/styles/skeleton.css` | 骨架屏 shimmer 动画与条纹样式 |
| 修改 | `src/api/frontend/src/main.tsx` | 包裹 Error Boundary |
| 修改 | `src/api/frontend/src/pages/DashboardPage.tsx` | loading 态渲染骨架屏 |
| 修改 | `src/api/frontend/src/pages/TaskDetailPage.tsx` | loading 态渲染骨架屏 |
| 修改 | `src/api/frontend/src/pages/EventTimelinePage.tsx` | loading 态渲染骨架屏 |
| 修改 | `src/api/frontend/src/pages/TaskBuilderPage.tsx` | loading 态渲染骨架屏 |
| 新建 | `tests/unit/test_error_boundary.py` | ErrorBoundary 渲染/恢复测试 |

---

### Task 1: 创建骨架屏 CSS

**Files:**
- Create: `src/api/frontend/src/styles/skeleton.css`

- [ ] **Step 1: 写入 skeleton.css**

```css
/* skeleton.css — shimmer animation + skeleton stripe primitives */

@keyframes shimmer {
  0%   { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}

.skeleton-stripe {
  background: linear-gradient(
    90deg,
    var(--line) 25%,
    rgba(255, 255, 255, 0.6) 50%,
    var(--line) 75%
  );
  background-size: 200% 100%;
  animation: shimmer 1.5s ease-in-out infinite;
  border-radius: 4px;
}

.skeleton-card {
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid rgba(0, 0, 0, 0.05);
  border-radius: var(--radius);
  display: grid;
  gap: 10px;
  padding: 18px;
}

.skeleton-hero {
  align-items: center;
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid rgba(0, 0, 0, 0.05);
  border-radius: var(--radius);
  display: flex;
  gap: 18px;
  justify-content: space-between;
  padding: 20px 24px;
}

.skeleton-metric-strip {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.skeleton-row {
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(0, 0, 0, 0.05);
  border-radius: var(--radius);
  display: grid;
  gap: 8px;
  padding: 12px;
}

.skeleton-side-stack {
  display: grid;
  gap: 16px;
}

.skeleton-dashboard-grid {
  align-items: start;
  display: grid;
  gap: 16px;
  grid-template-columns: minmax(0, 1fr) minmax(300px, 0.5fr);
}
```

- [ ] **Step 2: 确认 CSS 无语法错误**

```bash
wc -l src/api/frontend/src/styles/skeleton.css
# Expected: ~55 行
```

---

### Task 2: 创建 SkeletonCard.tsx

**Files:**
- Create: `src/api/frontend/src/components/SkeletonCard.tsx`

- [ ] **Step 1: 写入 SkeletonCard.tsx**

```tsx
import type { ReactNode } from "react";

/* ShimmerLine — 单条脉冲色条 */
function ShimmerLine({
  width,
  height = 14,
  delay = 0,
}: {
  width: string;
  height?: number;
  delay?: number;
}) {
  return (
    <div
      className="skeleton-stripe"
      style={{
        width,
        height,
        animationDelay: `${delay}ms`,
      }}
    />
  );
}

/* SkeletonMetricCard — 80px, 标签 + 数值 */
export function SkeletonMetricCard({ delay = 0 }: { delay?: number }) {
  return (
    <div className="skeleton-card" style={{ minHeight: 72 }}>
      <ShimmerLine width="40%" height={12} delay={delay} />
      <ShimmerLine width="55%" height={22} delay={delay + 100} />
    </div>
  );
}

/* SkeletonListRow — 56px, 两行文本 */
export function SkeletonListRow({ delay = 0 }: { delay?: number }) {
  return (
    <div className="skeleton-row">
      <ShimmerLine width="55%" height={14} delay={delay} />
      <ShimmerLine width="75%" height={12} delay={delay + 100} />
    </div>
  );
}

/* SkeletonInspectorCard — 120px */
export function SkeletonInspectorCard({ delay = 0 }: { delay?: number }) {
  return (
    <div className="skeleton-card" style={{ minHeight: 100 }}>
      <ShimmerLine width="50%" height={14} delay={delay} />
      <ShimmerLine width="70%" height={12} delay={delay + 100} />
      <ShimmerLine width="60%" height={12} delay={delay + 200} />
    </div>
  );
}

/* SkeletonPanel — 200px */
export function SkeletonPanel({ delay = 0 }: { delay?: number }) {
  return (
    <div className="skeleton-card" style={{ minHeight: 160 }}>
      <ShimmerLine width="35%" height={16} delay={delay} />
      <ShimmerLine width="80%" height={12} delay={delay + 100} />
      <ShimmerLine width="65%" height={12} delay={delay + 200} />
      <ShimmerLine width="50%" height={12} delay={delay + 300} />
    </div>
  );
}

/* SkeletonHero — 90px */
export function SkeletonHero({ delay = 0 }: { delay?: number }) {
  return (
    <div className="skeleton-hero">
      <div style={{ display: "grid", gap: 8, flex: 1 }}>
        <ShimmerLine width="30%" height={26} delay={delay} />
        <ShimmerLine width="55%" height={14} delay={delay + 100} />
      </div>
    </div>
  );
}

/* MetricStrip — 3 列骨架指标区 */
export function SkeletonMetricStrip({ delay = 0 }: { delay?: number }) {
  return (
    <div className="skeleton-metric-strip">
      <SkeletonMetricCard delay={delay} />
      <SkeletonMetricCard delay={delay + 150} />
      <SkeletonMetricCard delay={delay + 300} />
    </div>
  );
}

/* DashboardSkeleton — Dashboard 页面完整骨架 */
export function DashboardSkeleton() {
  return (
    <div className="dashboard-layout">
      <SkeletonHero delay={0} />
      <SkeletonMetricStrip delay={200} />
      <div className="skeleton-dashboard-grid">
        <div style={{ display: "grid", gap: 10 }}>
          <SkeletonListRow delay={400} />
          <SkeletonListRow delay={500} />
          <SkeletonListRow delay={600} />
          <SkeletonListRow delay={700} />
          <SkeletonListRow delay={800} />
        </div>
        <div className="skeleton-side-stack">
          <SkeletonInspectorCard delay={400} />
          <SkeletonInspectorCard delay={600} />
        </div>
      </div>
    </div>
  );
}

/* TaskDetailSkeleton — TaskDetail 页面完整骨架 */
export function TaskDetailSkeleton() {
  return (
    <div className="task-detail-layout">
      <SkeletonHero delay={0} />
      <SkeletonMetricStrip delay={200} />
      <div className="skeleton-dashboard-grid">
        <div style={{ display: "grid", gap: 16 }}>
          <SkeletonPanel delay={400} />
          <SkeletonPanel delay={600} />
        </div>
        <div className="skeleton-side-stack">
          <SkeletonInspectorCard delay={400} />
        </div>
      </div>
    </div>
  );
}

/* TimelineSkeleton — EventTimeline 页面完整骨架 */
export function TimelineSkeleton() {
  return (
    <div className="timeline-layout">
      <SkeletonHero delay={0} />
      <SkeletonMetricStrip delay={200} />
      <SkeletonPanel delay={400} />
    </div>
  );
}

/* TaskBuilderSkeleton — TaskBuilder 页面完整骨架 */
export function TaskBuilderSkeleton() {
  return (
    <div className="task-builder-layout">
      <SkeletonHero delay={0} />
      <SkeletonPanel delay={200} />
    </div>
  );
}
```

- [ ] **Step 2: 确认 TypeScript 编译通过**

```bash
npx tsc -p src/api/frontend/tsconfig.json --noEmit 2>&1 | grep -i "SkeletonCard"
# Expected: no output (no errors related to this file)
```

---

### Task 3: 创建错误降级 CSS

**Files:**
- Create: `src/api/frontend/src/styles/error-boundary.css`

- [ ] **Step 1: 写入 error-boundary.css**

```css
/* error-boundary.css — Error Boundary 降级卡片样式 */

@keyframes error-card-enter {
  from {
    opacity: 0;
    transform: translateY(-4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.column-error-card {
  align-content: start;
  animation: error-card-enter 200ms ease-out;
  background: rgba(255, 255, 255, 0.84);
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-left: 4px solid var(--danger);
  border-radius: var(--radius);
  display: grid;
  gap: 10px;
  padding: 16px;
}

.column-error-card strong {
  color: var(--danger);
  font-size: 0.9rem;
}

.column-error-card p {
  color: var(--muted);
  font-size: 0.82rem;
  line-height: 1.35;
  margin: 0;
  overflow-wrap: anywhere;
}

.app-error-fallback {
  align-content: center;
  background:
    linear-gradient(140deg, rgba(255, 255, 255, 0.94), rgba(246, 247, 251, 0.88)),
    #f5f6f9;
  display: grid;
  gap: 18px;
  height: 100vh;
  justify-content: center;
  padding: 40px;
  place-content: center;
}

.app-error-fallback h2 {
  color: var(--danger);
  font-size: 1.3rem;
  margin: 0;
}

.app-error-fallback pre {
  color: var(--muted);
  font-size: 0.8rem;
  line-height: 1.4;
  max-height: 200px;
  overflow: auto;
  white-space: pre-wrap;
}
```

---

### Task 4: 创建 ErrorBoundary.tsx

**Files:**
- Create: `src/api/frontend/src/components/ErrorBoundary.tsx`

- [ ] **Step 1: 写入 ErrorBoundary.tsx**

```tsx
import { Component, type ErrorInfo, type ReactNode } from "react";

/* ── ColumnErrorBoundary ────────────────────────────────────── */

interface ColumnErrorBoundaryProps {
  name: "sidebar" | "main" | "inspector";
  children: ReactNode;
}

interface ColumnErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ColumnErrorBoundary extends Component<
  ColumnErrorBoundaryProps,
  ColumnErrorBoundaryState
> {
  state: ColumnErrorBoundaryState = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): ColumnErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(`[ColumnErrorBoundary:${this.props.name}]`, error, info.componentStack);
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      const message = this.state.error?.message ?? "Unknown error";
      const truncated = message.length > 120 ? message.slice(0, 120) + "..." : message;
      return (
        <div className="column-error-card">
          <strong>{this.props.name} 不可用</strong>
          <p>{truncated}</p>
          <button type="button" onClick={this.handleRetry}>
            Retry
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

/* ── AppErrorBoundary ───────────────────────────────────────── */

interface AppErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class AppErrorBoundary extends Component<
  { children: ReactNode },
  AppErrorBoundaryState
> {
  state: AppErrorBoundaryState = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): AppErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[AppErrorBoundary]", error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="app-error-fallback">
          <h2>Something went wrong</h2>
          <p className="muted">
            The workspace encountered an unexpected error. Please reload the page.
          </p>
          <pre>{this.state.error?.message ?? "Unknown error"}</pre>
          <button type="button" onClick={() => window.location.reload()}>
            Reload Page
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
```

- [ ] **Step 2: 验证 TypeScript 编译**

```bash
npx tsc -p src/api/frontend/tsconfig.json --noEmit 2>&1 | grep -i "ErrorBoundary"
# Expected: no output
```

---

### Task 5: 在 main.tsx 中包裹 Error Boundary

**Files:**
- Modify: `src/api/frontend/src/main.tsx`

- [ ] **Step 1: 更新 imports，新增 Error Boundary + Skeleton 导入**

定位到 main.tsx 的 import 区域（第 1-18 行），在现有 import 后追加：

```tsx
import { AppErrorBoundary, ColumnErrorBoundary } from "./components/ErrorBoundary";
```

- [ ] **Step 2: 在 App 组件的 JSX return 中包裹 Error Boundary**

定位到 `App` 函数中的 `return` 语句（约第 153 行），将当前的：

```tsx
return (
  <main className="app-shell">
    <WorkbenchSidebar state={state} taskId={taskId} view={bootstrap.view} />
    <section className="workbench-main">
      {state.error ? <ErrorNotice message={state.error} /> : null}
      <div className="workbench-main-scroll">{content}</div>
    </section>
    <InspectorPanel>{inspector}</InspectorPanel>
  </main>
);
```

替换为：

```tsx
return (
  <AppErrorBoundary>
    <main className="app-shell">
      <ColumnErrorBoundary name="sidebar">
        <WorkbenchSidebar state={state} taskId={taskId} view={bootstrap.view} />
      </ColumnErrorBoundary>
      <ColumnErrorBoundary name="main">
        <section className="workbench-main">
          {state.error ? <ErrorNotice message={state.error} /> : null}
          <div className="workbench-main-scroll">{content}</div>
        </section>
      </ColumnErrorBoundary>
      <ColumnErrorBoundary name="inspector">
        <InspectorPanel>{inspector}</InspectorPanel>
      </ColumnErrorBoundary>
    </main>
  </AppErrorBoundary>
);
```

- [ ] **Step 3: 验证 TypeScript 和 Vite build**

```bash
npx tsc -p src/api/frontend/tsconfig.json --noEmit 2>&1
npm run build:ui 2>&1
# Expected: both succeed
```

- [ ] **Step 4: Commit**

```bash
git add src/api/frontend/src/components/ErrorBoundary.tsx \
        src/api/frontend/src/components/SkeletonCard.tsx \
        src/api/frontend/src/styles/error-boundary.css \
        src/api/frontend/src/styles/skeleton.css \
        src/api/frontend/src/main.tsx
git commit -m "feat(frontend): add Error Boundary hierarchy and skeleton primitives"
```

---

### Task 6: DashboardPage 接入骨架屏

**Files:**
- Modify: `src/api/frontend/src/pages/DashboardPage.tsx`

- [ ] **Step 1: 添加 skeleton import**

在现有 import 区域顶部追加：

```tsx
import { DashboardSkeleton } from "../components/SkeletonCard";
```

- [ ] **Step 2: 替换 loading 渲染**

定位到（约第 61 行）：

```tsx
{state.loading ? <p className="muted">Loading workspace data...</p> : null}
```

替换为：

```tsx
{state.loading ? <DashboardSkeleton /> : null}
```

- [ ] **Step 3: 包裹正常内容在 !loading 条件中**

将 DashboardPage return 中 `state.loading` 检查之后的所有内容（workspace-hero、metric-strip、dashboard-grid）包裹在条件中，确保 loading 时不渲染真实数据：

在 `return` 语句中，将：

```tsx
{state.loading ? <DashboardSkeleton /> : null}
<section className="workspace-hero">
```

替换为：

```tsx
{state.loading ? (
  <DashboardSkeleton />
) : (
  <>
    <section className="workspace-hero">
```

并在最后的 `</div>` 前闭合：

```tsx
    </section>
  </>
)}
```

完整结构：

```tsx
return (
  <div className="dashboard-layout">
    {state.loading ? (
      <DashboardSkeleton />
    ) : (
      <>
        <section className="workspace-hero">
          ...existing hero content...
        </section>
        <section className="metric-strip" ...>
          ...existing metric cards...
        </section>
        <section className="dashboard-grid">
          ...existing grid content...
        </section>
      </>
    )}
  </div>
);
```

- [ ] **Step 4: 验证 build**

```bash
npm run build:ui 2>&1
# Expected: success
```

---

### Task 7: TaskDetailPage 接入骨架屏

**Files:**
- Modify: `src/api/frontend/src/pages/TaskDetailPage.tsx`

- [ ] **Step 1: 添加 skeleton import**

```tsx
import { TaskDetailSkeleton } from "../components/SkeletonCard";
```

- [ ] **Step 2: 在 return 顶部根据 loading 渲染骨架**

将整个 return 内容包裹：

```tsx
return (
  <div className="task-detail-layout">
    {state.loading ? (
      <TaskDetailSkeleton />
    ) : (
      <>
        <section className="workspace-hero">
          ...existing hero content...
        </section>
        <section className="metric-strip" ...>
          ...existing metric cards...
        </section>
        <section className="detail-grid">
          ...existing detail grid content...
        </section>
      </>
    )}
  </div>
);
```

- [ ] **Step 3: 验证 build**

```bash
npm run build:ui 2>&1
# Expected: success
```

---

### Task 8: EventTimelinePage 接入骨架屏

**Files:**
- Modify: `src/api/frontend/src/pages/EventTimelinePage.tsx`

- [ ] **Step 1: 添加 skeleton import**

```tsx
import { TimelineSkeleton } from "../components/SkeletonCard";
```

- [ ] **Step 2: 在 return 顶部根据 loading 渲染骨架**

```tsx
return (
  <div className="timeline-layout">
    {state.loading ? (
      <TimelineSkeleton />
    ) : (
      <>
        <section className="workspace-hero">
          ...existing content...
        </section>
        <section className="metric-strip" ...>
          ...existing content...
        </section>
        <section className="panel timeline-panel">
          ...existing content...
        </section>
      </>
    )}
  </div>
);
```

- [ ] **Step 3: 验证 build**

```bash
npm run build:ui 2>&1
# Expected: success
```

---

### Task 9: TaskBuilderPage 接入骨架屏

**Files:**
- Modify: `src/api/frontend/src/pages/TaskBuilderPage.tsx`

TaskBuilderPage 不使用 `state.loading`，而是自己的 `busy`/`schema === null` 状态。

- [ ] **Step 1: 添加 skeleton import**

```tsx
import { TaskBuilderSkeleton } from "../components/SkeletonCard";
```

- [ ] **Step 2: 在 return 顶部根据 schema 是否加载渲染骨架**

```tsx
return (
  <div className="task-builder-layout">
    {schema === null ? (
      <TaskBuilderSkeleton />
    ) : (
      <>
        <section className="builder-hero">
          ...existing content...
        </section>
        ...existing body...
      </>
    )}
  </div>
);
```

`busy` 状态表现为按钮 disabled（已有），不需要骨架覆盖。

- [ ] **Step 3: 验证 build**

```bash
npm run build:ui 2>&1
# Expected: success
```

- [ ] **Step 4: Commit all page changes**

```bash
git add src/api/frontend/src/pages/DashboardPage.tsx \
        src/api/frontend/src/pages/TaskDetailPage.tsx \
        src/api/frontend/src/pages/EventTimelinePage.tsx \
        src/api/frontend/src/pages/TaskBuilderPage.tsx
git commit -m "feat(frontend): replace loading text with page-specific skeletons"
```

---

### Task 10: 最终验证

- [ ] **Step 1: 运行全部单元测试**

```bash
uv run pytest tests/unit/ -q 2>&1
# Expected: 全部通过（3 个预先存在的 candidate_generator 失败除外）
```

- [ ] **Step 2: 运行 Web smoke 测试**

```bash
uv run pytest tests/api/test_web_smoke.py -v 2>&1
# Expected: 11 passed
```

- [ ] **Step 3: 运行 basedpyright**

```bash
uv run basedpyright src/api/frontend/src/components/ErrorBoundary.tsx \
                    src/api/frontend/src/components/SkeletonCard.tsx \
                    src/api/frontend/src/main.tsx 2>&1
# Expected: 0 errors
```

- [ ] **Step 4: 完整构建验证**

```bash
npm run build:ui 2>&1
# Expected: success, style.css 约 22KB
```

- [ ] **Step 5: Commit**

```bash
git commit -m "chore(frontend): final verification of Error Boundary and skeleton"
```
