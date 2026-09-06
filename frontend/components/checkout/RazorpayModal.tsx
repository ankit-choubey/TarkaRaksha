"use client";

import React, { useState } from "react";
import {
  CreditCard,
  CheckCircle2,
  ShieldCheck,
  X,
  Lock,
  Smartphone,
  Building,
  QrCode,
  ArrowRight,
  AlertCircle,
  Clock,
} from "lucide-react";
import { MoneyValue } from "../../lib/types";
import { formatMoney } from "../../lib/formatters";

interface RazorpayModalProps {
  isOpen: boolean;
  onClose: () => void;
  orderId: string;
  itemTitle: string;
  amount: MoneyValue;
  onPaymentSuccess: (paymentId: string, orderId: string, signature: string) => void;
}

export const RazorpayModal: React.FC<RazorpayModalProps> = ({
  isOpen,
  onClose,
  orderId,
  itemTitle,
  amount,
  onPaymentSuccess,
}) => {
  const [paymentMethod, setPaymentMethod] = useState<"card" | "upi" | "netbanking">("card");
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [cardNumber, setCardNumber] = useState("4111 2222 3333 4444");
  const [expiry, setExpiry] = useState("12/28");
  const [cvv, setCvv] = useState("999");
  const [cardHolder, setCardHolder] = useState("Alice (Buyer Agent)");

  if (!isOpen) return null;

  const handleSimulatePayment = () => {
    setIsProcessing(true);
    setTimeout(() => {
      setIsProcessing(false);
      const paymentId = `pay_rzp_${Math.random().toString(36).substring(2, 9)}`;
      const signature = `sig_hmac_${Math.random().toString(36).substring(2, 12)}_verified`;
      onPaymentSuccess(paymentId, orderId, signature);
    }, 1200);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-200">
      <div className="w-full max-w-md overflow-hidden rounded-2xl bg-white shadow-2xl border border-neutral-200 text-neutral-900 font-sans">
        {/* Razorpay Test Mode Header */}
        <div className="bg-[#0c2340] text-white p-5 space-y-2 relative">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <span className="font-bold text-lg tracking-tight text-white flex items-center gap-1.5">
                <span className="text-[#3395ff] font-extrabold text-xl">Razorpay</span>
              </span>
              <span className="rounded-full bg-amber-400/20 text-amber-300 border border-amber-400/40 px-2 py-0.2 text-[10px] font-mono font-bold tracking-wider uppercase">
                TEST MODE
              </span>
            </div>
            <button
              onClick={onClose}
              className="text-neutral-400 hover:text-white p-1 rounded-lg transition"
              aria-label="Close Razorpay checkout"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          <div className="pt-2 border-t border-white/10 flex items-baseline justify-between">
            <div className="truncate max-w-[240px]">
              <span className="text-[11px] text-neutral-400 block truncate">{itemTitle}</span>
              <span className="text-[10px] font-mono text-neutral-400">Order: {orderId}</span>
            </div>
            <div className="text-right">
              <span className="text-xl font-bold font-mono text-white">{formatMoney(amount)}</span>
            </div>
          </div>
        </div>

        {/* Payment Methods Tabs */}
        <div className="flex border-b border-neutral-200 text-xs font-medium bg-neutral-50">
          <button
            onClick={() => setPaymentMethod("card")}
            className={`flex-1 py-3 px-2 flex items-center justify-center space-x-1.5 transition ${
              paymentMethod === "card"
                ? "border-b-2 border-[#3395ff] text-[#0c2340] font-bold bg-white"
                : "text-neutral-500 hover:text-neutral-900"
            }`}
          >
            <CreditCard className="h-4 w-4 text-[#3395ff]" />
            <span>Cards</span>
          </button>
          <button
            onClick={() => setPaymentMethod("upi")}
            className={`flex-1 py-3 px-2 flex items-center justify-center space-x-1.5 transition ${
              paymentMethod === "upi"
                ? "border-b-2 border-[#3395ff] text-[#0c2340] font-bold bg-white"
                : "text-neutral-500 hover:text-neutral-900"
            }`}
          >
            <Smartphone className="h-4 w-4" />
            <span>UPI / QR</span>
          </button>
          <button
            onClick={() => setPaymentMethod("netbanking")}
            className={`flex-1 py-3 px-2 flex items-center justify-center space-x-1.5 transition ${
              paymentMethod === "netbanking"
                ? "border-b-2 border-[#3395ff] text-[#0c2340] font-bold bg-white"
                : "text-neutral-500 hover:text-neutral-900"
            }`}
          >
            <Building className="h-4 w-4" />
            <span>Netbanking</span>
          </button>
        </div>

        {/* Method Body */}
        <div className="p-6 space-y-4 text-xs">
          {paymentMethod === "card" && (
            <div className="space-y-3">
              <div>
                <label className="block text-[11px] font-semibold text-neutral-600 mb-1">
                  Card Number (Test Mode Card)
                </label>
                <div className="relative">
                  <input
                    type="text"
                    value={cardNumber}
                    onChange={(e) => setCardNumber(e.target.value)}
                    className="w-full rounded-lg border border-neutral-300 px-3 py-2 text-xs font-mono focus:border-[#3395ff] focus:outline-none"
                  />
                  <div className="absolute right-2.5 top-2.5">
                    <span className="bg-neutral-100 text-neutral-600 text-[10px] font-bold px-1.5 py-0.5 rounded border border-neutral-200">
                      TEST VISA
                    </span>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-semibold text-neutral-600 mb-1">Expiry</label>
                  <input
                    type="text"
                    value={expiry}
                    onChange={(e) => setExpiry(e.target.value)}
                    className="w-full rounded-lg border border-neutral-300 px-3 py-2 text-xs font-mono focus:border-[#3395ff] focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-semibold text-neutral-600 mb-1">CVV</label>
                  <input
                    type="password"
                    value={cvv}
                    onChange={(e) => setCvv(e.target.value)}
                    className="w-full rounded-lg border border-neutral-300 px-3 py-2 text-xs font-mono focus:border-[#3395ff] focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-neutral-600 mb-1">Cardholder Name</label>
                <input
                  type="text"
                  value={cardHolder}
                  onChange={(e) => setCardHolder(e.target.value)}
                  className="w-full rounded-lg border border-neutral-300 px-3 py-2 text-xs focus:border-[#3395ff] focus:outline-none"
                />
              </div>
            </div>
          )}

          {paymentMethod === "upi" && (
            <div className="p-4 rounded-xl bg-neutral-50 text-center space-y-2 border border-neutral-200">
              <QrCode className="h-16 w-16 text-neutral-800 mx-auto" />
              <p className="text-xs text-neutral-600 font-medium">Scan QR with any UPI App (Test Mode)</p>
              <p className="text-[11px] font-mono text-neutral-400">VPA: buyer.agent@razorpay</p>
            </div>
          )}

          {paymentMethod === "netbanking" && (
            <div className="space-y-2">
              <span className="text-[11px] font-semibold text-neutral-600 block">Popular Test Banks</span>
              <div className="grid grid-cols-2 gap-2">
                <button className="p-2 border rounded-lg text-left text-xs hover:border-[#3395ff] bg-white font-medium">
                  HDFC Bank (Test)
                </button>
                <button className="p-2 border rounded-lg text-left text-xs hover:border-[#3395ff] bg-white font-medium">
                  ICICI Bank (Test)
                </button>
                <button className="p-2 border rounded-lg text-left text-xs hover:border-[#3395ff] bg-white font-medium">
                  SBI Bank (Test)
                </button>
                <button className="p-2 border rounded-lg text-left text-xs hover:border-[#3395ff] bg-white font-medium">
                  Axis Bank (Test)
                </button>
              </div>
            </div>
          )}

          {/* Security & Invariant Note */}
          <div className="flex items-start space-x-2 rounded-lg bg-blue-50/70 p-2.5 border border-blue-200/80 text-[11px] text-blue-900">
            <Lock className="h-4 w-4 text-[#3395ff] shrink-0 mt-0.5" />
            <p className="leading-snug">
              <strong>Simulated Gateway Authorization:</strong> Upon authorization, Razorpay issues server-side webhook signatures. TarkaRaksha will then evaluate whether the checkout matched the authorized intent contract.
            </p>
          </div>

          {/* Pay Button */}
          <button
            onClick={handleSimulatePayment}
            disabled={isProcessing}
            className="w-full rounded-xl bg-[#3395ff] hover:bg-[#287cd1] text-white py-3.5 text-sm font-bold flex items-center justify-center space-x-2 shadow-md active:scale-[0.98] transition disabled:opacity-60"
          >
            {isProcessing ? (
              <>
                <div className="h-4 w-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                <span>Authorizing Razorpay Test Mode...</span>
              </>
            ) : (
              <>
                <span>Pay {formatMoney(amount)}</span>
                <ArrowRight className="h-4 w-4" />
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
