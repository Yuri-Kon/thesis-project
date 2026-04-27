interface TaskRecord {
  id: string;
  goal: string;
  status: string;
  internal_status?: string | null;
}

interface TaskTimelineEvent {
  seq: number;
  task_id: string;
  ts: string | null;
  event_type: string;
  source_event?: string | null;
  pending_action_id?: string | null;
  decision_id?: string | null;
  step_id?: string | null;
  tool?: string | null;
  tool_id?: string | null;
  adapter_id?: string | null;
  execution_mode?: string | null;
  provider?: string | null;
  endpoint_type?: string | null;
  remote_job_id?: string | null;
  failure_code?: string | null;
  recovery_hint?: string | null;
  status?: string | null;
  from_status?: string | null;
  to_status?: string | null;
  actor_type?: string | null;
  summary: string;
  highlight: boolean;
  data: Record<string, unknown>;
  payload: Record<string, unknown>;
}

function byId<T extends HTMLElement>(id: string): T {
  const node = document.getElementById(id);
  if (!node) {
    throw new Error(`Missing element: #${id}`);
  }
  return node as T;
}

function parseBootstrapTaskId(): string {
  const raw = byId<HTMLScriptElement>("event-bootstrap").textContent;
  if (!raw) {
    return "";
  }
  try {
    const parsed = JSON.parse(raw) as { taskId?: string };
    return parsed.taskId ?? "";
  } catch {
    return "";
  }
}

function setMessage(text: string, isError = false): void {
  const node = byId<HTMLParagraphElement>("message");
  node.textContent = text;
  node.className = isError ? "error" : "muted";
}

function statusBadgeClass(status: string): string {
  if (status.startsWith("WAITING_")) {
    return "badge waiting";
  }
  if (status === "RUNNING" || status === "PLANNING" || status === "PLANNED") {
    return "badge running";
  }
  if (status === "DONE") {
    return "badge done";
  }
  return "badge";
}

async function parseError(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string };
    return payload.detail ?? `request failed: ${response.status}`;
  } catch {
    return `request failed: ${response.status}`;
  }
}

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return (await response.json()) as T;
}

function renderTaskSummary(task: TaskRecord): void {
  const badge = byId<HTMLSpanElement>("status-badge");
  badge.textContent = `${task.status}${task.internal_status ? ` / ${task.internal_status}` : ""}`;
  badge.className = statusBadgeClass(task.status);
  byId<HTMLDivElement>("task-summary").innerHTML = `
    <p><strong>Task ID:</strong> ${task.id}</p>
    <p><strong>Goal:</strong> ${task.goal}</p>
  `;
}

function renderTimeline(events: TaskTimelineEvent[]): void {
  const list = byId<HTMLOListElement>("timeline-list");
  const count = byId<HTMLSpanElement>("event-count");
  count.textContent = String(events.length);
  list.innerHTML = "";

  if (!events.length) {
    list.innerHTML = "<li class=\"timeline-item\">No events found.</li>";
    return;
  }

  for (const event of events) {
    const item = document.createElement("li");
    item.className = event.highlight ? "timeline-item highlight" : "timeline-item";
    const ts = event.ts ?? "-";
    const stateInfo = event.from_status || event.to_status
      ? `${event.from_status ?? "?"} -> ${event.to_status ?? "?"}`
      : event.status ?? "-";
    item.innerHTML = `
      <div class="event-title">
        <span>${event.event_type}</span>
        <span>${ts}</span>
      </div>
      <div class="event-meta">${event.summary}</div>
      <div class="event-meta">state: ${stateInfo}</div>
      <div class="event-meta">
        step: ${event.step_id ?? "-"} |
        tool: ${event.tool_id ?? event.tool ?? "-"} |
        adapter: ${event.adapter_id ?? "-"} |
        execution: ${event.execution_mode ?? "-"}
      </div>
      <div class="event-meta">
        provider: ${event.provider ?? "-"} |
        endpoint: ${event.endpoint_type ?? "-"} |
        remote job: ${event.remote_job_id ?? "-"} |
        failure: ${event.failure_code ?? "-"} |
        recovery: ${event.recovery_hint ?? "-"}
      </div>
    `;
    list.appendChild(item);
  }
}

