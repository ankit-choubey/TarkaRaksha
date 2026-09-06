"use client";

import React from "react";
import { DrawerContainer } from "./DrawerContainer";
import { ControlRoomSnapshot } from "../../../lib/types";
import { ShieldAlert, ShieldCheck, Lock, AlertTriangle, CheckCircle2, XCircle } from "lucide-react";

interface SecurityDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  snapshot: ControlRoomSnapshot;
}

export const SecurityDrawer: React.FC<SecurityDrawerProps> = ({
  isOpen,
  onClose,
  snapshot,
}) => {
  const sec = snapshot.security;
  const isClean = sec.threat_status === "CLEAN";

  const threatMatrix = [
    {
      threat: "Adversarial Prompt Injection",
      agent: "Merchant Payload",
      rule: "AI Advisory Isolation",
      action: "Advisory LLM output quarantined; Deterministic ceiling strictly enforced.",
      result: sec.prompt_injection_detected ? "BLOCKED" : "CLEAN",
    },
    {
      threat: "Unauthorized Capability Escalation",
      agent: "Merchant / Buyer Agent",
      rule: "E4 Policy Capability Gating",
      action: "Capabilities verified against signed authorization manifest before dispatch.",
      result: "ENFORCED",
    },
    {
      threat: "Intent Token Replay Attack",
      agent: "Untrusted Client",
      rule: "E1 Context Binding Verification",
      action: "Freshness and nonces validated against ledger. Stale session rejected.",
      result: "CLEAN",
    },
    {
      threat: "Evidence Payload Tampering",
      agent: "Network Intermediary",
      rule: "HMAC-SHA256 Signature Audit",
      action: "Signatures recomputed with secret keys. Tampered frames discarded.",
      result: sec.tampering_detected ? "TAMPER_DETECTED" : "VERIFIED",
    },
  ];

  return (
    <DrawerContainer
      isOpen={isOpen}
      onClose={onClose}
      title="Transaction Security & Threat Isolation (E4)"
      subtitle="Guarding autonomous agentic transactions against prompt injection, replay attacks, and capability abuse"
      badge={sec.threat_status}
      badgeType={isClean ? "pass" : "drift"}
    >
      {/* Kill Switch & Safety State */}
      <div className="grid grid-cols-2 gap-3 text-xs">
        <div className="rounded-xl border border-neutral-200 bg-white p-3 shadow-2xs">
          <span className="text-[10px] font-mono uppercase text-neutral-400 block">Kill Switch State</span>
          <span className="font-mono text-sm font-bold text-emerald-700 flex items-center gap-1.5 mt-0.5">
            <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
            {sec.kill_switch_state}
          </span>
        </div>

        <div className="rounded-xl border border-neutral-200 bg-white p-3 shadow-2xs">
          <span className="text-[10px] font-mono uppercase text-neutral-400 block">Context 4-Tuple Binding</span>
          <span className="font-mono text-sm font-bold text-neutral-900 flex items-center gap-1.5 mt-0.5">
            <CheckCircle2 className="h-4 w-4 text-emerald-600" />
            {sec.binding_verified ? "LOCKED & BOUND" : "MISMATCH"}
          </span>
        </div>
      </div>

      {/* Threat Matrix Table */}
      <div className="rounded-xl border border-neutral-200 overflow-hidden text-xs">
        <div className="bg-neutral-50 px-4 py-2.5 border-b border-neutral-200 font-mono text-[11px] font-bold text-neutral-700 uppercase tracking-wider">
          Transaction Threat Defenses
        </div>

        <div className="divide-y divide-neutral-100">
          {threatMatrix.map((item, i) => (
            <div key={i} className="p-3.5 space-y-1 bg-white hover:bg-neutral-50/50">
              <div className="flex items-center justify-between">
                <span className="font-bold text-neutral-900 font-sans">{item.threat}</span>
                <span
                  className={`font-mono text-[10px] px-2 py-0.5 rounded font-bold ${
                    item.result === "CLEAN" || item.result === "ENFORCED" || item.result === "VERIFIED"
                      ? "bg-emerald-50 text-emerald-800 border border-emerald-200"
                      : "bg-rose-50 text-rose-800 border border-rose-200"
                  }`}
                >
                  {item.result}
                </span>
              </div>
              <div className="text-[11px] text-neutral-500 flex flex-wrap gap-x-3 font-mono">
                <span>Target: {item.agent}</span>
                <span>·</span>
                <span>Rule: {item.rule}</span>
              </div>
              <p className="text-[11px] text-neutral-600 pt-0.5 font-sans leading-relaxed">
                {item.action}
              </p>
            </div>
          ))}
        </div>
      </div>
    </DrawerContainer>
  );
};
