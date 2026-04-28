import { useCallback, useEffect, useMemo, useState } from "react";
import { apiClient } from "../api/client";
import type { TaskIntakeSchema, TaskIntakeSession } from "../api/types";
import { ClarificationCard } from "../components/ClarificationCard";
import { FieldSourceBadge } from "../components/FieldSourceBadge";
import { IntakeConfirmPanel } from "../components/IntakeConfirmPanel";
import { TaskDraftForm } from "../components/TaskDraftForm";

interface TaskBuilderPageProps {
  onOpenTask: (taskId: string) => void;
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

function errorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

export function TaskBuilderPage({ onOpenTask }: TaskBuilderPageProps) {
  const [schema, setSchema] = useState<TaskIntakeSchema | null>(null);
  const [text, setText] = useState("");
  const [intake, setIntake] = useState<TaskIntakeSession | null>(null);
  const [acknowledgedWarnings, setAcknowledgedWarnings] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadSchema = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      setSchema(await apiClient.getTaskIntakeSchema());
    } catch (nextError) {
      setError(errorMessage(nextError));
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    void loadSchema();
  }, [loadSchema]);

  const warningCodes = useMemo(
    () => (intake?.safety_check.risk_flags ?? []).filter((risk) => risk.level === "warn").map((risk) => risk.code),
    [intake],
  );

  const canConfirm = useMemo(() => {
    if (!intake) {
      return false;
    }
    const allWarningsAcknowledged = warningCodes.every((code) => acknowledgedWarnings.includes(code));
    return (
      intake.missing_required_fields.length === 0 &&
      intake.ambiguous_fields.length === 0 &&
      intake.safety_check.action !== "block" &&
      allWarningsAcknowledged
    );
  }, [acknowledgedWarnings, intake, warningCodes]);

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
    } catch (nextError) {
      setError(errorMessage(nextError));
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
      setError(errorMessage(nextError));
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
      onOpenTask(confirmation.task_id);
    } catch (nextError) {
      setError(errorMessage(nextError));
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

  return (
    <div className="task-builder-layout">
      <section className="builder-hero">
        <div>
          <p className="eyebrow">Task Intake</p>
          <h2>Task Builder</h2>
        </div>
        <div className="builder-hero-actions">
          <span className="pill">{intake?.intake_id ?? "new intake"}</span>
          <button type="button" onClick={() => void loadSchema()} disabled={busy}>
            Reload Schema
          </button>
        </div>
      </section>

      {error ? <p className="error-text">{error}</p> : null}

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
        <IntakeConfirmPanel
          intake={intake}
          acknowledgedWarnings={acknowledgedWarnings}
          canConfirm={canConfirm}
          busy={busy}
          onToggleWarning={toggleWarning}
          onConfirm={() => void confirmDraft()}
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
                  <article className={isAmbiguous ? "draft-field-card warning" : "draft-field-card"} key={name}>
                    <div>
                      <strong>{name.replace(/_/g, " ")}</strong>
                      <p>{formatValue(field.value)}</p>
                    </div>
                    <div className="source-row">
                      <FieldSourceBadge source={field.source} confidence={field.confidence} warning={isAmbiguous} />
                      {field.confirmed ? <span className="source-chip ok">confirmed</span> : <span className="source-chip warning">review</span>}
                      {field.source_span ? <span className="source-chip">{field.source_span}</span> : null}
                    </div>
                  </article>
                );
              })}
            </div>
          ) : (
            <p className="muted">No draft fields yet.</p>
          )}
        </section>
      </section>
    </div>
  );
}
