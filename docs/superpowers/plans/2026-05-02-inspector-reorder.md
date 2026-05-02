# Inspector 卡片拖拽重排 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Inspector 面板内卡片支持用户自定义排序，通过 Pointer Events 拖拽手柄和上下移动按钮实现，排序按页面独立持久化到 localStorage。

**Architecture:** 将 InspectorPanel 从接收不透明 `children` 改为接收结构化 `InspectorCardDescriptor[]`，内部维护 `order: string[]` state 驱动排序渲染。拖拽期间状态保存在 ref，释放后一次性 `setState` + 写 localStorage。每张卡片提供 `<button>` 拖拽手柄和 ↑/↓ 移动按钮。

**Tech Stack:** React 18+, TypeScript, Pointer Events API, localStorage, CSS transitions

---

### Task 1: 定义 InspectorCardDescriptor 接口并更新 InspectorPanel 签名

**Files:**
- Modify: `src/api/frontend/src/components/InspectorPanel.tsx`
- Modify: `src/api/frontend/src/main.tsx:46-51`

**目标:** 导出 `InspectorCardDescriptor` 类型，将 InspectorPanel 从 `children: ReactNode` 迁移到 `cards: InspectorCardDescriptor[]; pageKey: string`，同步更新 main.tsx 中的类型和传递方式。此任务只改接口和渲染壳，不实现排序/拖拽逻辑。

- [ ] **Step 1: 重写 InspectorPanel — 导出类型，接受 cards/pageKey，基础渲染**

将 `src/api/frontend/src/components/InspectorPanel.tsx` 替换为：

```tsx
import { useState } from "react";
import type { ReactNode } from "react";

export interface InspectorCardDescriptor {
  key: string;
  title: string;
  tone?: "default" | "warning";
  statusBadge?: ReactNode;
  className?: string;
  children: ReactNode;
}

interface InspectorPanelProps {
  cards: InspectorCardDescriptor[];
  pageKey: string;
}

export function InspectorPanel({ cards }: InspectorPanelProps) {
  const [collapsed, setCollapsed] = useState(false);

  if (cards.length === 0) {
    return (
      <aside className="workbench-inspector" aria-label="Inspector">
        <button
          type="button"
          className="inspector-toggle"
          aria-expanded={!collapsed}
          title={collapsed ? "Show inspector" : "Hide inspector"}
          onClick={() => setCollapsed((c) => !c)}
        >
          {collapsed ? "Inspect" : "Collapse"}
        </button>
      </aside>
    );
  }

  return (
    <aside className={collapsed ? "workbench-inspector collapsed" : "workbench-inspector"} aria-label="Inspector">
      <button
        type="button"
        className="inspector-toggle"
        aria-expanded={!collapsed}
        title={collapsed ? "Show inspector" : "Hide inspector"}
        onClick={() => setCollapsed((c) => !c)}
      >
        {collapsed ? "Inspect" : "Collapse"}
      </button>
      <div className="inspector-content">
        {cards.map((card) => (
          <section
            key={card.key}
            className={`inspector-card${card.tone === "warning" ? " warning-card" : ""}${card.className ? ` ${card.className}` : ""}`}
          >
            <div className="inspector-card__body">{card.children}</div>
          </section>
        ))}
      </div>
    </aside>
  );
}
```

- [ ] **Step 2: 更新 main.tsx 中的 inspector state 类型和 InspectorPanel 调用**

在 `src/api/frontend/src/main.tsx` 中做两处修改：

**修改 1 — import (第 18 行附近):**

```tsx
// before
import { InspectorPanel } from "./components/InspectorPanel";

// after
import { InspectorPanel, type InspectorCardDescriptor } from "./components/InspectorPanel";
```

**修改 2 — state 声明 (第 51 行附近):**

```tsx
// before
const [inspector, setInspector] = useState<ReactNode>(null);

// after
const [inspector, setInspector] = useState<InspectorCardDescriptor[]>([]);
```

**修改 3 — InspectorPanel 调用 (第 188 行附近):**

```tsx
// before
<InspectorPanel>{inspector}</InspectorPanel>

// after
<InspectorPanel cards={inspector} pageKey={bootstrap.view} />
```

- [ ] **Step 3: 运行 build 验证编译通过**

```bash
cd src/api/frontend && npm run build
```

预期: build 失败 — 四个页面仍在传 `ReactNode`（类型不匹配）。这说明接口已生效，下一步逐页转换。

- [ ] **Step 4: Commit**

