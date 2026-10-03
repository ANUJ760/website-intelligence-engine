"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Building2, Plus, ExternalLink, Trash2, Globe, Clock, AlertCircle, CheckCircle2 } from "lucide-react";
import { api, Company } from "@/lib/api";

export default function OverviewPage() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Form state
  const [name, setName] = useState("");
  const [domain, setDomain] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);

  async function loadData() {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getCompanies();
      setCompanies(data);
    } catch (err: any) {
      setError(err.message || "Failed to connect to backend API");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  async function handleCreateCompany(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim() || !domain.trim()) {
      setFormError("Both company name and domain are required.");
      return;
    }

    try {
      setSubmitting(true);
      setFormError(null);
      await api.createCompany(name.trim(), domain.trim());
      setName("");
      setDomain("");
      setShowAddModal(false);
      await loadData();
    } catch (err: any) {
      setFormError(err.message || "Failed to register company");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDeleteCompany(id: number, compName: string) {
    if (!confirm(`Are you sure you want to hard-delete "${compName}" and all associated pages, snapshots, and diffs?`)) {
      return;
    }

    try {
      await api.deleteCompany(id);
      await loadData();
    } catch (err: any) {
      alert(`Deletion rejected: ${err.message}`);
    }
  }

  return (
    <div className="space-y-8">
      {/* Top Banner & Stats */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200 pb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Overview & Companies</h1>
          <p className="text-sm text-slate-500 mt-1">
            Register and monitor B2B target websites, track snapshots, and identify business shifts.
          </p>
        </div>

        <button
          onClick={() => setShowAddModal(true)}
          className="inline-flex items-center space-x-2 bg-indigo-600 hover:bg-indigo-700 text-white font-medium px-4 py-2 rounded-lg text-sm transition shadow-sm"
        >
          <Plus className="h-4 w-4" />
          <span>Register Company</span>
        </button>
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 text-red-700 rounded-lg flex items-center space-x-3 text-sm">
          <AlertCircle className="h-5 w-5 flex-shrink-0" />
          <div>{error}</div>
        </div>
      )}

      {/* Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm flex items-center space-x-4">
          <div className="p-3 bg-indigo-50 text-indigo-600 rounded-lg">
            <Building2 className="h-6 w-6" />
          </div>
          <div>
            <div className="text-2xl font-bold text-slate-900">{companies.length}</div>
            <div className="text-xs font-medium text-slate-500 uppercase tracking-wider">Registered Companies</div>
          </div>
        </div>

        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm flex items-center space-x-4">
          <div className="p-3 bg-emerald-50 text-emerald-600 rounded-lg">
            <CheckCircle2 className="h-6 w-6" />
          </div>
          <div>
            <div className="text-2xl font-bold text-slate-900">Active</div>
            <div className="text-xs font-medium text-slate-500 uppercase tracking-wider">Engine Operational</div>
          </div>
        </div>

        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm flex items-center space-x-4">
          <div className="p-3 bg-amber-50 text-amber-600 rounded-lg">
            <Clock className="h-6 w-6" />
          </div>
          <div>
            <div className="text-2xl font-bold text-slate-900">24h</div>
            <div className="text-xs font-medium text-slate-500 uppercase tracking-wider">Default Crawl Interval</div>
          </div>
        </div>
      </div>

      {/* Companies List */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-200 flex justify-between items-center">
          <h2 className="text-base font-semibold text-slate-900">Monitored Companies</h2>
          <span className="text-xs text-slate-500 font-medium">{companies.length} total</span>
        </div>

        {loading ? (
          <div className="p-12 text-center text-slate-500 text-sm">Loading registered companies...</div>
        ) : companies.length === 0 ? (
          <div className="p-12 text-center space-y-3">
            <Building2 className="h-10 w-10 text-slate-300 mx-auto" />
            <div className="text-sm font-medium text-slate-900">No companies registered yet</div>
            <p className="text-xs text-slate-500 max-w-sm mx-auto">
              Register your first company to begin monitoring its public website pages and detecting content changes.
            </p>
            <button
              onClick={() => setShowAddModal(true)}
              className="mt-2 inline-flex items-center space-x-2 bg-indigo-600 text-white px-3 py-1.5 rounded-lg text-xs font-medium"
            >
              <Plus className="h-3.5 w-3.5" />
              <span>Register Company</span>
            </button>
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {companies.map((company) => (
              <div
                key={company.id}
                className="px-6 py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:bg-slate-50 transition"
              >
                <div className="space-y-1">
                  <div className="flex items-center space-x-3">
                    <Link
                      href={`/companies/${company.id}`}
                      className="font-semibold text-slate-900 hover:text-indigo-600 transition"
                    >
                      {company.name}
                    </Link>
                    <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-xs font-mono bg-slate-100 text-slate-600">
                      <Globe className="h-3 w-3 text-slate-400" />
                      <span>{company.domain}</span>
                    </span>
                  </div>
                  <div className="text-xs text-slate-400">
                    Registered: {new Date(company.created_at).toLocaleString()}
                  </div>
                </div>

                <div className="flex items-center space-x-3">
                  <Link
                    href={`/companies/${company.id}`}
                    className="inline-flex items-center space-x-1.5 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-medium transition"
                  >
                    <span>Inspect</span>
                    <ExternalLink className="h-3 w-3" />
                  </Link>

                  <button
                    onClick={() => handleDeleteCompany(company.id, company.name)}
                    className="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition"
                    title="Hard Delete Company"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Register Company Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl border border-slate-200 w-full max-w-md overflow-hidden animate-in fade-in zoom-in-95 duration-100">
            <div className="px-6 py-4 border-b border-slate-200 flex justify-between items-center">
              <h3 className="font-semibold text-slate-900 text-base">Register Target Company</h3>
              <button
                onClick={() => setShowAddModal(false)}
                className="text-slate-400 hover:text-slate-600 text-sm font-semibold"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateCompany} className="p-6 space-y-4">
              {formError && (
                <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-xs flex items-center space-x-2">
                  <AlertCircle className="h-4 w-4 flex-shrink-0" />
                  <div>{formError}</div>
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                  Company Name
                </label>
                <input
                  type="text"
                  placeholder="e.g. Acme Corporation"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                  Primary Domain
                </label>
                <input
                  type="text"
                  placeholder="e.g. acme.com"
                  value={domain}
                  onChange={(e) => setDomain(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                  required
                />
                <p className="text-xs text-slate-500 mt-1">Enter domain without http:// or www.</p>
              </div>

              <div className="pt-2 flex justify-end space-x-3">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 border border-slate-300 text-slate-700 rounded-lg text-sm font-medium hover:bg-slate-50 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium transition disabled:opacity-50"
                >
                  {submitting ? "Registering..." : "Save Company"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
