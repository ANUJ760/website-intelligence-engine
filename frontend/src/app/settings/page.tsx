"use client";

import { useEffect, useState } from "react";
import { Sliders, ShieldCheck, Database, Cpu, HardDrive, CheckCircle2, AlertCircle } from "lucide-react";
import { api } from "@/lib/api";

export default function SettingsPage() {
  const [health, setHealth] = useState<{ status: string; database: string } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function checkHealth() {
      try {
        const data = await api.getHealth();
        setHealth(data);
      } catch (err) {
        setHealth({ status: "unreachable", database: "disconnected" });
      } finally {
        setLoading(false);
      }
    }
    checkHealth();
  }, []);

  return (
    <div className="space-y-8 max-w-4xl">
      <div className="border-b border-slate-200 pb-6">
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">System Settings & Status</h1>
        <p className="text-sm text-slate-500 mt-1">
          Review application health, local storage boundaries, and security parameters.
        </p>
      </div>

      {/* Health Overview */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-4">
        <h2 className="text-base font-semibold text-slate-900 flex items-center space-x-2">
          <Cpu className="h-5 w-5 text-indigo-600" />
          <span>Application Runtime Health</span>
        </h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
          <div className="p-4 bg-slate-50 rounded-lg border border-slate-200 flex items-center justify-between">
            <div>
              <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">FastAPI Backend</div>
              <div className="text-sm font-bold text-slate-900 mt-0.5">
                {loading ? "Checking..." : health?.status === "healthy" ? "Healthy (127.0.0.1:8000)" : "Unavailable"}
              </div>
            </div>
            {health?.status === "healthy" ? (
              <CheckCircle2 className="h-5 w-5 text-emerald-600" />
            ) : (
              <AlertCircle className="h-5 w-5 text-amber-500" />
            )}
          </div>

          <div className="p-4 bg-slate-50 rounded-lg border border-slate-200 flex items-center justify-between">
            <div>
              <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">SQLite Database</div>
              <div className="text-sm font-bold text-slate-900 mt-0.5 capitalize">
                {loading ? "Checking..." : health?.database || "Unknown"}
              </div>
            </div>
            {health?.database === "connected" ? (
              <Database className="h-5 w-5 text-emerald-600" />
            ) : (
              <AlertCircle className="h-5 w-5 text-amber-500" />
            )}
          </div>
        </div>
      </div>

      {/* Security & SSRF Rules */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-4">
        <h2 className="text-base font-semibold text-slate-900 flex items-center space-x-2">
          <ShieldCheck className="h-5 w-5 text-emerald-600" />
          <span>Active SSRF & Politeness Protections</span>
        </h2>

        <div className="text-xs text-slate-600 space-y-2 leading-relaxed">
          <p>
            &bull; <strong>Scheme & Port Whitelist:</strong> Only <code className="text-indigo-600 font-mono">http</code> and{" "}
            <code className="text-indigo-600 font-mono">https</code> on ports 80 and 443 are permitted.
          </p>
          <p>
            &bull; <strong>Private IP & Metadata Rejection:</strong> Loopback (127.0.0.1), RFC1918 private networks,
            link-local cloud metadata (169.254.169.254), IPv4-mapped IPv6, and CGNAT are rejected prior to any TCP connection.
          </p>
          <p>
            &bull; <strong>DNS Rebinding Defense:</strong> Target hostnames are resolved once and TCP connections are pinned directly to the validated IP.
          </p>
          <p>
            &bull; <strong>Robots.txt & Politeness:</strong> Every origin&apos;s <code className="text-indigo-600 font-mono">robots.txt</code> is respected with a mandatory 2s domain delay.
          </p>
        </div>
      </div>

      {/* Storage and AI Configuration */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-4">
        <h2 className="text-base font-semibold text-slate-900 flex items-center space-x-2">
          <HardDrive className="h-5 w-5 text-indigo-600" />
          <span>Storage & AI Settings</span>
        </h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs text-slate-700">
          <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 space-y-1">
            <span className="font-semibold text-slate-500">Database Engine</span>
            <div className="font-mono text-slate-900">SQLite (WAL mode, busy_timeout=5000, FK=ON)</div>
          </div>

          <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 space-y-1">
            <span className="font-semibold text-slate-500">Local Snapshot Path</span>
            <div className="font-mono text-slate-900">backend/storage/snapshots/</div>
          </div>

          <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 space-y-1">
            <span className="font-semibold text-slate-500">AI Classification Interface</span>
            <div className="font-mono text-slate-900">Active (Rule-based & LLM fallback)</div>
          </div>

          <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 space-y-1">
            <span className="font-semibold text-slate-500">Controlled Vocabulary</span>
            <div className="font-mono text-slate-900">8 Standard B2B Signal Types</div>
          </div>
        </div>
      </div>
    </div>
  );
}
