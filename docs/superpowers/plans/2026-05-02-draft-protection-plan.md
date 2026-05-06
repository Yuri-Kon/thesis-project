# Task Builder Draft Protection & Recovery — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent accidental draft loss in Task Builder via navigation interception dialog, browser beforeunload guard, and localStorage-based draft recovery dropdown.

**Architecture:** App coordinates cross-component communication via lifted state (`activeIntakeId`, `draftNavigateHref`). TaskBuilderPage reports active draft status upward, Sidebar/Dashboard check it before navigating away, and TaskBuilderPage renders the protection dialog when App signals an intercepted navigation. All new UI (dialog, recovery dropdown) lives in TaskBuilderPage via React portal.

**Tech Stack:** React 18, TypeScript, existing CSS variables, no new dependencies.

**Design Spec:** `docs/superpowers/specs/2026-05-02-draft-protection-design.md`

---

### Task 1: DraftProtectionDialog component

**Files:**
- Create: `src/api/frontend/src/components/DraftProtectionDialog.tsx`

- [ ] **Step 1: Create DraftProtectionDialog component**

```tsx
import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";

interface DraftProtectionDialogProps {
  intakeId: string;
  updatedAt: string;
  status: "collecting" | "needs_confirmation";
  onContinueEditing: () => void;
  onDiscardAndNew: () => void;
  onCancel: () => void;
}

export function DraftProtectionDialog({
  intakeId,
  updatedAt,
  status,
  onContinueEditing,
  onDiscardAndNew,
  onCancel,
}: DraftProtectionDialogProps) {
  const continueRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    continueRef.current?.focus();
  }, []);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onCancel();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onCancel]);

  return createPortal(
    <div className="draft-dialog-backdrop" role="presentation">
      <div
        className="draft-dialog"
        role="alertdialog"
        aria-modal="true"
        aria-label="Unsaved Intake Draft"
      >
        <h3>Unsaved Intake Draft</h3>
        <p>
          You have an active intake draft{" "}
          <strong>{intakeId}</strong> that has not been confirmed as a task.
        </p>
        <div className="draft-dialog-meta">
          <span>
            Last updated: <strong>{updatedAt}</strong>
          </span>
          <span>
            Status: <strong>{status.replace(/_/g, " ")}</strong>
          </span>
        </div>
        <div className="draft-dialog-actions">
          <button type="button" className="text-button" onClick={onCancel}>
            Cancel
          </button>
          <button type="button" className="secondary-button" onClick={onDiscardAndNew}>
            Discard &amp; New
          </button>
          <button ref={continueRef} onClick={onContinueEditing}>
            Continue Editing
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `npx tsc --noEmit src/api/frontend/src/components/DraftProtectionDialog.tsx --jsx react-jsx --esModuleInterop --moduleResolution bundler --target es2020 --lib es2020,dom 2>&1 | head -5`
Expected: No errors (or only missing module errors for react/ react-dom, which are fine).

---

### Task 2: Dialog CSS styles

**Files:**
- Modify: `src/api/frontend/src/styles/app.css` (append at end)

- [ ] **Step 1: Add dialog, backdrop, and animation styles to app.css**

Append at the end of `src/api/frontend/src/styles/app.css`:

```css
/* ---- Draft Protection Dialog ---- */

.draft-dialog-backdrop {
  align-items: center;
  animation: draftDialogFadeIn 150ms ease-out;
  background: rgba(0, 0, 0, 0.3);
  display: flex;
  inset: 0;
  justify-content: center;
  position: fixed;
  z-index: 1000;
}

.draft-dialog {
  animation: draftDialogScaleIn 200ms ease-out;
  background: var(--surface);
  border-radius: 12px;
  box-shadow: var(--shadow);
  max-width: 440px;
  padding: 28px 32px 24px;
  width: calc(100vw - 48px);
}

