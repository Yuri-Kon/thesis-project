const state = {
  schema: null,
  session: null,
  createdTask: null,
};

function byId(id) {
  const element = document.getElementById(id);
  if (!element) {
    throw new Error(`Missing element: #${id}`);
  }
  return element;
}

function setMessage(message, isError = false) {
  const node = byId("global-message");
  node.textContent = message;
  node.className = isError ? "global-message error" : "global-message";
}

async function parseError(response) {
  try {
    const payload = await response.json();
    return payload.detail || `Request failed: ${response.status}`;
  } catch {
    return `Request failed: ${response.status}`;
  }
}

async function getJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return await response.json();
}

async function sendJson(url, method, payload) {
  const response = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return await response.json();
}

function renderStatusPill(id, label, kind = "neutral") {
  const node = byId(id);
  node.textContent = label;
  node.className = `status-pill ${kind}`;
}

async function loadSchema() {
  renderStatusPill("schema-state", "Schema loading", "neutral");
  state.schema = await getJson("/task-intakes/schema");
  renderStatusPill("schema-state", `Schema ${state.schema.version}`, "ok");
  renderFieldForm();
}

function orderedFields() {
  if (!state.schema) {
    return [];
  }
  return Object.entries(state.schema.fields).sort((left, right) => {
    const groupCmp = String(left[1].group).localeCompare(String(right[1].group));
    if (groupCmp !== 0) {
      return groupCmp;
    }
    return left[0].localeCompare(right[0]);
  });
}

function renderFieldForm() {
  const container = byId("field-form");
  container.innerHTML = "";
  const fields = orderedFields();
  byId("field-count").textContent = `${fields.length} fields`;

  for (const [name, definition] of fields) {
    const card = document.createElement("div");
    card.className = shouldUseFullWidth(definition) ? "field-card full" : "field-card";
    card.dataset.fieldName = name;

    const label = document.createElement("label");
    label.htmlFor = fieldInputId(name);
    label.textContent = name;
    const support = document.createElement("span");
    support.className = "source-badge";
    support.textContent = definition.support_level || "-";
    label.appendChild(support);

    card.appendChild(label);
    card.appendChild(buildControl(name, definition));

    const meta = document.createElement("div");
    meta.className = "field-meta";
    meta.textContent = `${definition.group} - maps to ${definition.maps_to}`;
    card.appendChild(meta);
    container.appendChild(card);
  }
}

function shouldUseFullWidth(definition) {
  return ["protein_sequence", "artifact", "artifact/path", "tool_id_list"].includes(
    definition.type
  );
}

function fieldInputId(name) {
  return `field-${name}`;
}

function buildControl(name, definition) {
  const type = definition.type;
  if (type === "enum") {
    const group = document.createElement("div");
    group.id = fieldInputId(name);
    group.className = "segmented-control";
    group.dataset.fieldName = name;
    const options = ["", ...(definition.options || [])];
    for (const optionValue of options) {
      const optionId = `${fieldInputId(name)}-${optionValue || "unset"}`;
      const label = document.createElement("label");
      const radio = document.createElement("input");
      radio.type = "radio";
      radio.name = name;
      radio.value = optionValue;
      radio.id = optionId;
      radio.dataset.fieldName = name;
      radio.checked =
        optionValue === "" &&
        (definition.default === null || definition.default === undefined);
      if (definition.default !== null && definition.default !== undefined) {
        radio.checked = optionValue === String(definition.default);
      }
      const text = document.createElement("span");
      text.textContent = optionValue || "Not set";
      label.appendChild(radio);
      label.appendChild(text);
      group.appendChild(label);
    }
    return group;
  }

  if (type === "boolean") {
    const row = document.createElement("div");
    row.className = "toggle-row";
    const checkbox = document.createElement("input");
    checkbox.id = fieldInputId(name);
    checkbox.type = "checkbox";
    checkbox.dataset.fieldName = name;
    checkbox.checked = Boolean(definition.default);
    const text = document.createElement("span");
    text.textContent = "Enabled";
    row.appendChild(checkbox);
    row.appendChild(text);
    return row;
  }

  if (type === "integer_range") {
    const row = document.createElement("div");
    row.className = "range-control";
    const minInput = document.createElement("input");
    minInput.id = `${fieldInputId(name)}-min`;
    minInput.type = "number";
    minInput.placeholder = "min";
    minInput.dataset.fieldName = name;
    minInput.dataset.rangeRole = "min";
    const maxInput = document.createElement("input");
    maxInput.id = `${fieldInputId(name)}-max`;
    maxInput.type = "number";
    maxInput.placeholder = "max";
    maxInput.dataset.fieldName = name;
    maxInput.dataset.rangeRole = "max";
    row.appendChild(minInput);
    row.appendChild(maxInput);
    return row;
  }

  if (type === "integer") {
    const input = document.createElement("input");
    input.id = fieldInputId(name);
    input.type = "number";
    input.dataset.fieldName = name;
    if (definition.default !== null && definition.default !== undefined) {
      input.value = String(definition.default);
    }
    return input;
  }

  if (type === "artifact" || type === "artifact/path") {
    const row = document.createElement("div");
    row.className = "artifact-control";
    const pathInput = document.createElement("input");
    pathInput.id = fieldInputId(name);
    pathInput.type = "text";
    pathInput.placeholder = "Existing artifact path or ref";
    pathInput.dataset.fieldName = name;
    const fileInput = document.createElement("input");
    fileInput.type = "file";
    fileInput.dataset.fieldName = `${name}__file`;
    fileInput.addEventListener("change", () => {
      const file = fileInput.files?.[0];
      if (file) {
        pathInput.value = file.name;
      }
    });
    row.appendChild(pathInput);
    row.appendChild(fileInput);
    return row;
  }

  const textarea = document.createElement("textarea");
  textarea.id = fieldInputId(name);
  textarea.rows = type === "protein_sequence" ? 4 : 2;
  textarea.dataset.fieldName = name;
  textarea.placeholder = type === "tool_id_list" ? "Comma-separated tool ids" : "";
  return textarea;
}

