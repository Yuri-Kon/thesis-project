function byId(id) {
    const node = document.getElementById(id);
    if (!node) {
        throw new Error(`Missing element: #${id}`);
    }
    return node;
}
function parseBootstrapTaskId() {
    const raw = byId("event-bootstrap").textContent;
    if (!raw) {
        return "";
    }
    try {
        const parsed = JSON.parse(raw);
        return parsed.taskId ?? "";
    }
    catch {
        return "";
    }
}
function setMessage(text, isError = false) {
    const node = byId("message");
    node.textContent = text;
    node.className = isError ? "error" : "muted";
}
function statusBadgeClass(status) {
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
async function parseError(response) {
    try {
        const payload = (await response.json());
        return payload.detail ?? `request failed: ${response.status}`;
    }
    catch {
        return `request failed: ${response.status}`;
    }
}
async function fetchJson(url) {
    const response = await fetch(url);
    if (!response.ok) {
        throw new Error(await parseError(response));
    }
    return (await response.json());
}
function renderTaskSummary(task) {
    const badge = byId("status-badge");
    badge.textContent = `${task.status}${task.internal_status ? ` / ${task.internal_status}` : ""}`;
    badge.className = statusBadgeClass(task.status);
    byId("task-summary").innerHTML = `
    <p><strong>Task ID:</strong> ${task.id}</p>
    <p><strong>Goal:</strong> ${task.goal}</p>
  `;
}
function renderTimeline(events) {
    const list = byId("timeline-list");
    const count = byId("event-count");
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
      <div class="event-meta">step: ${event.step_id ?? "-"} | tool: ${event.tool ?? "-"}</div>
    `;
        list.appendChild(item);
    }
}
function isWaitingEnter(event) {
    if (event.event_type === "WAITING_ENTER") {
        return true;
    }
    return (event.event_type === "STATE_TRANSITION" &&
        typeof event.to_status === "string" &&
        event.to_status.startsWith("WAITING_"));
}
function isWaitingExit(event) {
    if (event.event_type === "WAITING_EXIT") {
        return true;
    }
    return (event.event_type === "STATE_TRANSITION" &&
        typeof event.from_status === "string" &&
        event.from_status.startsWith("WAITING_") &&
        (!event.to_status || !event.to_status.startsWith("WAITING_")));
}
function renderChainSummary(events) {
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
            }
            else if (isWaitingEnter(event)) {
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
    const node = byId("chain-summary");
    if (chains > 0) {
        node.textContent = `Detected ${chains} WAITING -> decision -> resume chain(s).`;
        node.className = "muted";
        return;
    }
    node.textContent =
        "No complete WAITING -> decision -> resume chain detected yet.";
    node.className = "muted";
}
function updateUrl(taskId) {
    const nextPath = `/ui/tasks/${encodeURIComponent(taskId)}/events`;
    if (window.location.pathname !== nextPath) {
        window.history.replaceState(null, "", nextPath);
    }
}
async function loadTaskTimeline(taskId) {
    byId("task-id-input").value = taskId;
    updateUrl(taskId);
    const events = await fetchJson(`/tasks/${taskId}/events`);
    try {
        const task = await fetchJson(`/tasks/${taskId}`);
        renderTaskSummary(task);
    }
    catch {
        byId("status-badge").textContent = "Task record unavailable";
        byId("status-badge").className = "badge";
        byId("task-summary").innerHTML = `
      <p><strong>Task ID:</strong> ${taskId}</p>
      <p class="muted">Task detail not found in memory store, timeline is shown from log file.</p>
    `;
    }
    renderTimeline(events);
    renderChainSummary(events);
    setMessage("Timeline loaded.");
}
function bindEvents() {
    const form = byId("timeline-query-form");
    const refreshButton = byId("refresh-button");
    const input = byId("task-id-input");
    form.addEventListener("submit", (event) => {
        event.preventDefault();
        const taskId = input.value.trim();
        if (!taskId) {
            setMessage("task id is required.", true);
            return;
        }
        void loadTaskTimeline(taskId).catch((error) => {
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
        void loadTaskTimeline(taskId).catch((error) => {
            const message = error instanceof Error ? error.message : String(error);
            setMessage(message, true);
        });
    });
}
async function bootstrap() {
    bindEvents();
    const taskId = parseBootstrapTaskId();
    if (!taskId) {
        setMessage("Enter task id to load timeline.");
        return;
    }
    try {
        await loadTaskTimeline(taskId);
    }
    catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        setMessage(message, true);
    }
}
void bootstrap();
export {};
