type PendingActionType = "plan_confirm" | "patch_confirm" | "replan_confirm";
type DecisionChoice = "accept" | "replan" | "continue" | "cancel";

interface PendingActionSummary {
  pending_action_id: string;
  task_id: string;
  action_type: PendingActionType;
  status: string;
  created_at: string;
  candidate_count: number;
  default_suggestion: string | null;
  explanation: string;
  summary: string;
}

interface PendingActionCandidate {
  candidate_id: string;
  summary?: string | null;
  explanation?: string | null;
  risk_level?: string | null;
  cost_estimate?: string | null;
  score_breakdown?: Record<string, number>;
}

interface PendingAction {
  pending_action_id: string;
  action_type: PendingActionType;
  default_suggestion?: string | null;
  default_recommendation?: string | null;
  explanation: string;
  candidates: PendingActionCandidate[];
}

interface DesignResult {
  report_path?: string | null;
  scores?: Record<string, number>;
}

interface TaskRecord {
  id: string;
  status: string;
  internal_status?: string | null;
  goal: string;
  pending_action?: PendingAction | null;
  safety_events?: unknown[];
  design_result?: DesignResult | null;
}

const ALLOWED_CHOICES: Record<PendingActionType, DecisionChoice[]> = {
  plan_confirm: ["accept", "replan", "cancel"],
  patch_confirm: ["accept", "replan", "cancel"],
  replan_confirm: ["accept", "continue", "cancel"],
};

const state: { selectedTaskId: string | null } = {
  selectedTaskId: null,
};

function byId<T extends HTMLElement>(id: string): T {
  const element = document.getElementById(id);
  if (!element) {
    throw new Error(`Missing element: #${id}`);
  }
  return element as T;
}

function formatActionType(actionType: PendingActionType): string {
  return actionType.replace("_", " ").toUpperCase();
}

function parseBootstrapTaskId(): string {
  const raw = byId<HTMLScriptElement>("app-bootstrap").textContent;
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

function setGlobalMessage(message: string, isError = false): void {
  const node = byId<HTMLParagraphElement>("global-message");
  node.textContent = message;
  node.className = isError ? "error" : "muted";
}

function statusChipClass(status: string): string {
  if (status.startsWith("WAITING_")) {
    return "chip waiting";
  }
  if (status === "DONE") {
    return "chip done";
  }
  if (status === "RUNNING" || status === "PLANNING" || status === "PLANNED") {
    return "chip active";
  }
  return "chip muted";
}

async function parseError(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string };
    return payload.detail ?? `Request failed: ${response.status}`;
  } catch {
    return `Request failed: ${response.status}`;
  }
}

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return (await response.json()) as T;
}

function renderPendingActions(items: PendingActionSummary[]): void {
  const tbody = byId<HTMLTableSectionElement>("pending-actions-body");
  const counter = byId<HTMLSpanElement>("pending-count");
  counter.textContent = String(items.length);
  tbody.innerHTML = "";

  if (!items.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 6;
    cell.textContent = "No pending actions.";
    row.appendChild(cell);
    tbody.appendChild(row);
    return;
  }

  for (const item of items) {
    const row = document.createElement("tr");

    const openCell = document.createElement("td");
    const openButton = document.createElement("button");
    openButton.type = "button";
    openButton.className = "row-action";
    openButton.textContent = "Open";
    openButton.addEventListener("click", () => {
      state.selectedTaskId = item.task_id;
      byId<HTMLInputElement>("task-id-input").value = item.task_id;
      updateUrlForTask(item.task_id);
      void refreshTaskDetail();
    });
    openCell.appendChild(openButton);
    row.appendChild(openCell);

    const taskCell = document.createElement("td");
    taskCell.textContent = item.task_id;
    row.appendChild(taskCell);

    const typeCell = document.createElement("td");
    typeCell.textContent = formatActionType(item.action_type);
    row.appendChild(typeCell);

    const candidateCell = document.createElement("td");
    candidateCell.textContent = String(item.candidate_count);
    row.appendChild(candidateCell);

    const defaultCell = document.createElement("td");
    defaultCell.textContent = item.default_suggestion ?? "-";
    row.appendChild(defaultCell);

    const summaryCell = document.createElement("td");
    summaryCell.textContent = item.summary || item.explanation;
    row.appendChild(summaryCell);

    tbody.appendChild(row);
  }
}

