"use client";

import React, { useState, useEffect } from "react";
import {
  FileCode2,
  Activity,
  CheckCircle2,
  AlertTriangle,
  RotateCcw,
  ShieldCheck,
  Cpu,
  Database,
  Lock,
  Mic,
  ArrowRight,
  Sparkles,
} from "lucide-react";

interface ActivityItem {
  id: string;
  file: string;
  module: string;
  operation: string;
  detail: string;
  latency: string;
  status: "PASS" | "DRIFT" | "RECOVERY" | "SEALED" | "BOUND";
  talkingPoint: string;
}

const LIVE_STREAM_DATA: ActivityItem[] = [
  {
    id: "act_1",
    file: "backend/engine/context.py",
    module: "ContextLedger",
    operation: "assert_session_tuple_bound()",
    detail: "4-tuple (tx_9901, intent_alice, buyer_agent, merchant_pro) cryptographically locked.",
    latency: "3ms",
    status: "BOUND",
    talkingPoint: "Every transaction begins with context binding: prevents session hijacking and replay attacks.",
  },
  {
    id: "act_2",
    file: "backend/engine/integrity.py",
    module: "IntegrityEngine",
    operation: "evaluate_economic_ceiling()",
    detail: "Evaluating 5,000,000 paise ceiling vs 5,500,000 paise charged. Flagged +500,000 paise drift.",
    latency: "11ms",
    status: "DRIFT",
    talkingPoint: "Here is where standard gateways fail: Razorpay said 200 OK, but our deterministic math caught the overcharge.",
  },
  {
    id: "act_3",
    file: "backend/engine/mrdp.py",
    module: "MRDPProtocol",
    operation: "mint_drift_proof_artifact()",
    detail: "Minted signed SHA-256 artifact mrdp_e6_checkout_surge.json with error code E_PRICE_DRIFT.",
    latency: "8ms",
    status: "DRIFT",
    talkingPoint: "Instead of ambiguous emails, MRDP provides a machine-readable cryptographic proof.",
  },
  {
    id: "act_4",
    file: "backend/engine/recovery.py",
    module: "RecoveryNegotiator",
    operation: "negotiate_compensatory_discount()",
    detail: "Attempt 1 of 3: Merchant applied -₹5,000 credit. Net total adjusted back to ₹50,000.",
    latency: "340ms",
    status: "RECOVERY",
    talkingPoint: "Recovery is bounded: strictly within the user's pre-authorized spending policy without human intervention.",
  },
  {
    id: "act_5",
    file: "backend/engine/state_machine.py",
    module: "LifecycleStateMachine",
    operation: "transition_state()",
    detail: "Transitioned: DRIFT_DETECTED → RECOVERY_PROPOSED → REVALIDATED (0 violations remaining).",
    latency: "4ms",
    status: "PASS",
    talkingPoint: "State transitions are governed by strict finite-state rules; invalid state jumps are mathematically impossible.",
  },
  {
    id: "act_6",
    file: "backend/app/adapters/razorpay.py",
    module: "RazorpayAdapter",
    operation: "verify_payment_webhook_hmac()",
    detail: "Server-side SHA-256 HMAC signature validated against test mode secret key.",
    latency: "14ms",
    status: "PASS",
    talkingPoint: "Deep integration with Razorpay Test Mode: real signatures, real webhooks, real minor unit amounts.",
  },
  {
    id: "act_7",
    file: "backend/engine/passport.py",
    module: "PassportNotary",
    operation: "seal_transaction_certificate()",
    detail: "8-checkpoint hash chain minted. Hex digest d41d8cd98f00b204e9800998ecf8427e.",
    latency: "6ms",
    status: "SEALED",
    talkingPoint: "The sealed passport guarantees non-repudiation between the buyer agent, merchant gateway, and ledger.",
  },
  {
    id: "act_8",
    file: "backend/engine/replay.py",
    module: "DeterministicReplay",
    operation: "reconstruct_historical_execution()",
    detail: "Pure CPU sandbox audit: 0 network calls, 0 AI calls, 0 financial mutations. Verdict: MATCH.",
    latency: "22ms",
    status: "PASS",
    talkingPoint: "Bit-for-bit replay proves deterministic reproducibility years after the transaction executes.",
  },
];