```bash
git add src/api/frontend/src/components/InspectorPanel.tsx src/api/frontend/src/main.tsx
git commit -m "refactor(frontend): replace InspectorPanel children with InspectorCardDescriptor[] interface"
```

---

### Task 2: 迁移 DashboardPage 到 InspectorCardDescriptor[]

**Files:**
- Modify: `src/api/frontend/src/pages/DashboardPage.tsx:32-58`

- [ ] **Step 1: 将 useEffect 中的 JSX fragment 替换为描述符数组**

```tsx
// 替换 DashboardPage.tsx 第 32-58 行的 useEffect 内容

useEffect(() => {
  onInspectorChange([
    {
      key: "inspector-overview",
      title: "Inspector",
      statusBadge: <span className="pill">overview</span>,
      children: (
        <dl className="kv compact-kv">
          <dt>Pending</dt>
          <dd>{state.pendingActions.length}</dd>
          <dt>Capabilities</dt>
          <dd>{state.readiness.length}</dd>
          <dt>Blocked</dt>
          <dd>{blockedCapabilities}</dd>
          <dt>Loaded task</dt>
          <dd>{state.task?.id ?? "none"}</dd>
        </dl>
      ),
    },
    {
      key: "action-required",
      title: "Action required",
      tone: "warning",
      children: (
        <p>{state.pendingActions.length ? "Open a pending action to review candidates and submit a decision." : "No pending review is currently reported by the API."}</p>
      ),
    },
  ]);
}, [blockedCapabilities, onInspectorChange, state.pendingActions.length, state.readiness.length, state.task?.id, activeIntakeId, onDraftNavigate]);
```

注意：card "Action required" 中的 `<a className="inspector-action" href="...">New intake</a>` 移到 `children` 中作为卡片内容的一部分。

- [ ] **Step 2: 添加缺失的依赖检查**

确认 `useEffect` 的依赖数组不变（`state.task?.id` 等已覆盖所有动态值）。

- [ ] **Step 3: Commit**

```bash
git add src/api/frontend/src/pages/DashboardPage.tsx
git commit -m "refactor(frontend): convert DashboardPage inspector to InspectorCardDescriptor[]"
```

---

### Task 3: 迁移 TaskDetailPage 到 InspectorCardDescriptor[]

**Files:**
- Modify: `src/api/frontend/src/pages/TaskDetailPage.tsx:27-61`

- [ ] **Step 1: 将 useEffect 中的 JSX fragment 替换为描述符数组**

```tsx
// 替换 TaskDetailPage.tsx 第 27-61 行的 useEffect 内容

useEffect(() => {
  onInspectorChange([
    {
      key: "inspector-overview",
      title: "Inspector",
      statusBadge: <StatusBadge value={task?.status} />,
      children: (
        <dl className="kv compact-kv">
          <dt>Task</dt>
          <dd>{task?.id ?? (taskId || "none")}</dd>
          <dt>External</dt>
          <dd>{task?.status ?? "not loaded"}</dd>
          <dt>Internal</dt>
          <dd>{task?.internal_status ?? "not loaded"}</dd>
          <dt>Pending</dt>
          <dd>{pendingLabel}</dd>
          <dt>Updated</dt>
          <dd>{task?.updated_at ?? "-"}</dd>
        </dl>
      ),
    },
    {
      key: "operation",
      title: "Operation",
      children: (
        <dl className="kv compact-kv">
          <dt>Candidates</dt>
          <dd>{state.pendingActionDetail?.candidates.length ?? 0}</dd>
          <dt>Default</dt>
          <dd>{state.pendingActionDetail?.default_suggestion ?? "none"}</dd>
          <dt>Report</dt>
          <dd>{state.report?.report_path ?? task?.design_result?.report_path ?? "not available"}</dd>
        </dl>
      ),
    },
  ]);
}, [onInspectorChange, pendingLabel, state.pendingActionDetail?.candidates.length, state.pendingActionDetail?.default_suggestion, state.report?.report_path, task, taskId]);
```

- [ ] **Step 2: Commit**

```bash
git add src/api/frontend/src/pages/TaskDetailPage.tsx
git commit -m "refactor(frontend): convert TaskDetailPage inspector to InspectorCardDescriptor[]"
```

---

### Task 4: 迁移 TaskBuilderPage 到 InspectorCardDescriptor[]

**Files:**
- Modify: `src/api/frontend/src/pages/TaskBuilderPage.tsx:326-365`

- [ ] **Step 1: 将 useEffect 中的 JSX fragment 替换为描述符数组**

