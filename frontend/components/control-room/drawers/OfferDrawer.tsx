"use client";

import React, { useState, useEffect } from "react";
import { DrawerContainer } from "./DrawerContainer";
import { ControlRoomSnapshot } from "../../../lib/types";
import { formatMoney } from "../../../lib/formatters";
import { Tag, Truck, ShieldCheck, Clock, CheckCircle2, Box } from "lucide-react";

interface OfferDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  snapshot: ControlRoomSnapshot;
}

export const OfferDrawer: React.FC<OfferDrawerProps> = ({
  isOpen,
  onClose,
  snapshot,
}) => {
  const merchant = snapshot.merchant_agent;
  const auth = snapshot.authorization;

  // Real backend countdown if expires_at is present
  const [timeLeft, setTimeLeft] = useState<string | null>(null);

  useEffect(() => {
    if (!auth.expires_at) return;
    const updateCountdown = () => {
      const diff = new Date(auth.expires_at!).getTime() - Date.now();
      if (diff <= 0) {
        setTimeLeft("EXPIRED");
        return;
      }
      const mins = Math.floor(diff / 60000);
      const secs = Math.floor((diff % 60000) / 1000);
      setTimeLeft(`${mins}m ${secs}s`);
    };

    updateCountdown();
    const interval = setInterval(updateCountdown, 1000);
    return () => clearInterval(interval);
  }, [auth.expires_at]);

  return (
    <DrawerContainer
      isOpen={isOpen}
      onClose={onClose}
      title="Merchant Offer & Price Composition"
      subtitle="Auditing merchant pricing line items, inventory claims, and delivery terms"
      badge={merchant.inventory_status || "OFFER ACTIVE"}
      badgeType="neutral"
    >
      {/* Expiry Banner if present */}
      {timeLeft && (
        <div className="rounded-xl bg-amber-50 p-3 border border-amber-200 text-xs flex items-center justify-between text-amber-800">
          <div className="flex items-center space-x-2">
            <Clock className="h-4 w-4 text-amber-600" />
            <span className="font-semibold">Offer Expiration Boundary:</span>
          </div>
          <span className="font-mono font-bold">{timeLeft}</span>
        </div>
      )}

      {/* Item & SKU Details */}
      <div className="rounded-xl border border-neutral-200 bg-neutral-50/60 p-4 space-y-3">
        <div className="flex items-center justify-between pb-2 border-b border-neutral-200">
          <div>
            <span className="text-[10px] uppercase font-mono text-neutral-400 block">Offered Item SKU</span>
            <span className="font-mono text-sm font-bold text-neutral-900">{merchant.sku || "—"}</span>
          </div>
          <div className="text-right">
            <span className="text-[10px] uppercase font-mono text-neutral-400 block">Quantity</span>
            <span className="font-mono text-sm font-bold text-neutral-900">{merchant.quantity || 1} unit</span>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4 text-xs pt-1">
          <div>
            <span className="text-[10px] uppercase font-mono text-neutral-400 block">Inventory Reservation</span>
            <span className="font-mono text-emerald-700 font-semibold flex items-center gap-1">
              <Box className="h-3.5 w-3.5" />
              {merchant.inventory_status || "VERIFIED"}
            </span>
          </div>
          <div>
            <span className="text-[10px] uppercase font-mono text-neutral-400 block">Delivery Estimate</span>
            <span className="font-mono text-neutral-800 font-semibold flex items-center gap-1">
              <Truck className="h-3.5 w-3.5 text-neutral-500" />
              {merchant.delivery_estimate || "2 Business Days"}
            </span>
          </div>
        </div>
      </div>

      {/* Line Item Pricing Breakdown */}
      <div className="rounded-xl border border-neutral-200 bg-white p-4 space-y-2 text-xs">
        <h4 className="font-mono text-[11px] font-bold text-neutral-400 uppercase tracking-wider pb-1 border-b border-neutral-100">
          Pricing Line Items (Minor Units)
        </h4>

        <div className="flex justify-between py-1 text-neutral-600">
          <span>Base Unit Price:</span>
          <span className="font-mono font-medium text-neutral-800">{formatMoney(merchant.unit_price)}</span>
        </div>

        {merchant.shipping && (
          <div className="flex justify-between py-1 text-neutral-600">
            <span>Shipping & Handling:</span>
            <span className="font-mono font-medium text-neutral-800">{formatMoney(merchant.shipping)}</span>
          </div>
        )}

        {merchant.tax && (
          <div className="flex justify-between py-1 text-neutral-600">
            <span>GST / Taxes:</span>
            <span className="font-mono font-medium text-neutral-800">{formatMoney(merchant.tax)}</span>
          </div>
        )}

        {merchant.discount && (
          <div className="flex justify-between py-1 text-emerald-700 font-medium">
            <span>Merchant / Recovery Discount:</span>
            <span className="font-mono font-bold">- {formatMoney(merchant.discount)}</span>
          </div>
        )}

        <div className="pt-2 mt-2 border-t border-neutral-200 flex justify-between items-center text-sm">
          <span className="font-bold text-neutral-900">Total Net Cart:</span>
          <span className="font-mono font-bold text-neutral-900 text-base">{formatMoney(merchant.total)}</span>
        </div>

        <div className="pt-1 flex justify-between items-center text-xs text-neutral-400">
          <span>Authorized Ceiling Limit:</span>
          <span className="font-mono text-neutral-500">{formatMoney(auth.max_total)}</span>
        </div>
      </div>
    </DrawerContainer>
  );
};
