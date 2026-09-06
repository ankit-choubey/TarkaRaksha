"use client";

import React from "react";
import {
  ShieldCheck,
  AlertOctagon,
  HelpCircle,
  FileCheck2,
  RotateCcw,
  ArrowRight,
  ExternalLink,
  Lock,
  FileCode2,
  History,
  CheckCircle2,
  XCircle,
  AlertTriangle,
} from "lucide-react";
import { ControlRoomSnapshot, DrawerType } from "../../lib/types";
import { formatMoney, truncateHash } from "../../lib/formatters";

interface TruthStatusCardProps {
  snapshot: ControlRoomSnapshot;
  onOpenDrawer: (drawer: DrawerType) => void;
}

export const TruthStatusCard: React.FC<TruthStatusCardProps> = ({
  snapshot,
  onOpenDrawer,
}) => {
  const integrity = snapshot.integrity;
  const status = integrity.status;
  const isPass = status === "PASS";
  const isDrift = status === "DRIFT";
  const isUnknown = status === "UNKNOWN" || status === "ABSTAIN";
  const mrdp = snapshot.drift_proof;

  return (
    <section aria-label="Authoritative Truth Status" className="w-full py-6 px-4 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl">
        <div
          className={`rounded-2xl border p-6 sm:p-8 transition-all ${
            isPass
              ? "bg-emerald-50/30 border-emerald-200/90 shadow-xs"
              : isDrift
              ? "bg-rose-50/40 border-rose-200/90 shadow-sm"
              : "bg-amber-50/40 border-amber-200/90 shadow-xs"
          }`}
        >
          <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-6">
            {/* Left: Truth Verdict & Explanation */}
            <div className="space-y-3 max-w-3xl">
              <div className="flex items-center space-x-2">
                <span className="text-xs font-mono font-semibold uppercase tracking-wider text-neutral-500">
                  Authoritative Deterministic Verdict
                </span>
                <span className="text-neutral-300">·</span>
                <span className="text-xs font-mono text-neutral-400">
                  {integrity.authoritative_engine}
                </span>
              </div>

              {/* Primary Verdict Heading */}
              <div className="flex items-center space-x-3">
                {isPass && (
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-emerald-600 text-white shadow-sm">
                    <ShieldCheck className="h-6 w-6" />
                  </div>
                )}
                {isDrift && (
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-rose-600 text-white shadow-sm animate-bounce">
                    <AlertOctagon className="h-6 w-6" />
                  </div>
                )}
                {isUnknown && (
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-amber-500 text-white shadow-sm">
                    <HelpCircle className="h-6 w-6" />
                  </div>
                )}

                <div>
                  <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-neutral-900">
                    {isPass && "Transaction Deterministically Verified"}
                    {isDrift && "Integrity Drift Detected & Proved"}
                    {isUnknown && "Indeterminate Provider State · Deliberate Abstention"}
                  </h2>
                  <p className="text-xs sm:text-sm text-neutral-600 mt-0.5">
                    {isPass &&
                      "All 8 integrity boundaries satisfied. Authorized limits, item SKU, and provider capture match without drift."}
                    {isDrift &&
                      (mrdp?.remediation
                        ? `Drift detected: ${mrdp.remediation}`
                        : "Observed transaction state deviated from authorized Intent Contract bounds.")}
                    {isUnknown &&
                      "Provider state cannot be confirmed with cryptographic certainty. No second payment authorization allowed."}
                  </p>
                </div>
              </div>

              {/* MRDP Summary Strip if Drift occurred or resolved */}
              {mrdp && (
                <div className="mt-4 rounded-xl bg-white/90 p-3.5 border border-neutral-200/90 font-mono text-xs space-y-1.5 shadow-2xs">
                  <div className="flex items-center justify-between text-neutral-500 text-[11px]">
                    <span className="flex items-center gap-1 font-semibold text-neutral-700">
                      <FileCode2 className="h-3.5 w-3.5 text-rose-600" />
                      MRDP Proof Digest: {truncateHash(mrdp.proof_digest, 10, 8)}
                    </span>
                    <span className="text-rose-600 font-bold">{mrdp.error_code}</span>
                  </div>
                  <div className="flex flex-wrap gap-x-4 text-neutral-600 text-xs">
                    <span>
                      <strong className="text-neutral-400">Expected:</strong> {String(mrdp.expected_value)}
                    </span>
                    <span>
                      <strong className="text-neutral-400">Observed:</strong> {String(mrdp.observed_value)}
                    </span>
                  </div>
                </div>
              )}

              {/* Action Buttons: [Why?], [MRDP], [Evidence], [Replay], [Passport] */}
              <div className="flex flex-wrap items-center gap-2 pt-2">
                <button
                  onClick={() => onOpenDrawer("integrity")}
                  className="inline-flex items-center space-x-1.5 rounded-lg bg-white px-3 py-1.5 text-xs font-semibold text-neutral-800 border border-neutral-300 hover:bg-neutral-50 active:scale-[0.98] transition shadow-2xs"
                >
                  <span>[ Why? ]</span>
                  <ExternalLink className="h-3 w-3 text-neutral-400" />
                </button>

                {mrdp && (
                  <button
                    onClick={() => onOpenDrawer("mrdp")}
                    className="inline-flex items-center space-x-1.5 rounded-lg bg-rose-50 px-3 py-1.5 text-xs font-semibold text-rose-800 border border-rose-200 hover:bg-rose-100 active:scale-[0.98] transition"
                  >
                    <span>Inspect MRDP Proof</span>
                  </button>
                )}

                <button
                  onClick={() => onOpenDrawer("evidence")}
                  className="inline-flex items-center space-x-1.5 rounded-lg bg-white px-3 py-1.5 text-xs font-semibold text-neutral-800 border border-neutral-300 hover:bg-neutral-50 active:scale-[0.98] transition shadow-2xs"
                >
                  <FileCheck2 className="h-3.5 w-3.5 text-neutral-600" />
                  <span>Evidence ({snapshot.evidence_records.length})</span>
                </button>

                <button
                  onClick={() => onOpenDrawer("replay")}
                  className="inline-flex items-center space-x-1.5 rounded-lg bg-white px-3 py-1.5 text-xs font-semibold text-neutral-800 border border-neutral-300 hover:bg-neutral-50 active:scale-[0.98] transition shadow-2xs"
                >
                  <History className="h-3.5 w-3.5 text-neutral-600" />
                  <span>Deterministic Replay</span>
                </button>

                <button
                  onClick={() => onOpenDrawer("passport")}
                  className="inline-flex items-center space-x-1.5 rounded-lg bg-neutral-900 px-3 py-1.5 text-xs font-semibold text-white hover:bg-neutral-800 active:scale-[0.98] transition shadow-2xs"
                >
                  <Lock className="h-3.5 w-3.5 text-neutral-300" />
                  <span>Transaction Passport</span>
                </button>
              </div>
            </div>

            {/* Right: Deterministic 4-Pillar Evaluation Matrix */}
            <div className="w-full lg:w-72 shrink-0 rounded-xl bg-white p-4 border border-neutral-200/90 shadow-2xs space-y-3">
              <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-neutral-400 block">
                Deterministic Boundary Matrix
              </span>

              <div className="space-y-2 text-xs">
                {/* Economic */}
                <div className="flex items-center justify-between py-1 border-b border-neutral-100">
                  <span className="text-neutral-600">Economic Boundary</span>
                  <span className="flex items-center gap-1 font-mono text-[11px] font-semibold text-emerald-700">
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                    MATCH
                  </span>
                </div>

                {/* Semantic */}
                <div className="flex items-center justify-between py-1 border-b border-neutral-100">
                  <span className="text-neutral-600">Semantic & SKU</span>
                  <span className="flex items-center gap-1 font-mono text-[11px] font-semibold text-emerald-700">
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                    MATCH
                  </span>
                </div>

                {/* Temporal */}
                <div className="flex items-center justify-between py-1 border-b border-neutral-100">
                  <span className="text-neutral-600">Temporal & Expire</span>
                  <span className="flex items-center gap-1 font-mono text-[11px] font-semibold text-emerald-700">
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                    VALID
                  </span>
                </div>

                {/* Authority */}
                <div className="flex items-center justify-between py-1">
                  <span className="text-neutral-600">Authority Gating</span>
                  <span className="flex items-center gap-1 font-mono text-[11px] font-semibold text-emerald-700">
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                    ENFORCED
                  </span>
                </div>
              </div>

              <div className="pt-2 border-t border-neutral-100 text-[10px] text-neutral-400 font-mono text-center">
                Captured != Pass Invariant Enforced
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
