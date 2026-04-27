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

export type DecisionChoice = "accept" | "reject" | "modify" | "cancel" | "replan";

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
  overall_score?: number | null;
  score_breakdown: Record<string, number>;
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
  metadata: Record<string, unknown>;
}
