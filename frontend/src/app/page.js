"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import {
  Building2,
  ShieldCheck,
  Users,
  FileText,
  Database,
  ArrowRight,
  UserPlus,
  CheckCircle2,
  Sparkles,
  Layers,
  Lock,
  Upload,
  Globe,
  Loader2,
  AlertCircle,
  Clock,
  RefreshCw,
  Trash2,
  Eye,
  X,
  FileCode,
  Tag,
  Search,
  SlidersHorizontal,
  Zap,
  MessageSquare,
  BarChart3,
  Activity,
} from "lucide-react";
import ChatInterface from "@/components/ChatInterface";
import EvaluationDashboard from "@/components/EvaluationDashboard";
import ObservabilityDashboard from "@/components/ObservabilityDashboard";

export default function HomePage() {
  const { user, activeOrg, loading } = useAuth();
  
  // Dashboard Tab state ("chat", "search", "documents", "team")
  const [dashboardTab, setDashboardTab] = useState("chat");

  // Documents state
  const [documents, setDocuments] = useState([]);
  const [docsLoading, setDocsLoading] = useState(false);
  const [activeTab, setActiveTab] = useState("file"); // "file" or "url"
  
  // Upload form state
  const [uploadFile, setUploadFile] = useState(null);
  const [uploadTags, setUploadTags] = useState("");
  const [uploadLoading, setUploadLoading] = useState(false);
  const [uploadError, setUploadError] = useState("");

  // URL Ingest form state
  const [ingestUrl, setIngestUrl] = useState("");
  const [ingestTitle, setIngestTitle] = useState("");
  const [urlTags, setUrlTags] = useState("");
  const [urlLoading, setUrlLoading] = useState(false);
  const [urlError, setUrlError] = useState("");

  // Inspect Chunks Modal state
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [chunks, setChunks] = useState([]);
  const [chunksLoading, setChunksLoading] = useState(false);

  // Search Explorer state (Phase 3)
  const [searchQuery, setSearchQuery] = useState("");
  const [searchHybrid, setSearchHybrid] = useState(true);
  const [searchRerank, setSearchRerank] = useState(true);
  const [searchDocFilter, setSearchDocFilter] = useState("");
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchResults, setSearchResults] = useState(null);
  const [searchError, setSearchError] = useState("");

  // Members state
  const [members, setMembers] = useState([]);
  const [newMemberEmail, setNewMemberEmail] = useState("");
  const [newMemberRole, setNewMemberRole] = useState("member");
  const [inviteLoading, setInviteLoading] = useState(false);
  const [inviteMessage, setInviteMessage] = useState({ type: "", text: "" });

  const fileInputRef = useRef(null);

  // Load documents and members when activeOrg changes
  useEffect(() => {
    if (activeOrg) {
      loadDocuments();
      loadMembers();
    }
  }, [activeOrg]);

  // Polling for processing documents
  useEffect(() => {
    const hasProcessing = documents.some(
      (d) => d.status === "pending" || d.status === "processing"
    );
    if (!hasProcessing) return;

    const interval = setInterval(() => {
      loadDocuments(false);
    }, 2500);

    return () => clearInterval(interval);
  }, [documents]);

  const loadDocuments = async (showLoading = true) => {
    try {
      if (showLoading) setDocsLoading(true);
      const data = await api.documents.list();
      setDocuments(data);
    } catch (err) {
      console.warn("Could not load documents:", err.message);
    } finally {
      if (showLoading) setDocsLoading(false);
    }
  };

  const loadMembers = async () => {
    try {
      const data = await api.organizations.getMembers(activeOrg.id);
      setMembers(data);
    } catch (err) {
      console.warn("Could not load members:", err.message);
    }
  };

  const handleFileUpload = async (e) => {
    e.preventDefault();
    if (!uploadFile) return;

    setUploadLoading(true);
    setUploadError("");

    const formData = new FormData();
    formData.append("file", uploadFile);
    if (uploadTags) formData.append("tags", uploadTags);

    try {
      await api.documents.upload(formData);
      setUploadFile(null);
      setUploadTags("");
      if (fileInputRef.current) fileInputRef.current.value = "";
      await loadDocuments();
    } catch (err) {
      setUploadError(err.message || "Failed to upload document");
    } finally {
      setUploadLoading(false);
    }
  };

  const handleUrlIngest = async (e) => {
    e.preventDefault();
    if (!ingestUrl) return;

    setUrlLoading(true);
    setUrlError("");

    const tagList = urlTags.split(",").map((t) => (t.strip ? t.strip() : t.trim())).filter(Boolean);

    try {
      await api.documents.ingestUrl({
        url: ingestUrl,
        title: ingestTitle || undefined,
        tags: tagList,
      });
      setIngestUrl("");
      setIngestTitle("");
      setUrlTags("");
      await loadDocuments();
    } catch (err) {
      setUrlError(err.message || "Failed to ingest website URL");
    } finally {
      setUrlLoading(false);
    }
  };

  const handleInspectChunks = async (doc) => {
    setSelectedDoc(doc);
    setChunksLoading(true);
    try {
      const chunkData = await api.documents.getChunks(doc.id);
      setChunks(chunkData);
    } catch (err) {
      console.warn("Failed to fetch chunks:", err.message);
      setChunks([]);
    } finally {
      setChunksLoading(false);
    }
  };

  const handleReindex = async (docId) => {
    try {
      await api.documents.reindex(docId);
      loadDocuments(false);
    } catch (err) {
      alert("Failed to re-index document: " + err.message);
    }
  };

  const handleDeleteDoc = async (docId, title) => {
    if (!confirm(`Are you sure you want to delete "${title}"?`)) return;
    try {
      await api.documents.delete(docId);
      loadDocuments(false);
    } catch (err) {
      alert("Failed to delete document: " + err.message);
    }
  };

  const handleSearch = async (e) => {
    if (e) e.preventDefault();
    if (!searchQuery.trim()) return;

    setSearchLoading(true);
    setSearchError("");

    try {
      const payload = {
        query: searchQuery,
        hybrid: searchHybrid,
        rerank: searchRerank,
        document_ids: searchDocFilter ? [searchDocFilter] : undefined,
        limit: 5,
        candidate_k: 20,
      };
      const res = await api.retrieval.search(payload);
      setSearchResults(res);
    } catch (err) {
      setSearchError(err.message || "Search failed");
      setSearchResults(null);
    } finally {
      setSearchLoading(false);
    }
  };

  const handleAddMember = async (e) => {
    e.preventDefault();
    setInviteLoading(true);
    setInviteMessage({ type: "", text: "" });

    try {
      await api.organizations.addMember(activeOrg.id, {
        email: newMemberEmail,
        role: newMemberRole,
      });
      setInviteMessage({
        type: "success",
        text: `Successfully added ${newMemberEmail} as ${newMemberRole}.`,
      });
      setNewMemberEmail("");
      loadMembers();
    } catch (err) {
      setInviteMessage({
        type: "error",
        text: err.message || "Failed to add member.",
      });
    } finally {
      setInviteLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-[calc(100vh-4rem)] items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
          <p className="text-xs text-zinc-500 font-mono">Loading tenant session...</p>
        </div>
      </div>
    );
  }

  // Logged-out landing page
  if (!user) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8 space-y-12">
        <div className="relative overflow-hidden rounded-3xl border border-white/[0.08] bg-gradient-to-b from-zinc-900/70 via-zinc-950/80 to-zinc-950 p-8 sm:p-14 lg:p-18 backdrop-blur-2xl text-center space-y-8 shadow-2xl">
          <div className="inline-flex items-center gap-2 rounded-full border border-indigo-500/30 bg-indigo-500/10 px-4 py-1.5 text-xs font-semibold text-indigo-300 backdrop-blur-md shadow-sm">
            <Sparkles className="h-3.5 w-3.5 text-indigo-400 animate-pulse" />
            <span>Production Multi-Tenant RAG Platform • Hybrid Search, SSE Streaming & LLM Judge</span>
          </div>

          <h1 className="mx-auto max-w-4xl text-4xl font-extrabold tracking-tight sm:text-6xl text-white leading-tight">
            Enterprise Knowledge Assistant with{" "}
            <span className="bg-gradient-to-r from-indigo-400 via-violet-300 to-pink-400 bg-clip-text text-transparent">
              Grounded Citations
            </span>
          </h1>

          <p className="mx-auto max-w-2xl text-sm sm:text-base text-zinc-400 leading-relaxed">
            Multi-tenant AI platform backed by FastAPI, PostgreSQL with pgvector, and Next.js.
            Upload PDF, DOCX, and web sources with dense cosine similarity, lexical FTS, and reranking.
          </p>

          <div className="flex flex-wrap items-center justify-center gap-4 pt-2">
            <Link
              href="/signup"
              className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 px-6 py-3.5 text-sm font-semibold text-white shadow-xl shadow-indigo-600/30 hover:from-indigo-500 hover:to-violet-500 transition-all hover:scale-105"
            >
              Get Started Free
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              href="/login"
              className="inline-flex items-center gap-2 rounded-xl border border-white/[0.12] bg-zinc-900/80 px-6 py-3.5 text-sm font-semibold text-zinc-200 hover:border-white/[0.2] hover:bg-zinc-800 transition-all"
            >
              Sign In to Existing Tenant
            </Link>
          </div>

          {/* Demo Credentials Callout */}
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-zinc-900/60 border border-white/[0.06] text-xs text-zinc-400 font-mono">
            <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" />
            <span>Demo Tenant:</span>
            <span className="text-zinc-200">admin@acme.com</span>
            <span className="text-zinc-500">•</span>
            <span>Password:</span>
            <span className="text-zinc-200">SuperPassword123!</span>
          </div>

          {/* 4 Feature Cards Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 pt-6 text-left">
            <div className="rounded-2xl border border-white/[0.06] bg-zinc-900/40 p-5 backdrop-blur-md space-y-2 hover:border-indigo-500/30 transition-all">
              <div className="h-9 w-9 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
                <Zap className="h-4 w-4" />
              </div>
              <h3 className="text-sm font-bold text-white">Hybrid Retrieval Engine</h3>
              <p className="text-xs text-zinc-400 leading-relaxed">
                pgvector cosine distance + Postgres FTS tsvector with Reciprocal Rank Fusion (k=60) & reranking.
              </p>
            </div>

            <div className="rounded-2xl border border-white/[0.06] bg-zinc-900/40 p-5 backdrop-blur-md space-y-2 hover:border-violet-500/30 transition-all">
              <div className="h-9 w-9 rounded-xl bg-violet-500/10 border border-violet-500/20 flex items-center justify-center text-violet-400">
                <FileText className="h-4 w-4" />
              </div>
              <h3 className="text-sm font-bold text-white">Strict Grounded Citations</h3>
              <p className="text-xs text-zinc-400 leading-relaxed">
                Bracketed citation discipline with interactive modals displaying exact source snippets & confidence.
              </p>
            </div>

            <div className="rounded-2xl border border-white/[0.06] bg-zinc-900/40 p-5 backdrop-blur-md space-y-2 hover:border-emerald-500/30 transition-all">
              <div className="h-9 w-9 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
                <BarChart3 className="h-4 w-4" />
              </div>
              <h3 className="text-sm font-bold text-white">LLM-as-a-Judge Harness</h3>
              <p className="text-xs text-zinc-400 leading-relaxed">
                Precision@K, Recall@K, MRR, atomic claim-level Faithfulness verification, and synthetic benchmark runner.
              </p>
            </div>

            <div className="rounded-2xl border border-white/[0.06] bg-zinc-900/40 p-5 backdrop-blur-md space-y-2 hover:border-pink-500/30 transition-all">
              <div className="h-9 w-9 rounded-xl bg-pink-500/10 border border-pink-500/20 flex items-center justify-center text-pink-400">
                <Activity className="h-4 w-4" />
              </div>
              <h3 className="text-sm font-bold text-white">Enterprise Observability</h3>
              <p className="text-xs text-zinc-400 leading-relaxed">
                Prometheus scrape endpoint, distributed trace IDs, and Redis sliding-window tenant rate limiting.
              </p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Logged-in tenant dashboard
  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8 space-y-5">
      {/* Sleek Command Strip */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 px-1 py-1">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-tr from-indigo-600/30 via-violet-600/20 to-transparent border border-indigo-500/30 text-indigo-400 shadow-md">
            <Building2 className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-bold text-white tracking-tight">{activeOrg?.name}</h1>
              <span className="rounded-full bg-gradient-to-r from-indigo-500/20 to-violet-500/20 border border-indigo-500/30 px-2 py-0.5 text-[10px] font-mono text-indigo-300 uppercase font-semibold">
                {activeOrg?.role}
              </span>
            </div>
            <p className="text-[11px] text-zinc-400 font-mono">
              Tenant ID: <span className="text-zinc-300">{activeOrg?.id?.slice(0, 8)}...</span> • Ingested Docs:{" "}
              <span className="text-emerald-400 font-semibold">{documents.length}</span>
            </p>
          </div>
        </div>

        {/* Live Subsystem Badges */}
        <div className="flex items-center gap-2 flex-wrap">
          <div className="flex items-center gap-1.5 rounded-xl bg-zinc-900/80 border border-white/[0.08] px-3 py-1.5 text-xs text-zinc-300 shadow-sm backdrop-blur-md">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
            </span>
            <span className="font-medium text-[11px]">Hybrid RAG Ready</span>
          </div>

          <div className="hidden sm:flex items-center gap-1.5 rounded-xl bg-zinc-900/80 border border-white/[0.08] px-2.5 py-1.5 text-[11px] text-zinc-400 font-mono">
            <Database className="h-3 w-3 text-indigo-400" />
            <span>pgvector 768d</span>
          </div>
        </div>
      </div>

      {/* Modern Segmented Navigation Bar */}
      <div className="flex items-center gap-1.5 p-1.5 rounded-2xl bg-zinc-900/70 border border-white/[0.08] backdrop-blur-xl overflow-x-auto no-scrollbar shadow-lg shadow-black/20">
        <button
          onClick={() => setDashboardTab("chat")}
          className={`flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-semibold whitespace-nowrap transition-all ${
            dashboardTab === "chat"
              ? "bg-gradient-to-r from-indigo-600 to-violet-600 text-white shadow-md shadow-indigo-600/30 scale-[1.01]"
              : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50"
          }`}
        >
          <MessageSquare className="h-4 w-4" />
          <span>AI Assistant (RAG Chat)</span>
          <span className="rounded-full bg-white/20 px-1.5 py-0.2 text-[9px] text-white font-mono uppercase tracking-wide">
            Live
          </span>
        </button>

        <button
          onClick={() => setDashboardTab("search")}
          className={`flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-semibold whitespace-nowrap transition-all ${
            dashboardTab === "search"
              ? "bg-gradient-to-r from-indigo-600 to-violet-600 text-white shadow-md shadow-indigo-600/30 scale-[1.01]"
              : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50"
          }`}
        >
          <Zap className="h-4 w-4" />
          <span>Hybrid Search Explorer</span>
        </button>

        <button
          onClick={() => setDashboardTab("documents")}
          className={`flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-semibold whitespace-nowrap transition-all ${
            dashboardTab === "documents"
              ? "bg-gradient-to-r from-indigo-600 to-violet-600 text-white shadow-md shadow-indigo-600/30 scale-[1.01]"
              : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50"
          }`}
        >
          <FileText className="h-4 w-4" />
          <span>Knowledge Documents ({documents.length})</span>
        </button>

        <button
          onClick={() => setDashboardTab("evaluation")}
          className={`flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-semibold whitespace-nowrap transition-all ${
            dashboardTab === "evaluation"
              ? "bg-gradient-to-r from-indigo-600 to-violet-600 text-white shadow-md shadow-indigo-600/30 scale-[1.01]"
              : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50"
          }`}
        >
          <BarChart3 className="h-4 w-4" />
          <span>Evaluation & Benchmarks</span>
        </button>

        <button
          onClick={() => setDashboardTab("observability")}
          className={`flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-semibold whitespace-nowrap transition-all ${
            dashboardTab === "observability"
              ? "bg-gradient-to-r from-indigo-600 to-violet-600 text-white shadow-md shadow-indigo-600/30 scale-[1.01]"
              : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50"
          }`}
        >
          <Activity className="h-4 w-4" />
          <span>Observability & Telemetry</span>
        </button>

        <button
          onClick={() => setDashboardTab("team")}
          className={`flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-semibold whitespace-nowrap transition-all ${
            dashboardTab === "team"
              ? "bg-gradient-to-r from-indigo-600 to-violet-600 text-white shadow-md shadow-indigo-600/30 scale-[1.01]"
              : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50"
          }`}
        >
          <Users className="h-4 w-4" />
          <span>Team & RBAC ({members.length})</span>
        </button>
      </div>

      {/* TAB 1: AI ASSISTANT CHAT (PHASE 4 & 5) */}
      {dashboardTab === "chat" && (
        <ChatInterface activeOrg={activeOrg} documents={documents} />
      )}

      {/* TAB 2: PHASE 3 HYBRID RETRIEVAL EXPLORER */}
      {dashboardTab === "search" && (
      <div className="rounded-2xl border border-indigo-500/30 bg-zinc-900/70 p-6 backdrop-blur-xl shadow-xl space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div className="space-y-1">
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              <Zap className="h-4 w-4 text-indigo-400" />
              Hybrid Retrieval & Reranker Explorer
            </h2>
            <p className="text-xs text-zinc-400">
              Query PostgreSQL pgvector (cosine distance) + full-text search (`tsvector`) with Reciprocal Rank Fusion & reranking.
            </p>
          </div>
          {searchResults && (
            <span className="text-xs font-mono text-zinc-400 bg-zinc-950 border border-zinc-800 px-2.5 py-1 rounded-lg">
              {searchResults.results.length} results in {searchResults.execution_time_ms}ms
            </span>
          )}
        </div>

        {/* Search Input Bar */}
        <form onSubmit={handleSearch} className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3.5 top-3 h-4 w-4 text-zinc-500" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Ask or search your documents (e.g., 'machine learning architectures', 'refund policies')..."
              className="w-full rounded-xl border border-zinc-800 bg-zinc-950/80 py-2.5 pl-10 pr-4 text-sm text-white placeholder-zinc-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>
          <button
            type="submit"
            disabled={searchLoading || !searchQuery.trim()}
            className="flex items-center gap-2 rounded-xl bg-indigo-600 px-5 py-2.5 text-xs font-semibold text-white hover:bg-indigo-500 disabled:opacity-50 transition-all shadow-md shadow-indigo-600/20"
          >
            {searchLoading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Searching...
              </>
            ) : (
              <>
                <Search className="h-4 w-4" />
                Retrieve
              </>
            )}
          </button>
        </form>

        {/* Search Controls & Filters */}
        <div className="flex flex-wrap items-center gap-4 pt-1 text-xs">
          {/* Hybrid Mode Toggle */}
          <label className="flex items-center gap-2 cursor-pointer text-zinc-300">
            <input
              type="checkbox"
              checked={searchHybrid}
              onChange={(e) => setSearchHybrid(e.target.checked)}
              className="rounded border-zinc-700 bg-zinc-950 text-indigo-600 focus:ring-indigo-500"
            />
            <span className="font-medium">Hybrid Search (Dense + Sparse)</span>
          </label>

          {/* Reranking Toggle */}
          <label className="flex items-center gap-2 cursor-pointer text-zinc-300">
            <input
              type="checkbox"
              checked={searchRerank}
              onChange={(e) => setSearchRerank(e.target.checked)}
              className="rounded border-zinc-700 bg-zinc-950 text-indigo-600 focus:ring-indigo-500"
            />
            <span className="font-medium">Cross-Encoder / LLM Reranker</span>
          </label>

          {/* Document Filter Dropdown */}
          {documents.length > 0 && (
            <div className="flex items-center gap-2 text-zinc-400">
              <span>Filter Doc:</span>
              <select
                value={searchDocFilter}
                onChange={(e) => setSearchDocFilter(e.target.value)}
                className="rounded-lg border border-zinc-800 bg-zinc-950 px-2.5 py-1 text-xs text-white focus:outline-none"
              >
                <option value="">All Documents</option>
                {documents.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.title}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>

        {searchError && (
          <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-xs text-rose-400 flex items-center gap-2">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{searchError}</span>
          </div>
        )}

        {/* Retrieved Results Card View */}
        {searchResults && (
          <div className="space-y-3 pt-2">
            <div className="flex items-center justify-between text-xs text-zinc-400">
              <span>
                Found {searchResults.results.length} relevant passage(s) (out of {searchResults.total_candidates} candidates):
              </span>
              <span className="font-mono text-[11px] text-indigo-400">Mode: {searchResults.search_mode}</span>
            </div>

            {searchResults.results.length === 0 ? (
              <div className="p-8 text-center text-xs text-zinc-500 rounded-xl border border-zinc-800 bg-zinc-950/40">
                No matching chunks found for this query within this organization.
              </div>
            ) : (
              searchResults.results.map((res, i) => (
                <div
                  key={res.chunk_id}
                  className="rounded-xl border border-zinc-800/80 bg-zinc-950/60 p-4 space-y-2.5 hover:border-zinc-700 transition-colors"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-800/60 pb-2">
                    <div className="flex items-center gap-2 text-xs font-medium text-white">
                      <span className="flex h-5 w-5 items-center justify-center rounded bg-indigo-600/20 text-indigo-400 font-mono text-[10px]">
                        #{i + 1}
                      </span>
                      <span className="text-zinc-200">{res.document_title}</span>
                      <span className="uppercase text-[10px] font-mono px-1.5 py-0.5 rounded bg-zinc-800 border border-zinc-700 text-zinc-400">
                        {res.file_type}
                      </span>
                      {res.page_number && (
                        <span className="text-[11px] text-zinc-400 font-mono">
                          p. {res.page_number}
                        </span>
                      )}
                      {res.section && (
                        <span className="text-[11px] text-zinc-400 font-mono truncate max-w-[200px]">
                          [{res.section}]
                        </span>
                      )}
                    </div>

                    {/* Scores Badge Group */}
                    <div className="flex items-center gap-2 font-mono text-[10px]">
                      {res.rerank_score !== null && (
                        <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-semibold" title="Reranker Relevance Score">
                          Rerank: {res.rerank_score}
                        </span>
                      )}
                      {res.dense_score !== null && (
                        <span className="px-2 py-0.5 rounded bg-violet-500/10 text-violet-400 border border-violet-500/20" title="pgvector Cosine Similarity">
                          Dense: {res.dense_score}
                        </span>
                      )}
                      {res.fts_score !== null && (
                        <span className="px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20" title="Postgres FTS ts_rank">
                          FTS: {res.fts_score}
                        </span>
                      )}
                      <span className="px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/20" title="Reciprocal Rank Fusion Score">
                        RRF: {res.combined_score}
                      </span>
                    </div>
                  </div>

                  <p className="text-xs text-zinc-300 leading-relaxed font-sans whitespace-pre-wrap">
                    {res.content}
                  </p>
                </div>
              ))
            )}
          </div>
        )}
      </div>
      )}

      {/* TAB 3: PHASE 2 INGESTION HUB */}
      {dashboardTab === "documents" && (
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column: Upload & Ingest Controls */}
        <div className="lg:col-span-1 space-y-6">
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-6 space-y-5">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-bold text-white flex items-center gap-2">
                <Upload className="h-4 w-4 text-indigo-400" />
                Ingest Document
              </h2>
              <div className="flex rounded-lg bg-zinc-950 p-1 border border-zinc-800 text-xs">
                <button
                  onClick={() => setActiveTab("file")}
                  className={`px-3 py-1 rounded-md transition-colors ${
                    activeTab === "file" ? "bg-indigo-600 text-white font-medium" : "text-zinc-400 hover:text-white"
                  }`}
                >
                  File
                </button>
                <button
                  onClick={() => setActiveTab("url")}
                  className={`px-3 py-1 rounded-md transition-colors ${
                    activeTab === "url" ? "bg-indigo-600 text-white font-medium" : "text-zinc-400 hover:text-white"
                  }`}
                >
                  Web URL
                </button>
              </div>
            </div>

            {/* TAB 1: File Upload */}
            {activeTab === "file" && (
              <form onSubmit={handleFileUpload} className="space-y-4">
                {uploadError && (
                  <div className="flex items-center gap-2 rounded-lg bg-rose-500/10 border border-rose-500/20 p-2.5 text-xs text-rose-400">
                    <AlertCircle className="h-4 w-4 shrink-0" />
                    <span>{uploadError}</span>
                  </div>
                )}

                <div className="relative border-2 border-dashed border-zinc-700/80 hover:border-indigo-500/80 rounded-xl p-5 text-center transition-colors bg-zinc-950/40">
                  <input
                    ref={fileInputRef}
                    type="file"
                    required
                    accept=".pdf,.docx,.doc,.txt,.md"
                    onChange={(e) => setUploadFile(e.target.files[0])}
                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                  />
                  <div className="flex flex-col items-center gap-2 pointer-events-none">
                    <FileText className="h-8 w-8 text-zinc-500" />
                    {uploadFile ? (
                      <div className="space-y-0.5">
                        <span className="text-xs font-semibold text-indigo-400 truncate max-w-[200px] block">
                          {uploadFile.name}
                        </span>
                        <span className="text-[10px] text-zinc-500">
                          {(uploadFile.size / 1024).toFixed(1)} KB
                        </span>
                      </div>
                    ) : (
                      <>
                        <span className="text-xs text-zinc-300 font-medium">
                          Click or drag file to upload
                        </span>
                        <span className="text-[10px] text-zinc-500">
                          PDF, DOCX, TXT, MD (Max 50MB)
                        </span>
                      </>
                    )}
                  </div>
                </div>

                <div className="space-y-1">
                  <label className="text-[11px] font-medium text-zinc-400 flex items-center gap-1">
                    <Tag className="h-3 w-3 text-zinc-500" /> Tags (optional, comma-separated)
                  </label>
                  <input
                    type="text"
                    value={uploadTags}
                    onChange={(e) => setUploadTags(e.target.value)}
                    placeholder="finance, policy, q3"
                    className="w-full rounded-lg border border-zinc-800 bg-zinc-950/60 px-3 py-2 text-xs text-white placeholder-zinc-500 focus:border-indigo-500 focus:outline-none"
                  />
                </div>

                <button
                  type="submit"
                  disabled={uploadLoading || !uploadFile}
                  className="flex w-full items-center justify-center gap-2 rounded-lg bg-indigo-600 py-2.5 text-xs font-semibold text-white shadow-md shadow-indigo-600/20 hover:bg-indigo-500 disabled:opacity-50 transition-all"
                >
                  {uploadLoading ? (
                    <>
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      Ingesting & Embedding...
                    </>
                  ) : (
                    <>
                      <Upload className="h-3.5 w-3.5" />
                      Upload & Ingest
                    </>
                  )}
                </button>
              </form>
            )}

            {/* TAB 2: URL Ingestion */}
            {activeTab === "url" && (
              <form onSubmit={handleUrlIngest} className="space-y-4">
                {urlError && (
                  <div className="flex items-center gap-2 rounded-lg bg-rose-500/10 border border-rose-500/20 p-2.5 text-xs text-rose-400">
                    <AlertCircle className="h-4 w-4 shrink-0" />
                    <span>{urlError}</span>
                  </div>
                )}

                <div className="space-y-1">
                  <label className="text-[11px] font-medium text-zinc-400">Website URL</label>
                  <div className="relative">
                    <Globe className="absolute left-3 top-2.5 h-3.5 w-3.5 text-zinc-500" />
                    <input
                      type="url"
                      required
                      value={ingestUrl}
                      onChange={(e) => setIngestUrl(e.target.value)}
                      placeholder="https://docs.company.com/handbook"
                      className="w-full rounded-lg border border-zinc-800 bg-zinc-950/60 py-2 pl-8 pr-3 text-xs text-white placeholder-zinc-500 focus:border-indigo-500 focus:outline-none"
                    />
                  </div>
                </div>

                <div className="space-y-1">
                  <label className="text-[11px] font-medium text-zinc-400">Document Title (optional)</label>
                  <input
                    type="text"
                    value={ingestTitle}
                    onChange={(e) => setIngestTitle(e.target.value)}
                    placeholder="Company Handbook"
                    className="w-full rounded-lg border border-zinc-800 bg-zinc-950/60 px-3 py-2 text-xs text-white placeholder-zinc-500 focus:border-indigo-500 focus:outline-none"
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-[11px] font-medium text-zinc-400 flex items-center gap-1">
                    <Tag className="h-3 w-3 text-zinc-500" /> Tags (optional)
                  </label>
                  <input
                    type="text"
                    value={urlTags}
                    onChange={(e) => setUrlTags(e.target.value)}
                    placeholder="web, handbook, engineering"
                    className="w-full rounded-lg border border-zinc-800 bg-zinc-950/60 px-3 py-2 text-xs text-white placeholder-zinc-500 focus:border-indigo-500 focus:outline-none"
                  />
                </div>

                <button
                  type="submit"
                  disabled={urlLoading || !ingestUrl}
                  className="flex w-full items-center justify-center gap-2 rounded-lg bg-indigo-600 py-2.5 text-xs font-semibold text-white shadow-md shadow-indigo-600/20 hover:bg-indigo-500 disabled:opacity-50 transition-all"
                >
                  {urlLoading ? (
                    <>
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      Scraping & Ingesting...
                    </>
                  ) : (
                    <>
                      <Globe className="h-3.5 w-3.5" />
                      Crawl & Ingest Web Page
                    </>
                  )}
                </button>
              </form>
            )}
          </div>
        </div>

        {/* Right Column: Ingested Documents List */}
        <div className="lg:col-span-2 space-y-6">
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-6 space-y-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FileCode className="h-5 w-5 text-indigo-400" />
                <h2 className="text-base font-semibold text-white">Organization Knowledge Base</h2>
              </div>
              <button
                onClick={() => loadDocuments()}
                title="Refresh documents list"
                className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors"
              >
                <RefreshCw className={`h-4 w-4 ${docsLoading ? "animate-spin" : ""}`} />
              </button>
            </div>

            {/* Documents Table */}
            {documents.length === 0 ? (
              <div className="text-center py-12 border border-zinc-800/80 rounded-xl bg-zinc-950/30">
                <FileText className="mx-auto h-8 w-8 text-zinc-600" />
                <p className="mt-2 text-xs font-medium text-zinc-400">No documents ingested yet</p>
                <p className="text-[11px] text-zinc-600">
                  Upload a PDF, DOCX, TXT file or crawl a website URL on the left.
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-zinc-800 text-zinc-400 font-medium">
                      <th className="pb-3">Source Title</th>
                      <th className="pb-3">Type</th>
                      <th className="pb-3">Status</th>
                      <th className="pb-3">Chunks</th>
                      <th className="pb-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-800/60">
                    {documents.map((doc) => (
                      <tr key={doc.id} className="text-zinc-300 hover:bg-zinc-800/20 transition-colors">
                        <td className="py-3">
                          <div className="font-medium text-white max-w-[200px] truncate" title={doc.title}>
                            {doc.title}
                          </div>
                          <div className="text-[10px] text-zinc-500 font-mono">
                            {new Date(doc.created_at).toLocaleDateString()}
                          </div>
                        </td>
                        <td className="py-3">
                          <span className="uppercase text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-800 border border-zinc-700 text-zinc-300">
                            {doc.file_type}
                          </span>
                        </td>
                        <td className="py-3">
                          {doc.status === "completed" ? (
                            <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-400">
                              <CheckCircle2 className="h-3.5 w-3.5" /> Ready
                            </span>
                          ) : doc.status === "processing" ? (
                            <span className="inline-flex items-center gap-1 text-[11px] font-medium text-amber-400 animate-pulse">
                              <Loader2 className="h-3.5 w-3.5 animate-spin" /> Ingesting...
                            </span>
                          ) : doc.status === "pending" ? (
                            <span className="inline-flex items-center gap-1 text-[11px] font-medium text-zinc-400">
                              <Clock className="h-3.5 w-3.5" /> Queued
                            </span>
                          ) : (
                            <span
                              className="inline-flex items-center gap-1 text-[11px] font-medium text-rose-400"
                              title={doc.error_message || "Failed"}
                            >
                              <AlertCircle className="h-3.5 w-3.5" /> Failed
                            </span>
                          )}
                        </td>
                        <td className="py-3 font-mono text-zinc-300">
                          {doc.total_chunks}
                        </td>
                        <td className="py-3 text-right space-x-1">
                          <button
                            onClick={() => handleInspectChunks(doc)}
                            disabled={doc.total_chunks === 0}
                            title="Inspect Chunks"
                            className="p-1 rounded text-zinc-400 hover:text-indigo-400 hover:bg-indigo-500/10 disabled:opacity-30 transition-colors"
                          >
                            <Eye className="h-3.5 w-3.5" />
                          </button>
                          <button
                            onClick={() => handleReindex(doc.id)}
                            title="Re-index Document"
                            className="p-1 rounded text-zinc-400 hover:text-amber-400 hover:bg-amber-500/10 transition-colors"
                          >
                            <RefreshCw className="h-3.5 w-3.5" />
                          </button>
                          <button
                            onClick={() => handleDeleteDoc(doc.id, doc.title)}
                            title="Delete Document"
                            className="p-1 rounded text-zinc-400 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>
      )}

      {/* CHUNK INSPECTION MODAL */}
      {selectedDoc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div className="w-full max-w-3xl max-h-[85vh] flex flex-col rounded-2xl border border-zinc-800 bg-zinc-900 shadow-2xl overflow-hidden">
            <div className="flex items-center justify-between border-b border-zinc-800 p-4">
              <div>
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <Database className="h-4 w-4 text-indigo-400" />
                  Chunks for: {selectedDoc.title}
                </h3>
                <p className="text-[11px] text-zinc-400 font-mono">
                  {chunks.length} pgvector chunks with page & section metadata
                </p>
              </div>
              <button
                onClick={() => setSelectedDoc(null)}
                className="p-1 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {chunksLoading ? (
                <div className="py-12 flex flex-col items-center justify-center gap-2 text-zinc-400">
                  <Loader2 className="h-6 w-6 animate-spin text-indigo-400" />
                  <span className="text-xs">Fetching chunks from PostgreSQL...</span>
                </div>
              ) : chunks.length === 0 ? (
                <p className="text-center py-8 text-xs text-zinc-500">No chunks found.</p>
              ) : (
                chunks.map((chk) => (
                  <div
                    key={chk.id}
                    className="p-3.5 rounded-xl border border-zinc-800 bg-zinc-950/60 space-y-2 text-xs"
                  >
                    <div className="flex items-center justify-between font-mono text-[10px] text-zinc-400 border-b border-zinc-800/60 pb-1.5">
                      <span className="text-indigo-400 font-bold">Chunk #{chk.chunk_index}</span>
                      <div className="flex items-center gap-3">
                        {chk.page_number && <span>Page: {chk.page_number}</span>}
                        {chk.section && <span className="truncate max-w-[150px]">Section: {chk.section}</span>}
                        <span>~{chk.token_count} tokens</span>
                      </div>
                    </div>
                    <p className="text-zinc-300 font-sans leading-relaxed whitespace-pre-wrap">
                      {chk.content}
                    </p>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* TAB 4: EVALUATION & BENCHMARKING (PHASE 6) */}
      {dashboardTab === "evaluation" && (
        <EvaluationDashboard activeOrg={activeOrg} documents={documents} />
      )}

      {/* TAB 6: OBSERVABILITY & TELEMETRY (PHASE 7) */}
      {dashboardTab === "observability" && (
        <ObservabilityDashboard activeOrg={activeOrg} />
      )}

      {/* TAB 5: TEAM MEMBERS & RBAC SECTION */}
      {dashboardTab === "team" && (
      <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Users className="h-5 w-5 text-indigo-400" />
            <h2 className="text-base font-semibold text-white">Team Members & RBAC</h2>
          </div>
          <span className="text-xs text-zinc-400">{members.length} member(s)</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-zinc-800 text-zinc-400 font-medium">
                <th className="pb-3">User</th>
                <th className="pb-3">Role</th>
                <th className="pb-3">Joined</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/60">
              {members.map((member) => (
                <tr key={member.id} className="text-zinc-300">
                  <td className="py-3">
                    <div className="font-medium text-white">{member.full_name || "Member"}</div>
                    <div className="text-[11px] text-zinc-500 font-mono">{member.email}</div>
                  </td>
                  <td className="py-3">
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono uppercase border ${
                        member.role === "admin"
                          ? "bg-rose-500/10 text-rose-300 border-rose-500/20"
                          : member.role === "member"
                          ? "bg-indigo-500/10 text-indigo-300 border-indigo-500/20"
                          : "bg-zinc-800 text-zinc-400 border-zinc-700"
                      }`}
                    >
                      {member.role}
                    </span>
                  </td>
                  <td className="py-3 text-zinc-500">
                    {new Date(member.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {activeOrg?.role === "admin" && (
          <div className="pt-4 border-t border-zinc-800/80 space-y-3">
            <h3 className="text-xs font-semibold text-zinc-300 flex items-center gap-1.5">
              <UserPlus className="h-4 w-4 text-indigo-400" />
              Invite Member to {activeOrg.name}
            </h3>

            {inviteMessage.text && (
              <div
                className={`p-2.5 rounded-lg text-xs border ${
                  inviteMessage.type === "success"
                    ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-400"
                    : "bg-rose-500/10 border-rose-500/20 text-rose-400"
                }`}
              >
                {inviteMessage.text}
              </div>
            )}

            <form onSubmit={handleAddMember} className="flex flex-col sm:flex-row gap-3">
              <input
                type="email"
                required
                value={newMemberEmail}
                onChange={(e) => setNewMemberEmail(e.target.value)}
                placeholder="teammate@company.com"
                className="flex-1 rounded-lg border border-zinc-800 bg-zinc-950/60 px-3 py-2 text-xs text-white placeholder-zinc-500 focus:border-indigo-500 focus:outline-none"
              />
              <select
                value={newMemberRole}
                onChange={(e) => setNewMemberRole(e.target.value)}
                className="rounded-lg border border-zinc-800 bg-zinc-950/60 px-3 py-2 text-xs text-white focus:border-indigo-500 focus:outline-none"
              >
                <option value="member">Member</option>
                <option value="viewer">Viewer</option>
                <option value="admin">Admin</option>
              </select>
              <button
                type="submit"
                disabled={inviteLoading}
                className="rounded-lg bg-indigo-600 px-4 py-2 text-xs font-semibold text-white hover:bg-indigo-500 disabled:opacity-50 transition-colors"
              >
                {inviteLoading ? "Adding..." : "Add Member"}
              </button>
            </form>
          </div>
        )}
      </div>
      )}
    </div>
  );
}
