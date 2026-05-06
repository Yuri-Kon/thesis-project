import { FormEvent, useState } from "react";

interface TaskSearchProps {
  taskId: string;
  onTaskIdChange: (taskId: string) => void;
  onSubmit: (taskId: string) => void;
  onRefresh: () => void;
}

export function TaskSearch({ taskId, onTaskIdChange, onSubmit, onRefresh }: TaskSearchProps) {
  const [draft, setDraft] = useState(taskId);

  function submit(event: FormEvent) {
    event.preventDefault();
    const nextTaskId = draft.trim();
    onTaskIdChange(nextTaskId);
    onSubmit(nextTaskId);
  }

  return (
    <form className="task-search" onSubmit={submit}>
      <input value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="task_id" />
      <button type="submit">Load</button>
      <button type="button" onClick={onRefresh}>Refresh</button>
    </form>
  );
}
