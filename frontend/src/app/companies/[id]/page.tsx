"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  Building2,
  Globe,
  Plus,
  Play,
  History,
  Trash2,
  ArrowLeft,
  AlertCircle,
  CheckCircle2,
  Sparkles,
  ExternalLink,
  Info,
  Clock,
} from "lucide-react";
import { api, Company, MonitoredPage, BusinessSignal } from "@/lib/api";

export default function CompanyDetailPage() {
  const params = useParams();
  const router = useRouter();
  const companyId = Number(params.id);

  const [company, setCompany] = useState<Company | null>(null);
  const [pages, setPages] = useState<MonitoredPage[]>([]);
  const [signals, setSignals] = useState<BusinessSignal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Add Page Modal
  const [showAddPage, setShowAddPage] = useState(false);
  const [pageUrl, setPageUrl] = useState("");
  const [pageType, setPageType] = useState("homepage");
  const [intervalHours, setIntervalHours] = useState(24);
  const [submittingPage, setSubmittingPage] = useState(false);
  const [pageError, setPageError] = useState<string | null>(null);

  // Crawl trigger status message
  const [crawlStatus, setCrawlStatus] = useState<{ pageId: number; text: string; error?: boolean } | null>(null);

  async function loadAll() {
    try {
      setLoading(true);
      setError(null);
      const [compData, pagesData, signalsData] = await Promise.all([
        api.getCompany(companyId),
        api.getCompanyPages(companyId),
        api.getCompanySignals(companyId),
      ]);
      setCompany(compData);
      setPages(pagesData);
      setSignals(signalsData);
    } catch (err: any) {
      setError(err.message || "Failed to load company details");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (companyId) {
      loadAll();
    }
  }, [companyId]);

  async function handleAddPage(e: React.FormEvent) {
    e.preventDefault();
    if (!pageUrl.trim()) {
      setPageError("Page URL is required.");
      return;
    }

    try {
      setSubmittingPage(true);
      setPageError(null);
      await api.addPage(companyId, pageUrl.trim(), pageType, intervalHours);
      setPageUrl("");
      setPageType("homepage");
      setIntervalHours(24);
      setShowAddPage(false);
      await loadAll();
    } catch (err: any) {
      setPageError(err.message || "Failed to add monitored page");
    } finally {
      setSubmittingPage(false);
    }
  }

  async function handleTriggerCrawl(pageId: number) {
    try {
      setCrawlStatus({ pageId, text: "Queueing crawl..." });
      const res = await api.triggerManualCrawl(pageId);
      setCrawlStatus({ pageId, text: res.message || "Crawl queued successfully!" });
      setTimeout(() => setCrawlStatus(null), 4000);
      await loadAll();
    } catch (err: any) {
      setCrawlStatus({ pageId, text: err.message || "Crawl failed to queue", error: true });
      setTimeout(() => setCrawlStatus(null), 5000);
    }
  }

  async function handleDeleteCompany() {
    if (!company) return;
    if (!confirm(`Are you sure you want to delete ${company.name}? This will remove all monitored pages, snapshots, and diffs permanently.`)) {
      return;
    }

    try {
      await api.deleteCompany(companyId);
      router.push("/");
    } catch (err: any) {
      alert(`Delete failed: ${err.message}`);
    }
  }

  if (loading) {
    return <div className="p-12 text-center text-slate-500 text-sm">Loading company data...</div>;
  }

  if (error || !company) {
    return (
      <div className="p-8 max-w-lg mx-auto bg-white rounded-xl border border-red-200 text-center space-y-4">
        <AlertCircle className="h-8 w-8 text-red-500 mx-auto" />
        <div className="text-base font-semibold text-slate-900">Failed to load company</div>
        <p className="text-xs text-slate-500">{error || "Company not found"}</p>
        <Link href="/" className="inline-block px-4 py-2 bg-indigo-600 text-white rounded-lg text-xs font-medium">
          Return to Overview
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Navigation & Header */}
      <div>
        <Link
          href="/"
          className="inline-flex items-center space-x-1.5 text-xs font-semibold text-slate-500 hover:text-indigo-600 mb-4 transition"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          <span>Back to All Companies</span>
        </Link>

        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200 pb-6">
          <div className="space-y-1">
            <div className="flex items-center space-x-3">
              <h1 className="text-2xl font-bold text-slate-900 tracking-tight">{company.name}</h1>
              <a
                href={`https://${company.domain}`}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded text-xs font-mono bg-slate-100 text-slate-700 hover:bg-slate-200 transition"
              >
                <Globe className="h-3 w-3 text-slate-400" />
                <span>{company.domain}</span>
                <ExternalLink className="h-2.5 w-2.5 text-slate-400" />
              </a>
            </div>
            <div className="text-xs text-slate-400">
              Registered on {new Date(company.created_at).toLocaleString()}
            </div>
          </div>

          <div className="flex items-center space-x-3">
            <button
              onClick={() => setShowAddPage(true)}
              className="inline-flex items-center space-x-2 bg-indigo-600 hover:bg-indigo-700 text-white font-medium px-4 py-2 rounded-lg text-sm transition shadow-sm"
            >
              <Plus className="h-4 w-4" />
              <span>Add Page</span>
            </button>

            <button
              onClick={handleDeleteCompany}
              className="inline-flex items-center space-x-1.5 px-3 py-2 border border-red-200 text-red-600 hover:bg-red-50 rounded-lg text-sm font-medium transition"
              title="Hard Delete Company"
            >
              <Trash2 className="h-4 w-4" />
              <span>Delete</span>
            </button>
          </div>
        </div>
      </div>

      {/* Monitored Pages Section */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-200 flex justify-between items-center">
          <h2 className="text-base font-semibold text-slate-900">Monitored Pages</h2>
          <span className="text-xs text-slate-500 font-medium">{pages.length} pages</span>
        </div>

        {pages.length === 0 ? (
          <div className="p-8 text-center space-y-2">
            <div className="text-sm font-medium text-slate-900">No pages registered for {company.name}</div>
            <p className="text-xs text-slate-500">
              Add a URL (e.g. homepage, pricing, or product page) to establish an initial baseline.
            </p>
            <button
              onClick={() => setShowAddPage(true)}
              className="mt-2 inline-flex items-center space-x-1.5 bg-indigo-600 text-white px-3 py-1.5 rounded-lg text-xs font-medium"
            >
              <Plus className="h-3 w-3" />
              <span>Add First Page</span>
            </button>
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {pages.map((p) => (
              <div
                key={p.id}
                className="px-6 py-4 flex flex-col md:flex-row md:items-center justify-between gap-4 hover:bg-slate-50 transition"
              >
                <div className="space-y-1.5 max-w-xl">
                  <div className="flex items-center space-x-2.5">
                    <a
                      href={p.url}
                      target="_blank"
                      rel="noreferrer"
                      className="font-medium text-sm text-indigo-600 hover:underline break-all flex items-center space-x-1"
                    >
                      <span>{p.url}</span>
                      <ExternalLink className="h-3 w-3 flex-shrink-0" />
                    </a>
                    <span className="px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-700 capitalize">
                      {p.page_type}
                    </span>
                  </div>

                  <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
                    <span className="flex items-center space-x-1">
                      <Clock className="h-3 w-3 text-slate-400" />
                      <span>Interval: {p.crawl_interval_hours}h</span>
                    </span>
                    <span>Last Crawl: {p.last_crawled_at ? new Date(p.last_crawled_at).toLocaleString() : "Never"}</span>
                    <span>Next Due: {p.next_crawl_at ? new Date(p.next_crawl_at).toLocaleString() : "Pending"}</span>
                  </div>
                </div>

                <div className="flex items-center space-x-3">
                  {crawlStatus && crawlStatus.pageId === p.id && (
                    <span className={`text-xs font-medium ${crawlStatus.error ? "text-red-600" : "text-emerald-600"}`}>
                      {crawlStatus.text}
                    </span>
                  )}

                  <button
                    onClick={() => handleTriggerCrawl(p.id)}
                    className="inline-flex items-center space-x-1.5 px-3 py-1.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 rounded-lg text-xs font-semibold transition"
                  >
                    <Play className="h-3 w-3" />
                    <span>Trigger Crawl</span>
                  </button>

                  <Link
                    href={`/pages/${p.id}/history`}
                    className="inline-flex items-center space-x-1.5 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-medium transition"
                  >
                    <History className="h-3 w-3" />
                    <span>History & Diffs</span>
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Business Signals Section */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Sparkles className="h-4 w-4 text-indigo-600" />
            <h2 className="text-base font-semibold text-slate-900">Detected Business Signals</h2>
          </div>
          <span className="text-xs text-slate-500 font-medium">{signals.length} recorded</span>
        </div>

        {signals.length === 0 ? (
          <div className="p-8 text-center space-y-2">
            <div className="text-sm font-medium text-slate-900">No signals detected yet</div>
            <p className="text-xs text-slate-500 max-w-md mx-auto">
              Signals are recorded when monitored pages undergo meaningful content changes (such as product updates,
              pricing adjustments, or hiring shifts).
            </p>
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {signals.map((sig) => (
              <div key={sig.id} className="p-6 space-y-4 hover:bg-slate-50 transition">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center space-x-2">
                    <span className="px-2.5 py-1 rounded-md text-xs font-bold bg-indigo-50 text-indigo-700 border border-indigo-200">
                      {sig.signal_type}
                    </span>
                    <span className="text-xs text-slate-400">
                      Detected: {new Date(sig.created_at).toLocaleString()}
                    </span>
                  </div>

                  {sig.confidence !== null && (
                    <div className="text-xs text-slate-400 font-medium">
                      Model: {sig.model_name} (heuristic score: {Math.round(sig.confidence * 100)}%)
                    </div>
                  )}
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Observed Fact */}
                  <div className="p-4 bg-slate-50 rounded-lg border border-slate-200 space-y-1.5">
                    <div className="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center space-x-1.5">
                      <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                      <span>Observed Fact (From Page)</span>
                    </div>
                    <p className="text-xs text-slate-800 leading-relaxed font-sans">{sig.observed_change}</p>
                  </div>

                  {/* Inferred Implication */}
                  <div className="p-4 bg-indigo-50/50 rounded-lg border border-indigo-100 space-y-1.5">
                    <div className="text-xs font-bold text-indigo-700 uppercase tracking-wider flex items-center space-x-1.5">
                      <Info className="h-3.5 w-3.5 text-indigo-600" />
                      <span>Inferred Business Implication (Hypothesis)</span>
                    </div>
                    <p className="text-xs text-indigo-950 leading-relaxed font-sans">{sig.potential_implication}</p>
                  </div>
                </div>

                {/* Evidence quotes */}
                {sig.evidence && sig.evidence.length > 0 && (
                  <div className="space-y-1.5">
                    <div className="text-xs font-semibold text-slate-500">Cited Evidence (Verbatim Excerpts):</div>
                    <div className="flex flex-wrap gap-2">
                      {sig.evidence.map((quote, idx) => (
                        <div
                          key={idx}
                          className="px-2.5 py-1 bg-slate-100 text-slate-800 rounded text-xs font-mono border border-slate-200"
                        >
                          &ldquo;{quote}&rdquo;
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Add Page Modal */}
      {showAddPage && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl border border-slate-200 w-full max-w-md overflow-hidden animate-in fade-in zoom-in-95 duration-100">
            <div className="px-6 py-4 border-b border-slate-200 flex justify-between items-center">
              <h3 className="font-semibold text-slate-900 text-base">Add Monitored Page</h3>
              <button onClick={() => setShowAddPage(false)} className="text-slate-400 hover:text-slate-600 text-sm font-semibold">
                ✕
              </button>
            </div>

            <form onSubmit={handleAddPage} className="p-6 space-y-4">
              {pageError && (
                <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-xs flex items-center space-x-2">
                  <AlertCircle className="h-4 w-4 flex-shrink-0" />
                  <div>{pageError}</div>
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                  Page URL
                </label>
                <input
                  type="url"
                  placeholder="https://example.com/pricing"
                  value={pageUrl}
                  onChange={(e) => setPageUrl(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                  required
                />
                <p className="text-xs text-slate-500 mt-1">Must use http or https scheme. Private/local IPs will be rejected.</p>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                  Page Type
                </label>
                <select
                  value={pageType}
                  onChange={(e) => setPageType(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 bg-white"
                >
                  <option value="homepage">Homepage</option>
                  <option value="pricing">Pricing</option>
                  <option value="careers">Careers</option>
                  <option value="product">Product</option>
                  <option value="integrations">Integrations</option>
                  <option value="other">Other</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                  Crawl Interval (Hours)
                </label>
                <input
                  type="number"
                  min="1"
                  max="720"
                  value={intervalHours}
                  onChange={(e) => setIntervalHours(Number(e.target.value))}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                  required
                />
              </div>

              <div className="pt-2 flex justify-end space-x-3">
                <button
                  type="button"
                  onClick={() => setShowAddPage(false)}
                  className="px-4 py-2 border border-slate-300 text-slate-700 rounded-lg text-sm font-medium hover:bg-slate-50 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingPage}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium transition disabled:opacity-50"
                >
                  {submittingPage ? "Saving..." : "Add Page"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
