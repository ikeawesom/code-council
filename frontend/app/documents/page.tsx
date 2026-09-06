import { getDocuments } from "@/lib/api";
import EmptyState from "@/components/ui/EmptyState";
import SectorSection from "@/components/documents/SectorSection";

// Screen 5: the vault grouped by practice area. Sectors and counts come
// straight from GET /api/documents - never a hard-coded taxonomy.
export default async function DocumentsPage() {
  const data = await getDocuments();

  if (data === null) {
    return (
      <div className="max-w-6xl mx-auto px-8 py-8">
        <EmptyState
          icon="cloud_off"
          heading="Can't reach the Code Council API"
          description="Start the backend (uvicorn app.main:app --reload --port 8000 from backend/) and refresh to load the vault."
        />
      </div>
    );
  }

  const totalDocs = data.sectors.reduce((sum, s) => sum + s.count, 0);

  return (
    <div className="max-w-6xl mx-auto px-8 py-8">
      <div className="flex flex-col gap-1 pb-6 border-b border-border-hairline mb-6">
        <h1 className="text-[30px] font-medium text-text-main tracking-tight leading-tight">
          Documents
        </h1>
        <p className="text-[14.5px] text-text-secondary">
          {totalDocs} document{totalDocs === 1 ? "" : "s"} in the vault across {data.sectors.length}{" "}
          practice sector{data.sectors.length === 1 ? "" : "s"}
        </p>
      </div>

      {data.sectors.length === 0 ? (
        <EmptyState
          icon="folder_off"
          heading="The vault is empty"
          description="Ingest documents into data/inbox/<practice-sector>/ and run scripts/ingest.py to populate it."
        />
      ) : (
        <div className="flex flex-col gap-4">
          {data.sectors.map((s) => (
            <SectorSection key={s.sector} sector={s.sector} count={s.count} documents={s.documents} />
          ))}
        </div>
      )}
    </div>
  );
}
