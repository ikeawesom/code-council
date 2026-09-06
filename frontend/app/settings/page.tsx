// Stub for the demo - settings (user roles, sector taxonomy, scrape schedule)
// is not part of the M4 scope.
export default function SettingsPage() {
  return (
    <div className="max-w-3xl mx-auto px-8 py-8">
      <div className="flex flex-col gap-2 pb-6 border-b border-border-hairline mb-6">
        <h1 className="text-[30px] font-medium text-text-main tracking-tight leading-tight">
          Settings
        </h1>
        <p className="text-[14.5px] text-text-secondary">
          Firm configuration is not part of this build.
        </p>
      </div>
      <div className="bg-surface border border-border-hairline rounded-lg p-10 text-center text-text-secondary text-[14px]">
        Settings will cover user roles, practice-sector taxonomy, and scrape scheduling in a future
        milestone.
      </div>
    </div>
  );
}