function collectStructuredFields() {
  if (!state.schema) {
    return {};
  }
  const fields = {};
  for (const [name, definition] of orderedFields()) {
    const value = readFieldValue(name, definition);
    if (value !== null && value !== undefined && value !== "") {
      fields[name] = value;
    }
  }
  return fields;
}

function readFieldValue(name, definition) {
  const type = definition.type;
  if (type === "integer_range") {
    const minInput = document.querySelector(`[data-field-name="${name}"][data-range-role="min"]`);
    const maxInput = document.querySelector(`[data-field-name="${name}"][data-range-role="max"]`);
    if (!minInput.value && !maxInput.value) {
      return null;
    }
    return [Number(minInput.value), Number(maxInput.value)];
  }
  if (type === "enum") {
    const checked = document.querySelector(
      `[data-field-name="${name}"][type="radio"]:checked`
    );
    return checked?.value || null;
  }
  const input = document.querySelector(`[data-field-name="${name}"]`);
  if (!input) {
    return null;
  }
  if (type === "boolean") {
    return input.checked;
  }
  if (type === "integer") {
    return input.value ? Number(input.value) : null;
  }
  if (type === "tool_id_list") {
    return input.value
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
  }
  return input.value.trim();
}

function applyDraftToControls(session) {
  if (!state.schema) {
    return;
  }
  const fields = session.draft?.fields || {};
  for (const [name, field] of Object.entries(fields)) {
    const definition = state.schema.fields[name];
    if (!definition) {
      continue;
    }
    writeFieldValue(name, definition, field.value);
  }
}

function writeFieldValue(name, definition, value) {
  if (definition.type === "integer_range" && Array.isArray(value)) {
    const minInput = document.querySelector(`[data-field-name="${name}"][data-range-role="min"]`);
    const maxInput = document.querySelector(`[data-field-name="${name}"][data-range-role="max"]`);
    if (minInput) {
      minInput.value = value[0] ?? "";
    }
    if (maxInput) {
      maxInput.value = value[1] ?? "";
    }
    return;
  }
  if (definition.type === "enum") {
    const radio = document.querySelector(
      `[data-field-name="${name}"][type="radio"][value="${cssEscape(String(value))}"]`
    );
    if (radio) {
      radio.checked = true;
    }
    return;
  }
  const input = document.querySelector(`[data-field-name="${name}"]`);
  if (!input) {
    return;
  }
  if (definition.type === "boolean") {
    input.checked = Boolean(value);
    return;
  }
  if (definition.type === "tool_id_list" && Array.isArray(value)) {
    input.value = value.join(", ");
    return;
  }
  input.value = String(value ?? "");
}

