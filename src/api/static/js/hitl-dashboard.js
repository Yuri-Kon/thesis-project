const ALLOWED_CHOICES = {
    plan_confirm: ["accept", "replan", "cancel"],
    patch_confirm: ["accept", "replan", "cancel"],
    replan_confirm: ["accept", "continue", "cancel"],
};
const state = {
    selectedTaskId: null,
    selectedPendingActionId: null,
    lastTaskStatus: null,
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
function setDecisionProgress(message, isError = false) {
    const node = byId("decision-progress");
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
function readinessChipClass(status) {
    if (status === "ready") {
        return "chip done";
    }
    if (status === "degraded") {
        return "chip waiting";
    }
    if (status === "unavailable") {
        return "chip error-chip";
    }
    return "chip muted";
}
function formatScore(value) {
    if (typeof value !== "number" || Number.isNaN(value)) {
        return "-";
    }
    return value.toFixed(2);
}
function formatText(value) {
    const normalized = value?.trim();
    return normalized ? normalized : "-";
}
const MODEL_INVOCATION_CAPABILITIES = new Set([
    "sequence_generation",
    "sequence_design",
    "structure_prediction",
    "objective_scoring",
]);
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
            state.selectedPendingActionId = item.pending_action_id;
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
function renderCapabilityReadiness(items) {
    const tbody = byId("capability-readiness-body");
    tbody.innerHTML = "";
    if (!items.length) {
        const row = document.createElement("tr");
        const cell = document.createElement("td");
        cell.colSpan = 5;
        cell.textContent = "No capability readiness data.";
        row.appendChild(cell);
        tbody.appendChild(row);
        return;
    }
    for (const item of items) {
        const row = document.createElement("tr");
        const capabilityCell = document.createElement("td");
        capabilityCell.textContent = item.capability_id;
        row.appendChild(capabilityCell);
        const statusCell = document.createElement("td");
        const chip = document.createElement("span");
        chip.className = readinessChipClass(item.status);
        chip.textContent = item.status;
        statusCell.appendChild(chip);
        row.appendChild(statusCell);
        const toolCell = document.createElement("td");
        const fallback = item.fallback_tool_ids?.length
            ? ` fallback=${item.fallback_tool_ids.join(",")}`
            : "";
        toolCell.textContent = `${formatText(item.primary_tool_id)}${fallback}`;
        row.appendChild(toolCell);
        const reasonCell = document.createElement("td");
        reasonCell.textContent = item.degraded_reasons?.length
            ? item.degraded_reasons.join(" | ")
            : item.reason;
        row.appendChild(reasonCell);
        const recoveryCell = document.createElement("td");
        recoveryCell.textContent = formatText(item.suggested_recovery);
        row.appendChild(recoveryCell);
        tbody.appendChild(row);
    }
}
function renderModelInvocation(items) {
    const tbody = byId("model-invocation-body");
    tbody.innerHTML = "";
    const modelItems = items.filter((item) => MODEL_INVOCATION_CAPABILITIES.has(item.capability_id) ||
        Boolean(item.primary_tool_id));
    if (!modelItems.length) {
        const row = document.createElement("tr");
        const cell = document.createElement("td");
        cell.colSpan = 5;
        cell.textContent = "No model invocation readiness data.";
        row.appendChild(cell);
        tbody.appendChild(row);
        return;
    }
    for (const item of modelItems) {
        const row = document.createElement("tr");
        const capabilityCell = document.createElement("td");
        capabilityCell.textContent = item.capability_id;
        row.appendChild(capabilityCell);
        const statusCell = document.createElement("td");
        const chip = document.createElement("span");
        chip.className = readinessChipClass(item.status);
        chip.textContent = item.status;
        statusCell.appendChild(chip);
        row.appendChild(statusCell);
        const toolCell = document.createElement("td");
        const fallback = item.fallback_tool_ids?.length
            ? ` fallback=${item.fallback_tool_ids.join(",")}`
            : "";
        toolCell.textContent = `${formatText(item.primary_tool_id)}${fallback}`;
        row.appendChild(toolCell);
        const degradationCell = document.createElement("td");
        degradationCell.textContent = item.degraded_reasons?.length
            ? item.degraded_reasons.join(" | ")
            : item.reason;
        row.appendChild(degradationCell);
        const recoveryCell = document.createElement("td");
        recoveryCell.textContent = formatText(item.suggested_recovery);
        row.appendChild(recoveryCell);
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
function renderTaskOverview(task) {
    const badge = byId("task-state-badge");
    badge.textContent = `${task.status}${task.internal_status ? ` / ${task.internal_status}` : ""}`;
    badge.className = statusChipClass(task.status);
    const container = byId("task-detail");
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
    }
    else {
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
function renderNoPendingAction() {
    state.selectedPendingActionId = null;
    byId("candidate-count").textContent = "0";
    byId("recommendation-summary").textContent =
        "No pending action selected.";
    byId("candidate-compare-container").innerHTML =
        "<p>No candidate data for the selected task.</p>";
    byId("decision-form-container").innerHTML =
        "<p>No pending action for the selected task.</p>";
}
function renderCandidateComparison(detail) {
    const counter = byId("candidate-count");
    counter.textContent = String(detail.candidates.length);
    byId("recommendation-summary").textContent =
        detail.recommendation_summary || detail.explanation;
    const container = byId("candidate-compare-container");
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
        "Readiness",
        "Recovery",
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
        toolCell.textContent =
            `${formatText(candidate.tool.tool_id)} / ${formatText(candidate.tool.capability_id)} / ` +
                `${formatText(candidate.tool.io_type)} / mode=${formatText(candidate.tool.adapter_mode)} / ` +
                `source=${candidate.tool.source}`;
        row.appendChild(toolCell);
        const readinessCell = document.createElement("td");
        const readiness = candidate.tool.readiness_status ?? (candidate.tool.available ? "ready" : "degraded");
        const readinessChip = document.createElement("span");
        readinessChip.className = readinessChipClass(readiness);
        readinessChip.textContent = readiness;
        readinessCell.appendChild(readinessChip);
        readinessCell.title = candidate.tool.degraded_reasons?.length
            ? candidate.tool.degraded_reasons.join(" | ")
            : candidate.tool.availability_hint;
        row.appendChild(readinessCell);
        const recoveryCell = document.createElement("td");
        recoveryCell.textContent = formatText(candidate.tool.suggested_recovery);
        row.appendChild(recoveryCell);
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
function buildCandidateOptionLabel(candidate) {
    const source = candidate.tool.source;
    const mode = formatText(candidate.tool.adapter_mode);
    return `${candidate.candidate_id} | #${candidate.rank} | risk=${formatText(candidate.risk_level)} | cost=${formatText(candidate.cost_estimate)} | source=${source} | mode=${mode}`;
}
function renderDecisionForm(detail) {
    const container = byId("decision-form-container");
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
    const syncCandidateState = () => {
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
function findLatestEvent(events, eventType) {
    for (let index = events.length - 1; index >= 0; index -= 1) {
        if (events[index].event_type === eventType) {
            return events[index];
        }
    }
    return null;
}
async function refreshLatestProgress(taskId, previousStatus, currentStatus) {
    const lines = [];
    if (previousStatus && currentStatus && previousStatus !== currentStatus) {
        lines.push(`State updated: ${previousStatus} -> ${currentStatus}.`);
    }
    try {
        const events = await getJson(`/tasks/${taskId}/events`);
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
    }
    catch {
        if (lines.length) {
            setDecisionProgress(lines.join(" "));
            return;
        }
        setDecisionProgress("Event timeline is not available yet.");
    }
}
async function refreshPendingActionDetail(pendingActionId) {
    try {
        const detail = await getJson(`/pending-actions/${encodeURIComponent(pendingActionId)}`);
        renderCandidateComparison(detail);
        renderDecisionForm(detail);
    }
    catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        byId("recommendation-summary").textContent = message;
        byId("candidate-compare-container").innerHTML =
            `<p class="error">${message}</p>`;
        byId("decision-form-container").innerHTML =
            "<p>No pending action for the selected task.</p>";
        setGlobalMessage(message, true);
    }
}
async function submitDecision() {
    if (!state.selectedTaskId || !state.selectedPendingActionId) {
        setGlobalMessage("Task and pending action are required before submitting decision.", true);
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
    const previousStatus = state.lastTaskStatus;
    const response = await fetch(`/pending-actions/${encodeURIComponent(state.selectedPendingActionId)}/decision`, {
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
    const updatedTask = (await response.json());
    state.lastTaskStatus = updatedTask.status;
    renderTaskOverview(updatedTask);
    if (updatedTask.pending_action) {
        state.selectedPendingActionId = updatedTask.pending_action.pending_action_id;
        await refreshPendingActionDetail(state.selectedPendingActionId);
    }
    else {
        renderNoPendingAction();
    }
    setGlobalMessage("Decision submitted. Pending list and state are refreshed.");
    await Promise.all([
        refreshPendingActions(),
        refreshCapabilityReadiness(),
        refreshLatestProgress(updatedTask.id, previousStatus, updatedTask.status),
    ]);
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
async function refreshCapabilityReadiness() {
    try {
        const records = await getJson("/capabilities/readiness");
        renderCapabilityReadiness(records);
        renderModelInvocation(records);
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
        const previousStatus = state.lastTaskStatus;
        state.lastTaskStatus = task.status;
        renderTaskOverview(task);
        if (task.pending_action) {
            state.selectedPendingActionId = task.pending_action.pending_action_id;
            await refreshPendingActionDetail(state.selectedPendingActionId);
        }
        else {
            renderNoPendingAction();
        }
        await refreshLatestProgress(task.id, previousStatus, task.status);
    }
    catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        byId("task-detail").innerHTML = `<p class="error">${message}</p>`;
        renderNoPendingAction();
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
        void refreshCapabilityReadiness();
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
    renderNoPendingAction();
    await refreshPendingActions();
    await refreshCapabilityReadiness();
    if (state.selectedTaskId) {
        await refreshTaskDetail();
    }
    window.setInterval(() => {
        void refreshPendingActions();
        void refreshCapabilityReadiness();
        if (state.selectedTaskId) {
            void refreshTaskDetail();
        }
    }, 5000);
}
void bootstrap();
export {};
