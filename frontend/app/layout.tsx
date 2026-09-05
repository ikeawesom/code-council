import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Lex Sentinel",
  description: "Parliamentary change monitor for Singapore law firms",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  // TODO(M4): shell = sidebar nav + user switcher + notification bell
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-50 text-slate-900">{children}</body>
    </html>
  );
}
