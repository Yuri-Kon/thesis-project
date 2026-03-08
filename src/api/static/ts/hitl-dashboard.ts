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

interface PendingActionLite {
  pending_action_id: string;
  action_type: PendingActionType;
  default_suggestion?: string | null;
  default_recommendation?: string | null;
}

interface PendingActionToolDisplay {
  tool_id: string | null;
  capability_id: string | null;
  io_type: string | null;
  adapter_mode: string | null;
  source: string;
  available: boolean;
  can_fallback: boolean;
  availability_hint: string;
}

interface PendingActionCandidateDisplay {
  rank: number;
  candidate_id: string;
  is_default: boolean;
  summary: string;
  explanation: string;
  recommendation_reason: string;
  risk_level?: string | null;
  cost_estimate?: string | null;
  overall_score?: number | null;
  score_breakdown?: Record<string, number>;
  tool: PendingActionToolDisplay;
}

interface PendingActionDetail {
  pending_action_id: string;
  task_id: string;
  action_type: PendingActionType;
  status: string;
  created_at: string;
  default_suggestion?: string | null;
  explanation: string;
  recommendation_summary: string;
  candidates: PendingActionCandidateDisplay[];
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
  pending_action?: PendingActionLite | null;
  safety_events?: unknown[];
  design_result?: DesignResult | null;
}

interface TaskTimelineEvent {
  event_type: string;
  summary: string;
  ts?: string | null;
}

const ALLOWED_CHOICES: Record<PendingActionType, DecisionChoice[]> = {
  plan_confirm: ["accept", "replan", "cancel"],
  patch_confirm: ["accept", "replan", "cancel"],
  replan_confirm: ["accept", "continue", "cancel"],
};

