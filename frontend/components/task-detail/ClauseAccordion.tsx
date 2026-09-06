"use client";

import { useState } from "react";
import type { Proposal } from "@/lib/api";
import RedlineDiff from "./RedlineDiff";
import ProposalActions from "./ProposalActions";

const STATUS_LABEL: Record<Proposal["status"], string> = {
  pending: "Pending",
  approved: "Approved",
  rejected: "Rejected",
};

// Screen 3 - any proposal beyond the primary one, collapsed by default.
export default function ClauseAccordion({
  proposal,
  documentTitle,
  documentVersion,
  userId,
}: {
  proposal: Proposal;
  documentTitle: string;
  documentVersion: number;
  userId: number;
}) {
  const [open, setOpen] = useState(false);

  return (
    <section className="bg-surface border border-border-hairline rounded-lg p-5 shadow-sm transition-all">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between gap-3 text-left"
      >
        <div className="flex items-start gap-3">
          <span
            className={`material-symbols-outlined text-text-muted text-[20px] transition-transform duration-200 ${
              open ? "rotate-180" : ""
            }`}
          >
            expand_more
          </span>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="text-[15px] font-semibold text-text-main">
                Clause {proposal.clause.number} &mdash; {proposal.clause.heading}
              </h3>
              <span className="px-2 py-0.5 text-[11px] font-medium bg-surface-subtle text-text-secondary border border-border-hairline rounded">
                {STATUS_LABEL[proposal.status]}
              </span>
            </div>
          </div>
        </div>
        <span className="px-3 py-1.5 rounded-md border border-border-hairline text-text-main text-[12.5px] font-medium shrink-0">
          {open ? "Collapse" : "Expand clause"}
        </span>
      </button>

      {open && (
        <div className="mt-4 pt-4 border-t border-border-hairline flex flex-col gap-4">
          <div className="bg-surface-subtle border border-border-hairline rounded-md p-4">
            <RedlineDiff diff={proposal.diff} />
          </div>
          <p className="text-[13.5px] text-text-secondary leading-relaxed">{proposal.rationale}</p>
          <ProposalActions
            proposal={proposal}
            userId={userId}
            documentTitle={documentTitle}
            documentVersion={documentVersion}
          />
        </div>
      )}
    </section>
  );
}
