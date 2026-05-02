export type ExternalStatus =
  | "CREATED"
  | "PLANNING"
  | "WAITING_PLAN_CONFIRM"
  | "PLANNED"
  | "RUNNING"
  | "WAITING_PATCH_CONFIRM"
  | "WAITING_REPLAN_CONFIRM"
  | "SUMMARIZING"
  | "DONE"
  | "FAILED"
  | "CANCELLED";

export type InternalStatus = ExternalStatus | "WAITING_PATCH" | "PATCHING" | "WAITING_REPLAN" | "REPLANNING";

export type DecisionChoice = "accept" | "replan" | "continue" | "cancel";

export type PendingActionStatus = "pending" | "decided" | "expired" | "cancelled";

export interface TaskRecord {
  id: string;
  status: ExternalStatus;
  internal_status: InternalStatus;
  goal: string;
  constraints: Record<string, unknown>;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  pending_action?: PendingAction | null;
  design_result?: DesignResult | null;
}

export interface DesignResult {
  task_id: string;
  sequence?: string | null;
  structure_pdb_path?: string | null;
  scores?: Record<string, unknown>;
  risk_flags?: string[];
  report_path?: string | null;
  metadata?: Record<string, unknown>;
}

export interface TaskDraftField {
  value: unknown;
  source: string;
  confidence: number;
  source_span?: string | null;
  confirmed: boolean;
  warnings: string[];
  last_modified_by?: string | null;
}

export interface TaskSpecDraft {
  fields: Record<string, TaskDraftField>;
  unmapped_text: string[];
  extraction_mode: "none" | "rule_extract" | "llm_extract" | "manual_fallback";
  extraction_errors: string[];
}

export interface TaskIntakeSession {
  intake_id: string;
  status: "collecting" | "needs_confirmation" | "confirmed" | "cancelled";
  raw_input: Record<string, unknown>;
  draft: TaskSpecDraft;
  missing_required_fields: string[];
  ambiguous_fields: string[];
  unmapped_text: string[];
  warnings: string[];
  safety_check: TaskIntakeSafetyCheck;
  audit_events: TaskIntakeAuditEvent[];
  human_summary: string;
  created_at: string;
  updated_at: string;
}

export interface TaskIntakeSafetyRisk {
  level: "ok" | "warn" | "block";
  code: string;
  message: string;
  scope: "input";
  details: Record<string, unknown>;
}

export interface TaskIntakeSafetyCheck {
  action: "ok" | "warn" | "block";
  risk_flags: TaskIntakeSafetyRisk[];
  checked_at: string;
  input_summary: Record<string, unknown>;
}

export interface TaskIntakeAuditEvent {
  event_type: string;
  intake_id: string;
  timestamp: string;
  actor_type: string;
  actor_id?: string | null;
  data: Record<string, unknown>;
}

export interface TaskIntakeCreateRequest {
  text?: string | null;
  structured_fields: Record<string, unknown>;
  source: "web" | "cli" | "api" | "script" | "legacy";
}

export interface TaskIntakePatchRequest {
  fields: Record<string, unknown>;
  updated_by: string;
}

export interface TaskIntakeConditionalRequiredRule {
  profile?: string;
  if?: {
    field: string;
    equals?: unknown;
  };
  required: string[];
  reason?: string;
}

export interface TaskIntakeTaskProfile {
  support_level: string;
  required: string[];
  optional: string[];
  conditional_required: TaskIntakeConditionalRequiredRule[];
  capability_hints: string[];
}

export interface TaskIntakeFieldDefinition {
  group: string;
  type: string;
  ui_control: string;
  nl_aliases: string[];
  validators: Record<string, unknown>;
  options: string[];
  default: unknown;
  maps_to: string;
  support_level: string;
  audit_visibility: string;
  tool_options?: TaskIntakeToolOption[];
}

export interface TaskIntakeToolOption {
  tool_id: string;
  label?: string | null;
  capabilities?: string[];
  support_level?: string | null;
  execution?: unknown;
}

export interface TaskIntakeWebSchemaGroup {
  id: string;
  fields: string[];
}

