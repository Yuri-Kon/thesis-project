import type { TaskIntakeSession } from "../api/types";
import { SafetyPrecheckPanel } from "./SafetyPrecheckPanel";

interface IntakeConfirmPanelProps {
  intake: TaskIntakeSession | null;
  acknowledgedWarnings: string[];
  canConfirm: boolean;
  busy: boolean;
  onToggleWarning: (code: string) => void;
  onConfirm: () => void;
}

export function IntakeConfirmPanel({
  intake,
  acknowledgedWarnings,
  canConfirm,
  busy,
  onToggleWarning,
  onConfirm,
}: IntakeConfirmPanelProps) {
  const safety = intake?.safety_check;

  return (
    <aside className="task-builder-side">
      <SafetyPrecheckPanel
        action={safety?.action}
        risks={safety?.risk_flags ?? []}
        acknowledgedWarnings={acknowledgedWarnings}
        onToggleWarning={onToggleWarning}
      />
      <section className="panel">
        <div className="panel-header">
          <h2>Confirm</h2>
          <span className="pill">{intake?.status ?? "idle"}</span>
        </div>
        <dl className="kv compact-kv">
          <dt>Missing</dt>
          <dd>{intake?.missing_required_fields.length ?? 0}</dd>
          <dt>Ambiguous</dt>
          <dd>{intake?.ambiguous_fields.length ?? 0}</dd>
          <dt>Unmapped</dt>
          <dd>{intake?.unmapped_text.length ?? 0}</dd>
        </dl>
        <button type="button" className="primary-action" onClick={onConfirm} disabled={busy || !canConfirm}>
          Create Task
        </button>
      </section>
    </aside>
  );
}