.draft-dialog h3 {
  color: var(--text);
  font-size: 1.1rem;
  font-weight: 800;
  margin: 0 0 4px;
}

.draft-dialog p {
  color: var(--muted);
  font-size: 0.875rem;
  line-height: 1.5;
  margin: 0 0 16px;
}

.draft-dialog strong {
  color: var(--text);
}

.draft-dialog-meta {
  background: var(--surface-tint);
  border-radius: var(--radius);
  color: var(--muted);
  display: flex;
  font-size: 0.8125rem;
  gap: 20px;
  margin-bottom: 20px;
  padding: 10px 14px;
}

.draft-dialog-meta strong {
  color: var(--text);
}

.draft-dialog-actions {
  align-items: center;
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}

.draft-dialog-actions .text-button {
  background: transparent;
  border: none;
  box-shadow: none;
  color: var(--muted);
  font-size: 0.8125rem;
  font-weight: 500;
  min-height: auto;
  padding: 8px 14px;
}

.draft-dialog-actions .secondary-button {
  background: var(--surface);
  border: 1px solid var(--line);
  box-shadow: none;
  color: var(--text);
  font-size: 0.8125rem;
  font-weight: 600;
  min-height: auto;
  padding: 8px 16px;
}

.draft-dialog-actions > button:not(.text-button):not(.secondary-button) {
  font-size: 0.8125rem;
  min-height: auto;
  padding: 8px 18px;
}

@keyframes draftDialogFadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes draftDialogScaleIn {
  from { transform: scale(0.95); opacity: 0; }
  to { transform: scale(1); opacity: 1; }
}

/* ---- Draft Recovery Select ---- */

.recovery-select {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  color: var(--text);
  cursor: pointer;
  font-size: 0.8125rem;
  min-height: auto;
  padding: 6px 30px 6px 10px;
  width: auto;
}
```

- [ ] **Step 2: Verify CSS is valid (no syntax check needed, review visually)**

No command needed — CSS will be verified visually when running the app.

---

### Task 3: App coordination layer (main.tsx)

**Files:**
- Modify: `src/api/frontend/src/main.tsx:46-171`

- [ ] **Step 1: Add activeIntakeId and draftNavigateHref state to App**

Read `src/api/frontend/src/main.tsx` first to confirm current content, then apply the following edits.

Edit 1 — Add new state after `useState(bootstrap.taskId)` (line 48):

```tsx
const [activeIntakeId, setActiveIntakeId] = useState<string | null>(null);
const [draftNavigateHref, setDraftNavigateHref] = useState<string | null>(null);
```

Edit 2 — Add callbacks after the `loadWorkspace` useCallback block (after line 106):

```tsx
const handleActiveIntakeChange = useCallback((intakeId: string | null) => {
  setActiveIntakeId(intakeId);
}, []);

const handleDraftNavigate = useCallback((href: string) => {
  setDraftNavigateHref(href);
}, []);

const handleResolveDraftNavigate = useCallback(
  (action: "continue" | "discard" | "cancel") => {
    if (action === "discard" && draftNavigateHref) {
      window.location.href = draftNavigateHref;
      return;
    }
    setDraftNavigateHref(null);
  },
  [draftNavigateHref],
);
```

Edit 3 — Update WorkbenchSidebar JSX to pass new props (line 158):

```tsx
<WorkbenchSidebar
  state={state}
  taskId={taskId}
  view={bootstrap.view}
  activeIntakeId={activeIntakeId}
  onDraftNavigate={handleDraftNavigate}
/>
```

Edit 4 — Update DashboardPage JSX to pass new props (line 151):

```tsx
<DashboardPage
  state={state}
  taskId={taskId}
  onTaskIdChange={setTaskId}
  onOpenTask={openTask}
  onRefresh={() => loadWorkspace(taskId)}
  onInspectorChange={setInspector}
  activeIntakeId={activeIntakeId}
  onDraftNavigate={handleDraftNavigate}
