import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { identifierLabel } from "../utils/displayText";

interface DraftProtectionDialogProps {
  intakeId: string;
  updatedAt: string;
  status: "collecting" | "needs_confirmation";
  onContinueEditing: () => void;
  onDiscardAndLeave: () => void;
  onSaveAndLeave: () => void;
  onCancel: () => void;
}

export function DraftProtectionDialog({
  intakeId,
  updatedAt,
  status,
  onContinueEditing,
  onDiscardAndLeave,
  onSaveAndLeave,
  onCancel,
}: DraftProtectionDialogProps) {
  const saveRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    saveRef.current?.focus();
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
        aria-label="未保存的任务录入草稿"
      >
        <h3>未保存的任务录入草稿</h3>
        <p>
          当前存在尚未确认成任务的录入草稿 <strong>{intakeId}</strong>。
        </p>
        <div className="draft-dialog-meta">
          <span>
            最后更新：<strong>{updatedAt}</strong>
          </span>
          <span>
            状态：<strong>{identifierLabel(status)}</strong>
          </span>
        </div>
        <div className="draft-dialog-actions">
          <button type="button" className="text-button" onClick={onCancel}>
            取消
          </button>
          <button type="button" className="secondary-button danger-text" onClick={onDiscardAndLeave}>
            丢弃并离开
          </button>
          <button type="button" ref={saveRef} onClick={onSaveAndLeave}>
            保存并离开
          </button>
          <button type="button" className="secondary-button" onClick={onContinueEditing}>
            继续编辑
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