```tsx
// 替换 TaskBuilderPage.tsx 第 326-365 行的 useEffect 内容

useEffect(() => {
  const safety = intake?.safety_check;
  onInspectorChange([
    {
      key: "inspector-overview",
      title: "Inspector",
      statusBadge: <span className="pill">{intake?.status ?? "idle"}</span>,
      children: (
        <dl className="kv compact-kv">
          <dt>Intake</dt>
          <dd>{intake?.intake_id ?? "new"}</dd>
          <dt>Missing</dt>
          <dd>{intake?.missing_required_fields.length ?? 0}</dd>
          <dt>Ambiguous</dt>
          <dd>{intake?.ambiguous_fields.length ?? 0}</dd>
          <dt>Unmapped</dt>
          <dd>{intake?.unmapped_text.length ?? 0}</dd>
          <dt>Profile</dt>
          <dd>{taskKind ? `${taskKind} · ${supportLabel(taskProfile?.support_level)}` : "not selected"}</dd>
          <dt>Confirmable</dt>
          <dd>{canConfirm ? "yes" : "no"}</dd>
        </dl>
      ),
    },
    {
      key: "safety-precheck",
      title: "Safety Precheck",
      children: (
        <SafetyPrecheckPanel
          action={safety?.action}
          risks={safety?.risk_flags ?? []}
          acknowledgedWarnings={acknowledgedWarnings}
          onToggleWarning={toggleWarning}
        />
      ),
    },
    {
      key: "action-required",
      title: "Action required",
      tone: "warning",
      children: (
        <>
          <p>{canConfirm ? "The intake is ready to become a formal task." : "Resolve missing fields, field validation warnings, ambiguous fields, or safety warnings before confirming."}</p>
          <button type="button" className="primary-action" onClick={() => void confirmDraft()} disabled={busy || !canConfirm}>
            Create Task
          </button>
        </>
      ),
    },
  ]);
}, [acknowledgedWarnings, busy, canConfirm, intake, onInspectorChange, taskKind, taskProfile]);
```

- [ ] **Step 2: Commit**

```bash
git add src/api/frontend/src/pages/TaskBuilderPage.tsx
git commit -m "refactor(frontend): convert TaskBuilderPage inspector to InspectorCardDescriptor[]"
```

---

### Task 5: 迁移 EventTimelinePage 到 InspectorCardDescriptor[]

**Files:**
- Modify: `src/api/frontend/src/pages/EventTimelinePage.tsx:26-51`

- [ ] **Step 1: 将 useEffect 中的 JSX fragment 替换为描述符数组**

```tsx
// 替换 EventTimelinePage.tsx 第 26-51 行的 useEffect 内容

useEffect(() => {
  onInspectorChange([
    {
      key: "inspector-overview",
      title: "Inspector",
      statusBadge: <StatusBadge value={state.task?.status} />,
      children: (
        <dl className="kv compact-kv">
          <dt>Task</dt>
          <dd>{state.task?.id ?? (taskId || "none")}</dd>
          <dt>Events</dt>
          <dd>{state.events.length}</dd>
          <dt>Highlighted</dt>
          <dd>{highlighted}</dd>
          <dt>Latest</dt>
          <dd>{latestEvent?.event_type ?? "none"}</dd>
        </dl>
      ),
    },
    {
      key: "timeline-boundary",
      title: "Timeline boundary",
      children: (
        <p>Recent events stay in a bounded scroll area; older entries remain available through the timeline list.</p>
      ),
    },
  ]);
}, [highlighted, latestEvent?.event_type, onInspectorChange, state.events.length, state.task?.id, state.task?.status, taskId]);
```

- [ ] **Step 2: Commit**

```bash
git add src/api/frontend/src/pages/EventTimelinePage.tsx
git commit -m "refactor(frontend): convert EventTimelinePage inspector to InspectorCardDescriptor[]"
```

---

### Task 6: 运行 build 确认所有页面迁移完成

- [ ] **Step 1: 运行 TypeScript 编译和构建**

```bash
cd src/api/frontend && npx tsc --noEmit
```

预期: 无类型错误。四个页面均已迁移为 `InspectorCardDescriptor[]`，InspectorPanel 接受 `cards` prop。

- [ ] **Step 2: Commit**

```bash
# 如果有 lint/format 修复，一并提交
git add src/api/frontend/src/
git commit -m "chore(frontend): verify all pages use InspectorCardDescriptor[]"
```

---

