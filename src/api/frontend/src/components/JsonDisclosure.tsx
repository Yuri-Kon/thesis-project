interface JsonDisclosureProps {
  title: string;
  value: unknown;
  defaultOpen?: boolean;
}

export function JsonDisclosure({ title, value, defaultOpen = false }: JsonDisclosureProps) {
  return (
    <details className="json-disclosure" open={defaultOpen}>
      <summary>{title}</summary>
      <pre>{JSON.stringify(value ?? {}, null, 2)}</pre>
    </details>
  );
}
