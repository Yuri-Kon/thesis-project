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
      <input value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="任务 ID" />
      <button type="submit">加载</button>
      <button type="button" onClick={onRefresh}>刷新</button>
    </form>
  );
}