function renderReservedSections(task: TaskRecord): void {
  const safetyCount = task.safety_events?.length ?? 0;
  byId<HTMLParagraphElement>("reserved-safety").textContent =
    safetyCount > 0
      ? `Safety events: ${safetyCount} (details can be expanded later).`
      : "No safety events yet. Area reserved for event cards.";

  const reportPath = task.design_result?.report_path ?? "";
  byId<HTMLParagraphElement>("reserved-report").textContent = reportPath
    ? `Report path: ${reportPath}`
    : "No report yet. Area reserved for report preview.";

  byId<HTMLParagraphElement>("reserved-steps").textContent =
    "Step timeline area reserved for future execution details.";
}

function renderTaskDetail(task: TaskRecord): void {
  const badge = byId<HTMLSpanElement>("task-state-badge");
  badge.textContent = `${task.status}${task.internal_status ? ` / ${task.internal_status}` : ""}`;
  badge.className = statusChipClass(task.status);

  const container = byId<HTMLDivElement>("task-detail");
  const pending = task.pending_action;
  const lines: string[] = [
    `<p><strong>Task ID:</strong> ${task.id}</p>`,
    `<p><strong>Goal:</strong> ${task.goal}</p>`,
  ];

  if (pending) {
    const defaultSuggestion =
      pending.default_suggestion ?? pending.default_recommendation ?? "-";
    lines.push(`<p><strong>Action Type:</strong> ${pending.action_type}</p>`);
    lines.push(`<p><strong>Default Suggestion:</strong> ${defaultSuggestion}</p>`);
    lines.push(`<p><strong>Explanation:</strong> ${pending.explanation}</p>`);

    const candidateLines = pending.candidates.map((candidate) => {
      const risk = candidate.risk_level ?? "-";
      const cost = candidate.cost_estimate ?? "-";
      const summary = candidate.summary ?? candidate.explanation ?? "No summary";
      return `<li><strong>${candidate.candidate_id}</strong> | risk=${risk} | cost=${cost}<br/>${summary}</li>`;
    });
    lines.push(`<ul class="candidate-list">${candidateLines.join("")}</ul>`);
  } else {
    lines.push("<p>No pending action for this task.</p>");
  }

  container.innerHTML = lines.join("");
  renderReservedSections(task);
  renderDecisionForm(pending ?? null);
}

function renderDecisionForm(pendingAction: PendingAction | null): void {
  const container = byId<HTMLDivElement>("decision-form-container");
  container.innerHTML = "";

  if (!pendingAction || !state.selectedTaskId) {
    container.innerHTML = "<p>No pending action for the selected task.</p>";
    return;
  }

  const allowed = ALLOWED_CHOICES[pendingAction.action_type];
  const defaultSuggestion =
    pendingAction.default_suggestion ?? pendingAction.default_recommendation ?? "";

  const form = document.createElement("form");
  form.id = "decision-form";
  form.innerHTML = `
    <label for="decision-choice">Choice</label>
    <select id="decision-choice" name="choice">
      ${allowed.map((choice) => `<option value="${choice}">${choice}</option>`).join("")}
    </select>
    <label for="decision-candidate">Candidate (required for accept)</label>
    <select id="decision-candidate" name="candidate">
      <option value="">-- Select candidate --</option>
      ${pendingAction.candidates
        .map((candidate) => {
          const selected = candidate.candidate_id === defaultSuggestion ? " selected" : "";
          return `<option value="${candidate.candidate_id}"${selected}>${candidate.candidate_id}</option>`;
        })
        .join("")}
    </select>
    <label for="decision-by">Decided By</label>
    <input id="decision-by" name="decided_by" type="text" value="ui_user" />
    <label for="decision-comment">Comment</label>
    <textarea id="decision-comment" name="comment" rows="3" placeholder="optional note"></textarea>
    <button type="submit">Submit Decision</button>
  `;

  container.appendChild(form);

  const choiceNode = byId<HTMLSelectElement>("decision-choice");
  const candidateNode = byId<HTMLSelectElement>("decision-candidate");

  const syncCandidateState = (): void => {
    const isAccept = choiceNode.value === "accept";
    candidateNode.disabled = !isAccept;
    if (!isAccept) {
      candidateNode.value = "";
    }
  };

  syncCandidateState();
  choiceNode.addEventListener("change", syncCandidateState);

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    void submitDecision(pendingAction.pending_action_id);
  });
}

