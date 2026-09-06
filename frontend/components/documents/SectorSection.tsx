import { sectorLabel } from "@/lib/sector";
import type { DocumentSummary } from "@/lib/api";
import DocumentRow from "./DocumentRow";
import UnsupportedFileNotice from "./UnsupportedFileNotice";

const SECTOR_ICON: Record<string, string> = {
  "real-estate": "holiday_village",
  "mergers-and-acquisition": "handshake",
  "energy-and-infrastructure": "bolt",
  general: "folder_special",
};

// Sectors are a plain string carried on documents.sector, never a fixed enum
// (see CLAUDE.md naming conventions) - unrecognised sectors fall back to a
// generic folder icon rather than breaking.
// Native <details>/<summary> gives free, uncontrolled collapse per section
// with zero client JS - matches "shortest thing that looks right on stage".
export default function SectorSection({
  sector,
  count,
  documents,
}: {
  sector: string;
  count: number;
  documents: DocumentSummary[];
}) {
  const icon = SECTOR_ICON[sector] ?? "folder";
  return (
    <details
      open
      className="group bg-surface rounded-lg border border-border-hairline shadow-sm overflow-hidden"
    >
      <summary className="flex items-center justify-between px-5 py-3.5 bg-surface-subtle/70 border-b border-border-hairline cursor-pointer select-none list-none [&::-webkit-details-marker]:hidden">
        <div className="flex items-center gap-3">
          <span className="material-symbols-outlined text-text-muted text-[19px] transition-transform group-open:rotate-180">
            expand_more
          </span>
          <span className="material-symbols-outlined text-primary text-[19px]">{icon}</span>
          <h2 className="text-[13px] font-semibold uppercase tracking-[0.08em] text-text-main">
            {sectorLabel(sector)}
          </h2>
          <span className="text-[11px] px-2 py-0.5 rounded bg-surface text-text-secondary border border-border-hairline font-medium">
            {count} document{count === 1 ? "" : "s"}
          </span>
        </div>
      </summary>
      <div className="flex flex-col divide-y divide-border-hairline/70">
        {documents.map((doc) =>
          doc.parse_error ? (
            <UnsupportedFileNotice key={doc.id} document={doc} />
          ) : (
            <DocumentRow key={doc.id} document={doc} />
          )
        )}
      </div>
    </details>
  );
}