### Task 7: 实现 InspectorPanel 排序核心 — resolveOrder、localStorage、order state、header 渲染、上下移动按钮

**Files:**
- Modify: `src/api/frontend/src/components/InspectorPanel.tsx`

**目标:** 卡片 header 含标题、状态徽章、上移/下移按钮和拖拽手柄。排序状态在 `order` state 中，按 `sorted` 顺序渲染。localStorage 读写 + 恢复规则。上下移动按钮工作。

- [ ] **Step 1: 将 InspectorPanel 替换为包含排序核心的完整版本**

将 `src/api/frontend/src/components/InspectorPanel.tsx` 替换为：

```tsx
import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";

export interface InspectorCardDescriptor {
  key: string;
  title: string;
  tone?: "default" | "warning";
  statusBadge?: ReactNode;
  className?: string;
  children: ReactNode;
}

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

function readOrder(pageKey: string): string[] {
  try {
    const raw = localStorage.getItem(`inspector-order:v1:${pageKey}`);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed) || !parsed.every((v) => typeof v === "string")) return [];
    return parsed;
  } catch {
    return [];
  }
}

function persistOrder(pageKey: string, order: string[]): void {
  try {
    localStorage.setItem(`inspector-order:v1:${pageKey}`, JSON.stringify(order));
  } catch {
    /* quota exceeded or private mode */
  }
}

interface InspectorPanelProps {
  cards: InspectorCardDescriptor[];
  pageKey: string;
}

export function InspectorPanel({ cards, pageKey }: InspectorPanelProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [order, setOrder] = useState<string[]>(() =>
    resolveOrder(readOrder(pageKey), cards.map((c) => c.key)),
  );
  const liveRef = useRef<HTMLParagraphElement>(null);

  // Re-resolve when cards or pageKey change
  useEffect(() => {
    setOrder(resolveOrder(readOrder(pageKey), cards.map((c) => c.key)));
  }, [cards, pageKey]);

  const cardsByKey = useMemo(() => new Map(cards.map((c) => [c.key, c])), [cards]);

  // Duplicate key warning in dev
  useEffect(() => {
    if (import.meta.env.DEV) {
      const seen = new Set<string>();
      for (const key of cards.map((c) => c.key)) {
        if (seen.has(key)) {
          console.warn(`[InspectorPanel] Duplicate card key: "${key}"`);
        }
        seen.add(key);
      }
    }
  }, [cards]);

  const announce = useCallback((message: string) => {
    const el = liveRef.current;
    if (el) el.textContent = message;
  }, []);

  const moveCard = useCallback(
    (fromIndex: number, toIndex: number) => {
      if (fromIndex === toIndex || toIndex < 0 || toIndex >= order.length) return;
      const next = [...order];
      const [moved] = next.splice(fromIndex, 1);
      next.splice(toIndex, 0, moved);
      const safe = resolveOrder(next, cards.map((c) => c.key));
      setOrder(safe);
      persistOrder(pageKey, safe);
      const card = cardsByKey.get(moved);
      if (card) {
        announce(`${card.title} moved to position ${toIndex + 1} of ${order.length}`);
      }
    },
    [order, pageKey, cards, cardsByKey, announce],
  );

  const sorted = useMemo(() => {
    const resolved = resolveOrder(order, cards.map((c) => c.key));
    return resolved.map((key) => cardsByKey.get(key)!);
  }, [order, cards, cardsByKey]);

  if (cards.length === 0) {
    return (
      <aside className="workbench-inspector" aria-label="Inspector">
        <button
          type="button"
          className="inspector-toggle"
          aria-expanded={!collapsed}
          title={collapsed ? "Show inspector" : "Hide inspector"}
          onClick={() => setCollapsed((c) => !c)}
        >
          {collapsed ? "Inspect" : "Collapse"}
        </button>
      </aside>
    );
  }

  const showControls = order.length >= 2;

  return (
    <aside className={collapsed ? "workbench-inspector collapsed" : "workbench-inspector"} aria-label="Inspector">
      <button
        type="button"
        className="inspector-toggle"
        aria-expanded={!collapsed}
        title={collapsed ? "Show inspector" : "Hide inspector"}
        onClick={() => setCollapsed((c) => !c)}
      >
        {collapsed ? "Inspect" : "Collapse"}
      </button>
      <div className="inspector-content" role="list" aria-describedby="inspector-reorder-help">
        {sorted.map((card, index) => (
          <section
            key={card.key}
            className={`inspector-card${card.tone === "warning" ? " warning-card" : ""}${card.className ? ` ${card.className}` : ""}`}
            data-card-key={card.key}
            role="listitem"
          >
            <div className="inspector-card__header">
              <h2 className="inspector-card__title">{card.title}</h2>
              {card.statusBadge}
              {showControls ? (
                <>
                  <button
                    type="button"
                    className="inspector-card__move"
                    aria-label={`Move ${card.title} up`}
                    disabled={index === 0}
                    onClick={() => moveCard(index, index - 1)}
                  >
                    ↑
                  </button>
                  <button
                    type="button"
                    className="inspector-card__move"
                    aria-label={`Move ${card.title} down`}
                    disabled={index === order.length - 1}
                    onClick={() => moveCard(index, index + 1)}
                  >
                    ↓
                  </button>
                  <button
                    type="button"
                    className="drag-handle"
                    aria-label={`Reorder ${card.title}`}
                    aria-describedby="inspector-reorder-help"
                  >
                    ↕
                  </button>
                </>
              ) : null}
            </div>
            <div className="inspector-card__body">{card.children}</div>
          </section>
        ))}
      </div>
      <p id="inspector-reorder-help" className="sr-only">
        Drag cards by the reorder handle, or use the move up and move down buttons.
      </p>
      <p className="sr-only" aria-live="polite" ref={liveRef} />
    </aside>
  );
}
```

