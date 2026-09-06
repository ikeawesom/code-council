// Sector display helper, deliberately in a plain module rather than in
// Sidebar.tsx: Sidebar is a client component, and AppShell (a server
// component that wraps every route) calls this. Exporting it from a
// "use client" file made every page render throw at request time - which
// neither `tsc` nor `next build` catches, because these routes are only
// rendered on demand.
//
// Sectors are a plain string carried on documents.sector, never a fixed enum
// (see CLAUDE.md naming conventions).
export function sectorLabel(sector: string): string {
  return sector
    .split("-")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}
