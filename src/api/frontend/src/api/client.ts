import type {
  CapabilityReadinessEntry,
  DecisionRequest,
  PendingActionDetail,
  PendingActionSummary,
  ScenarioGateResult,
  TaskIntakeConfirmation,
  TaskIntakeCreateRequest,
  TaskIntakePatchRequest,
  TaskIntakeSchema,
  TaskIntakeSession,
  TaskRecord,
  TaskReportDetail,
  TaskTimelineEvent,
} from "./types";

export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;

  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : `API 请求失败，状态码 ${status}`);
    this.status = status;
    this.detail = detail;
  }
}

function detailMessage(detail: unknown): string {
  if (typeof detail === "string") {
    return detail;
  }
  if (detail && typeof detail === "object") {
    const record = detail as Record<string, unknown>;
    if (typeof record.detail === "string") {
      const validationErrors = Array.isArray(record.validation_errors)
        ? ` (${record.validation_errors.join(", ")})`
        : "";
      return `${record.detail}${validationErrors}`;
    }
    if (Array.isArray(record.detail)) {
      return record.detail
        .map((item) => (typeof item === "string" ? item : JSON.stringify(item)))
        .join("; ");
    }
  }
  return JSON.stringify(detail);
}

export function apiErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return `HTTP ${error.status}: ${detailMessage(error.detail)}`;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
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

async function requestText(path: string, init?: RequestInit): Promise<string> {
  const response = await fetch(path, init);
  if (!response.ok) {
    let detail: unknown = response.statusText;
    try {
      detail = await response.json();
    } catch {
      detail = await response.text();
    }
    throw new ApiError(response.status, detail);
  }
  return response.text();
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
  getTaskStructure(taskId: string): Promise<string> {
    return requestText(`/tasks/${encodeURIComponent(taskId)}/structure`);
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
  getTaskIntakeSchema(): Promise<TaskIntakeSchema> {
    return requestJson<TaskIntakeSchema>("/task-intakes/schema");
  },
  getTaskIntake(intakeId: string): Promise<TaskIntakeSession> {
    return requestJson<TaskIntakeSession>(`/task-intakes/${encodeURIComponent(intakeId)}`);
  },
  patchTaskIntake(intakeId: string, body: TaskIntakePatchRequest): Promise<TaskIntakeSession> {
    return requestJson<TaskIntakeSession>(`/task-intakes/${encodeURIComponent(intakeId)}`, {
      method: "PATCH",
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
  getScenarioGatePreview(structuredFields: Record<string, unknown>): Promise<ScenarioGateResult> {
    const params = new URLSearchParams({
      structured_fields: JSON.stringify(structuredFields),
    });
    return requestJson<ScenarioGateResult>(`/capabilities/scenario-gate/preview?${params.toString()}`);
  },
};
