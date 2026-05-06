interface ClarificationCardProps {
  title: string;
  items: string[];
  tone?: "warning" | "danger" | "neutral";
}

export function ClarificationCard({ title, items, tone = "neutral" }: ClarificationCardProps) {
  return (
    <article className={`clarification-card ${tone}`}>
      <header>
        <strong>{title}</strong>
        <span className="counter">{items.length}</span>
      </header>
      {items.length ? (
        <ul>
          {items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : (
        <p className="muted">Clear</p>
      )}
    </article>
  );
}
