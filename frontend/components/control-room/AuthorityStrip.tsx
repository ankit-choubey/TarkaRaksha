"use client";

import React, { useState } from "react";
import { ShieldCheck, Cpu, Database, Award, Info, CheckCircle2 } from "lucide-react";

export const AuthorityStrip: React.FC = () => {
  const [activeInfo, setActiveInfo] = useState<string | null>(null);

  return (
    <section aria-label="Authority Matrix" className="w-full bg-neutral-900 text-white py-3.5 px-4 sm:px-6 lg:px-8 border-b border-neutral-800 transition-colors">
      <div className="mx-auto max-w-7xl flex flex-col md:flex-row items-center justify-between gap-3">
        {/* Core invariant banner */}
        <div className="flex items-center space-x-3 text-xs sm:text-sm font-medium tracking-tight">
          <span className="flex h-2 w-2 rounded-full bg-emerald-400 ring-4 ring-emerald-400/20" />
          <span className="text-neutral-400 uppercase tracking-wider text-[11px] font-mono">
            Core Authority Invariant:
          </span>
          <span className="text-white font-semibold flex items-center gap-1.5 flex-wrap">
            <span className="text-violet-300">AI proposes</span>
            <span className="text-neutral-600">·</span>
            <span className="text-blue-300">Evidence proves</span>
            <span className="text-neutral-600">·</span>
            <span className="text-emerald-300">Deterministic logic decides</span>
          </span>
        </div>

        {/* Interactive Authority Category Chips */}
        <div className="flex items-center space-x-1.5 text-xs">
          {/* AI Chip */}
          <div className="group relative">
            <button
              onClick={() => setActiveInfo(activeInfo === "ai" ? null : "ai")}
              className="inline-flex items-center space-x-1 rounded-md bg-violet-950/70 border border-violet-700/50 px-2 py-0.5 text-[11px] font-mono text-violet-300 hover:bg-violet-900/80 transition"
            >
              <Cpu className="h-3 w-3 text-violet-400" />
              <span>AI (Advisory)</span>
            </button>
            <div className="absolute right-0 top-full mt-1.5 hidden group-hover:block z-50 w-64 rounded-lg bg-neutral-900 p-3 text-xs text-neutral-300 shadow-xl border border-neutral-700">
              <p className="font-semibold text-white mb-1">AI Authority: Advisory Only</p>
              <p className="text-[11px] leading-relaxed text-neutral-400">
                LLMs parse intent and draft candidate recovery options. They possess zero financial authority, zero payment permission, and cannot declare PASS.
              </p>
            </div>
          </div>

          {/* Provider Chip */}
          <div className="group relative">
            <button
              onClick={() => setActiveInfo(activeInfo === "provider" ? null : "provider")}
              className="inline-flex items-center space-x-1 rounded-md bg-blue-950/70 border border-blue-700/50 px-2 py-0.5 text-[11px] font-mono text-blue-300 hover:bg-blue-900/80 transition"
            >
              <Database className="h-3 w-3 text-blue-400" />
              <span>Provider (Gateway)</span>
            </button>
            <div className="absolute right-0 top-full mt-1.5 hidden group-hover:block z-50 w-64 rounded-lg bg-neutral-900 p-3 text-xs text-neutral-300 shadow-xl border border-neutral-700">
              <p className="font-semibold text-white mb-1">Provider: Razorpay Test Mode</p>
              <p className="text-[11px] leading-relaxed text-neutral-400">
                Provides authoritative payment capture records, order IDs, and webhook signatures. Note: Payment captured does not imply transaction success.
              </p>
            </div>
          </div>

          {/* Deterministic Engine Chip */}
          <div className="group relative">
            <button
              onClick={() => setActiveInfo(activeInfo === "det" ? null : "det")}
              className="inline-flex items-center space-x-1 rounded-md bg-emerald-950/70 border border-emerald-700/50 px-2 py-0.5 text-[11px] font-mono text-emerald-300 hover:bg-emerald-900/80 transition"
            >
              <ShieldCheck className="h-3 w-3 text-emerald-400" />
              <span>Deterministic (Authoritative)</span>
            </button>
            <div className="absolute right-0 top-full mt-1.5 hidden group-hover:block z-50 w-64 rounded-lg bg-neutral-900 p-3 text-xs text-neutral-300 shadow-xl border border-neutral-700">
              <p className="font-semibold text-white mb-1">T04 Deterministic Engine</p>
              <p className="text-[11px] leading-relaxed text-neutral-400">
                Authoritatively verifies economic, semantic, temporal, and authority boundaries. Issues MRDP drift proofs and validates recovery before gate unlocks.
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
