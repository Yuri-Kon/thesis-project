import { type FormEvent, useEffect, useMemo, useState } from "react";
import { apiClient, apiErrorMessage } from "../api/client";
import type {
  CapabilityHint,
  CapabilityReadinessEntry,
  ScenarioGateResult,
  TaskIntakeConditionalRequiredRule,
  TaskIntakeFieldDefinition,
  TaskIntakeSchema,
  TaskIntakeSession,
  TaskIntakeTaskProfile,
  TaskIntakeToolOption,
} from "../api/types";

interface TaskDraftFormProps {
  schema: TaskIntakeSchema | null;
  intake: TaskIntakeSession | null;
  text: string;
  busy: boolean;
  onTextChange: (value: string) => void;
  onCreate: (structuredFields: Record<string, unknown>) => void;
  onPatch: (structuredFields: Record<string, unknown>) => void;
}

type FieldValue = string | number | boolean | string[] | number[] | null;

const LIST_TYPES = new Set(["string_list", "residue_list", "tool_id_list", "artifact_ref_list"]);

function fieldLabel(name: string): string {
  return name.replace(/_/g, " ");
}

function supportLabel(supportLevel: string): string {
  if (supportLevel === "P0") {
    return "supported";
  }
  if (supportLevel === "P1") {
    return "experimental";
  }
  if (supportLevel === "P2") {
    return "unsupported";
  }
  return supportLevel;
}

