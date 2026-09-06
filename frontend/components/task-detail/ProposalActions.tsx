"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { approveProposal, rejectProposal, type Proposal } from "@/lib/api";
import ConfirmDialog from "./ConfirmDialog";

// Approve/reject for one proposal. Approve goes through ConfirmDialog first
// (it rewrites vault markdown and bumps the document version); reject is a
// single click since it only flips a status. On success we call
// router.refresh() so the server-fetched page data (status, version) updates
// without a full client-side state model.
export default function ProposalActions({
  proposal,
  userId,
  documentTitle,
  documentVersion,
}: {
  proposal: Proposal;
  userId: number;
  documentTitle: string;
  documentVersion: number;
}) {
  const router = useRouter();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (proposal.status !== "pending") {
    const approved = proposal.status === "approved";
    return (
      <span
        className={
          "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[13px] font-medium " +
          (approved
            ? "bg-status-approved/10 text-status-approved"
            : "bg-status-dismissed/10 text-status-dismissed")
        }
      >
        <span className="material-symbols-outlined text-[16px]">
          {approved ? "check_circle" : "cancel"}
        </span>
        {approved ? "Approved" : "Rejected"}
      </span>
    );
  }

  async function handleReject() {
    setBusy(true);
    setError(null);
    const result = await rejectProposal(proposal.id, userId);
    setBusy(false);
    if (result === null) {
      setError("Could not reach the API - nothing was saved.");
      return;
    }
    router.refresh();
  }

  async function handleApprove() {
    setBusy(true);
    setError(null);
    const result = await approveProposal(proposal.id, userId);
    setBusy(false);
    if (result === null) {
      setError("Could not reach the API - nothing was saved.");
      return;
    }
    setConfirmOpen(false);
    router.refresh();
  }

  return (
    <div className="flex flex-wrap items-center gap-2.5">
      <button
        type="button"
        onClick={handleReject}
        disabled={busy}
        className="px-3.5 py-2 rounded-md bg-surface border border-border-hairline text-text-main hover:bg-surface-subtle transition-colors text-[13px] font-medium disabled:opacity-60"
      >
        Reject
      </button>
      <button
        type="button"
        onClick={() => setConfirmOpen(true)}
        disabled={busy}
        className="px-4 py-2 rounded-md bg-primary hover:bg-primary-hover text-white text-[13.5px] font-semibold shadow-sm transition-all flex items-center gap-1.5 disabled:opacity-60"
      >
        <span className="material-symbols-outlined text-[18px]">check_circle</span>
        Approve and update document
      </button>
      {error && <span className="text-[12.5px] text-severity-high">{error}</span>}

      <ConfirmDialog
        open={confirmOpen}
        title="Approve this amendment?"
        description={`Clause ${proposal.clause.number} of ${documentTitle} will be updated and saved as version ${
          documentVersion + 1
        }. Colleagues will be notified. You can review the change in the document's history afterwards.`}
        confirmLabel={busy ? "Approving..." : "Approve and update"}
        busy={busy}
        error={error}
        onConfirm={handleApprove}
        onCancel={() => setConfirmOpen(false)}
      />
    </div>
  );
}
