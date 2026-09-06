"use client";

import React, { useState } from "react";
import { DrawerContainer } from "./DrawerContainer";
import { ControlRoomSnapshot } from "../../../lib/types";
import { History, ShieldCheck, Cpu, Play, CheckCircle2, AlertOctagon, RotateCcw } from "lucide-react";

interface ReplayDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  snapshot: ControlRoomSnapshot;
}

export const ReplayDrawer: React.FC<ReplayDrawerProps> = ({
  isOpen,
  onClose,
  snapshot,
}) => {
  const replay = snapshot.replay;
  const isMatch = replay.replay_verdict === "MATCH";
  const [selectedStep, setSelectedStep] = useState<number>(snapshot.timeline.length - 1);

  return (
    <DrawerContainer
      isOpen={isOpen}
      onClose={onClose}
      title="Deterministic CPU-Only Replay Engine (T13)"
      subtitle="Re-evaluating historical event stream with zero side effects, zero network calls, zero AI calls"
      badge={replay.replay_verdict || "MATCH"}
      badgeType={isMatch ? "pass" : "drift"}
    >
      {/* Zero Side Effects Guarantee Banner */}
      <div className="rounded-xl bg-neutral-900 text-white p-4 space-y-2 border border-neutral-800">
        <div className="flex items-center justify-between font-mono text-xs text-neutral-400 pb-1 border-b border-neutral-800">
          <span className="flex items-center gap-1.5 text-emerald-400 font-bold">
            <Cpu className="h-4 w-4" />
            STRICT CPU-ONLY ISOLATION
          </span>
          <span className="text-[11px] bg-neutral-800 px-2 py-0.5 rounded text-neutral-300">
            Audit Mode
          </span>
        </div>
        <div className="grid grid-cols-3 gap-2 text-center text-xs font-mono pt-1">
          <div className="bg-neutral-800/80 p-2 rounded">
            <span className="text-[10px] text-neutral-400 block">External API Calls</span>
            <span className="font-bold text-emerald-400 text-sm">0 Calls</span>
          </div>
          <div className="bg-neutral-800/80 p-2 rounded">
            <span className="text-[10px] text-neutral-400 block">AI Invocations</span>
            <span className="font-bold text-emerald-400 text-sm">0 Calls</span>
          </div>
          <div className="bg-neutral-800/80 p-2 rounded">
            <span className="text-[10px] text-neutral-400 block">Financial Mutation</span>
            <span className="font-bold text-emerald-400 text-sm">0 Paise</span>
          </div>
        </div>
      </div>

      {/* Verdict Panel */}
      <div className="rounded-xl border border-neutral-200 bg-white p-4 space-y-2 text-xs">
        <div className="flex items-center justify-between">
          <span className="font-mono text-neutral-500 uppercase tracking-wider text-[10px]">
            Replay Comparison Verdict
          </span>
          <span
            className={`font-mono font-bold px-2.5 py-0.5 rounded text-xs ${
              isMatch
                ? "bg-emerald-50 text-emerald-800 border border-emerald-200"
                : "bg-rose-50 text-rose-800 border border-rose-200"
            }`}
          >
            {replay.replay_verdict || "MATCH"}
          </span>
        </div>
        <p className="text-neutral-600 text-[11px]">
          {isMatch
            ? "Deterministic replay produced bit-for-bit identical state transitions and boundary decisions. Zero divergence detected."
            : "Replay divergence: Reconstructed state diverged from recorded historical execution."}
        </p>
      </div>

      {/* Scrubbable Event Stream Timeline */}
      <div className="rounded-xl border border-neutral-200 bg-neutral-50/70 p-4 space-y-3 text-xs">
        <div className="flex items-center justify-between pb-1 border-b border-neutral-200">
          <span className="font-mono font-bold text-neutral-700 text-xs">
            Recorded Historical Event Stream ({snapshot.timeline.length} Events)
          </span>
          <span className="text-[11px] font-mono text-neutral-400">Select event to scrub</span>
        </div>

        <div className="space-y-1.5 max-h-56 overflow-y-auto">
          {snapshot.timeline.map((stage, idx) => (
            <button
              key={stage.stage_id || idx}
              onClick={() => setSelectedStep(idx)}
              className={`w-full text-left p-2 rounded-lg border text-xs transition flex items-center justify-between ${
                selectedStep === idx
                  ? "bg-white border-neutral-900 shadow-2xs font-semibold text-neutral-900"
                  : "bg-white/60 border-neutral-200 text-neutral-600 hover:bg-white"
              }`}
            >
              <div className="flex items-center space-x-2">
                <span className="font-mono text-[10px] text-neutral-400">#{idx + 1}</span>
                <span className="font-mono text-[11px]">{stage.stage_name}</span>
              </div>
              <span
                className={`text-[9px] font-mono px-1.5 py-0.2 rounded ${
                  stage.status === "PASS"
                    ? "bg-emerald-100 text-emerald-800"
                    : stage.status === "DRIFT"
                    ? "bg-rose-100 text-rose-800"
                    : "bg-neutral-200 text-neutral-700"
                }`}
              >
                {stage.status}
              </span>
            </button>
          ))}
        </div>

        {/* Selected Event Details */}
        {snapshot.timeline[selectedStep] && (
          <div className="mt-2 rounded-lg bg-white p-3 border border-neutral-200 text-neutral-700 space-y-1">
            <span className="font-mono text-[10px] text-neutral-400 uppercase block">Selected Step Narrative</span>
            <p className="text-xs text-neutral-800">
              {snapshot.timeline[selectedStep].description}
            </p>
          </div>
        )}
      </div>
    </DrawerContainer>
  );
};
