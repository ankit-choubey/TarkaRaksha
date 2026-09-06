"use client";

import React from "react";
import { DrawerContainer } from "./DrawerContainer";
import { ControlRoomSnapshot } from "../../../lib/types";
import { formatMoney } from "../../../lib/formatters";
import { CreditCard, CheckCircle2, AlertTriangle, ShieldCheck, Database, Key } from "lucide-react";

interface PaymentDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  snapshot: ControlRoomSnapshot;
}

export const PaymentDrawer: React.FC<PaymentDrawerProps> = ({
  isOpen,
  onClose,
  snapshot,
}) => {
  const payment = snapshot.payment;
  const isCaptured = payment.payment_captured;

  return (
    <DrawerContainer
      isOpen={isOpen}
      onClose={onClose}
      title="Payment Provider Gateway"
      subtitle="Razorpay Test Mode gateway telemetry and cryptographic signature verification"
      badge={payment.payment_status.toUpperCase()}
      badgeType={isCaptured ? "pass" : "unknown"}
    >
      {/* Crucial Thesis Banner: CAPTURED IS NOT PASS */}
      <div className="rounded-xl bg-blue-50/70 p-4 border border-blue-200/90 text-xs text-blue-900 space-y-1">
        <div className="flex items-center space-x-2 font-bold font-mono text-[11px] text-blue-800">
          <Database className="h-4 w-4 text-blue-600" />
          <span>INVARIANT: CAPTURED != TRANSACTION SUCCESS</span>
        </div>
        <p className="text-[11px] text-blue-700 leading-relaxed">
          A successful gateway authorization or capture proves only that money transferred. It does not prove that the item was correct, that taxes were valid, or that the merchant honored the user's authorized contract.
        </p>
      </div>

      {/* Gateway State Card */}
      <div className="rounded-xl border border-neutral-200 bg-white p-4 space-y-3 text-xs">
        <div className="flex items-center justify-between pb-2 border-b border-neutral-100">
          <span className="font-mono text-[11px] uppercase font-bold text-neutral-400">
            Gateway Record ({payment.provider.toUpperCase()})
          </span>
          <span className="font-mono text-xs px-2 py-0.5 rounded bg-emerald-50 text-emerald-800 border border-emerald-200 font-semibold">
            {payment.payment_status}
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
          <div>
            <span className="text-[10px] uppercase font-mono text-neutral-400 block">Gateway Order ID</span>
            <span className="font-mono text-neutral-900 font-semibold">{payment.order_id}</span>
          </div>

          <div>
            <span className="text-[10px] uppercase font-mono text-neutral-400 block">Gateway Payment ID</span>
            <span className="font-mono text-neutral-900 font-semibold">{payment.payment_id}</span>
          </div>

          <div>
            <span className="text-[10px] uppercase font-mono text-neutral-400 block">Captured Amount</span>
            <span className="font-mono text-neutral-900 font-bold text-sm">{formatMoney(payment.amount)}</span>
          </div>

          <div>
            <span className="text-[10px] uppercase font-mono text-neutral-400 block">Capture Confirmation</span>
            <span className="font-mono font-semibold text-emerald-700 flex items-center gap-1">
              <CheckCircle2 className="h-3.5 w-3.5" />
              {isCaptured ? "CONFIRMED_CAPTURED" : "PENDING"}
            </span>
          </div>
        </div>
      </div>

      {/* Signature Verification */}
      <div className="rounded-xl border border-neutral-200 bg-neutral-50/70 p-4 space-y-2 text-xs font-mono">
        <div className="flex items-center justify-between text-neutral-500 text-[11px] pb-1 border-b border-neutral-200">
          <span className="flex items-center gap-1.5 font-bold text-neutral-800">
            <Key className="h-3.5 w-3.5 text-blue-600" />
            Server-Side Cryptographic Signature
          </span>
          <span className="text-emerald-700 font-bold">HMAC-SHA256 VERIFIED</span>
        </div>
        <p className="text-[11px] text-neutral-600 font-sans leading-relaxed">
          TarkaRaksha verifies Razorpay payment signatures server-side using the secret key before admitting gateway evidence into the integrity engine.
        </p>
      </div>
    </DrawerContainer>
  );
};
