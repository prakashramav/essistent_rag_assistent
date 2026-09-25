"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import { Building2, ShieldCheck, LogOut, CheckCircle2, AlertCircle, Sparkles, ChevronDown } from "lucide-react";

export default function Navbar() {
  const { user, activeOrg, organizations, switchOrg, logout } = useAuth();
  const [health, setHealth] = useState({ status: "checking", vector: false });

  useEffect(() => {
    let mounted = true;
    api.health()
      .then((res) => {
        if (mounted) {
          setHealth({ status: res.status, vector: res.pgvector_enabled });
        }
      })
      .catch(() => {
        if (mounted) {
          setHealth({ status: "offline", vector: false });
        }
      });
    return () => {
      mounted = false;
    };
  }, []);

  return (
    <header className="sticky top-0 z-50 w-full border-b border-white/[0.08] bg-zinc-950/75 backdrop-blur-xl transition-all">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Brand */}
        <div className="flex items-center gap-4">
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="relative flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-violet-500 shadow-lg shadow-indigo-500/25 group-hover:scale-105 transition-all">
              <ShieldCheck className="h-5 w-5 text-white" />
              <div className="absolute inset-0 rounded-xl bg-white/20 opacity-0 group-hover:opacity-100 transition-opacity" />
            </div>
            <div className="flex items-baseline gap-2">
              <span className="font-bold tracking-tight text-white group-hover:text-indigo-300 transition-colors text-base">
                Enterprise RAG
              </span>
              <span className="rounded-full bg-indigo-500/10 px-2 py-0.5 text-[10px] font-semibold text-indigo-400 border border-indigo-500/20 tracking-wider">
                v1.0
              </span>
            </div>
          </Link>

          {/* System Health Badge */}
          <div className="hidden md:flex items-center gap-2 ml-2 px-3 py-1 rounded-full text-xs border border-white/[0.06] bg-zinc-900/60 backdrop-blur-md">
            {health.status === "healthy" ? (
              <>
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
                </span>
                <span className="text-zinc-300 font-medium text-[11px]">System Online</span>
                {health.vector && (
                  <span className="text-[10px] font-mono bg-emerald-500/10 text-emerald-400 px-1.5 py-0.5 rounded border border-emerald-500/20">
                    pgvector
                  </span>
                )}
              </>
            ) : health.status === "checking" ? (
              <>
                <span className="h-2 w-2 rounded-full bg-amber-500 animate-pulse" />
                <span className="text-zinc-400 text-[11px]">Connecting...</span>
              </>
            ) : (
              <>
                <span className="h-2 w-2 rounded-full bg-rose-500" />
                <span className="text-rose-400 text-[11px]">Backend Offline</span>
              </>
            )}
          </div>
        </div>

        {/* Right side navigation & tenant selector */}
        <div className="flex items-center gap-3">
          {user ? (
            <>
              {/* Organization Switcher */}
              <div className="flex items-center gap-2 bg-zinc-900/80 hover:bg-zinc-900 border border-white/[0.08] rounded-xl px-3 py-1.5 text-xs text-zinc-300 shadow-sm transition-all">
                <Building2 className="h-3.5 w-3.5 text-indigo-400" />
                {organizations.length > 1 ? (
                  <div className="relative flex items-center">
                    <select
                      value={activeOrg?.id || ""}
                      onChange={(e) => switchOrg(e.target.value)}
                      className="bg-transparent text-white font-medium focus:outline-none cursor-pointer pr-4 appearance-none text-xs"
                    >
                      {organizations.map((org) => (
                        <option key={org.id} value={org.id} className="bg-zinc-900 text-white">
                          {org.name} ({org.role})
                        </option>
                      ))}
                    </select>
                    <ChevronDown className="h-3 w-3 text-zinc-400 pointer-events-none absolute right-0" />
                  </div>
                ) : (
                  <span className="font-semibold text-white text-xs">
                    {activeOrg?.name || "My Organization"}
                  </span>
                )}
                {activeOrg?.role && (
                  <span className="ml-1 text-[10px] uppercase font-mono px-2 py-0.5 rounded-full bg-gradient-to-r from-indigo-500/20 to-violet-500/20 text-indigo-300 border border-indigo-500/30 font-semibold">
                    {activeOrg.role}
                  </span>
                )}
              </div>

              {/* User Avatar & Logout */}
              <div className="flex items-center gap-3 pl-2 border-l border-white/[0.08]">
                <div className="flex flex-col text-right">
                  <span className="text-xs font-semibold text-zinc-100">
                    {user.fullName || user.email.split("@")[0]}
                  </span>
                  <span className="text-[10px] text-zinc-400 font-mono truncate max-w-[130px]">
                    {user.email}
                  </span>
                </div>
                <button
                  onClick={logout}
                  title="Sign out"
                  className="p-2 rounded-xl text-zinc-400 hover:text-rose-400 hover:bg-rose-500/10 border border-transparent hover:border-rose-500/20 transition-all"
                >
                  <LogOut className="h-4 w-4" />
                </button>
              </div>
            </>
          ) : (
            <div className="flex items-center gap-2">
              <Link
                href="/login"
                className="px-3.5 py-1.5 text-xs font-medium text-zinc-300 hover:text-white rounded-xl hover:bg-zinc-900 transition-colors"
              >
                Sign In
              </Link>
              <Link
                href="/signup"
                className="px-4 py-1.5 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-500 rounded-xl shadow-md shadow-indigo-600/25 transition-all hover:scale-[1.02]"
              >
                Get Started
              </Link>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
