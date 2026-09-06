"use client";

import React, { useState } from "react";
import {
  Copy,
  Check,
  Clock,
  Layers,
  ArrowRight,
  ShieldCheck,
  AlertTriangle,
  HelpCircle,
  ChevronDown,
  Hash,
  ExternalLink,
} from "lucide-react";
import { ControlRoomSnapshot, ControlRoomSummary } from "../../lib/types";
import { formatMoney, formatTimestamp, truncateHash } from "../../lib/formatters";

interface TransactionHeaderProps {
  snapshot: ControlRoomSnapshot;
  recentSummaries: ControlRoomSummary[];
  onSelectTransaction: (txId: string) => void;
}

export const TransactionHeader: React.FC<TransactionHeaderProps> = ({
  snapshot,
  recentSummaries,
  onSelectTransaction,
}) => {
  const [copiedField, setCopiedField] = useState<string | null>(null);
  const [showDropdown, setShowDropdown] = useState<boolean>(false);

  const copyToClipboard = (text: string, fieldName: string) => {
    navigator.clipboard.writeText(text);
    setCopiedField(fieldName);
    setTimeout(() => setCopiedField(null), 2000);
  };

  const integrityStatus = snapshot.integrity.status;
  const isPass = integrityStatus === "PASS";
  const isDrift = integrityStatus === "DRIFT";
  const isUnknown = integrityStatus === "UNKNOWN" || integrityStatus === "ABSTAIN";

  const getStatusBadge = () => {
    if (isPass) {
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-800 border border-emerald-200">
          <span className="h-2 w-2 rounded-full bg-emerald-500" />
          INTEGRITY PASS
        </span>
      );
    }
    if (isDrift) {
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-rose-50 px-3 py-1 text-xs font-semibold text-rose-800 border border-rose-200 animate-pulse">
          <span className="h-2 w-2 rounded-full bg-rose-500" />
          DRIFT DETECTED
        </span>
      );
    }
    if (isUnknown) {
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-800 border border-amber-200">
          <span className="h-2 w-2 rounded-full bg-amber-500" />
          UNKNOWN / ABSTAINED
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-neutral-100 px-3 py-1 text-xs font-semibold text-neutral-800 border border-neutral-200">
        <span className="h-2 w-2 rounded-full bg-neutral-400" />
        {snapshot.lifecycle.current_state}
      </span>
    );
  };

  return (
    <section aria-label="Transaction Overview" className="w-full bg-neutral-50/80 border-b border-neutral-200/90 py-4 px-4 sm:px-6 lg:px-8 transition-all">
      <div className="mx-auto max-w-7xl">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
          {/* Left Column: Transaction ID, Selector, and Basic Context */}
          <div className="space-y-1.5">
            <div className="flex items-center flex-wrap gap-2.5">
              {/* Transaction Selector Dropdown */}
              <div className="relative">
                <button
                  onClick={() => setShowDropdown(!showDropdown)}
                  className="inline-flex items-center space-x-1.5 rounded-lg bg-white px-2.5 py-1 text-xs font-mono text-neutral-800 border border-neutral-300 hover:border-neutral-400 shadow-xs"
                >
                  <Hash className="h-3 w-3 text-neutral-400" />
                  <span className="font-semibold">{snapshot.identity.transaction_id}</span>
                  <ChevronDown className="h-3 w-3 text-neutral-400 ml-1" />
                </button>

                {showDropdown && (
                  <div className="absolute left-0 top-full mt-1.5 z-50 w-72 rounded-xl bg-white p-2 shadow-xl border border-neutral-200 text-xs">
                    <p className="px-2 py-1 text-[11px] font-semibold text-neutral-400 uppercase tracking-wider">
                      Recent Transactions
                    </p>
                    <div className="mt-1 space-y-1 max-h-56 overflow-y-auto">
                      {recentSummaries.map((s) => (
                        <button
                          key={s.transaction_id}
                          onClick={() => {
                            onSelectTransaction(s.transaction_id);
                            setShowDropdown(false);
                          }}
                          className={`w-full text-left px-2.5 py-1.5 rounded-md flex items-center justify-between transition ${
                            s.transaction_id === snapshot.identity.transaction_id
                              ? "bg-neutral-100 font-semibold text-neutral-900"
                              : "hover:bg-neutral-50 text-neutral-600"
                          }`}
                        >
                          <div className="truncate pr-2">
                            <span className="font-mono text-[11px] block">{s.transaction_id}</span>
                            <span className="text-[10px] text-neutral-400 block truncate">{s.intent_id}</span>
                          </div>
                          <span
                            className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${
                              s.integrity_status === "PASS"
                                ? "bg-emerald-100 text-emerald-800"
                                : s.integrity_status === "DRIFT"
                                ? "bg-rose-100 text-rose-800"
                                : "bg-amber-100 text-amber-800"
                            }`}
                          >
                            {s.integrity_status}
                          </span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Copy Transaction ID button */}
              <button
                onClick={() => copyToClipboard(snapshot.identity.transaction_id, "tx")}
                className="inline-flex items-center space-x-1 text-neutral-400 hover:text-neutral-700 p-1 text-xs"
                title="Copy Transaction ID"
              >
                {copiedField === "tx" ? (
                  <Check className="h-3.5 w-3.5 text-emerald-600" />
                ) : (
                  <Copy className="h-3.5 w-3.5" />
                )}
              </button>

              {/* Status Badge */}
              {getStatusBadge()}

              {/* Execution Mode */}
              <span className="rounded-full bg-neutral-200/70 px-2 py-0.5 text-[10px] font-mono text-neutral-600 border border-neutral-300">
                {snapshot.execution_mode}
              </span>
            </div>

            {/* Sub-identifiers: Intent, Order, Payment */}
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-neutral-500 font-mono">
              <span className="flex items-center gap-1">
                <span className="text-neutral-400">Intent:</span>
                <span className="text-neutral-700 font-medium">{snapshot.identity.intent_id}</span>
              </span>
              <span className="text-neutral-300">·</span>
              <span className="flex items-center gap-1">
                <span className="text-neutral-400">Order:</span>
                <span className="text-neutral-700 font-medium">{snapshot.identity.order_id}</span>
              </span>
              <span className="text-neutral-300">·</span>
              <span className="flex items-center gap-1">
                <span className="text-neutral-400">Payment:</span>
                <span className="text-neutral-700 font-medium">{snapshot.identity.payment_id}</span>
              </span>
              <span className="text-neutral-300">·</span>
              <span className="flex items-center gap-1">
                <Clock className="h-3 w-3 text-neutral-400" />
                <span>{formatTimestamp(snapshot.lifecycle.started_at)}</span>
                {snapshot.lifecycle.duration_ms && (
                  <span className="text-neutral-400">({snapshot.lifecycle.duration_ms}ms)</span>
                )}
              </span>
            </div>
          </div>

          {/* Right Column: Key Economic Metrics */}
          <div className="flex items-center gap-4 sm:gap-6 bg-white rounded-xl p-3 border border-neutral-200/90 shadow-2xs">
            {/* Authorized Ceiling */}
            <div className="space-y-0.5">
              <span className="text-[10px] font-medium uppercase tracking-wider text-neutral-400 font-mono block">
                Authorized Max
              </span>
              <span className="font-mono text-sm font-semibold text-neutral-900 block">
                {formatMoney(snapshot.authorization.max_total)}
              </span>
              <span className="text-[10px] text-neutral-400 font-mono">Intent Ceiling</span>
            </div>

            <div className="h-8 w-px bg-neutral-200" />

            {/* Observed Total */}
            <div className="space-y-0.5">
              <span className="text-[10px] font-medium uppercase tracking-wider text-neutral-400 font-mono block">
                Observed Total
              </span>
              <span
                className={`font-mono text-sm font-semibold block ${
                  isDrift
                    ? "text-rose-600"
                    : isPass
                    ? "text-emerald-700"
                    : "text-neutral-900"
                }`}
              >
                {formatMoney(snapshot.integrity.observed_total || snapshot.payment.amount)}
              </span>
              <span className="text-[10px] text-neutral-400 font-mono">
                {snapshot.payment.payment_captured ? "Payment Captured" : "Pre-capture"}
              </span>
            </div>

            <div className="h-8 w-px bg-neutral-200" />

            {/* Replay Verification */}
            <div className="space-y-0.5">
              <span className="text-[10px] font-medium uppercase tracking-wider text-neutral-400 font-mono block">
                Replay Audit
              </span>
              <span
                className={`font-mono text-sm font-semibold block ${
                  snapshot.replay.replay_verdict === "MATCH"
                    ? "text-emerald-700"
                    : "text-amber-700"
                }`}
              >
                {snapshot.replay.replay_verdict || "PENDING"}
              </span>
              <span className="text-[10px] text-neutral-400 font-mono">CPU Deterministic</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
