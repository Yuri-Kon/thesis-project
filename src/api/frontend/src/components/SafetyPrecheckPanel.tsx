import type { TaskIntakeSafetyRisk } from "../api/types";
import { identifierLabel } from "../utils/displayText";

interface SafetyPrecheckPanelProps {
  action?: "ok" | "warn" | "block";
  risks: TaskIntakeSafetyRisk[];
  acknowledgedWarnings: string[];
  onToggleWarning: (code: string) => void;
}

export function SafetyPrecheckPanel({
  action = "ok",
  risks,
  acknowledgedWarnings,
  onToggleWarning,
}: SafetyPrecheckPanelProps) {
  const tone = action === "block" ? "danger" : action === "warn" ? "warning" : "ok";

  return (
    <section className={`panel safety-card ${tone}`}>
      <div className="panel-header">
        <h2>安全预检查</h2>
        <span className="pill">{identifierLabel(action)}</span>
      </div>
      {risks.length ? (
        <div className="risk-list">
          {risks.map((risk) => (
            <label className="warning-ack" key={`${risk.level}-${risk.code}-${risk.message}`}>
              <input
                type="checkbox"
                checked={risk.level === "warn" && acknowledgedWarnings.includes(risk.code)}
                disabled={risk.level !== "warn"}
                onChange={() => onToggleWarning(risk.code)}
              />
              <span>
                <strong>{identifierLabel(risk.level)}</strong> {risk.code}: {risk.message}
              </span>
            </label>
          ))}
        </div>
      ) : (
        <p className="muted">未返回安全风险。</p>
      )}
    </section>
  );
}
