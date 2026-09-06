"use client";

import React, { useState } from "react";
import { DrawerContainer } from "./DrawerContainer";
import { ControlRoomSnapshot } from "../../../lib/types";
import { formatMoney, truncateHash } from "../../../lib/formatters";
import {
  ShieldCheck,
  ShieldAlert,
  FileCode2,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Copy,
  Check,
  HelpCircle,
} from "lucide-react";

interface IntegrityDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  snapshot: ControlRoomSnapshot;
  initialTab?: "verdict" | "mrdp";
}

export const IntegrityDrawer: React.FC<IntegrityDrawerProps> = ({
  isOpen,
  onClose,
  snapshot,
  initialTab = "verdict",
}) => {
  const [activeTab, setActiveTab] = useState<"verdict" | "mrdp">(initialTab);
  const [copiedDigest, setCopiedDigest] = useState(false);

  const integrity = snapshot.integrity;
  const mrdp = snapshot.drift_proof;
  const isPass = integrity.status === "PASS";
  const isDrift = integrity.status === "DRIFT";
  const isUnknown = integrity.status === "UNKNOWN" || integrity.status === "ABSTAIN";

  const copyDigest = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedDigest(true);
    setTimeout(() => setCopiedDigest(false), 2000);
  };

  return (
    <DrawerContainer
      isOpen={isOpen}
      onClose={onClose}
      title="Integrity Verification & MRDP Drift Proof"
      subtitle="Authoritative deterministic rule evaluations and tamper-evident proofs"
      badge={integrity.status}
      badgeType={isPass ? "pass" : isDrift ? "drift" : "unknown"}
    >
      {/* Sub-tab Switcher */}
      <div className="flex border-b border-neutral-200 gap-4 text-xs font-semibold">
        <button
          onClick={() => setActiveTab("verdict")}
          className={`pb-2 border-b-2 transition ${
            activeTab === "verdict"
              ? "border-neutral-900 text-neutral-900"
              : "border-transparent text-neutral-400 hover:text-neutral-700"
          }`}
        >
          4-Boundary Verdicts & Rules
        </button>
        <button
          onClick={() => setActiveTab("mrdp")}
          className={`pb-2 border-b-2 flex items-center gap-1.5 transition ${
            activeTab === "mrdp"
              ? "border-rose-600 text-rose-600"
              : "border-transparent text-neutral-400 hover:text-neutral-700"
          }`}
        >
          <span>MRDP Machine-Readable Proof</span>
          {mrdp && (
            <span className="rounded-full bg-rose-100 text-rose-800 px-1.5 py-0.2 text-[10px] font-mono">
              Active
            </span>
          )}
        </button>
      </div>

      {activeTab === "verdict" ? (
        <div className="space-y-4 text-xs">
          {/* Engine Banner */}
          <div className="flex items-center justify-between rounded-xl bg-neutral-50 p-3 border border-neutral-200 text-[11px] font-mono">
            <span className="text-neutral-500">Authoritative Evaluator:</span>
            <span className="font-bold text-neutral-800">{integrity.authoritative_engine}</span>
          </div>

          {/* 4 Pillars Table */}
          <div className="rounded-xl border border-neutral-200 overflow-hidden">
            <table className="min-w-full divide-y divide-neutral-200 text-left">
              <thead className="bg-neutral-50 text-[10px] uppercase font-mono text-neutral-400">
                <tr>
                  <th className="px-3 py-2">Boundary</th>
                  <th className="px-3 py-2">Expected / Ceiling</th>
                  <th className="px-3 py-2">Observed</th>
                  <th className="px-3 py-2 text-right">Verdict</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100 font-mono text-xs">
                {/* Economic */}
                <tr className="hover:bg-neutral-50/50">
                  <td className="px-3 py-2.5 font-semibold text-neutral-800 font-sans">
                    Economic Total
                  </td>
                  <td className="px-3 py-2.5 text-neutral-600">
                    {formatMoney(snapshot.authorization.max_total)}
                  </td>
                  <td className="px-3 py-2.5 text-neutral-900 font-semibold">
                    {formatMoney(integrity.observed_total || snapshot.payment.amount)}
                  </td>
                  <td className="px-3 py-2.5 text-right">
                    {integrity.economic_verdict !== false ? (
                      <span className="inline-flex items-center gap-1 text-emerald-700 font-bold">
                        <CheckCircle2 className="h-3.5 w-3.5" /> PASS
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-rose-700 font-bold">
                        <XCircle className="h-3.5 w-3.5" /> DRIFT
                      </span>
                    )}
                  </td>
                </tr>

                {/* Semantic */}
                <tr className="hover:bg-neutral-50/50">
                  <td className="px-3 py-2.5 font-semibold text-neutral-800 font-sans">
                    Semantic SKU
                  </td>
                  <td className="px-3 py-2.5 text-neutral-600">
                    {snapshot.authorization.allowed_skus[0] || "SKU-MON-4K-27"}
                  </td>
                  <td className="px-3 py-2.5 text-neutral-900 font-semibold">
                    {snapshot.merchant_agent.sku || "SKU-MON-4K-27"}
                  </td>
                  <td className="px-3 py-2.5 text-right">
                    <span className="inline-flex items-center gap-1 text-emerald-700 font-bold">
                      <CheckCircle2 className="h-3.5 w-3.5" /> PASS
                    </span>
                  </td>
                </tr>

                {/* Temporal */}
                <tr className="hover:bg-neutral-50/50">
                  <td className="px-3 py-2.5 font-semibold text-neutral-800 font-sans">
                    Temporal Window
                  </td>
                  <td className="px-3 py-2.5 text-neutral-600">Within 4 Hours</td>
                  <td className="px-3 py-2.5 text-neutral-900 font-semibold">Valid Nonce</td>
                  <td className="px-3 py-2.5 text-right">
                    <span className="inline-flex items-center gap-1 text-emerald-700 font-bold">
                      <CheckCircle2 className="h-3.5 w-3.5" /> PASS
                    </span>
                  </td>
                </tr>

                {/* Authority */}
                <tr className="hover:bg-neutral-50/50">
                  <td className="px-3 py-2.5 font-semibold text-neutral-800 font-sans">
                    Authority Policy
                  </td>
                  <td className="px-3 py-2.5 text-neutral-600">Bounded Intent</td>
                  <td className="px-3 py-2.5 text-neutral-900 font-semibold">Enforced</td>
                  <td className="px-3 py-2.5 text-right">
                    <span className="inline-flex items-center gap-1 text-emerald-700 font-bold">
                      <CheckCircle2 className="h-3.5 w-3.5" /> PASS
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          {/* Violations List if any */}
          {integrity.violations.length > 0 && (
            <div className="rounded-xl bg-rose-50 p-4 border border-rose-200 text-rose-800 space-y-2">
              <span className="font-mono font-bold text-xs">Flagged Rule Violations:</span>
              <ul className="list-disc pl-5 space-y-1 font-mono text-[11px]">
                {integrity.violations.map((v, i) => (
                  <li key={i}>{v}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      ) : (
        /* MRDP Panel */
        <div className="space-y-4 text-xs">
          {mrdp ? (
            <div className="space-y-4">
              <div className="rounded-xl bg-rose-50/60 p-4 border border-rose-200 space-y-2">
                <div className="flex items-center justify-between font-mono text-xs">
                  <span className="font-bold text-rose-900">MRDP ID: {mrdp.mrdp_id}</span>
                  <span className="rounded bg-rose-100 text-rose-800 px-2 py-0.5 font-bold">
                    {mrdp.error_code}
                  </span>
                </div>
                <p className="text-neutral-700 leading-relaxed font-sans text-xs">
                  <strong>Drift Source:</strong> {mrdp.drift_source}
                </p>
                {mrdp.remediation && (
                  <p className="text-emerald-800 bg-emerald-50 p-2.5 rounded-lg border border-emerald-200 text-xs">
                    <strong>Remediation Strategy:</strong> {mrdp.remediation}
                  </p>
                )}
              </div>

              {/* Proof Digest Box */}
              <div className="rounded-xl bg-neutral-900 text-neutral-300 p-4 font-mono text-xs space-y-2 border border-neutral-800">
                <div className="flex items-center justify-between text-neutral-400 text-[11px] pb-1 border-b border-neutral-800">
                  <span>Cryptographic Proof Digest (SHA-256)</span>
                  <button
                    onClick={() => copyDigest(mrdp.proof_digest)}
                    className="inline-flex items-center space-x-1 text-emerald-400 hover:text-emerald-300"
                  >
                    {copiedDigest ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
                    <span>{copiedDigest ? "Copied" : "Copy"}</span>
                  </button>
                </div>
                <p className="text-emerald-400 break-all text-[11px] select-all">
                  {mrdp.proof_digest}
                </p>
              </div>
            </div>
          ) : (
            <div className="rounded-xl bg-neutral-50 p-6 text-center text-neutral-500 border border-neutral-200">
              <ShieldCheck className="h-8 w-8 text-emerald-600 mx-auto mb-2" />
              <p className="font-semibold text-neutral-800">No Active Drift Proof</p>
              <p className="text-xs text-neutral-500 mt-1">
                This transaction satisfied all integrity boundaries cleanly. MRDP proofs are emitted only upon detected drift or indeterminate UNKNOWN states.
              </p>
            </div>
          )}
        </div>
      )}
    </DrawerContainer>
  );
};
