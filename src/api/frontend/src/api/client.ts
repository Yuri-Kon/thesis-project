import type {
  CapabilityReadinessEntry,
  DecisionRequest,
  PendingActionDetail,
  PendingActionSummary,
  TaskIntakeConfirmation,
  TaskIntakeCreateRequest,
  TaskIntakeSession,
  TaskRecord,
  TaskReportDetail,
  TaskTimelineEvent,
} from "./types";

export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;

  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : `API request failed with ${status}`);
    this.status = status;
    this.detail = detail;
  }
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });
  if (!response.ok) {
    let detail: unknown = response.statusText;
    try {
      detail = await response.json();
    } catch {
      detail = await response.text();
    }
    throw new ApiError(response.status, detail);
  }
  return (await response.json()) as T;
}

export const apiClient = {
  getTask(taskId: string): Promise<TaskRecord> {
    return requestJson<TaskRecord>(`/tasks/${encodeURIComponent(taskId)}`);
  },
  getTaskEvents(taskId: string): Promise<TaskTimelineEvent[]> {
    return requestJson<TaskTimelineEvent[]>(`/tasks/${encodeURIComponent(taskId)}/events`);
  },
  getTaskReport(taskId: string): Promise<TaskReportDetail> {
    return requestJson<TaskReportDetail>(`/tasks/${encodeURIComponent(taskId)}/report`);
  },
  listPendingActions(): Promise<PendingActionSummary[]> {
    return requestJson<PendingActionSummary[]>("/pending-actions");
  },
  getPendingAction(pendingActionId: string): Promise<PendingActionDetail> {
    return requestJson<PendingActionDetail>(`/pending-actions/${encodeURIComponent(pendingActionId)}`);
  },
  submitDecision(pendingActionId: string, body: DecisionRequest): Promise<TaskRecord> {
    return requestJson<TaskRecord>(`/pending-actions/${encodeURIComponent(pendingActionId)}/decision`, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },
  createTaskIntake(body: TaskIntakeCreateRequest): Promise<TaskIntakeSession> {
    return requestJson<TaskIntakeSession>("/task-intakes", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },
  confirmTaskIntake(intakeId: string, acknowledgedWarnings: string[] = []): Promise<TaskIntakeConfirmation> {
    return requestJson<TaskIntakeConfirmation>(`/task-intakes/${encodeURIComponent(intakeId)}/confirm`, {
      method: "POST",
      body: JSON.stringify({ confirmed_by: "web", acknowledged_warnings: acknowledgedWarnings }),
    });
  },
  getCapabilityReadiness(): Promise<CapabilityReadinessEntry[]> {
    return requestJson<CapabilityReadinessEntry[]>("/capabilities/readiness");
  },
};
