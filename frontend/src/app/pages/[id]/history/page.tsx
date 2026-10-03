"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Clock, FileText, GitCompare, Hash, AlertCircle } from "lucide-react";
import { api, PageHistoryResponse, SnapshotItem, ChangeEventItem } from "@/lib/api";

export default function PageHistoryPage() {
  const params = useParams();
  const pageId = Number(params.id);

  const [history, setHistory] = useState<PageHistoryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Selected snapshot to view text
  const [selectedSnapshot, setSelectedSnapshot] = useState<SnapshotItem | null>(null);

  async function loadHistory() {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getPageHistory(pageId);
      setHistory(data);
      if (data.snapshots.length > 0) {
        setSelectedSnapshot(data.snapshots[0]);
      }
    } catch (err: any) {
      setError(err.message || "Failed to load page history");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (pageId) {
      loadHistory();
    }
  }, [pageId]);

  if (loading) {
    return <div className="p-12 text-center text-slate-500 text-sm">Loading page history & diffs...</div>;
  }

  if (error || !history) {
    return (
      <div className="p-8 max-w-lg mx-auto bg-white rounded-xl border border-red-200 text-center space-y-4">
        <AlertCircle className="h-8 w-8 text-red-500 mx-auto" />
        <div className="text-base font-semibold text-slate-900">Failed to load history</div>
        <p className="text-xs text-slate-500">{error || "Page history not found"}</p>
        <button
          onClick={() => window.history.back()}
          className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-xs font-medium"
        >
          Go Back
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Top Header */}
      <div>
        <button
          onClick={() => window.history.back()}
          className="inline-flex items-center space-x-1.5 text-xs font-semibold text-slate-500 hover:text-indigo-600 mb-4 transition"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          <span>Back to Company</span>
        </button>

        <div className="border-b border-slate-200 pb-4">
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Page Snapshot & Change History</h1>
          <p className="text-sm text-slate-500 mt-1">
            Review immutable snapshot records, plain-text comparisons, and detected content differences.
          </p>
        </div>
      </div>

      {/* Detected Changes / Diffs Section */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <GitCompare className="h-4 w-4 text-indigo-600" />
            <h2 className="text-base font-semibold text-slate-900">Detected Changes & Diff Excerpts</h2>
          </div>
          <span className="text-xs text-slate-500 font-medium">{history.changes.length} change events</span>
        </div>

        {history.changes.length === 0 ? (
          <div className="p-8 text-center text-slate-500 text-xs">
            No changes have been detected on this page yet. All successful crawls match the baseline snapshot.
          </div>
        ) : (
          <div className="divide-y divide-slate-200">
            {history.changes.map((c) => (
              <div key={c.id} className="p-6 space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center space-x-2.5">
                    <span
                      className={`px-2 py-0.5 rounded text-xs font-bold ${
                        c.is_meaningful
                          ? "bg-amber-50 text-amber-700 border border-amber-200"
                          : "bg-slate-100 text-slate-600"
                      }`}
                    >
                      {c.is_meaningful ? "Meaningful Change" : "Noise / Minor"}
                    </span>
                    <span className="text-sm font-semibold text-slate-900">{c.change_summary}</span>
                  </div>
                  <div className="text-xs text-slate-400">
                    Detected: {new Date(c.detected_at).toLocaleString()}
                  </div>
                </div>

                {/* Diff Viewer (Strictly Plain Text / Never injected as HTML per §12) */}
                {c.diff_text && (
                  <div className="bg-slate-950 text-slate-100 p-4 rounded-lg overflow-x-auto text-xs font-mono border border-slate-800 max-h-96">
                    <pre className="whitespace-pre">
                      {c.diff_text.split("\n").map((line, lIdx) => {
                        let lineStyle = "text-slate-400";
                        if (line.startsWith("+") && !line.startsWith("+++")) {
                          lineStyle = "text-emerald-400 bg-emerald-950/40 px-1";
                        } else if (line.startsWith("-") && !line.startsWith("---")) {
                          lineStyle = "text-rose-400 bg-rose-950/40 px-1";
                        } else if (line.startsWith("@@")) {
                          lineStyle = "text-indigo-400 font-bold";
                        }
                        return (
                          <div key={lIdx} className={lineStyle}>
                            {line}
                          </div>
                        );
                      })}
                    </pre>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Snapshots History Section */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <FileText className="h-4 w-4 text-indigo-600" />
            <h2 className="text-base font-semibold text-slate-900">Historical Text Snapshots</h2>
          </div>
          <span className="text-xs text-slate-500 font-medium">{history.snapshots.length} snapshots</span>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 divide-y lg:divide-y-0 lg:divide-x divide-slate-200">
          {/* Snapshots List */}
          <div className="divide-y divide-slate-100 max-h-[500px] overflow-y-auto">
            {history.snapshots.length === 0 ? (
              <div className="p-8 text-center text-slate-500 text-xs">No snapshots recorded yet.</div>
            ) : (
              history.snapshots.map((s, idx) => (
                <div
                  key={s.id}
                  onClick={() => setSelectedSnapshot(s)}
                  className={`p-4 cursor-pointer transition ${
                    selectedSnapshot?.id === s.id ? "bg-indigo-50/70 border-l-4 border-indigo-600" : "hover:bg-slate-50"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-xs text-slate-900">
                      Snapshot #{s.id} {idx === history.snapshots.length - 1 && "(Baseline)"}
                    </span>
                    <span className="text-[11px] text-slate-400">
                      {new Date(s.captured_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    </span>
                  </div>

                  <div className="text-xs text-slate-600 truncate mt-1">{s.title || "Untitled Page"}</div>

                  <div className="flex items-center space-x-1 mt-2 text-[11px] text-slate-400 font-mono">
                    <Hash className="h-3 w-3" />
                    <span>{s.content_hash.slice(0, 16)}...</span>
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Snapshot Content Viewer */}
          <div className="p-6 lg:col-span-2 space-y-3 bg-slate-50/50">
            {selectedSnapshot ? (
              <>
                <div className="flex items-center justify-between border-b border-slate-200 pb-3">
                  <div>
                    <h3 className="text-sm font-semibold text-slate-900">
                      {selectedSnapshot.title || `Snapshot #${selectedSnapshot.id}`}
                    </h3>
                    <div className="text-xs text-slate-400">
                      Captured: {new Date(selectedSnapshot.captured_at).toLocaleString()}
                    </div>
                  </div>
                  <span className="text-xs font-mono bg-white px-2 py-1 rounded border border-slate-200 text-slate-600">
                    Hash: {selectedSnapshot.content_hash.slice(0, 12)}
                  </span>
                </div>

                <div className="bg-white p-4 rounded-lg border border-slate-200 max-h-[400px] overflow-y-auto">
                  <pre className="text-xs font-mono text-slate-800 whitespace-pre-wrap">
                    {selectedSnapshot.content_text || "No text body available for this snapshot."}
                  </pre>
                </div>
              </>
            ) : (
              <div className="text-center py-20 text-xs text-slate-400">
                Select a snapshot on the left to inspect its normalized extracted content.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
