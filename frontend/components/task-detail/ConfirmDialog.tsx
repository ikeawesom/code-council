"use client";

// Generic confirmation modal - used before approve (destructive-ish: it
// rewrites vault markdown and bumps a version), but written with no
// approve-specific copy so it can be reused anywhere a confirm step is needed.
export default function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel,
  cancelLabel = "Cancel",
  busy = false,
  error,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  cancelLabel?: string;
  busy?: boolean;
  error?: string | null;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-[2px] p-4">
      <div className="bg-surface border border-border-hairline rounded-lg shadow-2xl max-w-lg w-full p-6 flex flex-col gap-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-md bg-primary-subtle flex items-center justify-center shrink-0">
              <span className="material-symbols-outlined text-primary text-[20px]">edit_document</span>
            </div>
            <h3 className="text-[17px] font-semibold text-text-main tracking-tight">{title}</h3>
          </div>
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="text-text-muted hover:text-text-main transition-colors p-1"
          >
            <span className="material-symbols-outlined text-[20px]">close</span>
          </button>
        </div>

        <p className="text-[13.5px] text-text-secondary leading-relaxed">{description}</p>

        {error && <p className="text-[12.5px] text-severity-high">{error}</p>}

        <div className="flex items-center justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="px-3.5 py-2 rounded-md border border-border-hairline bg-surface hover:bg-surface-subtle transition-colors text-text-main text-[13px] font-medium disabled:opacity-50"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={busy}
            className="px-4 py-2 rounded-md bg-primary hover:bg-primary-hover text-white text-[13px] font-semibold shadow-sm transition-all flex items-center gap-1.5 disabled:opacity-60"
          >
            <span className="material-symbols-outlined text-[16px]">check</span>
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
