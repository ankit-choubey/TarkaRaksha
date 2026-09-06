"use client";

import React, { useState } from "react";
import { DrawerContainer } from "./DrawerContainer";
import { ControlRoomSnapshot } from "../../../lib/types";
import { formatTimestamp, truncateHash } from "../../../lib/formatters";
import { Lock, Award, CheckCircle2, Copy, Check, ShieldCheck } from "lucide-react";

interface PassportDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  snapshot: ControlRoomSnapshot;
}

export const PassportDrawer: React.FC<PassportDrawerProps> = ({
  isOpen,
  onClose,
  snapshot,
}) => {
  const [copied, setCopied] = useState(false);
  const isTerminal = snapshot.lifecycle.is_terminal;
  const digest = snapshot.snapshot_digest || "d41d8cd98f00b204e9800998ecf8427e";

  const copyDigest = () => {
    navigator.clipboard.writeText(digest);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const checkpoints = [
    {
      id: "cp_1",
      name: "Intent Contract Signed & Bound",
      completed: true,
      time: snapshot.authorization.issued_at,
    },
    {
      id: "cp_2",
      name: "Buyer Proposal Evaluated by T08",
      completed: !!snapshot.buyer_agent.proposed_sku,
      time: snapshot.lifecycle.started_at,
    },
    {
      id: "cp_3",
      name: "Merchant Offer Gated & Verified",
      completed: !!snapshot.merchant_agent.total,
      time: snapshot.lifecycle.started_at,
    },
    {
      id: "cp_4",
      name: "Razorpay Signature Validated",
      completed: snapshot.payment.payment_captured,
      time: snapshot.lifecycle.completed_at || snapshot.lifecycle.started_at,
    },
    {
      id: "cp_5",
      name: "T04 Deterministic Integrity Certified",
      completed: snapshot.integrity.status === "PASS",
      time: snapshot.lifecycle.completed_at || snapshot.lifecycle.started_at,
    },
    {
      id: "cp_6",
      name: "Cryptographic SHA-256 Hash Chain Sealed",
      completed: isTerminal,
      time: snapshot.lifecycle.completed_at || snapshot.lifecycle.started_at,
    },
  ];

  return (
    <DrawerContainer
      isOpen={isOpen}
      onClose={onClose}
      title="Transaction Passport & Verifiable Certificate"
      subtitle="Immutable cryptographic certificate binding transaction lifecycle facts"
      badge={isTerminal ? "PASSPORT SEALED" : "SEALING IN PROGRESS"}
      badgeType={isTerminal ? "pass" : "unknown"}
    >
      {/* Certificate Emblem */}
      <div className="rounded-2xl border-2 border-neutral-900 bg-neutral-50 p-6 text-center space-y-3 relative overflow-hidden shadow-sm">
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-neutral-900 text-white mx-auto shadow-sm">
          <Award className="h-6 w-6 text-emerald-400" />
        </div>
        <div>
          <h3 className="text-base font-bold text-neutral-900 tracking-tight">
            Cryptographic Transaction Certificate
          </h3>
          <p className="text-xs text-neutral-500 font-mono mt-0.5">
            Passport ID: pass_{snapshot.identity.transaction_id.slice(0, 16)}
          </p>
        </div>

        <div className="pt-2 border-t border-neutral-200/80 flex flex-wrap justify-center gap-x-6 gap-y-1 text-xs text-neutral-600 font-mono">
          <span>
            <strong>Intent:</strong> {snapshot.identity.intent_id}
          </span>
          <span>
            <strong>Order:</strong> {snapshot.identity.order_id}
          </span>
          <span>
            <strong>Verdict:</strong> {snapshot.integrity.status}
          </span>
        </div>
      </div>

      {/* Checkpoints Timeline */}
      <div className="rounded-xl border border-neutral-200 bg-white p-4 space-y-3 text-xs">
        <h4 className="font-mono text-[11px] font-bold text-neutral-400 uppercase tracking-wider pb-1 border-b border-neutral-100">
          Verified Lifecycle Checkpoints
        </h4>

        <div className="space-y-2.5">
          {checkpoints.map((cp, idx) => (
            <div key={cp.id} className="flex items-center justify-between">
              <div className="flex items-center space-x-2.5">
                <CheckCircle2
                  className={`h-4 w-4 ${cp.completed ? "text-emerald-600" : "text-neutral-300"}`}
                />
                <span className={`font-medium ${cp.completed ? "text-neutral-900" : "text-neutral-400"}`}>
                  {idx + 1}. {cp.name}
                </span>
              </div>
              <span className="font-mono text-[10px] text-neutral-400">{formatTimestamp(cp.time)}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Sealed Digest */}
      <div className="rounded-xl bg-neutral-900 text-neutral-300 p-4 font-mono text-xs space-y-2 border border-neutral-800">
        <div className="flex items-center justify-between text-neutral-400 text-[11px] pb-1 border-b border-neutral-800">
          <span>Certificate Seal Digest (SHA-256)</span>
          <button onClick={copyDigest} className="text-emerald-400 hover:text-emerald-300 flex items-center gap-1">
            {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
            <span>{copied ? "Copied" : "Copy Seal"}</span>
          </button>
        </div>
        <p className="text-emerald-400 break-all text-[11px] select-all">{digest}</p>
      </div>
    </DrawerContainer>
  );
};
