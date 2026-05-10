import { FormEvent, useEffect, useState } from "react";
import { apiClient } from "../api/client";
import type { DecisionChoice, PendingActionDetail } from "../api/types";
import { identifierLabel } from "../utils/displayText";

interface DecisionFormProps {
  detail: PendingActionDetail | null;
  onSubmitted: () => void;
}

const actionLabels: Record<string, string> = {
  accept: "批准",
  replan: "修改或请求重规划",
  continue: "继续原方案",
  cancel: "拒绝或取消",
};

function choicesForAction(actionType?: string): DecisionChoice[] {
  if (actionType === "replan_confirm") {
    return ["accept", "continue", "cancel"];
  }
  return ["accept", "replan", "cancel"];
}

export function DecisionForm({ detail, onSubmitted }: DecisionFormProps) {
  const [choice, setChoice] = useState<DecisionChoice>("accept");
  const [candidateId, setCandidateId] = useState("");
  const [decidedBy, setDecidedBy] = useState("web-user");
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState("");
  const availableChoices = choicesForAction(detail?.action_type);

  useEffect(() => {
    if (!availableChoices.includes(choice)) {
      setChoice(availableChoices[0]);
    }
  }, [availableChoices, choice]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!detail) {
      return;
    }
    setSubmitting(true);
    setMessage("");
    try {
      await apiClient.submitDecision(detail.pending_action_id, {
        choice,
        selected_candidate_id: candidateId || null,
        decided_by: decidedBy,
        comment: comment || null,
      });
      setMessage("决策已提交，正在刷新服务端状态。");
      onSubmitted();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <h2>决策表单</h2>
        <span className="counter">{identifierLabel(detail?.status ?? "idle")}</span>
      </div>
      {!detail ? <p className="muted">当前任务没有待处理操作。</p> : null}
      {detail ? (
        <form className="decision-form" onSubmit={submit}>
          <fieldset className="choice-grid">
            <legend>选择</legend>
            {availableChoices.map((item) => (
              <label key={item}>
                <input
                  type="radio"
                  name="decision-choice"
                  value={item}
                  checked={choice === item}
                  onChange={() => setChoice(item)}
                />
                <span>{actionLabels[item]}</span>
              </label>
            ))}
          </fieldset>
          <label>
            候选方案
            <select value={candidateId} onChange={(event) => setCandidateId(event.target.value)}>
              <option value="">无</option>
              {detail.candidates.map((candidate) => (
                <option key={candidate.candidate_id} value={candidate.candidate_id}>{candidate.candidate_id}</option>
              ))}
            </select>
          </label>
          <label>
            决策人
            <input value={decidedBy} onChange={(event) => setDecidedBy(event.target.value)} />
          </label>
          <label>
            备注
            <textarea value={comment} onChange={(event) => setComment(event.target.value)} />
          </label>
          <button type="submit" disabled={submitting}>{submitting ? "提交中" : "提交决策"}</button>
          {message ? <p className="muted">{message}</p> : null}
        </form>
      ) : null}
    </section>
  );
}
