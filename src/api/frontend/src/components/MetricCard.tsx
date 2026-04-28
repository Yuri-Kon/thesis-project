interface MetricCardProps {
  label: string;
  value: string | number;
  detail?: string;
  tone?: "neutral" | "blue" | "green" | "amber" | "red";
}

export function MetricCard({ label, value, detail, tone = "neutral" }: MetricCardProps) {
  return (
    <article className={`metric-card ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      {detail ? <p>{detail}</p> : null}
    </article>
  );
}
