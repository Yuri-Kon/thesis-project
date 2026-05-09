import { identifierLabel } from "../utils/displayText";

interface FieldSourceBadgeProps {
  source: string;
  confidence?: number;
  warning?: boolean;
}

function sourceLabel(source: string): string {
  return identifierLabel(source);
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