- [ ] **Step 2: 运行 TypeScript 检查**

```bash
cd src/api/frontend && npx tsc --noEmit
```

预期: 无类型错误。

- [ ] **Step 3: 运行构建**

```bash
cd src/api/frontend && npm run build
```

预期: 构建成功。卡片按默认顺序渲染，header 含标题/徽章/移动按钮/手柄。

- [ ] **Step 4: Commit**

```bash
git add src/api/frontend/src/components/InspectorPanel.tsx
git commit -m "feat(frontend): add InspectorPanel order state, localStorage persistence, and move up/down buttons"
```

---

### Task 8: 实现 Pointer Events 拖拽

**Files:**
- Modify: `src/api/frontend/src/components/InspectorPanel.tsx`

**目标:** 手柄支持 Pointer Events 拖拽，含 4px 阈值、pointer capture、rAF 批处理、drop indicator、Escape 取消、collapse 时中断拖拽、live region 公告。

- [ ] **Step 1: 添加 DragSession 类型、drag ref、dragState 和指针事件处理**

在现有 `InspectorPanel` 函数体内，`liveRef` 声明之后，`announce` 之前，插入以下代码：

```tsx
// --- Drag state (ref for performance, state for rendering) ---
interface DragSession {
  activeKey: string;
  pointerId: number;
  originY: number;
  cardRects: Map<string, DOMRect>;
  dropIndex: number | null;
  frameId: number | null;
}

const dragRef = useRef<DragSession | null>(null);
const [dragState, setDragState] = useState<{ activeKey: string; dropIndex: number | null } | null>(null);
const cardRefs = useRef<Map<string, HTMLElement>>(new Map());
```

- [ ] **Step 2: 添加 pointer event handlers 和 Escape 监听**

在 `moveCard` 声明之后，`sorted` 之前，添加：