async function submitDecision(pendingActionId: string): Promise<void> {
  if (!state.selectedTaskId) {
    setGlobalMessage("Task id is required before submitting decision.", true);
    return;
  }

  const choiceNode = byId<HTMLSelectElement>("decision-choice");
  const candidateNode = byId<HTMLSelectElement>("decision-candidate");
  const decidedByNode = byId<HTMLInputElement>("decision-by");
  const commentNode = byId<HTMLTextAreaElement>("decision-comment");

  const choice = choiceNode.value as DecisionChoice;
  const selectedCandidate = candidateNode.value.trim();
  if (choice === "accept" && !selectedCandidate) {
    setGlobalMessage("accept requires selected candidate id.", true);
    return;
  }

  const payload: {
    choice: DecisionChoice;
    selected_candidate_id?: string;
    decided_by: string;
    comment?: string;
  } = {
    choice,
    decided_by: decidedByNode.value.trim() || "ui_user",
  };
  if (choice === "accept") {
    payload.selected_candidate_id = selectedCandidate;
  }
  if (commentNode.value.trim()) {
    payload.comment = commentNode.value.trim();
  }

  const response = await fetch(`/pending-actions/${pendingActionId}/decision`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const detail = await parseError(response);
    if (response.status === 409) {
      setGlobalMessage(`Decision conflict (409): ${detail}`, true);
    } else {
      setGlobalMessage(detail, true);
    }
    return;
  }

  setGlobalMessage("Decision submitted. Refreshing task state.");
  await Promise.all([refreshPendingActions(), refreshTaskDetail()]);
}

async function refreshPendingActions(): Promise<void> {
  try {
    const records = await getJson<PendingActionSummary[]>("/pending-actions");
    renderPendingActions(records);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    setGlobalMessage(message, true);
  }
}

async function refreshTaskDetail(): Promise<void> {
  const taskId = state.selectedTaskId;
  if (!taskId) {
    return;
  }

  try {
    const task = await getJson<TaskRecord>(`/tasks/${taskId}`);
    renderTaskDetail(task);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    byId<HTMLDivElement>("task-detail").innerHTML = `<p class="error">${message}</p>`;
    byId<HTMLDivElement>("decision-form-container").innerHTML =
      "<p>No pending action for the selected task.</p>";
    setGlobalMessage(message, true);
  }
}

function updateUrlForTask(taskId: string): void {
  if (window.location.pathname === `/ui/tasks/${taskId}`) {
    return;
  }
  window.history.replaceState(null, "", `/ui/tasks/${encodeURIComponent(taskId)}`);
}

function bindEvents(): void {
  const form = byId<HTMLFormElement>("task-query-form");
  const refreshButton = byId<HTMLButtonElement>("refresh-button");
  const input = byId<HTMLInputElement>("task-id-input");

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const taskId = input.value.trim();
    if (!taskId) {
      setGlobalMessage("Task id is empty. Showing pending actions only.");
      state.selectedTaskId = null;
      return;
    }
    state.selectedTaskId = taskId;
    updateUrlForTask(taskId);
    void refreshTaskDetail();
  });

  refreshButton.addEventListener("click", () => {
    void refreshPendingActions();
    if (state.selectedTaskId) {
      void refreshTaskDetail();
    }
  });
}

async function bootstrap(): Promise<void> {
  bindEvents();

  const taskIdFromPath = parseBootstrapTaskId();
  if (taskIdFromPath) {
    state.selectedTaskId = taskIdFromPath;
    byId<HTMLInputElement>("task-id-input").value = taskIdFromPath;
  }

  await refreshPendingActions();
  if (state.selectedTaskId) {
    await refreshTaskDetail();
  }

  window.setInterval(() => {
    void refreshPendingActions();
    if (state.selectedTaskId) {
      void refreshTaskDetail();
    }
  }, 5000);
}

void bootstrap();
