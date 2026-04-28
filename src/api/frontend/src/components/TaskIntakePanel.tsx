import { type FormEvent, useMemo, useState } from "react";
import { apiClient } from "../api/client";
import type { TaskIntakeSession } from "../api/types";

interface TaskIntakePanelProps {
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

export function TaskIntakePanel({ onOpenTask }: TaskIntakePanelProps) {
  const [text, setText] = useState("");
  const [intake, setIntake] = useState<TaskIntakeSession | null>(null);
  const [acknowledgedWarnings, setAcknowledgedWarnings] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const safetyWarnings = useMemo(
    () => (intake?.safety_check.risk_flags ?? []).filter((risk) => risk.level === "warn"),
    [intake],
  );
  const hasSafetyBlock = useMemo(
    () => intake?.safety_check.action === "block",
    [intake],
  );

  const canConfirm = useMemo(() => {
    if (!intake) {
      return false;
    }
    const allWarningsAcknowledged = safetyWarnings.every((risk) =>
      acknowledgedWarnings.includes(risk.code),
    );
    return (
      intake.missing_required_fields.length === 0 &&
      intake.ambiguous_fields.length === 0 &&
      !hasSafetyBlock &&
      allWarningsAcknowledged
    );
  }, [acknowledgedWarnings, hasSafetyBlock, intake, safetyWarnings]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const nextIntake = await apiClient.createTaskIntake({
        text: text.trim() || null,
        structured_fields: {},
        source: "web",
      });
      setIntake(nextIntake);
      setAcknowledgedWarnings([]);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : String(nextError));
    } finally {
      setBusy(false);
    }
  }

  async function handleConfirm() {
    if (!intake) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const confirmation = await apiClient.confirmTaskIntake(
        intake.intake_id,
        acknowledgedWarnings,
      );
      onOpenTask(confirmation.task_id);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : String(nextError));
    } finally {
      setBusy(false);
    }
  }

  const fields = Object.entries(intake?.draft.fields ?? {});
  const ambiguous = new Set(intake?.ambiguous_fields ?? []);

  function toggleAcknowledgement(code: string) {
    setAcknowledgedWarnings((current) =>
      current.includes(code)
        ? current.filter((item) => item !== code)
        : [...current, code],
    );
  }

  return (
    <section className="panel intake-panel">
      <div className="panel-header">
        <div>
          <h2>Task Intake</h2>
        </div>
        <span className="pill">{intake?.status ?? "draft"}</span>
      </div>
      <form className="intake-form" onSubmit={handleSubmit}>
        <textarea
          value={text}
          onChange={(event) => setText(event.target.value)}
          placeholder="Describe the protein design request..."
        />
        <div className="button-row">
          <button type="submit" disabled={busy || !text.trim()}>
            Extract
          </button>
          <button type="button" onClick={handleConfirm} disabled={busy || !canConfirm}>
            Create Task
          </button>
        </div>
      </form>
      {error ? <p className="error-text">{error}</p> : null}
      {intake ? (
        <div className="intake-result">
          <dl className="kv">
            <dt>summary</dt>
            <dd>{intake.human_summary || "-"}</dd>
            <dt>mode</dt>
            <dd>{intake.draft.extraction_mode}</dd>
            <dt>missing</dt>
            <dd>{intake.missing_required_fields.join(", ") || "-"}</dd>
            <dt>ambiguous</dt>
            <dd>{intake.ambiguous_fields.join(", ") || "-"}</dd>
            <dt>unmapped</dt>
            <dd>{intake.unmapped_text.join(" | ") || "-"}</dd>
          </dl>
          {intake.draft.extraction_errors.length ? (
            <div className="notice compact">
              {intake.draft.extraction_errors.join(" | ")}
            </div>
          ) : null}
          {intake.safety_check.risk_flags.length ? (
            <div className={hasSafetyBlock ? "notice compact error" : "notice compact"}>
              {intake.safety_check.risk_flags.map((risk) => (
                <label className="warning-ack" key={`${risk.level}-${risk.code}-${risk.message}`}>
                  <input
                    type="checkbox"
                    checked={risk.level === "block" ? false : acknowledgedWarnings.includes(risk.code)}
                    disabled={risk.level === "block"}
                    onChange={() => toggleAcknowledgement(risk.code)}
                  />
                  <span>
                    <strong>{risk.level}</strong> {risk.code}: {risk.message}
                  </span>
                </label>
              ))}
            </div>
          ) : null}
          {fields.length ? (
            <div className="field-table" role="table" aria-label="Extracted intake fields">
              <div className="field-row field-row-head" role="row">
                <span>Field</span>
                <span>Value</span>
                <span>Source</span>
                <span>Confidence</span>
                <span>Span</span>
              </div>
              {fields.map(([name, field]) => (
                <div className={ambiguous.has(name) ? "field-row is-ambiguous" : "field-row"} role="row" key={name}>
                  <span>{name}</span>
                  <span>{formatValue(field.value)}</span>
                  <span>{field.source}</span>
                  <span>{field.confidence.toFixed(2)}</span>
                  <span>{field.source_span || "-"}</span>
                </div>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