```tsx
// --- Pointer event handlers ---

const handlePointerDown = useCallback(
  (e: React.PointerEvent<HTMLButtonElement>) => {
    if (!e.isPrimary) return;
    const handleEl = e.currentTarget;
    const cardEl = handleEl.closest(".inspector-card") as HTMLElement | null;
    if (!cardEl) return;
    const key = cardEl.dataset.cardKey;
    if (!key) return;
    if (order.length < 2) return;

    handleEl.setPointerCapture(e.pointerId);

    const cardRects = new Map<string, DOMRect>();
    cardRefs.current.forEach((el, k) => {
      cardRects.set(k, el.getBoundingClientRect());
    });

    dragRef.current = {
      activeKey: key,
      pointerId: e.pointerId,
      originY: e.clientY,
      cardRects,
      dropIndex: null,
      frameId: null,
    };
  },
  [order.length],
);

const handlePointerMove = useCallback(
  (e: React.PointerEvent<HTMLButtonElement>) => {
    const session = dragRef.current;
    if (!session || e.pointerId !== session.pointerId) return;

    const dy = e.clientY - session.originY;
    if (Math.abs(dy) < 4 && session.dropIndex === null) return;

    if (session.frameId !== null) {
      cancelAnimationFrame(session.frameId);
    }

    session.frameId = requestAnimationFrame(() => {
      session.frameId = null;

      let dropIndex = -1;
      const activeIdx = order.indexOf(session.activeKey);

      for (let i = 0; i < order.length; i++) {
        if (i === activeIdx) continue;
        const rect = session.cardRects.get(order[i]);
        if (!rect) continue;
        const midY = rect.top + rect.height / 2;
        if (e.clientY < midY) {
          dropIndex = i;
          break;
        }
        dropIndex = i + 1;
      }

      if (dropIndex > activeIdx) {
        dropIndex = Math.max(0, dropIndex - 1);
      }
      if (dropIndex === activeIdx) {
        dropIndex = -1;
      }

      session.dropIndex = dropIndex;
      setDragState({ activeKey: session.activeKey, dropIndex: dropIndex >= 0 ? dropIndex : null });
    });
  },
  [order],
);

const finishDrag = useCallback(
  (card: InspectorCardDescriptor, dropIndex: number | null) => {
    const fromIdx = order.indexOf(card.key);
    if (
      dropIndex !== null &&
      dropIndex >= 0 &&
      dropIndex < order.length &&
      fromIdx !== dropIndex
    ) {
      const next = [...order];
      const [moved] = next.splice(fromIdx, 1);
      next.splice(dropIndex, 0, moved);
      const safe = resolveOrder(next, cards.map((c) => c.key));
      setOrder(safe);
      persistOrder(pageKey, safe);
      announce(`${card.title} moved to position ${dropIndex + 1} of ${order.length}`);
    }
  },
  [order, pageKey, cards, cardsByKey, announce],
);

const cleanupDrag = useCallback(() => {
  const session = dragRef.current;
  if (!session) return;
  if (session.frameId !== null) {
    cancelAnimationFrame(session.frameId);
  }
  dragRef.current = null;
  setDragState(null);
}, []);

const handlePointerUp = useCallback(
  (e: React.PointerEvent<HTMLButtonElement>) => {
    const session = dragRef.current;
    if (!session || e.pointerId !== session.pointerId) return;
    e.currentTarget.releasePointerCapture(e.pointerId);
    const card = cardsByKey.get(session.activeKey);
    const dropIndex = session.dropIndex;
    cleanupDrag();
    if (card && dropIndex !== null) {
      finishDrag(card, dropIndex);
    }
  },
  [cardsByKey, cleanupDrag, finishDrag],
);

const handlePointerCancel = useCallback(
  (e: React.PointerEvent<HTMLButtonElement>) => {
    const session = dragRef.current;
    if (!session || e.pointerId !== session.pointerId) return;
    cleanupDrag();
    announce("Reorder cancelled");
  },
  [cleanupDrag, announce],
);

// Global Escape during drag
useEffect(() => {
  if (!dragState) return;
  const handler = (e: KeyboardEvent) => {
    if (e.key === "Escape" && dragRef.current) {
      cleanupDrag();
      announce("Reorder cancelled");
    }
  };
  window.addEventListener("keydown", handler);
  return () => window.removeEventListener("keydown", handler);
}, [dragState, cleanupDrag, announce]);

// Cancel drag on collapse
useEffect(() => {
  if (collapsed && dragRef.current) {
    cleanupDrag();
  }
}, [collapsed, cleanupDrag]);
```

- [ ] **Step 3: 更新 JSX — 添加 drag handler 绑定、card refs、is-reordering class、drop indicator、is-dragging class**

替换 `sorted.map` 的渲染部分。找到渲染 `.inspector-card` 的 JSX (Step 1 中 `sorted.map` 内的 `<section>`)，替换为带有 ref、drag class、drop indicator 的版本：

