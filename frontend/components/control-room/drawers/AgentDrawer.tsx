"use client";

import React from "react";
import { DrawerContainer } from "./DrawerContainer";
import { ControlRoomSnapshot } from "../../../lib/types";
import { formatMoney } from "../../../lib/formatters";
import { Bot, Store, ShieldCheck, ShieldAlert, Cpu, CheckCircle2, AlertTriangle, ArrowRight } from "lucide-react";

interface AgentDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  snapshot: ControlRoomSnapshot;
}

export const AgentDrawer: React.FC<AgentDrawerProps> = ({
  isOpen,
  onClose,
  snapshot,
}) => {
  const buyer = snapshot.buyer_agent;
  const merchant = snapshot.merchant_agent;
  const hasBlockedAction = merchant.gate_status === "BLOCKED" || buyer.gate_status === "BLOCKED";

  return (
    <DrawerContainer
      isOpen={isOpen}
      onClose={onClose}
      title="Agent Inspection & TIX Boundary"
      subtitle="Comparing Buyer Agent advisory proposal vs Merchant Agent claims and policy gating"
      badge="AUTHORITY GATED"
      badgeType="neutral"
    >
      {/* Blocked Action Alert if any */}
      {hasBlockedAction && (
        <div className="rounded-xl bg-rose-50 p-4 border border-rose-200 text-xs text-rose-800 space-y-1">
          <div className="flex items-center space-x-2 font-bold font-mono">
            <ShieldAlert className="h-4 w-4 text-rose-600" />
            <span>ATTEMPTED ACTION → BLOCKED → AUTHORITY DRIFT</span>
          </div>
          <p className="text-[11px] text-rose-700">
            Agent attempted to invoke an unauthorized capability or execute a financial action exceeding intent bounds.
          </p>
        </div>
      )}

      {/* Side-by-Side Agent Panels */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Buyer Agent Column */}
        <div className="rounded-xl border border-neutral-200 bg-neutral-50/50 p-4 space-y-3.5">
          <div className="flex items-center space-x-2 pb-2 border-b border-neutral-200">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-violet-100 text-violet-700">
              <Bot className="h-4 w-4" />
            </div>
            <div>
              <h3 className="text-xs font-bold text-neutral-900">Buyer Agent</h3>
              <p className="text-[10px] text-neutral-400 font-mono">{buyer.agent_id}</p>
            </div>
          </div>

          <div className="space-y-2 text-xs">
            <div>
              <span className="text-[10px] uppercase font-mono text-neutral-400 block">Advisory LLM Model</span>
              <span className="font-mono text-neutral-800 font-medium">{buyer.advisory_model}</span>
              <span className="text-[10px] text-violet-600 block mt-0.5">Advisory only · Zero financial authority</span>
            </div>

            <div>
              <span className="text-[10px] uppercase font-mono text-neutral-400 block">Proposed SKU</span>
              <span className="font-mono text-neutral-800 font-semibold">{buyer.proposed_sku || "—"}</span>
            </div>

            <div>
              <span className="text-[10px] uppercase font-mono text-neutral-400 block">Proposed Unit Price</span>
              <span className="font-mono text-neutral-800 font-semibold">{formatMoney(buyer.proposed_unit_price)}</span>
            </div>

            {buyer.proposal_rationale && (
              <div>
                <span className="text-[10px] uppercase font-mono text-neutral-400 block">AI Proposal Rationale</span>
                <p className="text-[11px] text-neutral-600 italic bg-white p-2 rounded border border-neutral-200 mt-1">
                  "{buyer.proposal_rationale}"
                </p>
              </div>
            )}

            <div className="pt-2 border-t border-neutral-200 flex items-center justify-between">
              <span className="text-neutral-500">Gate Status:</span>
              <span className="font-mono font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded text-[11px] border border-emerald-200">
                {buyer.gate_status || "VALID"}
              </span>
            </div>
          </div>
        </div>

        {/* Merchant Agent Column */}
        <div className="rounded-xl border border-neutral-200 bg-neutral-50/50 p-4 space-y-3.5">
          <div className="flex items-center space-x-2 pb-2 border-b border-neutral-200">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-blue-100 text-blue-700">
              <Store className="h-4 w-4" />
            </div>
            <div>
              <h3 className="text-xs font-bold text-neutral-900">Merchant Agent</h3>
              <p className="text-[10px] text-neutral-400 font-mono">{merchant.merchant_id}</p>
            </div>
          </div>

          <div className="space-y-2 text-xs">
            <div>
              <span className="text-[10px] uppercase font-mono text-neutral-400 block">Offer ID</span>
              <span className="font-mono text-neutral-800 font-medium">{merchant.offer_id || "—"}</span>
            </div>

            <div>
              <span className="text-[10px] uppercase font-mono text-neutral-400 block">Offered SKU</span>
              <span className="font-mono text-neutral-800 font-semibold">{merchant.sku || "—"}</span>
            </div>

            <div>
              <span className="text-[10px] uppercase font-mono text-neutral-400 block">Inventory Status</span>
              <span className="font-mono text-neutral-800 font-semibold">{merchant.inventory_status || "AVAILABLE"}</span>
            </div>

            <div>
              <span className="text-[10px] uppercase font-mono text-neutral-400 block">Declared Capabilities</span>
              <div className="flex flex-wrap gap-1 mt-1">
                {merchant.capabilities.map((cap) => (
                  <span
                    key={cap}
                    className="rounded bg-white px-1.5 py-0.5 text-[10px] font-mono text-neutral-600 border border-neutral-200"
                  >
                    {cap}
                  </span>
                ))}
              </div>
            </div>

            <div className="pt-2 border-t border-neutral-200 flex items-center justify-between">
              <span className="text-neutral-500">Gate Status:</span>
              <span className="font-mono font-semibold text-neutral-800 bg-neutral-100 px-2 py-0.5 rounded text-[11px] border border-neutral-200">
                {merchant.gate_status || "BOUNDED"}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* TIX Protocol Envelope */}
      <div className="rounded-xl bg-neutral-900 text-neutral-300 p-4 font-mono text-xs space-y-2 border border-neutral-800">
        <div className="flex items-center justify-between text-neutral-400 text-[11px] pb-1 border-b border-neutral-800">
          <span>TIX Transaction Envelope</span>
          <span className="text-emerald-400">HMAC-SHA256 SIGNED</span>
        </div>
        <div className="space-y-1 text-[11px]">
          <div><span className="text-neutral-500">source_agent:</span> {buyer.agent_id}</div>
          <div><span className="text-neutral-500">target_merchant:</span> {merchant.merchant_id}</div>
          <div><span className="text-neutral-500">intent_reference:</span> {snapshot.identity.intent_id}</div>
          <div><span className="text-neutral-500">session_binding:</span> {snapshot.identity.transaction_id}</div>
        </div>
      </div>
    </DrawerContainer>
  );
};
