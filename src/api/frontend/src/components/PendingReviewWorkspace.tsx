import type { PendingActionDetail } from "../api/types";
import { CandidateComparison } from "./CandidateComparison";
import { DecisionForm } from "./DecisionForm";

interface PendingReviewWorkspaceProps {
  detail: PendingActionDetail | null;
  onDecisionSubmitted: () => void;
}

export function PendingReviewWorkspace({ detail, onDecisionSubmitted }: PendingReviewWorkspaceProps) {
  return (
    <section className="workspace-band">
      <CandidateComparison detail={detail} />
      <DecisionForm detail={detail} onSubmitted={onDecisionSubmitted} />
    </section>
  );
}