function cssEscape(value) {
  if (window.CSS && typeof window.CSS.escape === "function") {
    return window.CSS.escape(value);
  }
  return value.replace(/["\\]/g, "\\$&");
}

async function createIntake(event) {
  event.preventDefault();
  const text = byId("natural-language-input").value.trim();
  const structuredFields = collectStructuredFields();
  const payload = {
    text: text || null,
    structured_fields: structuredFields,
    source: "web",
  };
  state.session = await sendJson("/task-intakes", "POST", payload);
  applyDraftToControls(state.session);
  renderSession();
  setMessage(`Draft ${state.session.intake_id} created.`);
}

async function updateIntake() {
  if (!state.session) {
    return;
  }
  state.session = await sendJson(
    `/task-intakes/${encodeURIComponent(state.session.intake_id)}`,
    "PATCH",
    {
      fields: collectStructuredFields(),
      updated_by: "web_task_builder",
    }
  );
  applyDraftToControls(state.session);
  renderSession();
  setMessage(`Draft ${state.session.intake_id} updated.`);
}

async function confirmIntake() {
  if (!state.session) {
    return;
  }
  const acknowledged = [];
  const safety = normalizeSafetyCheck(state.session);
  for (const warning of safety.warningCodes) {
    acknowledged.push(warning);
  }
  const result = await sendJson(
    `/task-intakes/${encodeURIComponent(state.session.intake_id)}/confirm`,
    "POST",
    {
      confirmed_by: "web_task_builder",
      acknowledged_warnings: acknowledged,
    }
  );
  state.createdTask = await getJson(`/tasks/${encodeURIComponent(result.task_id)}`);
  renderCreatedTask(result);
  renderProteinVisualization(state.session, state.createdTask);
  renderStatusPill("confirm-state", `Created ${result.task_id}`, "ok");
  setMessage(`Task ${result.task_id} created from ${result.intake_id}.`);
}

function renderSession() {
  const session = state.session;
  if (!session) {
    renderStatusPill("intake-state", "No intake", "neutral");
    renderStatusPill("confirm-state", "Not confirmed", "neutral");
    byId("update-intake-button").disabled = true;
    byId("confirm-intake-button").disabled = true;
    renderProteinVisualization(null, null);
    return;
  }
  renderStatusPill("intake-state", `${session.intake_id} - ${session.status}`, "ok");
  byId("update-intake-button").disabled = false;
  renderDraftFields(session);
  renderList("missing-fields-list", session.missing_required_fields || []);
  renderList("ambiguous-fields-list", session.ambiguous_fields || []);
  renderList("unmapped-text-list", session.unmapped_text || []);
  renderSafetyPrecheck(session);
  renderConfirmAvailability(session);
  renderProteinVisualization(session, state.createdTask);
}

function renderDraftFields(session) {
  const container = byId("draft-fields");
  container.innerHTML = "";
  const fields = session.draft?.fields || {};
  const entries = Object.entries(fields);
  byId("draft-summary").textContent = `${entries.length} draft fields`;
  if (!entries.length) {
    const empty = document.createElement("p");
    empty.className = "muted";
    empty.textContent = "No fields extracted yet.";
    container.appendChild(empty);
    return;
  }

  for (const [name, field] of entries) {
    const card = document.createElement("article");
    const isAmbiguous = (session.ambiguous_fields || []).includes(name);
    card.className = isAmbiguous ? "draft-card warning" : "draft-card";
    const title = document.createElement("h3");
    title.textContent = name;
    const confidence = document.createElement("span");
    confidence.className = "source-badge";
    confidence.textContent = `confidence ${formatConfidence(field.confidence)}`;
    title.appendChild(confidence);

    const value = document.createElement("div");
    value.className = "draft-value";
    value.textContent = JSON.stringify(field.value);

    const sourceRow = document.createElement("div");
    sourceRow.className = "source-row";
    addBadge(sourceRow, field.source);
    addBadge(sourceRow, field.confirmed ? "confirmed" : "needs review");
    if (field.source_span) {
      addBadge(sourceRow, `span: ${field.source_span}`);
    }
    if (isAmbiguous) {
      addBadge(sourceRow, "ambiguous");
    }

    card.appendChild(title);
    card.appendChild(value);
    card.appendChild(sourceRow);
    container.appendChild(card);
  }
}

function addBadge(parent, text) {
  const badge = document.createElement("span");
  badge.className = "source-badge";
  badge.textContent = text;
  parent.appendChild(badge);
}

function formatConfidence(value) {
  if (typeof value !== "number") {
    return "-";
  }
  return value.toFixed(2);
}

function renderList(id, items) {
  const list = byId(id);
  list.innerHTML = "";
  for (const item of items) {
    const li = document.createElement("li");
    li.textContent = item;
    list.appendChild(li);
  }
}

function normalizeSafetyCheck(session) {
  const safetyCheck = session?.safety_check || { action: "ok", risk_flags: [] };
  const riskFlags = safetyCheck.risk_flags || [];
  return {
    action: safetyCheck.action || "ok",
    summary:
      riskFlags.length > 0
        ? `${riskFlags.length} safety risk flag(s) detected.`
        : "No input safety warning detected.",
    warnings: riskFlags.map((risk) => `${risk.code}: ${risk.message}`),
    riskMessages: riskFlags.map((risk) => risk.message),
    warningCodes: riskFlags
      .filter((risk) => risk.level === "warn")
      .map((risk) => risk.code),
    acknowledgementRequired: riskFlags.some((risk) => risk.level === "warn"),
  };
}

function renderSafetyPrecheck(session) {
  const safety = normalizeSafetyCheck(session);
  const panel = byId("safety-panel");
  const ackRow = byId("safety-ack-row");
  const ack = byId("safety-ack-checkbox");
  const action = safety.action;
  panel.className = `safety-panel ${action}`;
  panel.innerHTML = "";
  const title = document.createElement("h3");
  title.textContent = "Safety precheck";
  const summary = document.createElement("p");
  summary.textContent = safety.summary;
  panel.appendChild(title);
  panel.appendChild(summary);
  if (safety.warnings.length) {
    const list = document.createElement("ul");
    list.className = "compact-list";
    for (const warning of safety.warnings) {
      const li = document.createElement("li");
      li.textContent = warning;
      list.appendChild(li);
    }
    panel.appendChild(list);
  }
  ackRow.classList.toggle("hidden", !safety.acknowledgementRequired);
  if (!safety.acknowledgementRequired) {
    ack.checked = false;
  }
}

function renderConfirmAvailability(session) {
  const button = byId("confirm-intake-button");
  const safety = normalizeSafetyCheck(session);
  const safetyMessages = new Set(safety.riskMessages);
  const fieldWarnings = (session.warnings || []).filter(
    (warning) => !safetyMessages.has(warning)
  );
  const ack = byId("safety-ack-checkbox");
  const blocked =
    (session.missing_required_fields || []).length > 0 ||
    (session.ambiguous_fields || []).length > 0 ||
    fieldWarnings.length > 0 ||
    safety.action === "block" ||
    (safety.acknowledgementRequired && !ack.checked);
  button.disabled = blocked;
  if (blocked) {
    renderStatusPill("confirm-state", "Needs review", "warn");
  } else {
    renderStatusPill("confirm-state", "Ready to confirm", "ok");
  }
}

function renderCreatedTask(result) {
  const container = byId("task-result");
  container.innerHTML = "";
  const rows = [
    ["Task ID", result.task_id],
    ["Intake ID", result.intake_id],
    ["Status", result.status],
  ];
  for (const [label, value] of rows) {
    const row = document.createElement("div");
    row.className = "result-line";
    const left = document.createElement("strong");
    left.textContent = label;
    const right = document.createElement("span");
    right.textContent = value;
    row.appendChild(left);
    row.appendChild(right);
    container.appendChild(row);
  }
  const detailLink = document.createElement("a");
  detailLink.href = `/ui/tasks/${encodeURIComponent(result.task_id)}`;
  detailLink.textContent = "Open Task Detail";
  container.appendChild(detailLink);
}

function renderProteinVisualization(session, task) {
  const viewer = byId("protein-viewer");
  const metrics = byId("protein-metrics");
  const structureLink = byId("structure-link");
  const snapshot = deriveProteinSnapshot(session, task);
  viewer.innerHTML = buildProteinSvg(snapshot);
  metrics.innerHTML = "";
  for (const metric of snapshot.metrics) {
    const node = document.createElement("div");
    node.className = "metric";
    const label = document.createElement("span");
    label.textContent = metric.label;
    const value = document.createElement("strong");
    value.textContent = metric.value;
    node.appendChild(label);
    node.appendChild(value);
    metrics.appendChild(node);
  }
  byId("protein-state").textContent = snapshot.mode;
  structureLink.textContent = snapshot.structurePath
    ? `Structure artifact: ${snapshot.structurePath}`
    : "No PDB artifact yet; showing intake-derived protein preview.";
}

function deriveProteinSnapshot(session, task) {
  const draftFields = session?.draft?.fields || {};
  const constraints = task?.constraints || {};
  const designResult = task?.design_result || null;
  const sequence =
    designResult?.sequence ||
    draftFields.sequence?.value ||
    constraints.sequence ||
    constraints.inputs?.sequence ||
    "";
  const lengthRange =
    draftFields.length_range?.value ||
    constraints.length_range ||
    inferRangeFromSequence(sequence);
  const scores = designResult?.scores || {};
  const structurePath = designResult?.structure_pdb_path || "";
  const lengthLabel = Array.isArray(lengthRange)
    ? `${lengthRange[0]}-${lengthRange[1]} aa`
    : sequence
      ? `${sequence.length} aa`
      : "unknown";
  return {
    sequence,
    lengthRange,
    structurePath,
    mode: structurePath ? "Structure result" : "Draft preview",
    metrics: [
      { label: "Length", value: lengthLabel },
      { label: "Objective", value: draftFields.objective_type?.value || "-" },
      { label: "pLDDT", value: formatMetric(scores.plddt_mean || scores.plddt) },
    ],
  };
}

function inferRangeFromSequence(sequence) {
  if (!sequence) {
    return [90, 130];
  }
  return [sequence.length, sequence.length];
}

function formatMetric(value) {
  if (typeof value !== "number") {
    return "-";
  }
  return value.toFixed(2);
}

function buildProteinSvg(snapshot) {
  const points = buildProteinPoints(snapshot);
  const path = points
    .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`)
    .join(" ");
  const beads = points
    .filter((_, index) => index % 2 === 0)
    .map(
      (point, index) =>
        `<circle cx="${point.x}" cy="${point.y}" r="${index % 3 === 0 ? 5 : 3.8}" />`
    )
    .join("");
  return `
    <svg viewBox="0 0 720 240" aria-label="Protein ribbon preview">
      <defs>
        <linearGradient id="proteinRibbon" x1="0" x2="1">
          <stop offset="0%" stop-color="#1769aa" />
          <stop offset="48%" stop-color="#0f766e" />
          <stop offset="100%" stop-color="#a15c07" />
        </linearGradient>
      </defs>
      <rect x="0" y="0" width="720" height="240" fill="transparent" />
      <path d="${path}" fill="none" stroke="url(#proteinRibbon)" stroke-width="13" stroke-linecap="round" stroke-linejoin="round" opacity="0.88" />
      <g fill="#ffffff" stroke="#1769aa" stroke-width="2">${beads}</g>
      <text x="24" y="36" fill="#182230" font-size="18" font-weight="700">${snapshot.mode}</text>
      <text x="24" y="60" fill="#627085" font-size="13">${snapshot.metrics[0].value}</text>
    </svg>
  `;
}

function buildProteinPoints(snapshot) {
  const range = snapshot.lengthRange;
  const maxLength = Array.isArray(range) ? Number(range[1]) || 120 : 120;
  const count = Math.max(12, Math.min(34, Math.round(maxLength / 8)));
  const points = [];
  for (let index = 0; index < count; index += 1) {
    const t = index / Math.max(1, count - 1);
    const x = 42 + t * 636;
    const y =
      122 +
      Math.sin(t * Math.PI * 4.2) * 48 +
      Math.cos(t * Math.PI * 9.1) * 14;
    points.push({ x: Number(x.toFixed(1)), y: Number(y.toFixed(1)) });
  }
  return points;
}

async function initialize() {
  try {
    await loadSchema();
    renderSession();
    setMessage("Task Builder is ready.");
  } catch (error) {
    setMessage(error instanceof Error ? error.message : String(error), true);
    renderStatusPill("schema-state", "Schema failed", "block");
  }
}

byId("task-builder-form").addEventListener("submit", (event) => {
  createIntake(event).catch((error) => {
    setMessage(error instanceof Error ? error.message : String(error), true);
  });
});

byId("update-intake-button").addEventListener("click", () => {
  updateIntake().catch((error) => {
    setMessage(error instanceof Error ? error.message : String(error), true);
  });
});

byId("confirm-intake-button").addEventListener("click", () => {
  confirmIntake().catch((error) => {
    setMessage(error instanceof Error ? error.message : String(error), true);
  });
});

byId("load-schema-button").addEventListener("click", () => {
  loadSchema()
    .then(() => setMessage("Schema reloaded."))
    .catch((error) => {
      setMessage(error instanceof Error ? error.message : String(error), true);
    });
});

byId("safety-ack-checkbox").addEventListener("change", () => {
  if (state.session) {
    renderConfirmAvailability(state.session);
  }
});

initialize();