```tsx
<div
  className={`inspector-content${dragState ? " has-drag" : ""}`}
  role="list"
  aria-describedby="inspector-reorder-help"
>
  {sorted.map((card, index) => {
    const toneClass = card.tone === "warning" ? " warning-card" : "";
    const dragClass =
      dragState?.activeKey === card.key ? " is-dragging" : "";
    const extraClass = card.className ? ` ${card.className}` : "";

    return (
      <Fragment key={card.key}>
        {dragState && dragState.dropIndex !== null && dragState.dropIndex === index && dragState.activeKey !== card.key ? (
          <div className="inspector-drop-indicator" />
        ) : null}
        <section
          ref={(el) => {
            if (el) cardRefs.current.set(card.key, el);
          }}
          className={`inspector-card${toneClass}${dragClass}${extraClass}`}
          data-card-key={card.key}
          role="listitem"
        >
          {/* header + body from Task 7: full structure below */}
          <div className="inspector-card__header">
            <h2 className="inspector-card__title">{card.title}</h2>
            {card.statusBadge}
            {showControls ? (
              <>
                <button
                  type="button"
                  className="inspector-card__move"
                  aria-label={`Move ${card.title} up`}
                  disabled={index === 0}
                  onClick={() => moveCard(index, index - 1)}
                >
                  ↑
                </button>
                <button
                  type="button"
                  className="inspector-card__move"
                  aria-label={`Move ${card.title} down`}
                  disabled={index === order.length - 1}
                  onClick={() => moveCard(index, index + 1)}
                >
                  ↓
                </button>
                <button
                  type="button"
                  className="drag-handle"
                  aria-label={`Reorder ${card.title}`}
                  aria-describedby="inspector-reorder-help"
                  onPointerDown={handlePointerDown}
                  onPointerMove={handlePointerMove}
                  onPointerUp={handlePointerUp}
                  onPointerCancel={handlePointerCancel}
                >
                  ↕
                </button>
              </>
            ) : null}
          </div>
          <div className="inspector-card__body">{card.children}</div>
        </section>
      </Fragment>
    );
  })}
```

同时给 `<aside>` 添加 `is-reordering` class (替换现有的 className 行)：

```tsx
<aside
  className={
    collapsed
      ? "workbench-inspector collapsed"
      : `workbench-inspector${dragState ? " is-reordering" : ""}`
  }
  aria-label="Inspector"
>
```

**完整文件** 请在实现时集成以上所有改动（避免逐个 patch），最终文件应符合：

1. `InspectorCardDescriptor` 接口及其导出
2. `resolveOrder` / `readOrder` / `persistOrder` 函数
3. `InspectorPanel` 组件含：
   - `collapsed` state
   - `order` state (从 localStorage 初始化)
   - `dragState` state
   - `dragRef` / `cardRefs` / `liveRef` refs
   - `cardsByKey` / `sorted` / `announce` / `moveCard`
   - `handlePointerDown/Move/Up/Cancel` + `finishDrag` + `cleanupDrag`
   - Escape 和 collapse 清理 effects
   - cards.length === 0 的空状态
   - 完整渲染 (aside + toggle + content + cards + help text + live region)

- [ ] **Step 4: 运行 TypeScript 检查**

```bash
cd src/api/frontend && npx tsc --noEmit
```

- [ ] **Step 5: Commit**

```bash
git add src/api/frontend/src/components/InspectorPanel.tsx
git commit -m "feat(frontend): add Pointer Events drag-to-reorder for Inspector cards"
```

---

### Task 9: 添加 CSS 样式

**Files:**
- Modify: `src/api/frontend/src/styles/app.css`

**目标:** 在 `app.css` 末尾添加所有新样式选择器。

- [ ] **Step 1: 在 app.css 末尾追加 CSS**

```css
/* ---- Inspector Card Header ---- */

.inspector-card__header {
  align-items: center;
  display: flex;
  gap: 8px;
}

.inspector-card__title {
  flex: 1;
  font-size: 0.92rem;
  font-weight: 800;
  margin: 0;
  min-width: 0;
}

.inspector-card__body {
  display: grid;
  gap: 8px;
}

/* ---- Move Buttons ---- */

.inspector-card__move {
  background: transparent;
  border: 1px solid transparent;
  border-radius: 4px;
  box-shadow: none;
  color: var(--muted);
  cursor: pointer;
  font-size: 0.75rem;
  line-height: 1;
  min-height: 32px;
  min-width: 32px;
  padding: 0;
}

.inspector-card__move:hover,
.inspector-card:focus-within .inspector-card__move {
  border-color: var(--line);
  color: var(--text);
}

.inspector-card__move:disabled {
  opacity: 0.25;
  pointer-events: none;
}

/* ---- Drag Handle ---- */

.drag-handle {
  align-items: center;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 4px;
  box-shadow: none;
  color: var(--muted);
  cursor: grab;
  display: flex;
  font-size: 0.9rem;
  justify-content: center;
  line-height: 1;
  min-height: 32px;
  min-width: 32px;
  padding: 0;
  touch-action: none;
  user-select: none;
}

.drag-handle:hover,
.inspector-card:focus-within .drag-handle {
  border-color: var(--line);
  color: var(--text);
}

.drag-handle:active {
  cursor: grabbing;
}

/* ---- Drag States ---- */

.inspector-card.is-dragging {
  opacity: 0.62;
}

.workbench-inspector.is-reordering {
  user-select: none;
}

/* ---- Drop Indicator ---- */

.inspector-drop-indicator {
  background: var(--accent);
  border-radius: 2px;
  height: 2px;
  margin: 2px 0;
  width: 100%;
}

/* ---- Screen Reader Only ---- */

.sr-only {
  clip: rect(0, 0, 0, 0);
  border: 0;
  height: 1px;
  margin: -1px;
  overflow: hidden;
  padding: 0;
  position: absolute;
  white-space: nowrap;
  width: 1px;
}

/* ---- Reduced Motion ---- */

@media (prefers-reduced-motion: reduce) {
  .inspector-card {
    transition: none;
  }
}
```