/>
```

Edit 5 — Update TaskBuilderPage JSX to pass new props (line 147):

```tsx
<TaskBuilderPage
  onOpenTask={openTask}
  onInspectorChange={setInspector}
  onActiveIntakeChange={handleActiveIntakeChange}
  draftNavigateHref={draftNavigateHref}
  onResolveDraftNavigate={handleResolveDraftNavigate}
/>
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd src/api/frontend && npx tsc --noEmit 2>&1 | head -20`
Expected: No new errors introduced by our changes (preexisting errors OK).

- [ ] **Step 3: Commit**

```bash
git add src/api/frontend/src/main.tsx
git commit -m "feat(frontend): add draft protection coordination state to App"
```

---

### Task 4: WorkbenchSidebar link interception

**Files:**
- Modify: `src/api/frontend/src/components/WorkbenchSidebar.tsx:1-94`

- [ ] **Step 1: Add new props and onClick interception**

Replace the entire `WorkbenchSidebar` component with:

```tsx
import type { WorkspaceState } from "../main";

interface WorkbenchSidebarProps {
  state: WorkspaceState;
  taskId: string;
  view: string;
  activeIntakeId: string | null;
  onDraftNavigate: (href: string) => void;
}

function navHref(item: string, taskId: string): string {
  if (item === "Overview") {
    return "/ui";
  }
  if (item === "Task Builder") {
    return "/ui/task-builder";
  }
  if (item === "Timeline" && taskId) {
    return `/ui/tasks/${encodeURIComponent(taskId)}/events`;
  }
  if ((item === "Task Detail" || item === "Review" || item === "Explorer") && taskId) {
    return `/ui/tasks/${encodeURIComponent(taskId)}`;
  }
  return "#";
}

function isActive(item: string, view: string): boolean {
  if (item === "Overview") {
    return view === "dashboard";
  }
  if (item === "Task Builder") {
    return view === "task_builder";
  }
  if (item === "Timeline") {
    return view === "event_timeline";
  }
  return view === "task_detail" && ["Task Detail", "Review", "Explorer"].includes(item);
}

