"use client";

import React from "react";
import { DrawerContainer } from "./DrawerContainer";
import { ControlRoomSnapshot } from "../../../lib/types";
import { formatMoney } from "../../../lib/formatters";
import { RotateCcw, ArrowRight, ShieldCheck, CheckCircle2, AlertTriangle, Cpu } from "lucide-react";

interface RecoveryDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  snapshot: ControlRoomSnapshot;
}

export const RecoveryDrawer: React.FC<RecoveryDrawerProps> = ({
  isOpen,
  onClose,
  snapshot,
}) => {
  const recovery = snapshot.recovery;
  const isInvoked = recovery.recovery_invoked;
  const revalidatedPass = recovery.revalidated_pass;

  return (
    <DrawerContainer
      isOpen={isOpen}
      onClose={onClose}
      title="Bounded Autonomous Recovery Loop (T11)"
      subtitle="Auditing AI-proposed remediation candidates against deterministic safety bounds"
      badge={isInvoked ? (revalidatedPass ? "RECOVERED PASS" : "RECOVERY ACTIVE") : "BYPASSED"}
      badgeType={revalidatedPass ? "pass" : isInvoked ? "unknown" : "neutral"}
    >
      {/* 6-Stage Loop Progression */}
      <div className="rounded-xl border border-neutral-200 bg-neutral-50/70 p-4 space-y-2">
        <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-neutral-400 block">
          Recovery Loop Sequence
        </span>
        <div className="flex items-center flex-wrap gap-1.5 text-xs font-mono font-semibold">
          <span className="bg-rose-100 text-rose-800 px-2 py-0.5 rounded">DRIFT</span>
          <ArrowRight className="h-3 w-3 text-neutral-400" />
          <span className="bg-neutral-200 text-neutral-800 px-2 py-0.5 rounded">MRDP PROOF</span>
          <ArrowRight className="h-3 w-3 text-neutral-400" />
          <span className="bg-violet-100 text-violet-800 px-2 py-0.5 rounded">AI CANDIDATES</span>
          <ArrowRight className="h-3 w-3 text-neutral-400" />
          <span className="bg-neutral-800 text-white px-2 py-0.5 rounded">SELECTED ACTION</span>
          <ArrowRight className="h-3 w-3 text-neutral-400" />
          <span className="bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded">REVALIDATION</span>
          <ArrowRight className="h-3 w-3 text-neutral-400" />
          <span className="bg-emerald-600 text-white px-2 py-0.5 rounded">FINAL PASS</span>
        </div>
      </div>

      {isInvoked ? (
        <div className="space-y-4 text-xs">
          {/* Recovery Attempt Budget */}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <div className="rounded-xl bg-white p-3 border border-neutral-200 shadow-2xs">
              <span className="text-[10px] font-mono uppercase text-neutral-400 block">Attempt Budget</span>
              <span className="font-mono text-sm font-bold text-neutral-900">
                {recovery.attempts_count} / {recovery.max_attempts}
              </span>
              <span className="text-[10px] text-neutral-400 block mt-0.5">Strict bounded ceiling</span>
            </div>

            <div className="rounded-xl bg-white p-3 border border-neutral-200 shadow-2xs">
              <span className="text-[10px] font-mono uppercase text-neutral-400 block">Replan Rounds</span>
              <span className="font-mono text-sm font-bold text-neutral-900">{recovery.replan_rounds}</span>
              <span className="text-[10px] text-neutral-400 block mt-0.5">Iterative negotiation</span>
            </div>

            <div className="rounded-xl bg-white p-3 border border-neutral-200 shadow-2xs col-span-2 sm:col-span-1">
              <span className="text-[10px] font-mono uppercase text-neutral-400 block">Revalidation Status</span>
              <span className="font-mono text-xs font-bold text-emerald-700 flex items-center gap-1 mt-0.5">
                <CheckCircle2 className="h-3.5 w-3.5" />
                {revalidatedPass ? "CONFIRMED PASS" : "PENDING"}
              </span>
              <span className="text-[10px] text-neutral-400 block mt-0.5">Deterministic check</span>
            </div>
          </div>

          {/* Selected Action Details */}
          <div className="rounded-xl border border-neutral-200 bg-white p-4 space-y-2">
            <h4 className="font-mono text-[11px] font-bold text-neutral-400 uppercase tracking-wider pb-1 border-b border-neutral-100">
              Selected Safe Remediation Action
            </h4>
            <div className="space-y-1.5 text-neutral-700">
              <div className="flex justify-between">
                <span>Action Type:</span>
                <span className="font-mono font-bold text-neutral-900">
                  {recovery.action_type || "APPLY_MERCHANT_DISCOUNT"}
                </span>
              </div>
              {recovery.action_amount && (
                <div className="flex justify-between">
                  <span>Compensation Amount:</span>
                  <span className="font-mono font-bold text-emerald-700">
                    {formatMoney(recovery.action_amount)}
                  </span>
                </div>
              )}
              <div className="flex justify-between">
                <span>Remediation Policy:</span>
                <span className="font-mono text-neutral-800">Compensatory Price Match</span>
              </div>
            </div>
          </div>

          {/* AI vs Deterministic Safety Boundary */}
          <div className="rounded-xl bg-violet-50/50 p-4 border border-violet-200/80 text-violet-950 space-y-1.5 text-xs">
            <div className="flex items-center space-x-2 font-bold font-mono text-[11px] text-violet-800">
              <Cpu className="h-3.5 w-3.5 text-violet-600" />
              <span>AI Proposal Validation Boundary</span>
            </div>
            <p className="text-[11px] leading-relaxed text-violet-900 font-sans">
              The AI advisory agent formulated the price adjustment remedy. However, the transaction was held until the T04 Deterministic Engine independently re-evaluated all boundary rules and confirmed 0 remaining discrepancies.
            </p>
          </div>
        </div>
      ) : (
        <div className="rounded-xl bg-neutral-50 p-6 text-center text-neutral-500 border border-neutral-200">
          <ShieldCheck className="h-8 w-8 text-emerald-600 mx-auto mb-2" />
          <p className="font-semibold text-neutral-800">Recovery Bypassed</p>
          <p className="text-xs text-neutral-500 mt-1">
            Zero drift detected during the initial execution slice. Autonomous recovery loops are only engaged when deterministic integrity rules flag discrepancies.
          </p>
        </div>
      )}
    </DrawerContainer>
  );
};