const state: {
  selectedTaskId: string | null;
  selectedPendingActionId: string | null;
  lastTaskStatus: string | null;
} = {
  selectedTaskId: null,
  selectedPendingActionId: null,
  lastTaskStatus: null,
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

function setDecisionProgress(message: string, isError = false): void {
  const node = byId<HTMLParagraphElement>("decision-progress");
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

function formatScore(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "-";
  }
  return value.toFixed(2);
}

function formatText(value: string | null | undefined): string {
  const normalized = value?.trim();
  return normalized ? normalized : "-";
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
      state.selectedPendingActionId = item.pending_action_id;
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

function renderTaskOverview(task: TaskRecord): void {
  const badge = byId<HTMLSpanElement>("task-state-badge");
  badge.textContent = `${task.status}${task.internal_status ? ` / ${task.internal_status}` : ""}`;
  badge.className = statusChipClass(task.status);

  const container = byId<HTMLDivElement>("task-detail");
  container.innerHTML = "";

  const idLine = document.createElement("p");
  idLine.textContent = `Task ID: ${task.id}`;
  container.appendChild(idLine);

  const goalLine = document.createElement("p");
  goalLine.textContent = `Goal: ${task.goal}`;
  container.appendChild(goalLine);

  if (task.pending_action) {
    const pendingLine = document.createElement("p");
    pendingLine.textContent =
      `PendingAction: ${task.pending_action.pending_action_id} (${task.pending_action.action_type})`;
    container.appendChild(pendingLine);
  } else {
    const pendingLine = document.createElement("p");
    pendingLine.textContent = "No pending action for this task.";
    container.appendChild(pendingLine);
  }

  const timelineLink = document.createElement("a");
  timelineLink.href = `/ui/tasks/${encodeURIComponent(task.id)}/events`;
  timelineLink.textContent = "Open event timeline";
  timelineLink.className = "timeline-link";
  container.appendChild(timelineLink);

  renderReservedSections(task);
}

function renderNoPendingAction(): void {
  state.selectedPendingActionId = null;
  byId<HTMLSpanElement>("candidate-count").textContent = "0";
  byId<HTMLParagraphElement>("recommendation-summary").textContent =
    "No pending action selected.";
  byId<HTMLDivElement>("candidate-compare-container").innerHTML =
    "<p>No candidate data for the selected task.</p>";
  byId<HTMLDivElement>("decision-form-container").innerHTML =
    "<p>No pending action for the selected task.</p>";
}

function renderCandidateComparison(detail: PendingActionDetail): void {
  const counter = byId<HTMLSpanElement>("candidate-count");
  counter.textContent = String(detail.candidates.length);

  byId<HTMLParagraphElement>("recommendation-summary").textContent =
    detail.recommendation_summary || detail.explanation;

  const container = byId<HTMLDivElement>("candidate-compare-container");
  container.innerHTML = "";

  if (!detail.candidates.length) {
    const empty = document.createElement("p");
    empty.textContent = "No candidates returned.";
    container.appendChild(empty);
    return;
  }

  const table = document.createElement("table");
  table.className = "candidate-table";

  const head = document.createElement("thead");
  const headRow = document.createElement("tr");
  for (const title of [
    "Rank",
    "Candidate",
    "Overall",
    "Risk",
    "Cost",
    "Tool",
    "Availability",
    "Reason",
    "Summary",
  ]) {
    const th = document.createElement("th");
    th.textContent = title;
    headRow.appendChild(th);
  }
  head.appendChild(headRow);
  table.appendChild(head);

  const body = document.createElement("tbody");
  for (const candidate of detail.candidates) {
    const row = document.createElement("tr");

    const rankCell = document.createElement("td");
    rankCell.textContent = String(candidate.rank);
    row.appendChild(rankCell);

    const idCell = document.createElement("td");
    idCell.textContent = candidate.candidate_id;
    if (candidate.is_default) {
      const badge = document.createElement("span");
      badge.className = "default-badge";
      badge.textContent = "default";
      idCell.appendChild(document.createTextNode(" "));
      idCell.appendChild(badge);
    }
    row.appendChild(idCell);

    const overallCell = document.createElement("td");
    overallCell.textContent = formatScore(candidate.overall_score);
    row.appendChild(overallCell);

    const riskCell = document.createElement("td");
    riskCell.textContent = formatText(candidate.risk_level);
    row.appendChild(riskCell);

    const costCell = document.createElement("td");
    costCell.textContent = formatText(candidate.cost_estimate);
    row.appendChild(costCell);

    const toolCell = document.createElement("td");
    toolCell.textContent = `${formatText(candidate.tool.tool_id)} / ${formatText(candidate.tool.capability_id)} / ${formatText(candidate.tool.io_type)} (${candidate.tool.source})`;
    row.appendChild(toolCell);

    const availabilityCell = document.createElement("td");
    const availability = candidate.tool.available ? "ready" : "degraded";
    const fallbackFlag = candidate.tool.can_fallback ? " fallback" : "";
    availabilityCell.textContent = `${availability}${fallbackFlag}`;
    availabilityCell.title = candidate.tool.availability_hint;
    row.appendChild(availabilityCell);

    const reasonCell = document.createElement("td");
    reasonCell.textContent = candidate.recommendation_reason;
    row.appendChild(reasonCell);

    const summaryCell = document.createElement("td");
    summaryCell.textContent = candidate.summary;
    row.appendChild(summaryCell);

    body.appendChild(row);
  }

  table.appendChild(body);
  container.appendChild(table);
}

function buildCandidateOptionLabel(candidate: PendingActionCandidateDisplay): string {
  const source = candidate.tool.source;
  return `${candidate.candidate_id} | #${candidate.rank} | risk=${formatText(candidate.risk_level)} | cost=${formatText(candidate.cost_estimate)} | ${source}`;
}

function renderDecisionForm(detail: PendingActionDetail): void {
  const container = byId<HTMLDivElement>("decision-form-container");
  container.innerHTML = "";

  if (!state.selectedTaskId || !detail.candidates.length) {
    container.innerHTML = "<p>No pending action for the selected task.</p>";
    return;
  }

  const allowed = ALLOWED_CHOICES[detail.action_type];
  const defaultSuggestion = detail.default_suggestion ?? "";

  const form = document.createElement("form");
  form.id = "decision-form";

  const choiceLabel = document.createElement("label");
  choiceLabel.htmlFor = "decision-choice";
  choiceLabel.textContent = "Choice";
  form.appendChild(choiceLabel);

  const choiceSelect = document.createElement("select");
  choiceSelect.id = "decision-choice";
  choiceSelect.name = "choice";
  for (const choice of allowed) {
    const option = document.createElement("option");
    option.value = choice;
    option.textContent = choice;
    choiceSelect.appendChild(option);
  }
  form.appendChild(choiceSelect);

  const candidateLabel = document.createElement("label");
  candidateLabel.htmlFor = "decision-candidate";
  candidateLabel.textContent = "Candidate (required for accept)";
  form.appendChild(candidateLabel);

  const candidateSelect = document.createElement("select");
  candidateSelect.id = "decision-candidate";
  candidateSelect.name = "candidate";
  const empty = document.createElement("option");
  empty.value = "";
  empty.textContent = "-- Select candidate --";
  candidateSelect.appendChild(empty);
  for (const candidate of detail.candidates) {
    const option = document.createElement("option");
    option.value = candidate.candidate_id;
    option.textContent = buildCandidateOptionLabel(candidate);
    if (candidate.candidate_id === defaultSuggestion) {
      option.selected = true;
    }
    candidateSelect.appendChild(option);
  }
  form.appendChild(candidateSelect);

  const byLabel = document.createElement("label");
  byLabel.htmlFor = "decision-by";
  byLabel.textContent = "Decided By";
  form.appendChild(byLabel);

  const decidedByInput = document.createElement("input");
  decidedByInput.id = "decision-by";
  decidedByInput.name = "decided_by";
  decidedByInput.type = "text";
  decidedByInput.value = "ui_user";
  form.appendChild(decidedByInput);

  const commentLabel = document.createElement("label");
  commentLabel.htmlFor = "decision-comment";
  commentLabel.textContent = "Comment";
  form.appendChild(commentLabel);

  const commentInput = document.createElement("textarea");
  commentInput.id = "decision-comment";
  commentInput.name = "comment";
  commentInput.rows = 3;
  commentInput.placeholder = "optional note";
  form.appendChild(commentInput);

  const submitButton = document.createElement("button");
  submitButton.type = "submit";
  submitButton.textContent = "Submit Decision";
  form.appendChild(submitButton);

  container.appendChild(form);

  const syncCandidateState = (): void => {
    const isAccept = choiceSelect.value === "accept";
    candidateSelect.disabled = !isAccept;
    if (!isAccept) {
      candidateSelect.value = "";
    }
  };

  syncCandidateState();
  choiceSelect.addEventListener("change", syncCandidateState);

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    void submitDecision();
  });
}

