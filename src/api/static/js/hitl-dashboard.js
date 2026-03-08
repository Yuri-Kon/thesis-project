const ALLOWED_CHOICES = {
    plan_confirm: ["accept", "replan", "cancel"],
    patch_confirm: ["accept", "replan", "cancel"],
    replan_confirm: ["accept", "continue", "cancel"],
};
const state = {
    selectedTaskId: null,
};
function byId(id) {
    const element = document.getElementById(id);
    if (!element) {
        throw new Error(`Missing element: #${id}`);
    }
    return element;
}
function formatActionType(actionType) {
    return actionType.replace("_", " ").toUpperCase();
}
function parseBootstrapTaskId() {
    const raw = byId("app-bootstrap").textContent;
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
function setGlobalMessage(message, isError = false) {
    const node = byId("global-message");
    node.textContent = message;
    node.className = isError ? "error" : "muted";
}
function statusChipClass(status) {
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
async function parseError(response) {
    try {
        const payload = (await response.json());
        return payload.detail ?? `Request failed: ${response.status}`;
    }
    catch {
        return `Request failed: ${response.status}`;
    }
}
async function getJson(url) {
    const response = await fetch(url);
    if (!response.ok) {
        throw new Error(await parseError(response));
    }
    return (await response.json());
}
function renderPendingActions(items) {
    const tbody = byId("pending-actions-body");
    const counter = byId("pending-count");
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
            byId("task-id-input").value = item.task_id;
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
function renderReservedSections(task) {
    const safetyCount = task.safety_events?.length ?? 0;
    byId("reserved-safety").textContent =
        safetyCount > 0
            ? `Safety events: ${safetyCount} (details can be expanded later).`
            : "No safety events yet. Area reserved for event cards.";
    const reportPath = task.design_result?.report_path ?? "";
    byId("reserved-report").textContent = reportPath
        ? `Report path: ${reportPath}`
        : "No report yet. Area reserved for report preview.";
    byId("reserved-steps").textContent =
        "Step timeline area reserved for future execution details.";
}
function renderTaskDetail(task) {
    const badge = byId("task-state-badge");
    badge.textContent = `${task.status}${task.internal_status ? ` / ${task.internal_status}` : ""}`;
    badge.className = statusChipClass(task.status);
    const container = byId("task-detail");
    const pending = task.pending_action;
    const lines = [
        `<p><strong>Task ID:</strong> ${task.id}</p>`,
        `<p><strong>Goal:</strong> ${task.goal}</p>`,
    ];
    if (pending) {
        const defaultSuggestion = pending.default_suggestion ?? pending.default_recommendation ?? "-";
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
    }
    else {
        lines.push("<p>No pending action for this task.</p>");
    }
    container.innerHTML = lines.join("");
    renderReservedSections(task);
    renderDecisionForm(pending ?? null);
}
function renderDecisionForm(pendingAction) {
    const container = byId("decision-form-container");
    container.innerHTML = "";
    if (!pendingAction || !state.selectedTaskId) {
        container.innerHTML = "<p>No pending action for the selected task.</p>";
        return;
    }
    const allowed = ALLOWED_CHOICES[pendingAction.action_type];
    const defaultSuggestion = pendingAction.default_suggestion ?? pendingAction.default_recommendation ?? "";
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
    const choiceNode = byId("decision-choice");
    const candidateNode = byId("decision-candidate");
    const syncCandidateState = () => {
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
async function submitDecision(pendingActionId) {
    if (!state.selectedTaskId) {
        setGlobalMessage("Task id is required before submitting decision.", true);
        return;
    }
    const choiceNode = byId("decision-choice");
    const candidateNode = byId("decision-candidate");
    const decidedByNode = byId("decision-by");
    const commentNode = byId("decision-comment");
    const choice = choiceNode.value;
    const selectedCandidate = candidateNode.value.trim();
    if (choice === "accept" && !selectedCandidate) {
        setGlobalMessage("accept requires selected candidate id.", true);
        return;
    }
    const payload = {
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
        }
        else {
            setGlobalMessage(detail, true);
        }
        return;
    }
    setGlobalMessage("Decision submitted. Refreshing task state.");
    await Promise.all([refreshPendingActions(), refreshTaskDetail()]);
}
async function refreshPendingActions() {
    try {
        const records = await getJson("/pending-actions");
        renderPendingActions(records);
    }
    catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        setGlobalMessage(message, true);
    }
}
async function refreshTaskDetail() {
    const taskId = state.selectedTaskId;
    if (!taskId) {
        return;
    }
    try {
        const task = await getJson(`/tasks/${taskId}`);
        renderTaskDetail(task);
    }
    catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        byId("task-detail").innerHTML = `<p class="error">${message}</p>`;
        byId("decision-form-container").innerHTML =
            "<p>No pending action for the selected task.</p>";
        setGlobalMessage(message, true);
    }
}
function updateUrlForTask(taskId) {
    if (window.location.pathname === `/ui/tasks/${taskId}`) {
        return;
    }
    window.history.replaceState(null, "", `/ui/tasks/${encodeURIComponent(taskId)}`);
}
function bindEvents() {
    const form = byId("task-query-form");
    const refreshButton = byId("refresh-button");
    const input = byId("task-id-input");
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
async function bootstrap() {
    bindEvents();
    const taskIdFromPath = parseBootstrapTaskId();
    if (taskIdFromPath) {
        state.selectedTaskId = taskIdFromPath;
        byId("task-id-input").value = taskIdFromPath;
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
export {};
