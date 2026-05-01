import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";

interface DraftProtectionDialogProps {
  intakeId: string;
  updatedAt: string;
  status: "collecting" | "needs_confirmation";
  onContinueEditing: () => void;
  onDiscardAndNew: () => void;
  onCancel: () => void;
}

export function DraftProtectionDialog({
  intakeId,
  updatedAt,
  status,
  onContinueEditing,
  onDiscardAndNew,
  onCancel,
}: DraftProtectionDialogProps) {
  const continueRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    continueRef.current?.focus();
  }, []);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onCancel();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onCancel]);

  return createPortal(
    <div className="draft-dialog-backdrop" role="presentation">
      <div
        className="draft-dialog"
        role="alertdialog"
        aria-modal="true"
        aria-label="Unsaved Intake Draft"
      >
        <h3>Unsaved Intake Draft</h3>
        <p>
          You have an active intake draft{" "}
          <strong>{intakeId}</strong> that has not been confirmed as a task.
        </p>
        <div className="draft-dialog-meta">
          <span>
            Last updated: <strong>{updatedAt}</strong>
          </span>
          <span>
            Status: <strong>{status.replace(/_/g, " ")}</strong>
          </span>
        </div>
        <div className="draft-dialog-actions">
          <button type="button" className="text-button" onClick={onCancel}>
            Cancel
          </button>
          <button type="button" className="secondary-button" onClick={onDiscardAndNew}>
            Discard &amp; New
          </button>
          <button ref={continueRef} onClick={onContinueEditing}>
            Continue Editing
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
