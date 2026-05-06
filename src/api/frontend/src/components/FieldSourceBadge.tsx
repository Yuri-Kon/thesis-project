interface FieldSourceBadgeProps {
  source: string;
  confidence?: number;
  warning?: boolean;
}

function sourceLabel(source: string): string {
  const labels: Record<string, string> = {
    user_explicit: "user",
    llm_extract: "extract",
    system_default: "default",
    kg_derived: "kg",
    user_modified: "edited",
  };
  return labels[source] ?? source;
}

export function FieldSourceBadge({ source, confidence, warning = false }: FieldSourceBadgeProps) {
  const confidenceLabel = typeof confidence === "number" ? ` ${Math.round(confidence * 100)}%` : "";
  return (
    <span className={warning ? "source-chip warning" : "source-chip"}>
      {sourceLabel(source)}
      {confidenceLabel}
    </span>
  );
}
