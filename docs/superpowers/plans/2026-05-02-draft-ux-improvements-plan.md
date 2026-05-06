# Draft UX Improvements — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add "Save & Leave" dialog option, upgrade recovery dropdown to always-visible Draft Switcher with auto-save, and add explicit Save Draft button.

**Architecture:** Incremental changes to 3 existing files on branch `issue318-draft-protection`. No new files. The App coordination action type extends from 3 to 4 values. TaskBuilderPage replaces `!intake`-gated recovery with an always-available draft switcher that auto-saves the current draft before loading the selected one.

**Tech Stack:** React 18, TypeScript, existing CSS variables.

**Design Spec:** `docs/superpowers/specs/2026-05-02-draft-ux-improvements-design.md`

---

### Task 1: DraftProtectionDialog — add Save & Leave, rename buttons

**Files:**
- Modify: `src/api/frontend/src/components/DraftProtectionDialog.tsx:1-73`

- [ ] **Step 1: Rewrite DraftProtectionDialog with 4 buttons**

Read the current file, then replace it completely:

```tsx
import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";

interface DraftProtectionDialogProps {
  intakeId: string;
  updatedAt: string;
  status: "collecting" | "needs_confirmation";
  onContinueEditing: () => void;
  onDiscardAndLeave: () => void;
  onSaveAndLeave: () => void;
  onCancel: () => void;
}

export function DraftProtectionDialog({
  intakeId,
  updatedAt,
  status,
  onContinueEditing,
  onDiscardAndLeave,
  onSaveAndLeave,
  onCancel,
}: DraftProtectionDialogProps) {
  const saveRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    saveRef.current?.focus();
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
          <button type="button" className="secondary-button danger-text" onClick={onDiscardAndLeave}>
            Discard &amp; Leave
          </button>
          <button type="button" ref={saveRef} onClick={onSaveAndLeave}>
            Save &amp; Leave
          </button>
          <button type="button" className="secondary-button" onClick={onContinueEditing}>
            Continue Editing
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
```

Key changes from current:
- `onDiscardAndNew` → `onDiscardAndLeave`
- New `onSaveAndLeave` prop and button (primary style, auto-focused instead of Continue Editing)
- "Discard & Leave" gets `danger-text` class for red text
- "Continue Editing" moves to `.secondary-button` (bordered)
- Auto-focus moves from Continue Editing to Save & Leave (the recommended action)

- [ ] **Step 2: Add danger-text CSS**

Append to `src/api/frontend/src/styles/app.css`:

```css
.draft-dialog-actions .danger-text {
  color: var(--danger);
}
```

- [ ] **Step 3: Commit**

```bash
git add src/api/frontend/src/components/DraftProtectionDialog.tsx src/api/frontend/src/styles/app.css
git commit -m "feat(frontend): add Save & Leave button to draft dialog, rename Discard & New to Discard & Leave"
```

---

### Task 2: App coordination — add "save" action

**Files:**
- Modify: `src/api/frontend/src/main.tsx:118-127`

- [ ] **Step 1: Add "save" action to handleResolveDraftNavigate**

Read the file, find lines 118-127:

```tsx
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

Replace with:

```tsx
  const handleResolveDraftNavigate = useCallback(
    (action: "continue" | "discard" | "save" | "cancel") => {
      if ((action === "discard" || action === "save") && draftNavigateHref) {
        window.location.href = draftNavigateHref;
        return;
      }
      setDraftNavigateHref(null);
    },
    [draftNavigateHref],
  );
```

- [ ] **Step 2: Commit**

```bash
git add src/api/frontend/src/main.tsx
git commit -m "feat(frontend): add save action to draft navigation resolution"
```

---

### Task 3: TaskBuilderPage — Draft Switcher, Save Draft, auto-save on switch

**Files:**
- Modify: `src/api/frontend/src/pages/TaskBuilderPage.tsx`

- [ ] **Step 1: Rename Discard handler and add Save handler**

Find `handleDiscardAndNew` (line ~160) and `handleCancelNavigate` (line ~171). Replace them with:

```tsx
  function handleDiscardAndLeave() {
    if (intake) {
      removeDraftId(intake.intake_id);
      setRecentIds(readDraftIds());
    }
    setIntake(null);
    setText("");
    setAcknowledgedWarnings([]);
    onResolveDraftNavigate("discard");
  }

  function handleSaveAndLeave() {
    setIntake(null);
    setText("");
    setAcknowledgedWarnings([]);
    onResolveDraftNavigate("save");
  }
```

- [ ] **Step 2: Replace handleRecover with handleSwitchDraft (auto-save before switch)**

Find `handleRecover` (line ~175-194) and replace with:

```tsx
  // --- Draft Switcher: auto-save current then load selected ---
  async function handleSwitchDraft(targetId: string) {
    if (intake && intake.intake_id === targetId) return;
    setBusy(true);
    setError(null);
    try {
      if (intake) {
        try {
          await apiClient.patchTaskIntake(intake.intake_id, {
            fields: intake.draft.fields,
            updated_by: "web_task_builder",
          });
        } catch {
          /* best-effort save before switching */
        }
      }
      const nextIntake = await apiClient.getTaskIntake(targetId);
      setIntake(nextIntake);
      setAcknowledgedWarnings([]);
    } catch (nextError) {
      if (nextError instanceof ApiError && nextError.status === 404) {
        removeDraftId(targetId);
        setRecentIds(readDraftIds());
        setError("Draft no longer available and has been removed from history.");
      } else {
        setError(apiErrorMessage(nextError));
      }
    } finally {
      setBusy(false);
    }
  }
