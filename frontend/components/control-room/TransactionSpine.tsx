"use client";

import React from "react";
import {
  FileText,
  Bot,
  Tag,
  CreditCard,
  FileCheck2,
  ShieldCheck,
  RotateCcw,
  CheckCircle,
  Flag,
  AlertCircle,
  ChevronRight,
  ExternalLink,
} from "lucide-react";
import { ControlRoomSnapshot, DrawerType } from "../../lib/types";

interface TransactionSpineProps {
  snapshot: ControlRoomSnapshot;
  onOpenDrawer: (drawer: DrawerType) => void;
  activeDrawer: DrawerType | null;
}

interface SpineNode {
  id: DrawerType;
  label: string;
  stageName: string;
  icon: React.ComponentType<{ className?: string }>;
  status: "PASS" | "DRIFT" | "UNKNOWN" | "ACTIVE" | "PENDING";
  summary: string;
}

export const TransactionSpine: React.FC<TransactionSpineProps> = ({
  snapshot,
  onOpenDrawer,
  activeDrawer,
}) => {
  // Derive stage status dynamically from authoritative snapshot
  const integrityStatus = snapshot.integrity.status;
  const isPass = integrityStatus === "PASS";
  const isDrift = integrityStatus === "DRIFT";
  const isUnknown = integrityStatus === "UNKNOWN" || integrityStatus === "ABSTAIN";
  const recoveryInvoked = snapshot.recovery.recovery_invoked;
  const revalidatedPass = snapshot.recovery.revalidated_pass;

  const nodes: SpineNode[] = [
    {
      id: "agent",
      label: "INTENT",
      stageName: "Intent Bound",
      icon: FileText,
      status: "PASS",
      summary: `Max ₹${(snapshot.authorization.max_total.amount / 100).toLocaleString()}`,
    },
    {
      id: "agent",
      label: "AGENT",
      stageName: "Buyer Agent",
      icon: Bot,
      status: snapshot.buyer_agent.gate_status === "VALID" ? "PASS" : "ACTIVE",
      summary: snapshot.buyer_agent.proposed_sku || "Proposal Ready",
    },
    {
      id: "offer",
      label: "OFFER",
      stageName: "Merchant Offer",
      icon: Tag,
      status: isDrift && !recoveryInvoked ? "DRIFT" : "PASS",
      summary: `Cart: ₹${((snapshot.merchant_agent.total?.amount || snapshot.payment.amount.amount) / 100).toLocaleString()}`,
    },
    {
      id: "payment",
      label: "PAYMENT",
      stageName: "Razorpay Test",
      icon: CreditCard,
      status: snapshot.payment.payment_captured ? "PASS" : "PENDING",
      summary: snapshot.payment.payment_status,
    },
    {
      id: "evidence",
      label: "EVIDENCE",
      stageName: "Fact Bundle",
      icon: FileCheck2,
      status: snapshot.evidence_records.length > 0 ? "PASS" : "PENDING",
      summary: `${snapshot.evidence_records.length} Records`,
    },
    {
      id: "integrity",
      label: "INTEGRITY",
      stageName: "Deterministic",
      icon: ShieldCheck,
      status: isDrift ? "DRIFT" : isPass ? "PASS" : isUnknown ? "UNKNOWN" : "ACTIVE",
      summary: integrityStatus,
    },
    {
      id: "recovery",
      label: "RECOVERY",
      stageName: "Bounded Loop",
      icon: RotateCcw,
      status: recoveryInvoked
        ? revalidatedPass
          ? "PASS"
          : "ACTIVE"
        : "PENDING",
      summary: recoveryInvoked ? "Remediated" : "Bypassed",
    },
    {
      id: "integrity",
      label: "REVALIDATE",
      stageName: "Re-evaluation",
      icon: CheckCircle,
      status: recoveryInvoked
        ? revalidatedPass
          ? "PASS"
          : "DRIFT"
        : isPass
        ? "PASS"
        : "PENDING",
      summary: revalidatedPass ? "Confirmed PASS" : isPass ? "Direct PASS" : "Pending",
    },
    {
      id: "passport",
      label: "OUTCOME",
      stageName: "Passport Seal",
      icon: Flag,
      status: snapshot.lifecycle.is_terminal ? "PASS" : "ACTIVE",
      summary: snapshot.lifecycle.current_state,
    },
  ];

  const getStatusClasses = (status: SpineNode["status"], isSelected: boolean) => {
    const base = "transition-all duration-200 cursor-pointer focus:outline-none focus:ring-2 focus:ring-offset-2";
    if (isSelected) {
      return `${base} ring-2 ring-neutral-900 ring-offset-2 shadow-md scale-102 bg-neutral-900 text-white`;
    }
    switch (status) {
      case "PASS":
        return `${base} bg-white text-neutral-800 border-emerald-300 hover:border-emerald-500 hover:bg-emerald-50/40`;
      case "DRIFT":
        return `${base} bg-rose-50/60 text-rose-900 border-rose-300 hover:border-rose-500 animate-pulse`;
      case "UNKNOWN":
        return `${base} bg-amber-50/60 text-amber-900 border-amber-300 hover:border-amber-500`;
      case "ACTIVE":
        return `${base} bg-indigo-50/60 text-indigo-900 border-indigo-300 hover:border-indigo-500 animate-pulse`;
      case "PENDING":
      default:
        return `${base} bg-neutral-50/80 text-neutral-400 border-neutral-200 hover:border-neutral-300 hover:bg-white`;
    }
  };

  const getIconBadge = (status: SpineNode["status"], isSelected: boolean) => {
    if (isSelected) return "text-white";
    switch (status) {
      case "PASS":
        return "text-emerald-600";
      case "DRIFT":
        return "text-rose-600";
      case "UNKNOWN":
        return "text-amber-600";
      case "ACTIVE":
        return "text-indigo-600";
      case "PENDING":
      default:
        return "text-neutral-400";
    }
  };

  return (
    <nav aria-label="Transaction Lifecycle Stages" className="w-full bg-white border-b border-neutral-200 py-4 px-4 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center space-x-2">
            <span className="text-xs font-semibold text-neutral-800 tracking-tight uppercase font-mono">
              Transaction Lifecycle Spine
            </span>
            <span className="text-[11px] text-neutral-400">
              (Click any stage to inspect verified evidence drawer)
            </span>
          </div>
          <span className="text-[11px] font-mono text-neutral-400 hidden sm:inline">
            Stage {nodes.findIndex((n) => n.status === "ACTIVE") + 1 || 9} of 9
          </span>
        </div>

        {/* Horizontal Spine Track */}
        <div className="overflow-x-auto pb-2 scrollbar-none">
          <div className="flex items-center min-w-[960px] justify-between relative py-2">
            {/* Connecting Track Line */}
            <div className="absolute left-6 right-6 top-1/2 -translate-y-1/2 h-0.5 bg-neutral-200 -z-0" />

            {nodes.map((node, index) => {
              const Icon = node.icon;
              const isSelected = activeDrawer === node.id;

              return (
                <div key={`${node.label}-${index}`} className="flex items-center relative z-10">
                  <button
                    onClick={() => onOpenDrawer(node.id)}
                    className={`flex flex-col items-center rounded-xl p-2.5 border shadow-2xs w-24 sm:w-26 ${getStatusClasses(
                      node.status,
                      isSelected
                    )}`}
                    aria-label={`Inspect ${node.label} stage: ${node.status}`}
                  >
                    {/* Icon & Status indicator */}
                    <div className="flex items-center justify-center h-8 w-8 rounded-lg bg-neutral-100/80 mb-1.5 transition-colors">
                      <Icon className={`h-4 w-4 ${getIconBadge(node.status, isSelected)}`} />
                    </div>

                    {/* Step label */}
                    <span className="text-[11px] font-bold tracking-tight font-mono uppercase">
                      {node.label}
                    </span>

                    {/* Stage status pill */}
                    <span
                      className={`text-[9px] font-medium tracking-wide mt-0.5 truncate max-w-[90px] ${
                        isSelected ? "text-neutral-200" : "text-neutral-500"
                      }`}
                    >
                      {node.summary}
                    </span>
                  </button>

                  {/* Arrow separator between nodes */}
                  {index < nodes.length - 1 && (
                    <ChevronRight className="h-4 w-4 text-neutral-300 mx-1 shrink-0" />
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </nav>
  );
};
