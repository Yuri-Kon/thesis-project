import type { PendingActionDetail } from "../api/types";

interface TheoryObjectSummaryProps {
  detail: PendingActionDetail | null;
}

interface TheoryValue {
  value?: number;
  utility?: number;
  action?: string;
  source?: string;
  formula_version?: string;
  shadow_only?: boolean;
}

interface TheoryToken {
  key: string;
  label: string;
  value: string;
  tone?: "positive" | "negative" | "neutral";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function theoryValue(value: unknown): TheoryValue {
  if (!isRecord(value)) return {};
  const summary: TheoryValue = {};
  if (typeof value.value === "number" && Number.isFinite(value.value)) {
    summary.value = value.value;
  }
  if (typeof value.utility === "number" && Number.isFinite(value.utility)) {
    summary.utility = value.utility;
  }
  if (typeof value.action === "string") summary.action = value.action;
  if (typeof value.source === "string") summary.source = value.source;
  if (typeof value.formula_version === "string") {
    summary.formula_version = value.formula_version;
  }
  if (typeof value.shadow_only === "boolean") summary.shadow_only = value.shadow_only;
  return summary;
}

function numericValue(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (isRecord(value)) {
    const raw = value.value ?? value.utility;
    if (typeof raw === "number" && Number.isFinite(raw)) return raw;
  }
  return null;
}

function stringValue(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function formatScore(value: unknown, fallback = "-"): string {
  const numeric = numericValue(value);
  return numeric === null ? fallback : numeric.toFixed(2);
}

function formatDelta(value: unknown): string {
  const numeric = numericValue(value);
  if (numeric === null) return "-";
  return `${numeric >= 0 ? "+" : ""}${numeric.toFixed(2)}`;
}

function valueTone(value: unknown): TheoryToken["tone"] {
  const numeric = numericValue(value);
  if (numeric === null) return "neutral";
  if (numeric > 0) return "positive";
  if (numeric < 0) return "negative";
  return "neutral";
}

function selectedUtility(theory: Record<string, unknown>): string {
  const utility = theoryValue(theory.action_utility);
  const raw = utility.utility ?? utility.value;
  return typeof raw === "number" && Number.isFinite(raw) ? raw.toFixed(2) : "-";
}

export function TheoryObjectSummary({ detail }: TheoryObjectSummaryProps) {
  if (!detail) {
    return <p className="muted">No pending runtime explanation.</p>;
  }

  const theory = detail.theory_objects ?? {};
  const selectedAction = stringValue(theory.selected_action) ?? detail.action_type;
  const staticScore = theory.static_score ?? detail.score_breakdown?.overall;
  const runtimeAdjustment = theory.runtime_adjustment;
  const finalScore = theory.final_score ?? detail.score_breakdown?.overall;
  const runtimeSummary = detail.runtime_state_summary ?? {};

  const flow: TheoryToken[] = [
    { key: "static", label: "static_score", value: formatScore(staticScore) },
    {
      key: "runtime",
      label: "runtime_adjustment",
      value: formatDelta(runtimeAdjustment),
      tone: valueTone(runtimeAdjustment),
    },
    { key: "final", label: "final_score", value: formatScore(finalScore) },
    { key: "action", label: "selected_action", value: selectedAction },
  ];

  const support: TheoryToken[] = [
    {
      key: "utility",
      label: "action_utility",
      value: selectedUtility(theory),
    },
    {
      key: "evidence",
      label: "evidence_sufficiency",
      value: formatScore(theory.evidence_sufficiency ?? runtimeSummary.evidence_sufficiency),
    },
    {
      key: "budget",
      label: "budget_pressure",
      value: formatScore(theory.budget_pressure ?? runtimeSummary.budget_pressure),
    },
  ];

  return (
    <div className="theory-summary" aria-label="Core theory objects">
      <ol className="theory-flow">
        {flow.map((item, index) => (
          <li className="theory-flow__item" key={item.key}>
            <span className={`theory-token${item.tone ? ` ${item.tone}` : ""}`}>
              <span>{item.label}</span>
              <strong>{item.value}</strong>
            </span>
            {index < flow.length - 1 ? <span className="theory-arrow">→</span> : null}
          </li>
        ))}
      </ol>
      <div className="theory-support" aria-label="Supporting theory signals">
        {support.map((item) => (
          <span className="theory-support__item" key={item.key}>
            <span>{item.label}</span>
            <strong>{item.value}</strong>
          </span>
        ))}
      </div>
    </div>
  );
}
