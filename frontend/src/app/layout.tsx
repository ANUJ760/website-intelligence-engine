import "./globals.css";
import Link from "next/link";
import { Activity, Building2, Sliders, ShieldCheck } from "lucide-react";

export const metadata = {
  title: "Website Intelligence Engine",
  description: "Local-first B2B website monitoring and change-intelligence engine.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen flex flex-col bg-slate-50 text-slate-900">
        <header className="bg-white border-b border-slate-200 sticky top-0 z-30">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex justify-between items-center h-16">
            <div className="flex items-center space-x-3">
              <div className="p-2 bg-indigo-600 rounded-lg text-white">
                <Activity className="h-5 w-5" />
              </div>
              <div>
                <Link href="/" className="font-bold text-lg text-slate-900 tracking-tight hover:text-indigo-600">
                  Website Intelligence Engine
                </Link>
                <div className="text-xs text-slate-500 font-medium">B2B Website Change & Signal Monitor</div>
              </div>
            </div>

            <nav className="flex items-center space-x-6">
              <Link
                href="/"
                className="flex items-center space-x-2 text-sm font-medium text-slate-600 hover:text-indigo-600 transition"
              >
                <Building2 className="h-4 w-4" />
                <span>Companies</span>
              </Link>
              <Link
                href="/settings"
                className="flex items-center space-x-2 text-sm font-medium text-slate-600 hover:text-indigo-600 transition"
              >
                <Sliders className="h-4 w-4" />
                <span>Settings</span>
              </Link>
              <div className="flex items-center space-x-1.5 px-2.5 py-1 bg-emerald-50 text-emerald-700 rounded-full text-xs font-semibold border border-emerald-200">
                <ShieldCheck className="h-3.5 w-3.5" />
                <span>SSRF Protected</span>
              </div>
            </nav>
          </div>
        </header>

        <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {children}
        </main>

        <footer className="border-t border-slate-200 bg-white py-4 mt-auto text-center text-xs text-slate-500">
          Website Intelligence Engine &bull; Local-first Single-Tenant Application &bull; Strictly Distinguishes Observed Facts from AI Inferences
        </footer>
      </body>
    </html>
  );
}