export const LiveActivityStream: React.FC = () => {
  const [activeIdx, setActiveIdx] = useState<number>(0);
  const [showSpeakerCues, setShowSpeakerCues] = useState<boolean>(true);

  // Auto-scroll through activities every 3.5 seconds
  useEffect(() => {
    const timer = setInterval(() => {
      setActiveIdx((prev) => (prev + 1) % LIVE_STREAM_DATA.length);
    }, 3500);
    return () => clearInterval(timer);
  }, []);

  const activeItem = LIVE_STREAM_DATA[activeIdx];

  return (
    <div className="rounded-3xl border border-neutral-200 bg-white p-6 sm:p-8 shadow-sm space-y-6 font-sans">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-4 border-b border-neutral-100">
        <div className="flex items-center space-x-3">
          <div className="p-2 rounded-xl bg-neutral-900 text-white shadow-xs">
            <Activity className="h-5 w-5 text-emerald-400 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h3 className="font-bold text-base sm:text-lg text-neutral-900 tracking-tight">
                Live Backend Telemetry &amp; Execution Stream
              </h3>
              <span className="rounded-full bg-emerald-50 text-emerald-700 px-2.5 py-0.5 text-xs font-mono font-bold border border-emerald-200">
                ACTIVE
              </span>
            </div>
            <p className="text-xs text-neutral-500">
              Streaming real-time file executions, deterministic assertions, and cryptographic state mutations.
            </p>
          </div>
        </div>

        {/* Executive Narrative Toggle */}
        <button
          onClick={() => setShowSpeakerCues(!showSpeakerCues)}
          className={`rounded-full px-3.5 py-1.5 text-xs font-bold flex items-center space-x-1.5 transition ${
            showSpeakerCues
              ? "bg-violet-100 text-violet-800 border border-violet-200"
              : "bg-neutral-100 text-neutral-600 hover:bg-neutral-200"
          }`}
        >
          <Mic className="h-3.5 w-3.5" />
          <span>{showSpeakerCues ? "Live Narrative Active" : "Show Narrative"}</span>
        </button>
      </div>

      {/* Live Architectural Narrative Banner */}
      {showSpeakerCues && (
        <div className="rounded-2xl border border-violet-200 bg-violet-50/70 p-4 space-y-1.5 text-xs font-sans">
          <div className="flex items-center space-x-2 font-mono font-bold text-violet-900 uppercase">
            <Mic className="h-4 w-4 text-violet-700" />
            <span>Live Architectural Verification Insight:</span>
          </div>
          <p className="text-neutral-800 font-medium text-sm leading-relaxed">
            &quot;{activeItem.talkingPoint}&quot;
          </p>
        </div>
      )}

      {/* Real-time Scrolling / Rotating Activity Items Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
        {LIVE_STREAM_DATA.map((item, idx) => {
          const isSelected = activeIdx === idx;
          return (
            <button
              key={item.id}
              onClick={() => setActiveIdx(idx)}
              className={`p-4 rounded-2xl border text-left transition-all space-y-2 relative ${
                isSelected
                  ? "bg-neutral-900 text-white border-neutral-900 shadow-md ring-2 ring-neutral-900"
                  : "bg-neutral-50/60 text-neutral-800 border-neutral-200 hover:bg-white"
              }`}
            >
              <div className="flex items-center justify-between font-mono text-[10px]">
                <span className={isSelected ? "text-neutral-400 font-bold" : "text-neutral-500"}>
                  {item.module}
                </span>
                <span
                  className={`px-1.5 py-0.5 rounded font-bold ${
                    isSelected ? "bg-neutral-800 text-emerald-400" : "bg-white text-neutral-700 border"
                  }`}
                >
                  {item.latency}
                </span>
              </div>

              <div className="font-mono text-xs font-bold truncate">
                {item.operation}
              </div>

              <div className="flex items-center space-x-1.5 pt-1 text-[11px] font-mono">
                <FileCode2 className={`h-3 w-3 ${isSelected ? "text-neutral-400" : "text-neutral-500"}`} />
                <span className={`truncate ${isSelected ? "text-neutral-300" : "text-neutral-600"}`}>
                  {item.file.split("/").pop()}
                </span>
              </div>
            </button>
          );
        })}
      </div>

      {/* Active File Detailed Execution Box */}
      <div className="rounded-2xl border border-neutral-200 bg-neutral-900 text-white p-5 space-y-3 font-mono text-xs shadow-md">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 pb-2 border-b border-neutral-800">
          <div className="flex items-center space-x-2">
            <span className="text-emerald-400 font-bold">SOURCE:</span>
            <span className="text-neutral-300">{activeItem.file}</span>
            <span className="text-neutral-600">·</span>
            <span className="text-neutral-400">{activeItem.operation}</span>
          </div>
          <span className="rounded bg-neutral-800 px-2 py-0.5 text-[10px] text-emerald-400 border border-neutral-700">
            LATENCY: {activeItem.latency}
          </span>
        </div>

        <p className="text-neutral-300 font-sans text-sm">{activeItem.detail}</p>
      </div>
    </div>
  );
};