function formatDefault(value: unknown): string {
  if (value === null || value === undefined) {
    return "none";
  }
  if (Array.isArray(value)) {
    return value.length ? value.join(", ") : "empty";
  }
  if (value && typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

function defaultValue(definition: TaskIntakeFieldDefinition): FieldValue {
  if (definition.default !== null && definition.default !== undefined) {
    if (Array.isArray(definition.default)) {
      return definition.default.map(String);
    }
    if (definition.type === "integer" || definition.type === "number") {
      return Number(definition.default);
    }
    if (definition.type === "boolean") {
      return Boolean(definition.default);
    }
    if (definition.type === "object") {
      return JSON.stringify(definition.default, null, 2);
    }
    return String(definition.default);
  }
  if (definition.type === "boolean") {
    return false;
  }
  if (definition.type === "integer_range") {
    return ["", ""];
  }
  if (LIST_TYPES.has(definition.type)) {
    return [];
  }
  return "";
}

function normalizeDraftValue(definition: TaskIntakeFieldDefinition, value: unknown): FieldValue {
  if (definition.type === "artifact_ref_list" && Array.isArray(value)) {
    return value
      .map((item) => {
        if (typeof item === "string") {
          return item;
        }
        if (item && typeof item === "object") {
          const artifact = item as Record<string, unknown>;
          return String(artifact.artifact_id ?? artifact.uri ?? artifact.path ?? artifact.ref ?? "");
        }
        return "";
      })
      .filter(Boolean);
  }
  if (definition.type === "integer_range" && Array.isArray(value)) {
    return [String(value[0] ?? ""), String(value[1] ?? "")];
  }
  if (LIST_TYPES.has(definition.type)) {
    return Array.isArray(value) ? value.map(String) : String(value ?? "").split(",").map((item) => item.trim()).filter(Boolean);
  }
  if (definition.type === "boolean") {
    return Boolean(value);
  }
  if (definition.type === "integer" || definition.type === "number") {
    return value === null || value === undefined || value === "" ? "" : Number(value);
  }
  if (definition.type === "object") {
    return value && typeof value === "object" ? JSON.stringify(value, null, 2) : String(value ?? "");
  }
  return value === null || value === undefined ? "" : String(value);
}

function collectValue(definition: TaskIntakeFieldDefinition, value: FieldValue): unknown {
  if (definition.type === "artifact_ref_list") {
    const items = Array.isArray(value)
      ? value.map(String)
      : String(value ?? "")
          .split(/[\n,]/)
          .map((item) => item.trim());
    return items.filter(Boolean).map((item) => ({
      kind: item.startsWith("artifact://") || item.startsWith("task://") ? "uri" : "file",
      path: item.startsWith("artifact://") || item.startsWith("task://") ? undefined : item,
      uri: item.startsWith("artifact://") || item.startsWith("task://") ? item : undefined,
    }));
  }
  if (definition.type === "integer_range") {
    const [min, max] = Array.isArray(value) ? value : ["", ""];
    if (min === "" || max === "") {
      return null;
    }
    return [Number(min), Number(max)];
  }
  if (definition.type === "integer") {
    return value === "" || value === null ? null : Number(value);
  }
  if (definition.type === "number") {
    return value === "" || value === null ? null : Number(value);
  }
  if (definition.type === "boolean") {
    return Boolean(value);
  }
  if (LIST_TYPES.has(definition.type)) {
    if (Array.isArray(value)) {
      return value.map(String).map((item) => item.trim()).filter(Boolean);
    }
    return String(value ?? "").split(/[\n,]/).map((item) => item.trim()).filter(Boolean);
  }
  if (definition.type === "object") {
    const raw = String(value ?? "").trim();
    if (!raw) {
      return null;
    }
    try {
      return JSON.parse(raw) as Record<string, unknown>;
    } catch {
      return raw;
    }
  }
  const normalized = String(value ?? "").trim();
  return normalized || null;
}

function hasValue(value: unknown): boolean {
  if (value === null || value === undefined || value === "") {
    return false;
  }
  return !Array.isArray(value) || value.length > 0;
}

function orderedGroups(schema: TaskIntakeSchema | null) {
  return schema?.web_schema.groups ?? [];
}

function groupStartsOpen(groupId: string): boolean {
  return ["objective", "inputs", "design_constraints", "safety_constraints"].includes(groupId);
}

function currentTaskKind(schema: TaskIntakeSchema | null, fieldValues: Record<string, FieldValue>): string {
  const rawValue = fieldValues.task_kind;
  const value = typeof rawValue === "string" && rawValue ? rawValue : "de_novo_design";
  return schema?.task_profiles[value] ? value : Object.keys(schema?.task_profiles ?? {})[0] ?? value;
}

function isRuleActive(
  rule: TaskIntakeConditionalRequiredRule,
  schema: TaskIntakeSchema,
  fieldValues: Record<string, FieldValue>,
): boolean {
  if (!rule.if?.field) {
    return true;
  }
  const definition = schema.fields[rule.if.field];
  const currentValue = definition ? collectValue(definition, fieldValues[rule.if.field] ?? defaultValue(definition)) : fieldValues[rule.if.field];
  return currentValue === rule.if.equals;
}

function profileForTaskKind(schema: TaskIntakeSchema | null, taskKind: string): TaskIntakeTaskProfile | null {
  return schema?.task_profiles[taskKind] ?? null;
}

function profileCapabilityHints(profile: TaskIntakeTaskProfile): CapabilityHint[] {
  if (profile.capability_hint_details?.length) {
    return profile.capability_hint_details;
  }
  return profile.capability_hints.map((name) => ({ name, required: true }));
}

function hintKey(hint: CapabilityHint): string {
  return hint.io_type ? `${hint.name}:${hint.io_type}` : hint.name;
}

function readinessForHint(preview: ScenarioGateResult | null, hint: CapabilityHint): CapabilityReadinessEntry | null {
  return preview?.readiness[hintKey(hint)] ?? null;
}

function CapabilityStatusBadge({
  hint,
  readiness,
  unavailableReason,
}: {
  hint: CapabilityHint;
  readiness: CapabilityReadinessEntry | null;
  unavailableReason?: string;
}) {
  const status = readiness?.status ?? "unavailable";
  const reason = readiness?.reason ?? unavailableReason ?? hint.degraded_message ?? "capability readiness is unavailable";
  return (
    <span className={`capability-status capability-${status}`} title={reason}>
      <strong>{hint.name}</strong>
      <small>
        {status}
        {hint.required ? " · required" : " · optional"}
        {hint.io_type ? ` · ${hint.io_type}` : ""}
      </small>
    </span>
  );
}

export function TaskDraftForm({
  schema,
  intake,
  text,
  busy,
  onTextChange,
  onCreate,
  onPatch,
}: TaskDraftFormProps) {
  const [fieldValues, setFieldValues] = useState<Record<string, FieldValue>>({});
  const [scenarioGatePreview, setScenarioGatePreview] = useState<ScenarioGateResult | null>(null);
  const [scenarioGatePreviewError, setScenarioGatePreviewError] = useState<string | null>(null);

  useEffect(() => {
    if (!schema) {
      return;
    }
    const nextValues: Record<string, FieldValue> = {};
    for (const [name, definition] of Object.entries(schema.fields)) {
      nextValues[name] = defaultValue(definition);
    }
    setFieldValues(nextValues);
  }, [schema]);

  useEffect(() => {
    if (!schema || !intake) {
      return;
    }
    setFieldValues((current) => {
      const nextValues = { ...current };
      for (const [name, field] of Object.entries(intake.draft.fields)) {
        const definition = schema.fields[name];
        if (definition) {
          nextValues[name] = normalizeDraftValue(definition, field.value);
        }
      }
      return nextValues;
    });
  }, [intake, schema]);

  const structuredFields = useMemo(() => {
    const fields: Record<string, unknown> = {};
    if (!schema) {
      return fields;
    }
    for (const [name, definition] of Object.entries(schema.fields)) {
      const value = collectValue(definition, fieldValues[name] ?? defaultValue(definition));
      if (hasValue(value)) {
        fields[name] = value;
      }
    }
    return fields;
  }, [fieldValues, schema]);
  const structuredFieldsJson = useMemo(() => JSON.stringify(structuredFields), [structuredFields]);
  const taskKind = useMemo(() => currentTaskKind(schema, fieldValues), [fieldValues, schema]);
  const activeProfile = useMemo(() => profileForTaskKind(schema, taskKind), [schema, taskKind]);
  const activeConditionalRules = useMemo(() => {
    if (!schema || !activeProfile) {
      return [];
    }
    return activeProfile.conditional_required.filter((rule) => isRuleActive(rule, schema, fieldValues));
  }, [activeProfile, fieldValues, schema]);
  const requiredFields = useMemo(() => new Set(activeProfile?.required ?? []), [activeProfile]);
  const optionalFields = useMemo(() => new Set(activeProfile?.optional ?? []), [activeProfile]);
  const activeCapabilityHints = useMemo(
    () => (activeProfile ? profileCapabilityHints(activeProfile) : []),
    [activeProfile],
  );
  const conditionalFields = useMemo(
    () => new Set(activeConditionalRules.flatMap((rule) => rule.required)),
    [activeConditionalRules],
  );

  useEffect(() => {
    if (!schema) {
      setScenarioGatePreview(null);
      setScenarioGatePreviewError(null);
      return;
    }
    let cancelled = false;
    const timeout = window.setTimeout(() => {
      const fields = JSON.parse(structuredFieldsJson) as Record<string, unknown>;
      apiClient
        .getScenarioGatePreview(fields)
        .then((preview) => {
          if (!cancelled) {
            setScenarioGatePreview(preview);
            setScenarioGatePreviewError(null);
          }
        })
        .catch((error: unknown) => {
          if (!cancelled) {
            setScenarioGatePreview(null);
            setScenarioGatePreviewError(apiErrorMessage(error));
          }
        });
    }, 150);
    return () => {
      cancelled = true;
      window.clearTimeout(timeout);
    };
  }, [schema, structuredFieldsJson]);

  function setFieldValue(name: string, value: FieldValue) {
    setFieldValues((current) => ({ ...current, [name]: value }));
  }

  function fieldRole(name: string): "required" | "conditional" | "optional" | "advanced" {
    if (requiredFields.has(name)) {
      return "required";
    }
    if (conditionalFields.has(name)) {
      return "conditional";
    }
    if (optionalFields.has(name) || name === "task_kind") {
      return "optional";
    }
    return "advanced";
  }

  function toggleListValue(name: string, option: string, checked: boolean) {
    setFieldValues((current) => {
      const existing = Array.isArray(current[name]) ? current[name].map(String) : [];
      return {
        ...current,
        [name]: checked ? [...existing, option] : existing.filter((item) => item !== option),
      };
    });
  }

  function renderToolOption(name: string, option: TaskIntakeToolOption, selected: string[]) {
    const optionId = option.tool_id;
    return (
      <label className="tool-option-card" key={optionId}>
        <input
          type="checkbox"
          checked={selected.includes(optionId)}
          onChange={(event) => toggleListValue(name, optionId, event.target.checked)}
        />
        <span>
          <strong>{option.label ?? optionId}</strong>
          <small>
            {optionId}
            {option.support_level ? ` · ${supportLabel(option.support_level)}` : ""}
          </small>
          {option.capabilities?.length ? <em>{option.capabilities.join(", ")}</em> : null}
        </span>
      </label>
    );
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onCreate(structuredFields);
  }

  function renderControl(name: string, definition: TaskIntakeFieldDefinition) {
    const value = fieldValues[name] ?? defaultValue(definition);

    if (definition.type === "enum") {
      return (
        <div className="segmented-control" role="radiogroup" aria-label={fieldLabel(name)}>
          {definition.options.map((option) => (
            <button
              type="button"
              role="radio"
              aria-checked={String(value) === option}
              key={option}
              onClick={() => setFieldValue(name, option)}
            >
              {option}
            </button>
          ))}
        </div>
      );
    }

    if (definition.type === "boolean") {
      return (
        <label className="toggle-control">
          <input
            type="checkbox"
            checked={Boolean(value)}
            onChange={(event) => setFieldValue(name, event.target.checked)}
          />
          <span>{Boolean(value) ? "Enabled" : "Disabled"}</span>
        </label>
      );
    }

    if (definition.type === "integer_range") {
      const [min, max] = Array.isArray(value) ? value : ["", ""];
      return (
        <div className="range-control">
          <input
            type="number"
            min={typeof definition.validators.min === "number" ? definition.validators.min : undefined}
            max={typeof definition.validators.max === "number" ? definition.validators.max : undefined}
            value={String(min ?? "")}
            placeholder="min"
            onChange={(event) => setFieldValue(name, [event.target.value, max as string])}
          />
          <input
            type="number"
            min={typeof definition.validators.min === "number" ? definition.validators.min : undefined}
            max={typeof definition.validators.max === "number" ? definition.validators.max : undefined}
            value={String(max ?? "")}
            placeholder="max"
            onChange={(event) => setFieldValue(name, [min as string, event.target.value])}
          />
        </div>
      );
    }

    if (definition.type === "tool_id_list" && definition.tool_options?.length) {
      const selected = Array.isArray(value) ? value.map(String) : [];
      return (
        <div className="tool-option-grid" aria-label={fieldLabel(name)}>
          {definition.tool_options.map((option) => renderToolOption(name, option, selected))}
        </div>
      );
    }

    if (definition.ui_control === "multi_select" || definition.type === "tool_id_list") {
      const selected = Array.isArray(value) ? value.map(String) : [];
      if (!definition.options.length) {
        return <p className="muted">No schema options are currently available.</p>;
      }
      return (
        <div className="checkbox-grid">
          {definition.options.map((option) => (
            <label key={option}>
              <input
                type="checkbox"
                checked={selected.includes(option)}
                onChange={(event) => toggleListValue(name, option, event.target.checked)}
              />
              <span>{option}</span>
            </label>
          ))}
        </div>
      );
    }

    if (definition.ui_control === "artifact_picker" || definition.type === "artifact_ref_list") {
      const textValue = Array.isArray(value) ? value.join(", ") : String(value ?? "");
      return (
        <div className="artifact-control">
          <textarea
            value={textValue}
            rows={2}
            placeholder="artifact://, task://, or path"
            onChange={(event) => setFieldValue(name, event.target.value)}
          />
          <input
            type="file"
            onChange={(event) => {
              const fileName = event.target.files?.[0]?.name;
              if (fileName) {
                setFieldValue(name, [fileName]);
              }
            }}
          />
        </div>
      );
    }

    if (definition.ui_control === "textarea" || definition.type === "protein_sequence") {
      return (
        <textarea
          value={String(value ?? "")}
          rows={definition.type === "protein_sequence" ? 5 : 3}
          onChange={(event) => setFieldValue(name, event.target.value)}
        />
      );
    }

    if (definition.type === "object") {
      return (
        <textarea
          value={String(value ?? "")}
          rows={4}
          onChange={(event) => setFieldValue(name, event.target.value)}
        />
      );
    }

    return (
      <input
        type={definition.type === "integer" || definition.type === "number" ? "number" : "text"}
        min={typeof definition.validators.min === "number" ? definition.validators.min : undefined}
        max={typeof definition.validators.max === "number" ? definition.validators.max : undefined}
        value={String(value ?? "")}
        onChange={(event) => setFieldValue(name, event.target.value)}
      />
    );
  }

  const hasAnyInput = text.trim().length > 0 || Object.keys(structuredFields).length > 0;

  return (
    <form className="task-draft-form" onSubmit={handleSubmit}>
      <section className="panel builder-input-panel">
        <div className="panel-header">
          <h2>Task Draft</h2>
          <span className="pill">{schema?.version ?? "schema"}</span>
        </div>
        <textarea
          className="natural-language-input"
          value={text}
          onChange={(event) => onTextChange(event.target.value)}
          placeholder="Design a stable de novo protein around 120 aa, balanced profile, require plan confirmation."
        />
        <div className="button-row">
          <button type="submit" disabled={busy || !schema || !hasAnyInput}>
            Parse Draft
          </button>
          <button type="button" onClick={() => onPatch(structuredFields)} disabled={busy || !schema || !intake}>
            Update Draft
          </button>
        </div>
        {activeProfile ? (
          <div className={`profile-summary support-${activeProfile.support_level.toLowerCase()}`}>
            <div className="profile-summary-head">
              <span className="source-chip">{taskKind.replace(/_/g, " ")}</span>
              <span className="source-chip">{supportLabel(activeProfile.support_level)}</span>
            </div>
            <div className="profile-summary-grid">
              <div>
                <strong>Required</strong>
                <span>{activeProfile.required.map(fieldLabel).join(", ")}</span>
              </div>
              <div>
                <strong>Conditional</strong>
                <span>
                {activeProfile.conditional_required.length
                  ? activeProfile.conditional_required
                      .map((rule) => `${rule.required.map(fieldLabel).join(", ")} when ${rule.if?.field ?? "condition"}=${String(rule.if?.equals ?? "true")}`)
                      .join("; ")
                  : "none"}
                </span>
              </div>
              <div>
                <strong>Capabilities</strong>
                <span className="capability-status-list">
                  {activeCapabilityHints.length
                    ? activeCapabilityHints.map((hint) => (
                        <CapabilityStatusBadge
                          key={`${hint.name}:${hint.io_type ?? ""}`}
                          hint={hint}
                          readiness={readinessForHint(scenarioGatePreview, hint)}
                          unavailableReason={scenarioGatePreviewError ?? undefined}
                        />
                      ))
                    : "none"}
                </span>
              </div>
            </div>
          </div>
        ) : null}
      </section>

      <section className="structured-field-groups">
        {orderedGroups(schema).map((group) => (
          <details className="panel field-group-panel" key={group.id} open={groupStartsOpen(group.id)}>
            <summary className="panel-header">
              <h2>{fieldLabel(group.id)}</h2>
              <span className="counter">{group.fields.length}</span>
            </summary>
            <div className="field-card-grid">
              {group.fields.map((name) => {
                const definition = schema?.fields[name];
                if (!definition) {
                  return null;
                }
                const role = fieldRole(name);
                const isConditional = conditionalFields.has(name);
                const defaultLabel = definition.default !== null && definition.default !== undefined
                  ? `default: ${formatDefault(definition.default)}`
                  : null;
                return (
                  <label
                    className={`schema-field-card field-role-${role} support-${definition.support_level.toLowerCase()}`}
                    key={name}
                  >
                    <span className="field-card-head">
                      <strong>{fieldLabel(name)}</strong>
                      <span className="field-badge-row">
                        <span className={`source-chip support-chip support-${definition.support_level.toLowerCase()}`}>
                          {supportLabel(definition.support_level)}
                        </span>
                        <span className={role === "required" || isConditional ? "source-chip warning" : "source-chip"}>
                          {role}
                        </span>
                      </span>
                    </span>
                    {renderControl(name, definition)}
                    <span className="field-meta">
                      {definition.maps_to}
                      {defaultLabel ? ` · ${defaultLabel}` : ""}
                    </span>
                  </label>
                );
              })}
            </div>
          </details>
        ))}
      </section>
    </form>
  );
}
