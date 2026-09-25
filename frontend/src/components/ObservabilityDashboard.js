"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import {
  Activity,
  Database,
  Server,
  Zap,
  Clock,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Terminal,
  Cpu,
  Layers,
  Copy,
  Check,
  Radio,
} from "lucide-react";

export default function ObservabilityDashboard({ activeOrg }) {
  const [diagnostics, setDiagnostics] = useState(null);
  const [metricsRaw, setMetricsRaw] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [lastRefreshed, setLastRefreshed] = useState(null);

  const fetchTelemetry = async () => {
    try {
      setLoading(true);
      setError("");
      const [diagData, metricsData] = await Promise.all([
        api.observability.getDiagnostics(),
        api.observability.getMetrics(),
      ]);
      setDiagnostics(diagData);
      setMetricsRaw(metricsData);
      setLastRefreshed(new Date().toLocaleTimeString());
    } catch (err) {
      setError(err.message || "Failed to fetch observability telemetry");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTelemetry();
  }, []);

  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(() => {
      fetchTelemetry();
    }, 5000);
    return () => clearInterval(interval);
  }, [autoRefresh]);

  const handleCopyMetrics = () => {
    if (!metricsRaw) return;
    navigator.clipboard.writeText(metricsRaw);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Parse key metrics from Prometheus output
  const parsePrometheusSummary = (raw) => {
    let uptime = 0;
    let totalRequests = 0;
    let requestCountsByStatus = {};

    if (!raw) return { uptime, totalRequests, requestCountsByStatus };

    const lines = raw.split("\n");
    for (const line of lines) {
      if (line.startsWith("#") || !line.trim()) continue;

      if (line.startsWith("system_uptime_seconds")) {
        const parts = line.split(" ");
        uptime = parseFloat(parts[1]) || 0;
      } else if (line.startsWith("http_requests_total")) {
        const match = line.match(/status="(\d+)"\}\s+([0-9.]+)/);
        if (match) {
          const status = match[1];
          const count = parseFloat(match[2]);
          totalRequests += count;
          requestCountsByStatus[status] = (requestCountsByStatus[status] || 0) + count;
        }
      }
    }

    return { uptime, totalRequests, requestCountsByStatus };
  };

  const summary = parsePrometheusSummary(metricsRaw);

  const formatUptime = (seconds) => {
    if (!seconds) return "0s";
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    if (hrs > 0) return `${hrs}h ${mins}m ${secs}s`;
    if (mins > 0) return `${mins}m ${secs}s`;
    return `${secs}s`;
  };

  return (
    <div className="space-y-6">
      {/* Top Banner & Control Bar */}
      <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-5 backdrop-blur-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-bold text-white flex items-center gap-2">
            <Activity className="h-5 w-5 text-indigo-400" />
            Observability & Production Diagnostics
          </h2>
          <p className="text-xs text-zinc-400 mt-1">
            Real-time multi-tenant telemetry: PostgreSQL pgvector health, Redis rate-limiting, and Prometheus metrics.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {lastRefreshed && (
            <span className="text-[11px] font-mono text-zinc-500">
              Updated: {lastRefreshed}
            </span>
          )}

          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium border transition-all ${
              autoRefresh
                ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                : "bg-zinc-800/60 border-zinc-700/50 text-zinc-400 hover:text-zinc-200"
            }`}
          >
            <Radio className={`h-3.5 w-3.5 ${autoRefresh ? "animate-pulse text-emerald-400" : ""}`} />
            Auto-refresh (5s)
          </button>

          <button
            onClick={fetchTelemetry}
            disabled={loading}
            className="flex items-center gap-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white px-3.5 py-1.5 rounded-xl text-xs font-semibold shadow-lg shadow-indigo-600/20 transition-all"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-950/20 p-4 text-xs text-red-300 flex items-center gap-3">
          <AlertTriangle className="h-4 w-4 text-red-400 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* KPI Overview Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* KPI 1: Application Health */}
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-4 backdrop-blur-xl">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-zinc-400">System Status</span>
            <CheckCircle2 className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="mt-2 text-xl font-bold text-white capitalize">
            {diagnostics?.status || (loading ? "Pinging..." : "Offline")}
          </div>
          <p className="text-[11px] text-zinc-500 mt-1">
            Env: <span className="font-mono text-zinc-300">{diagnostics?.environment || "development"}</span>
          </p>
        </div>

        {/* KPI 2: Total Uptime */}
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-4 backdrop-blur-xl">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-zinc-400">Process Uptime</span>
            <Clock className="h-4 w-4 text-indigo-400" />
          </div>
          <div className="mt-2 text-xl font-bold text-white font-mono">
            {formatUptime(summary.uptime)}
          </div>
          <p className="text-[11px] text-zinc-500 mt-1">Continuous daemon runtime</p>
        </div>

        {/* KPI 3: Requests Processed */}
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-4 backdrop-blur-xl">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-zinc-400">HTTP Requests</span>
            <Cpu className="h-4 w-4 text-amber-400" />
          </div>
          <div className="mt-2 text-xl font-bold text-white font-mono">
            {summary.totalRequests.toLocaleString()}
          </div>
          <div className="flex items-center gap-2 mt-1 text-[11px]">
            {Object.entries(summary.requestCountsByStatus).map(([status, cnt]) => (
              <span
                key={status}
                className={`font-mono px-1.5 py-0.5 rounded text-[10px] ${
                  status.startsWith("2")
                    ? "bg-emerald-500/10 text-emerald-400"
                    : status.startsWith("4")
                    ? "bg-amber-500/10 text-amber-400"
                    : "bg-red-500/10 text-red-400"
                }`}
              >
                {status}: {cnt}
              </span>
            ))}
          </div>
        </div>

        {/* KPI 4: Tenant Protection */}
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-4 backdrop-blur-xl">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-zinc-400">Rate Limiter</span>
            <ShieldCheck className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="mt-2 text-xl font-bold text-white">
            Active (Sliding)
          </div>
          <p className="text-[11px] text-zinc-500 mt-1">
            Backend: Redis + In-memory fallback
          </p>
        </div>
      </div>

      {/* Subsystems Diagnostics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Database & Vector */}
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-5 backdrop-blur-xl space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Database className="h-4 w-4 text-indigo-400" />
              <h3 className="text-xs font-semibold text-white">PostgreSQL & pgvector</h3>
            </div>
            <span
              className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${
                diagnostics?.subsystems?.database?.status === "healthy"
                  ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                  : "bg-red-500/10 text-red-400 border border-red-500/20"
              }`}
            >
              {diagnostics?.subsystems?.database?.status || "Unknown"}
            </span>
          </div>

          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1 border-b border-zinc-800/60 text-zinc-400">
              <span>Extension</span>
              <span className="font-mono text-zinc-200">
                pgvector {diagnostics?.subsystems?.database?.pgvector_version || "Enabled"}
              </span>
            </div>
            <div className="flex justify-between py-1 border-b border-zinc-800/60 text-zinc-400">
              <span>Ping Latency</span>
              <span className="font-mono text-emerald-400">
                {diagnostics?.subsystems?.database?.latency_ms ?? "--"} ms
              </span>
            </div>
            <div className="flex justify-between py-1 text-zinc-400">
              <span>Embedding Vector Dimension</span>
              <span className="font-mono text-zinc-200">768 (Cosine Distance)</span>
            </div>
          </div>
        </div>

        {/* Redis Cache & Rate Limiting */}
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-5 backdrop-blur-xl space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Server className="h-4 w-4 text-emerald-400" />
              <h3 className="text-xs font-semibold text-white">Redis Cache & Rate Limiting</h3>
            </div>
            <span
              className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${
                diagnostics?.subsystems?.redis_cache?.status === "healthy"
                  ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                  : "bg-amber-500/10 text-amber-400 border border-amber-500/20"
              }`}
            >
              {diagnostics?.subsystems?.redis_cache?.status || "Unknown"}
            </span>
          </div>

          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1 border-b border-zinc-800/60 text-zinc-400">
              <span>Mode</span>
              <span className="font-mono text-zinc-200">
                {diagnostics?.subsystems?.redis_cache?.mode || "Distributed ZSET"}
              </span>
            </div>
            <div className="flex justify-between py-1 border-b border-zinc-800/60 text-zinc-400">
              <span>Ping Latency</span>
              <span className="font-mono text-emerald-400">
                {diagnostics?.subsystems?.redis_cache?.latency_ms ?? "--"} ms
              </span>
            </div>
            <div className="flex justify-between py-1 text-zinc-400">
              <span>Sliding Window</span>
              <span className="font-mono text-zinc-200">60s rolling window</span>
            </div>
          </div>
        </div>

        {/* AI Model Adapters */}
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-5 backdrop-blur-xl space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Zap className="h-4 w-4 text-amber-400" />
              <h3 className="text-xs font-semibold text-white">AI Provider Adapters</h3>
            </div>
            <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              Active Fallback
            </span>
          </div>

          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1 border-b border-zinc-800/60 text-zinc-400">
              <span>Gemini Embeddings</span>
              <span className="font-mono text-zinc-200">
                {diagnostics?.subsystems?.ai_providers?.gemini?.default_embedding_model || "text-embedding-004"}
              </span>
            </div>
            <div className="flex justify-between py-1 border-b border-zinc-800/60 text-zinc-400">
              <span>Gemini LLM Chat</span>
              <span className="font-mono text-zinc-200">
                {diagnostics?.subsystems?.ai_providers?.gemini?.default_chat_model || "gemini-1.5-pro"}
              </span>
            </div>
            <div className="flex justify-between py-1 text-zinc-400">
              <span>Deterministic Offline Mode</span>
              <span className="font-mono text-emerald-400">Enabled (CI & Unit Safe)</span>
            </div>
          </div>
        </div>
      </div>

      {/* Prometheus Scraping Stream View */}
      <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-5 backdrop-blur-xl space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="space-y-1">
            <h3 className="text-xs font-bold text-white flex items-center gap-2">
              <Terminal className="h-4 w-4 text-indigo-400" />
              Prometheus Metrics Scraper Output (/api/v1/metrics)
            </h3>
            <p className="text-[11px] text-zinc-400">
              Standard Prometheus text format for Grafana agent, Datadog OpenMetrics, or Kubernetes monitoring.
            </p>
          </div>

          <button
            onClick={handleCopyMetrics}
            className="flex items-center gap-1.5 self-start sm:self-auto bg-zinc-800 hover:bg-zinc-700 text-zinc-200 px-3 py-1.5 rounded-xl text-xs font-mono transition-all border border-zinc-700/50"
          >
            {copied ? (
              <>
                <Check className="h-3.5 w-3.5 text-emerald-400" />
                <span className="text-emerald-400">Copied!</span>
              </>
            ) : (
              <>
                <Copy className="h-3.5 w-3.5 text-zinc-400" />
                <span>Copy Payload</span>
              </>
            )}
          </button>
        </div>

        <div className="relative rounded-xl border border-zinc-950 bg-zinc-950/90 p-4 font-mono text-[11px] text-zinc-300 max-h-72 overflow-y-auto leading-relaxed shadow-inner">
          {metricsRaw ? (
            <pre className="whitespace-pre-wrap">{metricsRaw}</pre>
          ) : (
            <div className="text-zinc-600 italic">No metrics collected yet.</div>
          )}
        </div>
      </div>
    </div>
  );
}