function findLatestEvent(
  events: TaskTimelineEvent[],
  eventType: string,
): TaskTimelineEvent | null {
  for (let index = events.length - 1; index >= 0; index -= 1) {
    if (events[index].event_type === eventType) {
      return events[index];
    }
  }
  return null;
}

async function refreshLatestProgress(
  taskId: string,
  previousStatus?: string | null,
  currentStatus?: string | null,
): Promise<void> {
  const lines: string[] = [];
  if (previousStatus && currentStatus && previousStatus !== currentStatus) {
    lines.push(`State updated: ${previousStatus} -> ${currentStatus}.`);
  }

  try {
    const events = await getJson<TaskTimelineEvent[]>(`/tasks/${taskId}/events`);
    const decisionEvent = findLatestEvent(events, "DECISION_APPLIED");
    const transitionEvent = findLatestEvent(events, "STATE_TRANSITION");

    if (decisionEvent) {
      lines.push(`Decision event: ${decisionEvent.summary}`);
    }
    if (transitionEvent) {
      lines.push(`Transition event: ${transitionEvent.summary}`);
    }

    if (!lines.length) {
      lines.push("No decision/state-transition events found yet.");
    }
    setDecisionProgress(lines.join(" "));
  } catch {
    if (lines.length) {
      setDecisionProgress(lines.join(" "));
      return;
    }
    setDecisionProgress("Event timeline is not available yet.");
  }
}

async function refreshPendingActionDetail(pendingActionId: string): Promise<void> {
  try {
    const detail = await getJson<PendingActionDetail>(
      `/pending-actions/${encodeURIComponent(pendingActionId)}`,
    );
    renderCandidateComparison(detail);
    renderDecisionForm(detail);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    byId<HTMLParagraphElement>("recommendation-summary").textContent = message;
    byId<HTMLDivElement>("candidate-compare-container").innerHTML =
      `<p class="error">${message}</p>`;
    byId<HTMLDivElement>("decision-form-container").innerHTML =
      "<p>No pending action for the selected task.</p>";
    setGlobalMessage(message, true);
  }
}

async function submitDecision(): Promise<void> {
  if (!state.selectedTaskId || !state.selectedPendingActionId) {
    setGlobalMessage("Task and pending action are required before submitting decision.", true);
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

  const previousStatus = state.lastTaskStatus;
  const response = await fetch(
    `/pending-actions/${encodeURIComponent(state.selectedPendingActionId)}/decision`,
    {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
    },
  );

  if (!response.ok) {
    const detail = await parseError(response);
    if (response.status === 409) {
      setGlobalMessage(`Decision conflict (409): ${detail}`, true);
    } else {
      setGlobalMessage(detail, true);
    }
    return;
  }

  const updatedTask = (await response.json()) as TaskRecord;
  state.lastTaskStatus = updatedTask.status;
  renderTaskOverview(updatedTask);

  if (updatedTask.pending_action) {
    state.selectedPendingActionId = updatedTask.pending_action.pending_action_id;
    await refreshPendingActionDetail(state.selectedPendingActionId);
  } else {
    renderNoPendingAction();
  }

  setGlobalMessage("Decision submitted. Pending list and state are refreshed.");
  await Promise.all([
    refreshPendingActions(),
    refreshLatestProgress(updatedTask.id, previousStatus, updatedTask.status),
  ]);
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
    const previousStatus = state.lastTaskStatus;
    state.lastTaskStatus = task.status;
    renderTaskOverview(task);

    if (task.pending_action) {
      state.selectedPendingActionId = task.pending_action.pending_action_id;
      await refreshPendingActionDetail(state.selectedPendingActionId);
    } else {
      renderNoPendingAction();
    }

    await refreshLatestProgress(task.id, previousStatus, task.status);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    byId<HTMLDivElement>("task-detail").innerHTML = `<p class="error">${message}</p>`;
    renderNoPendingAction();
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
      state.selectedPendingActionId = null;
      state.lastTaskStatus = null;
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

  renderNoPendingAction();
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
export {};
