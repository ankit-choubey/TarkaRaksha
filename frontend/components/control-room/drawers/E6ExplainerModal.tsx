"use client";

import React from "react";
import {
  Shield,
  ShieldCheck,
  ShieldAlert,
  AlertTriangle,
  RotateCcw,
  CheckCircle2,
  FileCheck2,
  X,
  Play,
  ArrowRight,
  Database,
  Sparkles,
} from "lucide-react";

interface E6ExplainerModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirmRun: () => void;
  onRunInSimulator?: () => void;
  isRunning?: boolean;
}

export const E6ExplainerModal: React.FC<E6ExplainerModalProps> = ({
  isOpen,
  onClose,
  onConfirmRun,
  onRunInSimulator,
  isRunning = false,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in">
      <div className="relative w-full max-w-2xl rounded-3xl border border-neutral-200 bg-white p-7 sm:p-9 shadow-2xl space-y-6 font-sans text-neutral-900">
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-5 right-5 p-2 rounded-full text-neutral-400 hover:text-neutral-900 hover:bg-neutral-100 transition"
          aria-label="Close modal"
        >
          <X className="h-5 w-5" />
        </button>

        {/* Header */}
        <div className="space-y-2">
          <div className="inline-flex items-center space-x-2 rounded-full bg-rose-50 px-3.5 py-1 text-xs font-mono font-bold text-rose-800 border border-rose-200">
            <AlertTriangle className="h-3.5 w-3.5" />
            <span>Canonical E6 Hero Journey</span>
          </div>
          <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-neutral-900">
            What Does the E6 Run Do?
          </h2>
          <p className="text-sm text-neutral-600 leading-relaxed">
            E6 is TarkaRaksha&apos;s flagship adversarial verification milestone: proving how the system
            catches and autonomously recovers a live dynamic pricing surge without human intervention.
          </p>
        </div>

        {/* The 5-Step Story Breakdown */}
        <div className="space-y-3 font-sans text-xs">
          <div className="rounded-2xl bg-neutral-50 p-4 border border-neutral-200 space-y-2">
            <div className="flex items-center justify-between font-mono">
              <span className="font-bold text-neutral-900 uppercase">1. Authorized User Intent</span>
              <span className="text-emerald-700 font-bold bg-emerald-100 px-2 py-0.5 rounded-full">
                Ceiling: ₹50,000
              </span>
            </div>
            <p className="text-neutral-600">
              Buyer Agent Alice signs an immutable IntentContract for a 27&quot; 4K Studio Display with a strict ceiling of ₹50,000 (5,000,000 paise).
            </p>
          </div>

          <div className="rounded-2xl bg-rose-50 p-4 border border-rose-200 space-y-2">
            <div className="flex items-center justify-between font-mono">
              <span className="font-bold text-rose-900 uppercase">2. Merchant Surge (+₹5,000 Drift)</span>
              <span className="text-rose-800 font-bold bg-rose-200/80 px-2 py-0.5 rounded-full">
                Charged: ₹55,000
              </span>
            </div>
            <p className="text-rose-800">
              Merchant cart injects dynamic demand surge. Razorpay returns 200 OK (Payment Captured). Standard systems fail silently here.
            </p>
          </div>

          <div className="rounded-2xl bg-amber-50 p-4 border border-amber-200 space-y-2">
            <div className="flex items-center justify-between font-mono">
              <span className="font-bold text-amber-900 uppercase">3. T04 Gate Interception &amp; MRDP Proof</span>
              <span className="text-amber-800 font-bold bg-amber-200/80 px-2 py-0.5 rounded-full">
                Held in 11ms
              </span>
            </div>
            <p className="text-amber-800">
              T04 asserts 5,000,000 paise &lt;= 5,500,000 paise is a VIOLATION. Emits signed SHA-256 MRDP Proof #mrdp_e6 holding settlement.
            </p>
          </div>

          <div className="rounded-2xl bg-emerald-50 p-4 border border-emerald-200 space-y-2">
            <div className="flex items-center justify-between font-mono">
              <span className="font-bold text-emerald-900 uppercase">4. Autonomous Recovery &amp; Revalidation</span>
              <span className="text-emerald-800 font-bold bg-emerald-200/80 px-2 py-0.5 rounded-full">
                Discount: -₹5,000
              </span>
            </div>
            <p className="text-emerald-800">
              Recovery loop negotiates compensatory price-match discount within 1 round. Net payable revalidated to ₹50,000. Passport sealed.
            </p>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="pt-2 flex flex-col sm:flex-row items-center justify-end gap-3 border-t border-neutral-100">
          <button
            onClick={onClose}
            className="w-full sm:w-auto px-5 py-2.5 rounded-xl border border-neutral-300 text-xs font-semibold text-neutral-700 hover:bg-neutral-50"
          >
            Cancel
          </button>

          {onRunInSimulator && (
            <button
              onClick={() => {
                onClose();
                onRunInSimulator();
              }}
              className="w-full sm:w-auto px-5 py-2.5 rounded-xl border border-neutral-900 bg-white text-neutral-900 text-xs font-bold hover:bg-neutral-50 flex items-center justify-center space-x-1.5 shadow-2xs"
            >
              <Sparkles className="h-4 w-4 text-emerald-600" />
              <span>Test in Live Order Studio</span>
            </button>
          )}

          <button
            onClick={() => {
              onClose();
              onConfirmRun();
            }}
            disabled={isRunning}
            className="w-full sm:w-auto px-6 py-2.5 rounded-xl bg-neutral-900 text-white text-xs font-bold hover:bg-neutral-800 flex items-center justify-center space-x-2 shadow-md disabled:opacity-50"
          >
            <Play className="h-3.5 w-3.5 text-emerald-400" />
            <span>{isRunning ? "Executing E6..." : "Execute E6 in Control Room"}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