export interface TaskIntakeSchema {
  version: string;
  groups: string[];
  fields: Record<string, TaskIntakeFieldDefinition>;
  web_schema: {
    groups: TaskIntakeWebSchemaGroup[];
    fields: Record<string, TaskIntakeFieldDefinition>;
  };
  task_profiles: Record<string, TaskIntakeTaskProfile>;
  tool_options: TaskIntakeToolOption[];
  conditional_required: TaskIntakeConditionalRequiredRule[];
  confirmed_task_spec_mapping: Record<string, string>;
  planner_capability_hints: Record<string, string[]>;
}

export interface TaskIntakeConfirmation {
  intake_id: string;
  task_id: string;
  status: ExternalStatus;
  human_summary: string;
  confirmed_task_spec: Record<string, unknown>;
}

export interface PendingAction {
  pending_action_id: string;
  task_id: string;
  action_type: string;
  status: PendingActionStatus;
  created_at: string;
  candidates: unknown[];
  explanation: string;
  default_suggestion?: string | null;
  default_recommendation?: string | null;
}

export interface PendingActionSummary {
  pending_action_id: string;
  task_id: string;
  action_type: string;
  status: PendingActionStatus;
  created_at: string;
  candidate_count: number;
  default_suggestion?: string | null;
  explanation: string;
  summary: string;
}

export interface PendingActionDetail {
  pending_action_id: string;
  task_id: string;
  action_type: string;
  status: PendingActionStatus;
  created_at: string;
  default_suggestion?: string | null;
  explanation: string;
  recommendation_summary: string;
  runtime_state_summary: Record<string, unknown>;
  workflow_action_reason?: string | null;
  evidence_refs: Record<string, unknown>[];
  score_breakdown: Record<string, number>;
  candidates: PendingActionCandidateDisplay[];
}

export interface PendingActionCandidateDisplay {
  rank: number;
  candidate_id: string;
  is_default: boolean;
  summary: string;
  explanation: string;
  recommendation_reason: string;
  risk_level?: string | null;
  cost_estimate?: string | null;
  expected_effect?: string | null;
  affected_steps: string[];
  recovery_semantics?: string | null;
  overall_score?: number | null;
  score_breakdown: Record<string, number>;
  runtime_state_summary: Record<string, unknown>;
  workflow_action_reason?: string | null;
  evidence_refs: Record<string, unknown>[];
  tool: PendingActionToolDisplay;
}

export interface PendingActionToolDisplay {
  tool_id?: string | null;
  adapter_id?: string | null;
  capability_id?: string | null;
  io_type?: string | null;
  adapter_mode?: string | null;
  execution_mode?: string | null;
  provider?: string | null;
  endpoint_type?: string | null;
  remote_job_id?: string | null;
  failure_code?: string | null;
  recovery_hint?: string | null;
  source: string;
  available: boolean;
  can_fallback: boolean;
  availability_hint: string;
  readiness_status?: string | null;
  degraded_reasons: string[];
  suggested_recovery?: string | null;
  readiness_snapshot: Record<string, unknown>;
}

export interface DecisionRequest {
  choice: DecisionChoice;
  selected_candidate_id?: string | null;
  decided_by: string;
  comment?: string | null;
}

export interface CapabilityReadinessEntry {
  capability_id: string;
  status: string;
  available_tools: ToolReadinessEntry[];
  blocked_tools: ToolReadinessEntry[];
  degraded_reasons: string[];
  last_checked_at: string;
  primary_tool_id?: string | null;
  fallback_tool_ids: string[];
  suggested_recovery?: string | null;
  reason: string;
  tools: ToolReadinessEntry[];
}

export interface ToolReadinessEntry {
  tool_id: string;
  status: string;
  reason: string;
  suggested_recovery?: string | null;
}

export interface TaskTimelineEvent {
  seq: number;
  task_id: string;
  ts?: string | null;
  event_type: string;
  source_event?: string | null;
  pending_action_id?: string | null;
  decision_id?: string | null;
  step_id?: string | null;
  tool?: string | null;
  tool_id?: string | null;
  adapter_mode?: string | null;
  execution_mode?: string | null;
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

export interface TaskReportDetail {
  task_id: string;
  report_path?: string | null;
  scores: Record<string, unknown>;
  objective_scoring: Record<string, unknown>;
  structure_similarity: Record<string, unknown>;
  metadata: Record<string, unknown>;
}