function isWaitingEnter(event: TaskTimelineEvent): boolean {
  if (event.event_type === "WAITING_ENTER") {
    return true;
  }
  return (
    event.event_type === "STATE_TRANSITION" &&
    typeof event.to_status === "string" &&
    event.to_status.startsWith("WAITING_")
  );
}

function isWaitingExit(event: TaskTimelineEvent): boolean {
  if (event.event_type === "WAITING_EXIT") {
    return true;
  }
  return (
    event.event_type === "STATE_TRANSITION" &&
    typeof event.from_status === "string" &&
    event.from_status.startsWith("WAITING_") &&
    (!event.to_status || !event.to_status.startsWith("WAITING_"))
  );
}

function renderChainSummary(events: TaskTimelineEvent[]): void {
  let stage = 0;
  let chains = 0;
  for (const event of events) {
    if (stage === 0) {
      if (isWaitingEnter(event)) {
        stage = 1;
      }
      continue;
    }
    if (stage === 1) {
      if (event.event_type === "DECISION_APPLIED") {
        stage = 2;
      } else if (isWaitingEnter(event)) {
        stage = 1;
      }
      continue;
    }
    if (stage === 2) {
      if (isWaitingExit(event)) {
        chains += 1;
        stage = 0;
      }
      continue;
    }
  }

  const node = byId<HTMLParagraphElement>("chain-summary");
  if (chains > 0) {
    node.textContent = `Detected ${chains} WAITING -> decision -> resume chain(s).`;
    node.className = "muted";
    return;
  }

  node.textContent =
    "No complete WAITING -> decision -> resume chain detected yet.";
  node.className = "muted";
}

function updateUrl(taskId: string): void {
  const nextPath = `/ui/tasks/${encodeURIComponent(taskId)}/events`;
  if (window.location.pathname !== nextPath) {
    window.history.replaceState(null, "", nextPath);
  }
}

async function loadTaskTimeline(taskId: string): Promise<void> {
  byId<HTMLInputElement>("task-id-input").value = taskId;
  updateUrl(taskId);

  const events = await fetchJson<TaskTimelineEvent[]>(`/tasks/${taskId}/events`);
  try {
    const task = await fetchJson<TaskRecord>(`/tasks/${taskId}`);
    renderTaskSummary(task);
  } catch {
    byId<HTMLSpanElement>("status-badge").textContent = "Task record unavailable";
    byId<HTMLSpanElement>("status-badge").className = "badge";
    byId<HTMLDivElement>("task-summary").innerHTML = `
      <p><strong>Task ID:</strong> ${taskId}</p>
      <p class="muted">Task detail not found in memory store, timeline is shown from log file.</p>
    `;
  }
  renderTimeline(events);
  renderChainSummary(events);
  setMessage("Timeline loaded.");
}

function bindEvents(): void {
  const form = byId<HTMLFormElement>("timeline-query-form");
  const refreshButton = byId<HTMLButtonElement>("refresh-button");
  const input = byId<HTMLInputElement>("task-id-input");

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const taskId = input.value.trim();
    if (!taskId) {
      setMessage("task id is required.", true);
      return;
    }
    void loadTaskTimeline(taskId).catch((error: unknown) => {
      const message = error instanceof Error ? error.message : String(error);
      setMessage(message, true);
    });
  });

  refreshButton.addEventListener("click", () => {
    const taskId = input.value.trim();
    if (!taskId) {
      setMessage("task id is required.", true);
      return;
    }
    void loadTaskTimeline(taskId).catch((error: unknown) => {
      const message = error instanceof Error ? error.message : String(error);
      setMessage(message, true);
    });
  });
}

async function bootstrap(): Promise<void> {
  bindEvents();
  const taskId = parseBootstrapTaskId();
  if (!taskId) {
    setMessage("Enter task id to load timeline.");
    return;
  }

  try {
    await loadTaskTimeline(taskId);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    setMessage(message, true);
  }
}

void bootstrap();
export {};
