import type { DocumentSummary } from "@/lib/api";

// The parse-failure card. A document the parser cannot read is a deliberate
// honest failure to surface, not something to hide: it renders whenever the API
// returns a non-null `parse_error` (legacy binary .doc, image-only PDF). The
// message shown is the real `parse_error` from the API, never invented text.
// No document in the current corpus triggers it.
export default function UnsupportedFileNotice({ document }: { document: DocumentSummary }) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3 px-5 py-3.5 bg-severity-high/[0.04]">
      <div className="flex items-start gap-3.5 min-w-0">
        <div className="w-8 h-8 rounded bg-severity-high/10 border border-severity-high/20 flex items-center justify-center shrink-0 text-severity-high">
          <span className="material-symbols-outlined text-[18px]">warning</span>
        </div>
        <div className="min-w-0">
          <div className="flex items-center gap-2.5 flex-wrap">
            <span className="text-[14px] font-medium text-text-main">{document.title}</span>
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-severity-medium/10 text-severity-medium">
              <span className="w-1.5 h-1.5 rounded-full bg-severity-medium" />
              Unsupported file type (.{document.file_type})
            </span>
          </div>
          <p className="text-[13px] text-text-secondary mt-0.5 max-w-2xl">
            {document.parse_error ??
              "This file could not be parsed for clauses. Re-export it as .docx or .pdf and re-ingest."}
          </p>
        </div>
      </div>
    </div>
  );
}
