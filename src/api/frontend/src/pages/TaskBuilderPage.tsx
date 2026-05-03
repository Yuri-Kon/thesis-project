import { useCallback, useEffect, useMemo, useState } from "react";
import type { InspectorCardDescriptor } from "../components/InspectorPanel";
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
  onInspectorChange: (cards: InspectorCardDescriptor[]) => void;
  onActiveIntakeChange: (intakeId: string | null) => void;
  draftNavigateHref: string | null;
  onResolveDraftNavigate: (action: "continue" | "discard" | "save" | "cancel") => void;
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
      const nextSchema = await apiClient.getTaskIntakeSchema();
      setSchema(nextSchema);
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
        e.preventDefault();
        e.returnValue = "";
      };
      window.addEventListener("beforeunload", handler);
      return () => {
        window.removeEventListener("beforeunload", handler);
        onActiveIntakeChange(null);
      };
    } else {
      onActiveIntakeChange(null);
    }
  }, [intake, onActiveIntakeChange]);

  const showDialog = draftNavigateHref !== null && isActiveDraft(intake) && intake !== null;

  function handleContinueEditing() {
    onResolveDraftNavigate("continue");
  }

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

  function handleCancelNavigate() {
    onResolveDraftNavigate("cancel");
  }

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
      if (!confirmation.task_id) {
        setError(confirmation.scenario_gate?.user_message ?? "Scenario gate kept this intake as draft only.");
        setIntake(await apiClient.getTaskIntake(intake.intake_id));
        return;
      }
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
            <dd>
              {taskProfile ? (
                <div className="inspector-profile-head">
                  {taskKind ? <span className="source-chip">{taskKind.replace(/_/g, " ")}</span> : null}
                  <span className={`source-chip support-chip support-${taskProfile.support_level.toLowerCase()}`}>
                    {supportLabel(taskProfile.support_level)}
                  </span>
                </div>
              ) : (
                "not selected"
              )}
            </dd>
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

  const showDraftSwitcher = recentIds.length > 0;

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
          onDiscardAndLeave={handleDiscardAndLeave}
          onSaveAndLeave={handleSaveAndLeave}
          onCancel={handleCancelNavigate}
        />
      ) : null}
    </div>
  );
}
