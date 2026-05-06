interface StatusBadgeProps {
  value?: string | null;
}

export function StatusBadge({ value }: StatusBadgeProps) {
  const normalized = value ?? "UNKNOWN";
  return <span className={`status-badge status-${normalized.toLowerCase()}`}>{normalized}</span>;
}
