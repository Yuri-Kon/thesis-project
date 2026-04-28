import { type FormEvent, useEffect, useMemo, useState } from "react";
import type { TaskIntakeFieldDefinition, TaskIntakeSchema, TaskIntakeSession } from "../api/types";

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
  return value === null || value === undefined ? "" : String(value);
}

function collectValue(definition: TaskIntakeFieldDefinition, value: FieldValue): unknown {
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

  function setFieldValue(name: string, value: FieldValue) {
    setFieldValues((current) => ({ ...current, [name]: value }));
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
            <label key={option}>
              <input
                type="radio"
                name={name}
                value={option}
                checked={String(value) === option}
                onChange={() => setFieldValue(name, option)}
              />
              <span>{option}</span>
            </label>
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
            value={String(min ?? "")}
            placeholder="min"
            onChange={(event) => setFieldValue(name, [event.target.value, max as string])}
          />
          <input
            type="number"
            value={String(max ?? "")}
            placeholder="max"
            onChange={(event) => setFieldValue(name, [min as string, event.target.value])}
          />
        </div>
      );
    }

    if (definition.ui_control === "multi_select" || definition.type === "tool_id_list") {
      const selected = Array.isArray(value) ? value.map(String) : [];
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
          <input value={textValue} onChange={(event) => setFieldValue(name, event.target.value)} />
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

    return (
      <input
        type={definition.type === "integer" || definition.type === "number" ? "number" : "text"}
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
                return (
                  <label className="schema-field-card" key={name}>
                    <span className="field-card-head">
                      <strong>{fieldLabel(name)}</strong>
                      <span className="source-chip">{definition.support_level}</span>
                    </span>
                    {renderControl(name, definition)}
                    <span className="field-meta">{definition.maps_to}</span>
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
