"use client";

import React, { useState } from "react";
import {
  CreditCard,
  ShieldCheck,
  ShieldAlert,
  ArrowRight,
  Database,
  Lock,
  Layers,
  CheckCircle2,
  AlertTriangle,
  RotateCcw,
  Sparkles,
  TrendingDown,
  TrendingUp,
  Scale,
} from "lucide-react";

export const RazorpayDeepDiveSection: React.FC = () => {
  const [activeStage, setActiveStage] = useState<number>(0);

  const stages = [
    {
      step: "01",
      title: "Gateway Order Creation",
      razorpayPerspective: "Creates order_rzp_990142 for ₹55,000. Assumes cart total is legitimate.",
      tarkaRakshaPerspective:
        "Validates that order ₹55,000 exceeds user signed ceiling ₹50,000. Flags +₹5,000 drift in memory before payment settlement.",
      moneyValuation: "Authorized: ₹50,000 (5,000,000 paise) | Observed: ₹55,000 (5,500,000 paise)",
      delta: "+ ₹5,000 (Unbudgeted Drift)",
      status: "DRIFT DETECTED",
    },
    {
      step: "02",
      title: "Customer Payment Capture",
      razorpayPerspective: "Customer authorizes card/UPI. Gateway transfers funds and returns 200 CAPTURED.",
      tarkaRakshaPerspective:
        "Interprets 200 CAPTURED as evidence of funds movement only. Enforces rule: CAPTURED != TRANSACTION SUCCESS.",
      moneyValuation: "Held in escrow state. Zero unverified release.",
      delta: "Status: Captured != Settled",
      status: "HELD FOR INTEGRITY",
    },
    {
      step: "03",
      title: "Asynchronous Webhook Ingestion",
      razorpayPerspective: "Emits payment.captured webhook with HMAC-SHA256 signature header.",
      tarkaRakshaPerspective:
        "Verifies secret key signature, deduplicates duplicate webhooks, normalizes evidence, and checks idempotency key.",
      moneyValuation: "Guarantees exact-once financial ledger recording.",
      delta: "Double Capture Blocked",
      status: "VERIFIED & BOUND",
    },
    {
      step: "04",
      title: "Autonomous Recovery & Revalidation",
      razorpayPerspective: "Does not participate in order repair. Gateway has no concept of autonomous negotiation.",
      tarkaRakshaPerspective:
        "T11 recovery loop applies -₹5,000 merchant credit. Revalidates net payable to ₹50,000. Unlocks passport.",
      moneyValuation: "Net Payable: Exactly ₹50,000.00 INR (Zero user loss).",
      delta: "Net Drift: 0 paise",
      status: "DETERMINISTIC PASS",
    },
  ];

  return (
    <section className="py-20 sm:py-28 bg-neutral-900 text-white border-b border-neutral-800">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8 space-y-12">
        {/* Header */}
        <div className="text-center space-y-3 max-w-3xl mx-auto">
          <div className="inline-flex items-center space-x-2 rounded-full bg-neutral-800 px-3.5 py-1 text-xs font-mono text-emerald-400 border border-neutral-700">
            <Scale className="h-3.5 w-3.5" />
            <span>Deep Architectural Comparison</span>
          </div>
          <h2 className="text-3xl sm:text-5xl font-bold tracking-tight text-white">
            How TarkaRaksha Values Every Rupee at Every Step
          </h2>
          <p className="text-neutral-400 text-sm sm:text-base">
            Payment gateways like Razorpay are masterpieces of money movement.
            TarkaRaksha sits on top as the transaction integrity authority, ensuring that what was charged
            matches what the user authorized.
          </p>
        </div>

        {/* Interactive Comparison Stepper */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          {stages.map((stg, idx) => (
            <button
              key={stg.step}
              onClick={() => setActiveStage(idx)}
              className={`p-4 rounded-2xl border text-left transition-all space-y-2 ${
                activeStage === idx
                  ? "bg-white text-neutral-900 border-white shadow-lg ring-2 ring-white"
                  : "bg-neutral-950 text-neutral-300 border-neutral-800 hover:border-neutral-700"
              }`}
            >
              <div className="flex items-center justify-between text-xs font-mono">
                <span className={activeStage === idx ? "text-neutral-400 font-bold" : "text-neutral-500"}>
                  STAGE {stg.step}
                </span>
                <span
                  className={`text-[9px] px-1.5 py-0.2 rounded font-bold ${
                    activeStage === idx ? "bg-neutral-100 text-neutral-900" : "bg-neutral-800 text-emerald-400"
                  }`}
                >
                  {stg.status}
                </span>
              </div>
              <h4 className="font-bold text-sm tracking-tight">{stg.title}</h4>
              <p className={`text-[11px] line-clamp-2 ${activeStage === idx ? "text-neutral-600" : "text-neutral-400"}`}>
                {stg.delta}
              </p>
            </button>
          ))}
        </div>

        {/* Deep Dive Stage Comparison Card */}
        <div className="rounded-3xl border border-neutral-800 bg-neutral-950 p-6 sm:p-8 space-y-6 shadow-2xl">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-4 border-b border-neutral-800">
            <div>
              <span className="text-[10px] font-mono text-emerald-400 uppercase font-bold tracking-wider">
                Stage 0{activeStage + 1} Deep Architectural Inspection
              </span>
              <h3 className="text-xl font-bold text-white tracking-tight mt-0.5">
                {stages[activeStage].title}
              </h3>
            </div>
            <div className="rounded-xl bg-neutral-900 p-2.5 border border-neutral-800 text-right font-mono text-xs">
              <span className="text-[10px] text-neutral-400 block uppercase">Money Valuation</span>
              <span className="text-emerald-400 font-bold">{stages[activeStage].delta}</span>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-xs">
            {/* Razorpay's Standard Gateway View */}
            <div className="rounded-2xl border border-neutral-800 bg-neutral-900/90 p-5 space-y-3">
              <div className="flex items-center space-x-2 pb-2 border-b border-neutral-800 text-[#3395ff]">
                <CreditCard className="h-4 w-4" />
                <span className="font-bold uppercase tracking-wider font-mono text-[11px]">
                  Standard Gateway Perspective (Razorpay)
                </span>
              </div>
              <p className="text-neutral-300 leading-relaxed font-sans text-xs">
                {stages[activeStage].razorpayPerspective}
              </p>
              <div className="p-3 rounded-xl bg-black/40 border border-neutral-800 font-mono text-[11px] text-neutral-400 space-y-1">
                <span className="text-neutral-500 block text-[10px] uppercase font-bold">Standard Gateway Limitation:</span>
                <p>Gateways treat all authorized amounts as valid. Zero semantic or price integrity auditing.</p>
              </div>
            </div>

            {/* TarkaRaksha's Deterministic Control Plane View */}
            <div className="rounded-2xl border border-emerald-900/60 bg-emerald-950/20 p-5 space-y-3">
              <div className="flex items-center space-x-2 pb-2 border-b border-emerald-900/40 text-emerald-400">
                <ShieldCheck className="h-4 w-4" />
                <span className="font-bold uppercase tracking-wider font-mono text-[11px]">
                  TarkaRaksha Deterministic Invariant
                </span>
              </div>
              <p className="text-neutral-200 leading-relaxed font-sans text-xs">
                {stages[activeStage].tarkaRakshaPerspective}
              </p>
              <div className="p-3 rounded-xl bg-emerald-950/40 border border-emerald-900/40 font-mono text-[11px] text-emerald-300 space-y-1">
                <span className="text-emerald-500 block text-[10px] uppercase font-bold">TarkaRaksha Guarantee:</span>
                <p>{stages[activeStage].moneyValuation}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
