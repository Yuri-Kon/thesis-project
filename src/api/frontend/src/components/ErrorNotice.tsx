interface ErrorNoticeProps {
  message: string;
}

export function ErrorNotice({ message }: ErrorNoticeProps) {
  return (
    <section className="notice error" role="alert">
      <strong>API error</strong>
      <span>{message}</span>
    </section>
  );
}
