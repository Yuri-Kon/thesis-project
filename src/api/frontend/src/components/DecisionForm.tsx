import { FormEvent, useState } from "react";
import { apiClient } from "../api/client";
import type { DecisionChoice, PendingActionDetail } from "../api/types";

interface DecisionFormProps {
  detail: PendingActionDetail | null;
  onSubmitted: () => void;
}

const choices: DecisionChoice[] = ["accept", "reject", "modify", "cancel", "replan"];

export function DecisionForm({ detail, onSubmitted }: DecisionFormProps) {
  const [choice, setChoice] = useState<DecisionChoice>("accept");
  const [candidateId, setCandidateId] = useState("");
  const [decidedBy, setDecidedBy] = useState("web-user");
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState("");

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
      setMessage("Decision submitted. Refreshing server state.");
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
        <h2>Decision Form</h2>
        <span className="counter">{detail?.status ?? "idle"}</span>
      </div>
      {!detail ? <p className="muted">No pending action for this task.</p> : null}
      {detail ? (
        <form className="decision-form" onSubmit={submit}>
          <label>
            Choice
            <select value={choice} onChange={(event) => setChoice(event.target.value as DecisionChoice)}>
              {choices.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
          <label>
            Candidate
            <select value={candidateId} onChange={(event) => setCandidateId(event.target.value)}>
              <option value="">None</option>
              {detail.candidates.map((candidate) => (
                <option key={candidate.candidate_id} value={candidate.candidate_id}>{candidate.candidate_id}</option>
              ))}
            </select>
          </label>
          <label>
            Decided by
            <input value={decidedBy} onChange={(event) => setDecidedBy(event.target.value)} />
          </label>
          <label>
            Comment
            <textarea value={comment} onChange={(event) => setComment(event.target.value)} />
          </label>
          <button type="submit" disabled={submitting}>{submitting ? "Submitting" : "Submit Decision"}</button>
          {message ? <p className="muted">{message}</p> : null}
        </form>
      ) : null}
    </section>
  );
}