export function WorkbenchSidebar({ state, taskId, view, activeIntakeId, onDraftNavigate }: WorkbenchSidebarProps) {
  const blockedCapabilities = state.readiness.filter((entry) => entry.status === "blocked").length;
  const warningCount = state.readiness.filter((entry) => entry.status === "degraded").length;
  const navItems = ["Overview", "Task Builder", "Task Detail", "Review", "Timeline", "Explorer"];

  const handleClick = (href: string) => (e: React.MouseEvent) => {
    if (activeIntakeId && view === "task_builder") {
      e.preventDefault();
      onDraftNavigate(href);
    }
  };

  return (
    <aside className="workbench-sidebar" aria-label="Workspace sidebar">
      <div className="sidebar-brand">
        <span className="brand-mark">PD</span>
        <div>
          <strong>Protein Design Console</strong>
          <p>Operator workspace</p>
        </div>
      </div>

      <section className="sidebar-attention">
        <div>
          <strong>Needs attention</strong>
          <p>Pending decisions, warnings, and blockers.</p>
        </div>
        <span className="counter">{state.pendingActions.length + warningCount + blockedCapabilities}</span>
      </section>

      <nav className="sidebar-nav" aria-label="Primary navigation">
        {navItems.map((item) => {
          const href = navHref(item, taskId);
          const disabled = href === "#";
          return disabled ? (
            <span key={item} className="disabled">
              {item}
            </span>
          ) : (
            <a
              key={item}
              href={href}
              className={isActive(item, view) ? "active" : undefined}
              onClick={handleClick(href)}
            >
              {item}
            </a>
          );
        })}
      </nav>

      <section className="sidebar-filters">
        <p className="eyebrow">Filters</p>
        <details>
          <summary>Status</summary>
          <span>waiting / running / done / failed</span>
        </details>
        <details>
          <summary>Category</summary>
          <span>capability / review / artifact</span>
        </details>
        <details>
          <summary>Time range</summary>
          <span>latest workspace data</span>
        </details>
      </section>
    </aside>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add src/api/frontend/src/components/WorkbenchSidebar.tsx
git commit -m "feat(frontend): add draft-aware navigation interception to WorkbenchSidebar"
```

---

### Task 5: DashboardPage link interception

**Files:**
- Modify: `src/api/frontend/src/pages/DashboardPage.tsx:1-83`

- [ ] **Step 1: Add new props and intercept "New intake" link**

Replace the `DashboardPage` component with:

```tsx
import { type ReactNode, useEffect } from "react";
import type { WorkspaceState } from "../main";
import { CapabilityReadinessPanel } from "../components/CapabilityReadinessPanel";
import { MetricCard } from "../components/MetricCard";
import { ModelInvocationPanel } from "../components/ModelInvocationPanel";
import { PendingActionList } from "../components/PendingActionList";
import { TaskSearch } from "../components/TaskSearch";
import { DashboardSkeleton } from "../components/SkeletonCard";

interface DashboardPageProps {
  state: WorkspaceState;
  taskId: string;
  onTaskIdChange: (taskId: string) => void;
  onOpenTask: (taskId: string) => void;
  onRefresh: () => void;
  onInspectorChange: (content: ReactNode) => void;
  activeIntakeId: string | null;
  onDraftNavigate: (href: string) => void;
}

export function DashboardPage({ state, taskId, onTaskIdChange, onOpenTask, onRefresh, onInspectorChange, activeIntakeId, onDraftNavigate }: DashboardPageProps) {
  const blockedCapabilities = state.readiness.filter((entry) => entry.status === "blocked").length;
  const degradedCapabilities = state.readiness.filter((entry) => entry.status === "degraded").length;

  const handleNewIntakeClick = (e: React.MouseEvent) => {
    if (activeIntakeId) {
      e.preventDefault();
      onDraftNavigate("/ui/task-builder");
    }
  };

  useEffect(() => {
    onInspectorChange(
      <>
        <section className="inspector-card">
          <div className="panel-header">
            <h2>Inspector</h2>
            <span className="pill">overview</span>
          </div>
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
        </section>
        <section className="inspector-card warning-card">
          <h2>Action required</h2>
          <p>{state.pendingActions.length ? "Open a pending action to review candidates and submit a decision." : "No pending review is currently reported by the API."}</p>
          <a className="inspector-action" href="/ui/task-builder" onClick={handleNewIntakeClick}>New intake</a>
        </section>
      </>,
    );
  }, [blockedCapabilities, onInspectorChange, state.pendingActions.length, state.readiness.length, state.task?.id, activeIntakeId, onDraftNavigate]);

  if (state.loading) {
    return (
      <div className="dashboard-layout">
        <DashboardSkeleton />
      </div>
    );
  }

  return (
    <div className="dashboard-layout">
      <section className="workspace-hero">
        <div>
          <p className="eyebrow">Operator Console</p>
          <h2>Dashboard</h2>
          <p>Review queue, task lookup, and capability health from the public API boundary.</p>
        </div>
        <TaskSearch taskId={taskId} onTaskIdChange={onTaskIdChange} onSubmit={onOpenTask} onRefresh={onRefresh} />
      </section>
      <section className="metric-strip" aria-label="Workspace overview">
        <MetricCard label="Pending reviews" value={state.pendingActions.length} detail="human decisions waiting" tone={state.pendingActions.length ? "amber" : "green"} />
        <MetricCard label="Capabilities" value={state.readiness.length} detail={`${blockedCapabilities} blocked - ${degradedCapabilities} degraded`} tone={blockedCapabilities ? "red" : degradedCapabilities ? "amber" : "blue"} />
        <MetricCard label="Loaded task" value={state.task?.status ?? "none"} detail={state.task?.id ?? "open a task to inspect"} />
      </section>
      <section className="dashboard-grid">
        <PendingActionList pendingActions={state.pendingActions} onOpenTask={onOpenTask} />
        <div className="side-stack">
          <CapabilityReadinessPanel readiness={state.readiness} />
          <ModelInvocationPanel readiness={state.readiness} pendingActionDetail={state.pendingActionDetail} />
        </div>
      </section>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add src/api/frontend/src/pages/DashboardPage.tsx
git commit -m "feat(frontend): add draft-aware navigation interception to DashboardPage"
```

---

### Task 6: TaskBuilderPage draft protection (beforeunload, localStorage, recovery dropdown, dialog)

**Files:**
- Modify: `src/api/frontend/src/pages/TaskBuilderPage.tsx:1-296`

- [ ] **Step 1: Read and rewrite TaskBuilderPage with all draft protection logic**

Replace the entire `TaskBuilderPage.tsx`:

```tsx
import { type ReactNode, useCallback, useEffect, useMemo, useState } from "react";
import { apiClient, apiErrorMessage, ApiError } from "../api/client";
import type { TaskIntakeSchema, TaskIntakeSession, TaskIntakeTaskProfile } from "../api/types";
import { ClarificationCard } from "../components/ClarificationCard";
import { DraftProtectionDialog } from "../components/DraftProtectionDialog";
import { ErrorNotice } from "../components/ErrorNotice";
import { FieldSourceBadge } from "../components/FieldSourceBadge";
import { SafetyPrecheckPanel } from "../components/SafetyPrecheckPanel";
import { TaskDraftForm } from "../components/TaskDraftForm";
import { TaskBuilderSkeleton } from "../components/SkeletonCard";

const DRAFT_IDS_KEY = "recent-intake-ids";
const MAX_DRAFT_IDS = 5;

function readDraftIds(): string[] {
  try {
    const raw = localStorage.getItem(DRAFT_IDS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function addDraftId(intakeId: string): void {
  try {
    const ids = readDraftIds().filter((id) => id !== intakeId);
    ids.unshift(intakeId);
    localStorage.setItem(DRAFT_IDS_KEY, JSON.stringify(ids.slice(0, MAX_DRAFT_IDS)));
  } catch {
    /* quota exceeded or private mode */
  }
}

function removeDraftId(intakeId: string): void {
  try {
    const ids = readDraftIds().filter((id) => id !== intakeId);
    localStorage.setItem(DRAFT_IDS_KEY, JSON.stringify(ids));
  } catch {
    /* quota exceeded or private mode */
  }
}

function isActiveDraft(intake: TaskIntakeSession | null): boolean {
  return intake?.status === "collecting" || intake?.status === "needs_confirmation";
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  if (typeof value === "string") {
    return value;
  }
  return JSON.stringify(value);
}

function supportLabel(supportLevel?: string): string {
  if (supportLevel === "P0") {
    return "P0 supported";
  }
  if (supportLevel === "P1") {
    return "P1 experimental";
  }
  if (supportLevel === "P2") {
    return "P2 unsupported";
  }
  return supportLevel ?? "unknown";
}

function selectedTaskKind(intake: TaskIntakeSession | null): string | null {
  const value = intake?.draft.fields.task_kind?.value;
  return typeof value === "string" ? value : null;
}

function draftHasFieldWarnings(intake: TaskIntakeSession | null): boolean {
  return Object.values(intake?.draft.fields ?? {}).some((field) => field.warnings.length > 0);
}

function ProfileNotice({ taskKind, profile }: { taskKind: string | null; profile?: TaskIntakeTaskProfile }) {
  if (!taskKind || !profile || profile.support_level === "P0") {
    return null;
  }
  const tone = profile.support_level === "P1" ? "warning" : "danger";
  return (
    <section className={`notice compact support-notice ${tone}`}>
      <strong>{supportLabel(profile.support_level)}</strong>
      <span>
        {taskKind.replace(/_/g, " ")} is visible for planning and review, but the first React Task Builder pass does not promise automatic execution for this profile.
      </span>
    </section>
  );
}

interface TaskBuilderPageProps {
  onOpenTask: (taskId: string) => void;
  onInspectorChange: (content: ReactNode) => void;
  onActiveIntakeChange: (intakeId: string | null) => void;
  draftNavigateHref: string | null;
  onResolveDraftNavigate: (action: "continue" | "discard" | "cancel") => void;
}

export function TaskBuilderPage({
  onOpenTask,
  onInspectorChange,
  onActiveIntakeChange,
  draftNavigateHref,
  onResolveDraftNavigate,
}: TaskBuilderPageProps) {
  const [schema, setSchema] = useState<TaskIntakeSchema | null>(null);
  const [text, setText] = useState("");
  const [intake, setIntake] = useState<TaskIntakeSession | null>(null);
  const [acknowledgedWarnings, setAcknowledgedWarnings] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recentIds, setRecentIds] = useState<string[]>(() => readDraftIds());

  const loadSchema = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      setSchema(await apiClient.getTaskIntakeSchema());
    } catch (nextError) {
      setError(apiErrorMessage(nextError));
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    void loadSchema();
  }, [loadSchema]);

  // --- Active draft reporting + beforeunload ---
  useEffect(() => {
    const active = isActiveDraft(intake);
    if (active && intake) {
      onActiveIntakeChange(intake.intake_id);
      const handler = (e: BeforeUnloadEvent) => {
        e.returnValue = "";
      };
      window.addEventListener("beforeunload", handler);
      return () => window.removeEventListener("beforeunload", handler);
    } else {
      onActiveIntakeChange(null);
    }
  }, [intake, onActiveIntakeChange]);

  const showDialog = draftNavigateHref !== null && isActiveDraft(intake) && intake !== null;

  function handleContinueEditing() {
    onResolveDraftNavigate("continue");
  }

  function handleDiscardAndNew() {
    if (intake) {
      removeDraftId(intake.intake_id);
      setRecentIds(readDraftIds());
    }
    setIntake(null);
    setText("");
    setAcknowledgedWarnings([]);
    onResolveDraftNavigate("discard");
  }

  function handleCancelNavigate() {
    onResolveDraftNavigate("cancel");
  }

  // --- Recovery ---
  async function handleRecover(intakeId: string) {
    setBusy(true);
    setError(null);
    try {
      const recovered = await apiClient.getTaskIntake(intakeId);
      setIntake(recovered);
      setAcknowledgedWarnings([]);
    } catch (nextError) {
      if (nextError instanceof ApiError && nextError.status === 404) {
        removeDraftId(intakeId);
        setRecentIds(readDraftIds());
        setError("Draft no longer available and has been removed from history.");
      } else {
        setError(apiErrorMessage(nextError));
      }
    } finally {
      setBusy(false);
    }
  }

  const warningCodes = useMemo(
    () => (intake?.safety_check.risk_flags ?? []).filter((risk) => risk.level === "warn").map((risk) => risk.code),
    [intake],
  );
  const taskKind = selectedTaskKind(intake);
  const taskProfile = taskKind ? schema?.task_profiles[taskKind] : undefined;
  const hasFieldWarnings = draftHasFieldWarnings(intake);

  const canConfirm = useMemo(() => {
    if (!intake) {
      return false;
    }
    const allWarningsAcknowledged = warningCodes.every((code) => acknowledgedWarnings.includes(code));
    return (
      intake.missing_required_fields.length === 0 &&
      intake.ambiguous_fields.length === 0 &&
      !hasFieldWarnings &&
      intake.safety_check.action !== "block" &&
      allWarningsAcknowledged
    );
  }, [acknowledgedWarnings, hasFieldWarnings, intake, warningCodes]);

  async function createDraft(structuredFields: Record<string, unknown>) {
    setBusy(true);
    setError(null);
    try {
      const nextIntake = await apiClient.createTaskIntake({
        text: text.trim() || null,
        structured_fields: structuredFields,
        source: "web",
      });
      setIntake(nextIntake);
      setAcknowledgedWarnings([]);
      addDraftId(nextIntake.intake_id);
      setRecentIds(readDraftIds());
    } catch (nextError) {
      setError(apiErrorMessage(nextError));
    } finally {
      setBusy(false);
    }
  }

  async function patchDraft(structuredFields: Record<string, unknown>) {
    if (!intake) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const nextIntake = await apiClient.patchTaskIntake(intake.intake_id, {
        fields: structuredFields,
        updated_by: "web_task_builder",
      });
      setIntake(nextIntake);
    } catch (nextError) {
      setError(apiErrorMessage(nextError));
    } finally {
      setBusy(false);
    }
  }

  async function confirmDraft() {
    if (!intake) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const confirmation = await apiClient.confirmTaskIntake(intake.intake_id, acknowledgedWarnings);
      removeDraftId(intake.intake_id);
      setRecentIds(readDraftIds());
      onActiveIntakeChange(null);
      onOpenTask(confirmation.task_id);
    } catch (nextError) {
      setError(apiErrorMessage(nextError));
    } finally {
      setBusy(false);
    }
  }

  function toggleWarning(code: string) {
    setAcknowledgedWarnings((current) =>
      current.includes(code) ? current.filter((item) => item !== code) : [...current, code],
    );
  }

  const fields = Object.entries(intake?.draft.fields ?? {});
  const ambiguousFields = new Set(intake?.ambiguous_fields ?? []);

  useEffect(() => {
    const safety = intake?.safety_check;
    onInspectorChange(
      <>
        <section className="inspector-card">
          <div className="panel-header">
            <h2>Inspector</h2>
            <span className="pill">{intake?.status ?? "idle"}</span>
          </div>
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
        </section>
        <SafetyPrecheckPanel
          action={safety?.action}
          risks={safety?.risk_flags ?? []}
          acknowledgedWarnings={acknowledgedWarnings}
          onToggleWarning={toggleWarning}
        />
        <section className="inspector-card warning-card">
          <h2>Action required</h2>
          <p>{canConfirm ? "The intake is ready to become a formal task." : "Resolve missing fields, field validation warnings, ambiguous fields, or safety warnings before confirming."}</p>
          <button type="button" className="primary-action" onClick={() => void confirmDraft()} disabled={busy || !canConfirm}>
            Create Task
          </button>
        </section>
      </>,
    );
  }, [acknowledgedWarnings, busy, canConfirm, intake, onInspectorChange, taskKind, taskProfile]);

  const showRecovery = !intake && recentIds.length > 0;

  if (schema === null) {
    return (
      <div className="task-builder-layout">
        <TaskBuilderSkeleton />
      </div>
    );
  }

  return (
    <div className="task-builder-layout">
      <section className="builder-hero">
        <div>
          <p className="eyebrow">Task Intake</p>
          <h2>Task Builder</h2>
        </div>
        <div className="builder-hero-actions">
          <span className="pill">{intake?.intake_id ?? "new intake"}</span>
          {showRecovery ? (
            <select
              className="recovery-select"
              value=""
              onChange={(e) => {
                const id = e.target.value;
                if (id) void handleRecover(id);
              }}
              disabled={busy}
            >
              <option value="">Recover draft ▾</option>
              {recentIds.map((id) => (
                <option key={id} value={id}>
                  {id}
                </option>
              ))}
            </select>
          ) : null}
          <button type="button" onClick={() => void loadSchema()} disabled={busy}>
            Reload Schema
          </button>
        </div>
      </section>

      {error ? <ErrorNotice message={error} /> : null}
      <ProfileNotice taskKind={taskKind} profile={taskProfile} />

      <section className="task-builder-grid">
        <TaskDraftForm
          schema={schema}
          intake={intake}
          text={text}
          busy={busy}
          onTextChange={setText}
          onCreate={(structuredFields) => void createDraft(structuredFields)}
          onPatch={(structuredFields) => void patchDraft(structuredFields)}
        />
      </section>

      <section className="review-band">
        <div className="clarification-grid">
          <ClarificationCard title="Missing Required" items={intake?.missing_required_fields ?? []} tone="danger" />
          <ClarificationCard title="Ambiguous Fields" items={intake?.ambiguous_fields ?? []} tone="warning" />
          <ClarificationCard title="Unmapped Text" items={intake?.unmapped_text ?? []} />
        </div>
        <section className="panel draft-review-panel">
          <div className="panel-header">
            <h2>Confirmed Draft Review</h2>
            <span className="counter">{fields.length}</span>
          </div>
          {intake?.human_summary ? <p className="summary-line">{intake.human_summary}</p> : null}
          {intake?.draft.extraction_errors.length ? (
            <div className="notice compact error">{intake.draft.extraction_errors.join(" | ")}</div>
          ) : null}
          {fields.length ? (
            <div className="draft-field-list">
              {fields.map(([name, field]) => {
                const isAmbiguous = ambiguousFields.has(name) || field.confidence < 0.8;
                return (
                  <details className={isAmbiguous ? "draft-field-card warning" : "draft-field-card"} key={name}>
                    <summary>
                      <span>
                        <strong>{name.replace(/_/g, " ")}</strong>
                        <p>{formatValue(field.value)}</p>
                      </span>
                      <FieldSourceBadge source={field.source} confidence={field.confidence} warning={isAmbiguous} />
                    </summary>
                    <div className="source-row">
                      {field.confirmed ? <span className="source-chip ok">confirmed</span> : <span className="source-chip warning">review</span>}
                      {field.source_span ? <span className="source-chip">{field.source_span}</span> : null}
                      {field.warnings.map((warning) => (
                        <span className="source-chip warning" key={warning}>{warning}</span>
                      ))}
                    </div>
                  </details>
                );
              })}
            </div>
          ) : (
            <p className="muted">No draft fields yet.</p>
          )}
        </section>
      </section>

      {showDialog ? (
        <DraftProtectionDialog
          intakeId={intake!.intake_id}
          updatedAt={intake!.updated_at}
          status={intake!.status as "collecting" | "needs_confirmation"}
          onContinueEditing={handleContinueEditing}
          onDiscardAndNew={handleDiscardAndNew}
          onCancel={handleCancelNavigate}
        />
      ) : null}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add src/api/frontend/src/pages/TaskBuilderPage.tsx
git commit -m "feat(frontend): add draft protection, recovery dropdown, and localStorage management to TaskBuilderPage"
```

---

### Task 7: Build verification

**Files:** None (verification only)

- [ ] **Step 1: Verify TypeScript compiles across the full frontend**

Run: `cd src/api/frontend && npx tsc --noEmit 2>&1 | head -30`
Expected: No new errors introduced by our changes.

- [ ] **Step 2: Verify the frontend builds**

Run: `cd src/api/frontend && npm run build 2>&1 | tail -10`
Expected: Build succeeds without errors.

- [ ] **Step 3: Commit if any fixes were needed**

```bash
git add -A
git commit -m "chore: fix build issues from draft protection implementation"
```

---

### Implementation Order

```
Task 1 (Dialog component) → Task 2 (CSS) → Task 3 (App coordination)
                                              ↓
                         Task 4 (Sidebar) ←──┘
                         Task 5 (Dashboard) ←┘
                         Task 6 (TaskBuilderPage) ←── (depends on Task 1 + Task 3)
                                                    ↓
                                              Task 7 (Verification)
```

Tasks 4 and 5 can run in parallel. Task 6 depends on Tasks 1 and 3 being complete.
