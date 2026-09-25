"use client";

import { useState, useEffect, useRef } from "react";
import { api } from "@/lib/api";
import {
  MessageSquare,
  Plus,
  Send,
  Bot,
  User,
  Sparkles,
  Trash2,
  Edit2,
  SlidersHorizontal,
  FileText,
  Check,
  ChevronDown,
  ChevronUp,
  Loader2,
  AlertCircle,
  X,
  ExternalLink,
  Layers,
  Search,
  BookOpen,
} from "lucide-react";

export default function ChatInterface({ activeOrg, documents = [] }) {
  const [conversations, setConversations] = useState([]);
  const [convLoading, setConvLoading] = useState(false);
  const [activeConvId, setActiveConvId] = useState(null);
  const [activeConv, setActiveConv] = useState(null);
  const [activeConvLoading, setActiveConvLoading] = useState(false);

  // Streaming / Generation state
  const [isGenerating, setIsGenerating] = useState(false);
  const [streamingStatus, setStreamingStatus] = useState("");
  const [streamingSources, setStreamingSources] = useState([]);
  const [streamingContent, setStreamingContent] = useState("");
  const [inputQuery, setInputQuery] = useState("");
  const [errorMsg, setErrorMsg] = useState("");

  // RAG Query Configuration
  const [topK, setTopK] = useState(5);
  const [hybrid, setHybrid] = useState(true);
  const [useReranking, setUseReranking] = useState(true);
  const [selectedDocFilter, setSelectedDocFilter] = useState("");
  const [showConfig, setShowConfig] = useState(false);

  // Citation Inspection Modal
  const [selectedCitation, setSelectedCitation] = useState(null);

  // Title edit state
  const [editingTitle, setEditingTitle] = useState(false);
  const [newTitle, setNewTitle] = useState("");

  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  // 1. Load conversations on mount or when org changes
  useEffect(() => {
    if (!activeOrg?.id) return;
    loadConversations();
  }, [activeOrg?.id]);

  // Auto-scroll when messages update or streaming content changes
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [activeConv?.messages, streamingContent, streamingStatus]);

  const loadConversations = async () => {
    try {
      setConvLoading(true);
      const res = await api.chat.listConversations(1, 50);
      setConversations(res.items || []);
      if (res.items && res.items.length > 0 && !activeConvId) {
        selectConversation(res.items[0].id);
      } else if (!res.items || res.items.length === 0) {
        setActiveConvId(null);
        setActiveConv(null);
      }
    } catch (err) {
      console.warn("Could not load conversations:", err.message);
    } finally {
      setConvLoading(false);
    }
  };

  const selectConversation = async (convId) => {
    setActiveConvId(convId);
    setActiveConvLoading(true);
    setErrorMsg("");
    setStreamingContent("");
    setStreamingStatus("");
    setStreamingSources([]);
    try {
      const data = await api.chat.getConversation(convId);
      setActiveConv(data);
      setNewTitle(data.title);
    } catch (err) {
      setErrorMsg("Failed to load conversation history: " + err.message);
    } finally {
      setActiveConvLoading(false);
    }
  };

  const handleCreateNewChat = async () => {
    try {
      setErrorMsg("");
      const newConv = await api.chat.createConversation({ title: "New Conversation" });
      setConversations((prev) => [newConv, ...prev]);
      setActiveConvId(newConv.id);
      setActiveConv({
        ...newConv,
        messages: [],
      });
      setNewTitle(newConv.title);
    } catch (err) {
      setErrorMsg("Failed to create new conversation: " + err.message);
    }
  };

  const handleDeleteConversation = async (e, convId) => {
    e.stopPropagation();
    if (!confirm("Are you sure you want to delete this conversation?")) return;
    try {
      await api.chat.deleteConversation(convId);
      const updated = conversations.filter((c) => c.id !== convId);
      setConversations(updated);
      if (activeConvId === convId) {
        if (updated.length > 0) {
          selectConversation(updated[0].id);
        } else {
          setActiveConvId(null);
          setActiveConv(null);
        }
      }
    } catch (err) {
      setErrorMsg("Failed to delete conversation: " + err.message);
    }
  };

  const handleUpdateTitle = async () => {
    if (!newTitle.trim() || !activeConvId) return;
    try {
      const updated = await api.chat.updateConversation(activeConvId, { title: newTitle.trim() });
      setActiveConv((prev) => ({ ...prev, title: updated.title }));
      setConversations((prev) =>
        prev.map((c) => (c.id === activeConvId ? { ...c, title: updated.title } : c))
      );
      setEditingTitle(false);
    } catch (err) {
      setErrorMsg("Failed to update title: " + err.message);
    }
  };

  const handleSendMessage = async (e) => {
    e?.preventDefault();
    const query = inputQuery.trim();
    if (!query || isGenerating) return;

    let targetConvId = activeConvId;
    if (!targetConvId) {
      // Auto-create conversation if none exists
      try {
        const newConv = await api.chat.createConversation({ title: query.slice(0, 30) });
        setConversations((prev) => [newConv, ...prev]);
        targetConvId = newConv.id;
        setActiveConvId(newConv.id);
        setActiveConv({ ...newConv, messages: [] });
      } catch (err) {
        setErrorMsg("Failed to start chat session: " + err.message);
        return;
      }
    }

    // Add user message to UI immediately for optimistic rendering
    const tempUserMsg = {
      id: "temp-" + Date.now(),
      conversation_id: targetConvId,
      sender_type: "user",
      content: query,
      created_at: new Date().toISOString(),
      citations: [],
    };

    setActiveConv((prev) => ({
      ...prev,
      messages: [...(prev?.messages || []), tempUserMsg],
    }));

    setInputQuery("");
    setIsGenerating(true);
    setStreamingContent("");
    setStreamingStatus("Searching internal knowledge base...");
    setStreamingSources([]);
    setErrorMsg("");

    const payload = {
      content: query,
      top_k: parseInt(topK, 10),
      hybrid: Boolean(hybrid),
      use_reranking: Boolean(useReranking),
      filter_document_ids: selectedDocFilter ? [selectedDocFilter] : undefined,
    };

    try {
      await api.chat.streamMessage(targetConvId, payload, {
        onStatus: (data) => {
          setStreamingStatus(data.status || "Retrieving relevant context...");
        },
        onSources: (sources) => {
          setStreamingSources(sources || []);
          setStreamingStatus(`Found ${sources.length} matching passages. Generating grounded response...`);
        },
        onDelta: (data) => {
          setStreamingStatus("");
          setStreamingContent((prev) => prev + (data.content || ""));
        },
        onDone: (data) => {
          const assistantMsg = {
            id: data.message_id,
            conversation_id: targetConvId,
            sender_type: "assistant",
            content: data.content,
            created_at: new Date().toISOString(),
            citations: data.citations || [],
          };

          setActiveConv((prev) => ({
            ...prev,
            messages: [...(prev?.messages || []).filter((m) => m.id !== tempUserMsg.id), tempUserMsg, assistantMsg],
          }));

          setStreamingContent("");
          setStreamingStatus("");
          setStreamingSources([]);
          setIsGenerating(false);

          // Refresh conversation list to get updated titles & timestamps
          loadConversations();
        },
        onError: (errData) => {
          setErrorMsg(errData.detail || "Error generating response");
          setIsGenerating(false);
          setStreamingStatus("");
        },
      });
    } catch (err) {
      setErrorMsg("Streaming failed: " + err.message);
      setIsGenerating(false);
      setStreamingStatus("");
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  // Helper to render text with clickable citation badges
  const renderMessageContent = (text, citations = []) => {
    if (!text) return null;

    // Build map of chunk_id -> citation
    const citeMap = {};
    citations.forEach((c) => {
      if (c.chunk_id) citeMap[c.chunk_id] = c;
    });

    // Split text by [cite:<uuid>] or [<uuid>]
    const regex = /\[(?:cite:)?([0-9a-fA-F\-]{36})\]/g;
    const parts = [];
    let lastIndex = 0;
    let match;
    let citeCounter = 1;
    const assignedNumbers = {};

    while ((match = regex.exec(text)) !== null) {
      const beforeText = text.substring(lastIndex, match.index);
      if (beforeText) {
        parts.push(beforeText);
      }

      const chunkId = match[1];
      const citationObj = citeMap[chunkId];

      if (!assignedNumbers[chunkId]) {
        assignedNumbers[chunkId] = citeCounter++;
      }
      const num = assignedNumbers[chunkId];

      const docTitle = citationObj?.document_title || "Source Doc";
      const pageInfo = citationObj?.page_number ? ` p.${citationObj.page_number}` : "";

      parts.push(
        <button
          key={`cite-${match.index}`}
          onClick={() => {
            if (citationObj) {
              setSelectedCitation(citationObj);
            }
          }}
          className="inline-flex items-center gap-1 mx-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 hover:bg-indigo-500/30 hover:border-indigo-400 transition-colors shadow-sm"
          title={`Click to inspect citation: ${docTitle}${pageInfo}`}
        >
          <BookOpen className="h-3 w-3" />
          <span>
            [{num}. {docTitle.length > 18 ? docTitle.slice(0, 16) + "..." : docTitle}{pageInfo}]
          </span>
        </button>
      );

      lastIndex = regex.lastIndex;
    }

    if (lastIndex < text.length) {
      parts.push(text.substring(lastIndex));
    }

    return (
      <div className="whitespace-pre-wrap leading-relaxed text-sm">
        {parts.map((p, i) => (typeof p === "string" ? <span key={i}>{p}</span> : p))}
      </div>
    );
  };

  return (
    <div className="flex h-[calc(100vh-190px)] min-h-[620px] w-full rounded-2xl border border-white/[0.08] bg-zinc-950/80 overflow-hidden shadow-2xl backdrop-blur-xl">
      {/* SIDEBAR: Conversation Manager */}
      <div className="w-72 flex-shrink-0 flex flex-col border-r border-white/[0.08] bg-zinc-900/50">
        {/* Sidebar Header */}
        <div className="p-4 border-b border-zinc-800/80 space-y-3">
          <button
            onClick={handleCreateNewChat}
            className="w-full flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 px-4 py-2.5 text-xs font-semibold text-white shadow-md shadow-indigo-500/20 hover:from-indigo-500 hover:to-violet-500 transition-all hover:scale-[1.01]"
          >
            <Plus className="h-4 w-4" />
            New Assistant Chat
          </button>
        </div>

        {/* Conversation List */}
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {convLoading ? (
            <div className="flex items-center justify-center py-10 text-xs text-zinc-500">
              <Loader2 className="h-4 w-4 animate-spin mr-2" />
              Loading chats...
            </div>
          ) : conversations.length === 0 ? (
            <div className="py-12 px-4 text-center space-y-2">
              <MessageSquare className="h-8 w-8 text-zinc-700 mx-auto" />
              <p className="text-xs text-zinc-400 font-medium">No conversations yet</p>
              <p className="text-[11px] text-zinc-500">
                Click New Chat to begin querying your ingested documents.
              </p>
            </div>
          ) : (
            conversations.map((c) => {
              const isActive = c.id === activeConvId;
              return (
                <div
                  key={c.id}
                  onClick={() => selectConversation(c.id)}
                  className={`group relative flex items-center justify-between rounded-xl px-3 py-2.5 text-xs cursor-pointer transition-all ${
                    isActive
                      ? "bg-indigo-600/15 text-white border border-indigo-500/30"
                      : "text-zinc-400 hover:bg-zinc-800/60 hover:text-zinc-200"
                  }`}
                >
                  <div className="flex items-center gap-2.5 truncate pr-6">
                    <MessageSquare
                      className={`h-3.5 w-3.5 flex-shrink-0 ${
                        isActive ? "text-indigo-400" : "text-zinc-500"
                      }`}
                    />
                    <span className="truncate font-medium">{c.title || "Untitled Chat"}</span>
                  </div>

                  <button
                    onClick={(e) => handleDeleteConversation(e, c.id)}
                    className="opacity-0 group-hover:opacity-100 p-1 text-zinc-500 hover:text-rose-400 hover:bg-rose-500/10 rounded transition-all"
                    title="Delete conversation"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              );
            })
          )}
        </div>

        {/* Sidebar Footer: System Status */}
        <div className="p-3 border-t border-zinc-800/80 bg-zinc-950/60 text-[11px] text-zinc-500 flex items-center justify-between">
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
            RAG Grounding Active
          </span>
          <span className="font-mono text-[10px] text-indigo-400">Gemini 1.5</span>
        </div>
      </div>

      {/* MAIN CHAT WORKSPACE */}
      <div className="flex-1 flex flex-col bg-zinc-950 overflow-hidden relative">
        {/* Chat Header Bar */}
        <div className="h-14 border-b border-zinc-800/80 px-5 flex items-center justify-between bg-zinc-900/40 backdrop-blur-md">
          <div className="flex items-center gap-3">
            {editingTitle ? (
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleUpdateTitle()}
                  className="rounded-lg border border-indigo-500 bg-zinc-900 px-2 py-1 text-xs text-white focus:outline-none"
                  autoFocus
                />
                <button
                  onClick={handleUpdateTitle}
                  className="p-1 text-emerald-400 hover:bg-emerald-500/10 rounded"
                >
                  <Check className="h-3.5 w-3.5" />
                </button>
                <button
                  onClick={() => setEditingTitle(false)}
                  className="p-1 text-zinc-400 hover:bg-zinc-800 rounded"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2 group cursor-pointer" onClick={() => setEditingTitle(true)}>
                <h2 className="text-sm font-bold text-white">
                  {activeConv?.title || "New Conversation"}
                </h2>
                <Edit2 className="h-3 w-3 text-zinc-500 opacity-0 group-hover:opacity-100 transition-opacity" />
              </div>
            )}
          </div>

          {/* RAG Controls Drawer Toggle */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowConfig(!showConfig)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                showConfig
                  ? "bg-indigo-600/20 text-indigo-300 border-indigo-500/40"
                  : "bg-zinc-900 text-zinc-400 border-zinc-800 hover:text-zinc-200"
              }`}
            >
              <SlidersHorizontal className="h-3.5 w-3.5" />
              <span>RAG Parameters</span>
              {showConfig ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
            </button>
          </div>
        </div>

        {/* RAG Controls Popdown Panel */}
        {showConfig && (
          <div className="border-b border-indigo-500/20 bg-zinc-900/90 p-4 grid grid-cols-1 sm:grid-cols-4 gap-4 text-xs animate-in slide-in-from-top-2">
            <div>
              <label className="text-zinc-400 font-medium block mb-1">Context Chunks (Top-K)</label>
              <select
                value={topK}
                onChange={(e) => setTopK(e.target.value)}
                className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2.5 py-1.5 text-white focus:outline-none focus:border-indigo-500"
              >
                <option value={3}>Top 3 Chunks</option>
                <option value={5}>Top 5 Chunks (Recommended)</option>
                <option value={8}>Top 8 Chunks</option>
                <option value={10}>Top 10 Chunks</option>
              </select>
            </div>

            <div>
              <label className="text-zinc-400 font-medium block mb-1">Search Strategy</label>
              <select
                value={hybrid ? "hybrid" : "dense"}
                onChange={(e) => setHybrid(e.target.value === "hybrid")}
                className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2.5 py-1.5 text-white focus:outline-none focus:border-indigo-500"
              >
                <option value="hybrid">Hybrid (pgvector + FTS RRF)</option>
                <option value="dense">Dense Vector Cosine Only</option>
              </select>
            </div>

            <div>
              <label className="text-zinc-400 font-medium block mb-1">Reranker Model</label>
              <select
                value={useReranking ? "true" : "false"}
                onChange={(e) => setUseReranking(e.target.value === "true")}
                className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2.5 py-1.5 text-white focus:outline-none focus:border-indigo-500"
              >
                <option value="true">Active (LLM & Coverage Rerank)</option>
                <option value="false">Disabled (Raw RRF Rank)</option>
              </select>
            </div>

            <div>
              <label className="text-zinc-400 font-medium block mb-1">Filter Document Scope</label>
              <select
                value={selectedDocFilter}
                onChange={(e) => setSelectedDocFilter(e.target.value)}
                className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2.5 py-1.5 text-white focus:outline-none focus:border-indigo-500 truncate"
              >
                <option value="">All Tenant Documents ({documents.length})</option>
                {documents.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.title}
                  </option>
                ))}
              </select>
            </div>
          </div>
        )}

        {/* Message Timeline Area */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {activeConvLoading ? (
            <div className="flex flex-col items-center justify-center h-full text-xs text-zinc-500 space-y-2">
              <Loader2 className="h-6 w-6 animate-spin text-indigo-400" />
              <span>Loading conversation history...</span>
            </div>
          ) : !activeConv || (!activeConv.messages?.length && !isGenerating) ? (
            /* Empty State */
            <div className="flex flex-col items-center justify-center h-full max-w-lg mx-auto text-center space-y-5">
              <div className="h-12 w-12 rounded-2xl bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center shadow-lg shadow-indigo-500/20">
                <Sparkles className="h-6 w-6 text-white" />
              </div>
              <div className="space-y-1.5">
                <h3 className="text-base font-bold text-white">Ask your Enterprise Knowledge Base</h3>
                <p className="text-xs text-zinc-400">
                  Every answer is strictly grounded in your ingested documents with clickable inline citations and verifiable source snippets.
                </p>
              </div>

              {/* Starter Prompt Chips */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 w-full pt-2">
                {[
                  "Summarize key requirements and system architecture",
                  "What are the compliance and SLA uptime guarantees?",
                  "Explain core policies or procedures in detail",
                  "What are the quarterly financial metrics?",
                ].map((prompt, i) => (
                  <button
                    key={i}
                    onClick={() => {
                      setInputQuery(prompt);
                      textareaRef.current?.focus();
                    }}
                    className="p-3 text-left rounded-xl border border-zinc-800/80 bg-zinc-900/60 hover:bg-zinc-800/80 hover:border-indigo-500/40 text-xs text-zinc-300 transition-all hover:scale-[1.01]"
                  >
                    "{prompt}"
                  </button>
                ))}
              </div>
            </div>
          ) : (
            /* Render Messages */
            <div className="space-y-6 max-w-3xl mx-auto">
              {activeConv.messages?.map((msg) => {
                const isUser = msg.sender_type === "user";
                return (
                  <div
                    key={msg.id}
                    className={`flex items-start gap-3.5 ${isUser ? "flex-row-reverse" : "flex-row"}`}
                  >
                    {/* Avatar */}
                    <div
                      className={`h-8 w-8 rounded-xl flex items-center justify-center flex-shrink-0 text-xs font-semibold shadow-md ${
                        isUser
                          ? "bg-zinc-800 text-zinc-200 border border-zinc-700"
                          : "bg-gradient-to-tr from-indigo-600 to-violet-500 text-white shadow-indigo-500/20"
                      }`}
                    >
                      {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
                    </div>

                    {/* Message Bubble */}
                    <div
                      className={`rounded-2xl p-4 max-w-[85%] space-y-3 ${
                        isUser
                          ? "bg-indigo-600 text-white rounded-tr-none shadow-md shadow-indigo-600/10"
                          : "bg-zinc-900/80 border border-zinc-800/80 text-zinc-200 rounded-tl-none backdrop-blur-md"
                      }`}
                    >
                      {isUser ? (
                        <p className="text-sm whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                      ) : (
                        <>
                          {renderMessageContent(msg.content, msg.citations)}

                          {/* Sources Accordion */}
                          {msg.citations && msg.citations.length > 0 && (
                            <div className="pt-2 border-t border-zinc-800/80">
                              <span className="text-[11px] font-semibold text-zinc-400 block mb-1.5 flex items-center gap-1">
                                <BookOpen className="h-3 w-3 text-indigo-400" />
                                Grounded Sources ({msg.citations.length}):
                              </span>
                              <div className="flex flex-wrap gap-1.5">
                                {msg.citations.map((cite, idx) => (
                                  <button
                                    key={cite.id || idx}
                                    onClick={() => setSelectedCitation(cite)}
                                    className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs bg-zinc-950 border border-zinc-800 hover:border-indigo-500/50 hover:bg-zinc-900 text-zinc-300 transition-colors"
                                  >
                                    <FileText className="h-3 w-3 text-indigo-400" />
                                    <span className="font-medium truncate max-w-[150px]">
                                      {cite.document_title}
                                    </span>
                                    {cite.page_number && (
                                      <span className="text-[10px] text-zinc-500">p.{cite.page_number}</span>
                                    )}
                                  </button>
                                ))}
                              </div>
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  </div>
                );
              })}

              {/* Streaming Assistant In-Progress Bubble */}
              {isGenerating && (
                <div className="flex items-start gap-3.5 flex-row">
                  <div className="h-8 w-8 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center flex-shrink-0 text-white shadow-md shadow-indigo-500/20">
                    <Bot className="h-4 w-4" />
                  </div>

                  <div className="rounded-2xl rounded-tl-none p-4 max-w-[85%] bg-zinc-900/80 border border-indigo-500/30 text-zinc-200 backdrop-blur-md space-y-3">
                    {/* Live Status indicator */}
                    {streamingStatus && (
                      <div className="flex items-center gap-2 text-xs text-indigo-400 font-medium py-1 animate-pulse">
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        <span>{streamingStatus}</span>
                      </div>
                    )}

                    {/* Streamed text */}
                    {streamingContent ? (
                      renderMessageContent(streamingContent)
                    ) : (
                      <div className="flex items-center gap-1.5 py-2">
                        <span className="h-2 w-2 rounded-full bg-indigo-500 animate-bounce" />
                        <span className="h-2 w-2 rounded-full bg-indigo-500 animate-bounce [animation-delay:0.2s]" />
                        <span className="h-2 w-2 rounded-full bg-indigo-500 animate-bounce [animation-delay:0.4s]" />
                      </div>
                    )}

                    {/* Discovered Sources preview during streaming */}
                    {streamingSources.length > 0 && !streamingContent && (
                      <div className="pt-2 border-t border-zinc-800">
                        <span className="text-[11px] text-zinc-400 block mb-1">Retrieved Context Passages:</span>
                        <div className="flex flex-wrap gap-1">
                          {streamingSources.map((s, idx) => (
                            <span
                              key={idx}
                              className="text-[10px] bg-zinc-950 border border-zinc-800 text-zinc-300 px-2 py-0.5 rounded"
                            >
                              {s.document_title}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Error Alert Bar */}
        {errorMsg && (
          <div className="mx-6 mb-2 flex items-center justify-between rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-2 text-xs text-rose-300">
            <div className="flex items-center gap-2">
              <AlertCircle className="h-4 w-4 text-rose-400 flex-shrink-0" />
              <span>{errorMsg}</span>
            </div>
            <button onClick={() => setErrorMsg("")} className="text-rose-400 hover:text-rose-200">
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        )}

        {/* Message Input Composer */}
        <div className="p-4 border-t border-white/[0.08] bg-zinc-900/60 backdrop-blur-xl">
          <form onSubmit={handleSendMessage} className="max-w-3xl mx-auto flex flex-col gap-2">
            <div className="relative rounded-2xl border border-white/[0.12] bg-zinc-950/90 focus-within:border-indigo-500/80 focus-within:ring-2 focus-within:ring-indigo-500/20 shadow-xl transition-all">
              <textarea
                ref={textareaRef}
                rows={2}
                value={inputQuery}
                onChange={(e) => setInputQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={isGenerating}
                placeholder={
                  selectedDocFilter
                    ? "Ask questions scoped to selected document..."
                    : "Ask questions across all internal documents..."
                }
                className="w-full resize-none bg-transparent px-4 pt-3 pb-2 text-sm text-white placeholder-zinc-500 focus:outline-none leading-relaxed"
              />

              {/* Active Scope Tag */}
              {selectedDocFilter && (
                <div className="px-4 pb-1.5 flex items-center gap-1.5 text-[10px] text-indigo-400">
                  <span className="h-1.5 w-1.5 rounded-full bg-indigo-400" />
                  <span>Filtered to specific document</span>
                  <button
                    type="button"
                    onClick={() => setSelectedDocFilter("")}
                    className="hover:text-white"
                  >
                    (Clear)
                  </button>
                </div>
              )}

              {/* Bottom Control Strip */}
              <div className="flex items-center justify-between px-3 py-2 border-t border-white/[0.05] bg-zinc-900/40 rounded-b-2xl">
                <div className="flex items-center gap-2 text-[11px] text-zinc-400 font-mono">
                  <span className="flex items-center gap-1 px-2 py-0.5 rounded-md bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
                    <Sparkles className="h-3 w-3 text-indigo-400" />
                    Gemini 1.5 Pro
                  </span>
                  <span className="hidden sm:inline text-zinc-500">•</span>
                  <span className="hidden sm:inline text-zinc-500 text-[10px]">Enter ↵ to send</span>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setShowConfig(!showConfig)}
                    className="p-1.5 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 rounded-lg transition-colors text-xs flex items-center gap-1"
                    title="Configure RAG parameters"
                  >
                    <SlidersHorizontal className="h-3.5 w-3.5" />
                    <span className="text-[11px] font-medium hidden sm:inline">RAG Config</span>
                  </button>

                  <button
                    type="submit"
                    disabled={isGenerating || !inputQuery.trim()}
                    className="px-4 py-1.5 rounded-xl bg-gradient-to-r from-indigo-600 via-indigo-500 to-violet-600 hover:from-indigo-500 hover:to-violet-500 disabled:opacity-40 text-white text-xs font-semibold flex items-center gap-1.5 shadow-md shadow-indigo-600/30 transition-all hover:scale-[1.02] cursor-pointer"
                  >
                    {isGenerating ? (
                      <>
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        <span>Generating</span>
                      </>
                    ) : (
                      <>
                        <span>Send</span>
                        <Send className="h-3.5 w-3.5" />
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>
          </form>
        </div>
      </div>

      {/* CITATION INSPECTOR MODAL */}
      {selectedCitation && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 animate-in fade-in">
          <div className="w-full max-w-lg rounded-2xl border border-zinc-800 bg-zinc-900 p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <div className="flex items-center gap-2">
                <BookOpen className="h-5 w-5 text-indigo-400" />
                <h3 className="text-sm font-bold text-white">Citation Source Details</h3>
              </div>
              <button
                onClick={() => setSelectedCitation(null)}
                className="rounded-lg p-1 text-zinc-400 hover:bg-zinc-800 hover:text-white"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div className="rounded-xl bg-zinc-950 border border-zinc-800 p-3 space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-white text-sm">
                    {selectedCitation.document_title}
                  </span>
                  {selectedCitation.file_type && (
                    <span className="uppercase text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
                      {selectedCitation.file_type}
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-4 text-zinc-400 font-mono text-[11px]">
                  {selectedCitation.page_number && (
                    <span>Page: {selectedCitation.page_number}</span>
                  )}
                  {selectedCitation.score && (
                    <span>Relevance: {(selectedCitation.score * 100).toFixed(1)}%</span>
                  )}
                </div>
              </div>

              <div>
                <label className="text-zinc-400 font-semibold block mb-1">
                  Context Passage Snippet:
                </label>
                <div className="max-h-60 overflow-y-auto rounded-xl border border-zinc-800 bg-zinc-950 p-3.5 text-zinc-300 font-mono text-xs leading-relaxed whitespace-pre-wrap">
                  {selectedCitation.snippet}
                </div>
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <button
                onClick={() => setSelectedCitation(null)}
                className="rounded-xl bg-zinc-800 px-4 py-2 text-xs font-semibold text-zinc-200 hover:bg-zinc-700"
              >
                Close Inspector
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