```

- [ ] **Step 3: Add Save Draft button handler**

Add after handleSwitchDraft:

```tsx
  // --- Explicit Save Draft ---
  const [draftSaved, setDraftSaved] = useState(false);

  async function handleSaveDraft() {
    if (!intake) return;
    setBusy(true);
    setError(null);
    try {
      await apiClient.patchTaskIntake(intake.intake_id, {
        fields: intake.draft.fields,
        updated_by: "web_task_builder",
      });
      addDraftId(intake.intake_id);
      setRecentIds(readDraftIds());
      setDraftSaved(true);
      setTimeout(() => setDraftSaved(false), 2000);
    } catch (nextError) {
      setError(apiErrorMessage(nextError));
    } finally {
      setBusy(false);
    }
  }
```

- [ ] **Step 4: Update showRecovery → showDraftSwitcher**

Find `const showRecovery = !intake && recentIds.length > 0;` (line ~326) and replace with:

```tsx
  const showDraftSwitcher = recentIds.length > 0;
```

- [ ] **Step 5: Replace the recovery select with draft switcher + Save Draft button in JSX**

Find the builder-hero-actions section (lines ~343-366). The current code:

```tsx
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
```

Replace with:

```tsx
        <div className="builder-hero-actions">
          <span className="pill">{intake?.intake_id ?? "new intake"}</span>
          {showDraftSwitcher ? (
            <div className="draft-switcher-group">
              <span className="draft-switcher-label">Drafts</span>
              <select
                className="recovery-select"
                value={intake?.intake_id ?? ""}
                onChange={(e) => {
                  const id = e.target.value;
                  if (id) void handleSwitchDraft(id);
                }}
                disabled={busy}
              >
                {recentIds.map((id) => (
                  <option key={id} value={id} disabled={id === intake?.intake_id}>
                    {id}{id === intake?.intake_id ? " (current)" : ""}
                  </option>
                ))}
              </select>
            </div>
          ) : null}
          {intake ? (
            <button type="button" className="save-draft-button" onClick={() => void handleSaveDraft()} disabled={busy}>
              {draftSaved ? "Saved" : "Save Draft"}
            </button>
          ) : null}
          <button type="button" onClick={() => void loadSchema()} disabled={busy}>
            Reload Schema
          </button>
        </div>
```

- [ ] **Step 6: Update DraftProtectionDialog JSX props**

Find the `<DraftProtectionDialog ... />` rendering (near end of return). Update props:

```tsx
      {showDialog ? (
        <DraftProtectionDialog
          intakeId={intake!.intake_id}
          updatedAt={intake!.updated_at}
          status={intake!.status as "collecting" | "needs_confirmation"}
          onContinueEditing={handleContinueEditing}
          onDiscardAndLeave={handleDiscardAndLeave}
          onSaveAndLeave={handleSaveAndLeave}
          onCancel={handleCancelNavigate}
        />
      ) : null}
```

- [ ] **Step 7: Add CSS for draft-switcher-group and save-draft-button**

Append to `src/api/frontend/src/styles/app.css`:

```css
.draft-switcher-group {
  align-items: center;
  background: var(--surface-tint);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  display: flex;
  gap: 4px;
  padding: 0 6px 0 8px;
}

.draft-switcher-label {
  color: var(--muted);
  font-size: 0.6875rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  white-space: nowrap;
}

.draft-switcher-group .recovery-select {
  background: transparent;
  border: none;
  min-height: auto;
  padding: 6px 28px 6px 4px;
}

.save-draft-button {
  font-size: 0.75rem;
  font-weight: 600;
  min-height: auto;
  padding: 6px 14px;
  white-space: nowrap;
}
```

- [ ] **Step 8: Commit**

```bash
git add src/api/frontend/src/pages/TaskBuilderPage.tsx src/api/frontend/src/styles/app.css
git commit -m "feat(frontend): add Draft Switcher with auto-save, Save Draft button, and Save & Leave dialog integration"
```

---

### Task 4: Build verification

**Files:** None

- [ ] **Step 1: TypeScript check**

Run: `cd /home/yurikon/Documents/thesis/thesis-project.dev && npx tsc --noEmit 2>&1 | head -10`
Expected: No output (0 errors).

- [ ] **Step 2: Commit any fixups**

```bash
git add -A && git commit -m "chore: fix build issues from draft UX improvements" || echo "no fixes needed"
```

---

### Implementation Order

```
Task 1 (Dialog) → Task 2 (App) → Task 3 (TaskBuilderPage) → Task 4 (Verify)
```

Task 1 and 2 can run in parallel (no dependency between them). Task 3 depends on both (uses new prop names from Task 1, new action type from Task 2).
