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
import { booleanLabel, identifierLabel, supportLabel as supportLabelText } from "../utils/displayText";

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
    return identifierLabel(value);
  }
  return JSON.stringify(value);
}

function supportLabel(supportLevel?: string): string {
  return supportLabelText(supportLevel);
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
        {identifierLabel(taskKind)} 可用于规划和复核，但当前任务构建器不承诺此类型一定能自动执行。
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
        setError("草稿已不可用，并已从历史记录中移除。");
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
        setError(confirmation.scenario_gate?.user_message ?? "场景门控将本次录入保留为草稿。");
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
        title: "检查器",
        statusBadge: <span className="pill">{identifierLabel(intake?.status ?? "idle")}</span>,
        children: (
          <dl className="kv compact-kv">
            <dt>录入</dt>
            <dd>{intake?.intake_id ?? "新建"}</dd>
            <dt>缺失</dt>
            <dd>{intake?.missing_required_fields.length ?? 0}</dd>
            <dt>歧义</dt>
            <dd>{intake?.ambiguous_fields.length ?? 0}</dd>
            <dt>未映射</dt>
            <dd>{intake?.unmapped_text.length ?? 0}</dd>
            <dt>类型</dt>
            <dd>
              {taskProfile ? (
                <div className="inspector-profile-head">
                  {taskKind ? <span className="source-chip">{identifierLabel(taskKind)}</span> : null}
                  <span className={`source-chip support-chip support-${taskProfile.support_level.toLowerCase()}`}>
                    {supportLabel(taskProfile.support_level)}
                  </span>
                </div>
              ) : (
                "未选择"
              )}
            </dd>
            <dt>可确认</dt>
            <dd>{booleanLabel(canConfirm)}</dd>
          </dl>
        ),
      },
      {
        key: "safety-precheck",
        title: "安全预检查",
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
        title: "需要处理",
        tone: "warning",
        children: (
          <>
            <p>{canConfirm ? "本次录入已可创建正式任务。" : "确认前请补齐缺失字段，处理字段校验警告、歧义字段或安全警告。"}</p>
            <button type="button" className="primary-action" onClick={() => void confirmDraft()} disabled={busy || !canConfirm}>
              创建任务
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
          <p className="eyebrow">任务录入</p>
          <h2>任务构建器</h2>
        </div>
        <div className="builder-hero-actions">
          <span className="pill">{intake?.intake_id ?? "新建录入"}</span>
          {showDraftSwitcher ? (
            <div className="draft-switcher-group">
              <span className="draft-switcher-label">草稿</span>
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
                    {id}{id === intake?.intake_id ? "（当前）" : ""}
                  </option>
                ))}
              </select>
            </div>
          ) : null}
          {intake ? (
            <button type="button" className="save-draft-button" onClick={() => void handleSaveDraft()} disabled={busy}>
              {draftSaved ? "已保存" : "保存草稿"}
            </button>
          ) : null}
          <button type="button" onClick={() => void loadSchema()} disabled={busy}>
            重新加载 Schema
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
          <ClarificationCard title="缺失必填项" items={intake?.missing_required_fields.map(identifierLabel) ?? []} tone="danger" />
          <ClarificationCard title="歧义字段" items={intake?.ambiguous_fields.map(identifierLabel) ?? []} tone="warning" />
          <ClarificationCard title="未映射文本" items={intake?.unmapped_text ?? []} />
        </div>
        <section className="panel draft-review-panel">
          <div className="panel-header">
            <h2>草稿复核</h2>
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
                        <strong>{identifierLabel(name)}</strong>
                        <p>{formatValue(field.value)}</p>
                      </span>
                      <FieldSourceBadge source={field.source} confidence={field.confidence} warning={isAmbiguous} />
                    </summary>
                    <div className="source-row">
                      {field.confirmed ? <span className="source-chip ok">已确认</span> : <span className="source-chip warning">待复核</span>}
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
            <p className="muted">暂无草稿字段。</p>
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