- [ ] **Step 2: 确认现有 `.warning-card` 与 `.inspector-card` 的兼容性**

`.warning-card` 样式 (第 364 行) 已在 `.inspector-card` 上叠加使用：
```css
.inspector-card { ... }
.warning-card { background: ...; border-color: ...; }
```
当 card 的 `tone === "warning"` 时，组件会输出 `className="inspector-card warning-card"`，两条规则正常叠加。无需修改现有规则。

- [ ] **Step 3: Commit**

```bash
git add src/api/frontend/src/styles/app.css
git commit -m "style(frontend): add Inspector card header, drag handle, move button, and drag state styles"
```

---

### Task 10: 构建与验证

**Files:** 无

**目标:** 运行构建，确认零错误。手动验证清单列在步骤中。

- [ ] **Step 1: 运行完整构建**

```bash
cd src/api/frontend && npm run build
```

预期: 构建成功，无 TS 错误，无 CSS 警告。

- [ ] **Step 2: 手动验证清单**

启动开发服务器后逐项检查：

| # | 验证项 | 预期行为 |
|---|--------|---------|
| 1 | Dashboard inspector 默认排序 | Inspector card 在上，Action required 在下 |
| 2 | Dashboard 拖拽手柄 hover | 手柄可见，border-color 加深 |
| 3 | Dashboard 点手柄拖拽下移 | drop indicator 出现，释放后卡片交换位置 |
| 4 | Dashboard 点 ↑/↓ 按钮 | 卡片移动，焦点保持在对应按钮 |
| 5 | Dashboard 拖拽中按 Escape | 拖拽取消，排序不变 |
| 6 | 拖拽后刷新页面 | 排序保持 |
| 7 | 切换到 TaskDetail 页面 | inspector 独立排序，不同于 Dashboard |
| 8 | TaskBuilder 三张卡片 | 均可独立拖拽和按钮移动 |
| 9 | EventTimeline 两张卡片 | 同上 |
| 10 | 剩一张卡片时 | 手柄和按钮均不渲染 |
| 11 | Inspector collapsed | 内容 `display: none`，collapse 状态下不启动拖拽 |
| 12 | localStorage.clear() 后刷新 | 恢复默认排序 |
| 13 | 卡片内按钮 (Create Task) | 点击不触发拖拽 |
| 14 | keyboard-only: Tab 到手柄 | 可聚焦，可见 focus ring |

- [ ] **Step 3: Commit (如有微调)**

```bash
git status
# 如有 CSS 或组件微调：
git add src/api/frontend/src/
git commit -m "chore(frontend): final adjustments for inspector reorder"
```

---

### 可选增强 (不阻塞交付)

以下增强在第一版完成后可后续跟进：

- **手柄键盘拖动** (Space/Enter 拾起态 → ArrowUp/Down 调整 → Space/Enter 放下): 模仿 dnd-kit keyboard sensor，需额外 `idle → picked → idle` 状态机
- **拖拽缩略图** (setDragImage 自定义幽灵图): 当前方案无幽灵图，若用户反馈手感不足可补充
- **触摸反馈** (haptic feedback): `navigator.vibrate` 在 pointerdown 时轻微振动

---

### 变更文件总览

```
src/api/frontend/src/components/InspectorPanel.tsx   ← 主要重写
src/api/frontend/src/pages/DashboardPage.tsx          ← JSX → descriptors
src/api/frontend/src/pages/TaskDetailPage.tsx         ← JSX → descriptors
src/api/frontend/src/pages/TaskBuilderPage.tsx        ← JSX → descriptors
src/api/frontend/src/pages/EventTimelinePage.tsx      ← JSX → descriptors
src/api/frontend/src/main.tsx                         ← state 类型变更
src/api/frontend/src/styles/app.css                   ← 新增样式
```

无新增文件。
