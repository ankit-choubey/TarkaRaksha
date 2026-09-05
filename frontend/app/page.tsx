"use client";

import { useState } from "react";

interface IntentItem {
  item_id: string;
  sku: string;
  name: string;
  quantity: number;
  unit_price: { amount: number; currency: string };
  total_price: { amount: number; currency: string };
}

interface IntentContract {
  intent_id: string;
  issued_by: string;
  issued_at: string;
  expires_at: string;
  currency: string;
  max_total: { amount: number; currency: string };
  items: IntentItem[];
}

interface CreateResponse {
  transaction_id: string;
  intent_id: string;
  order_id: string;
  amount: { amount: number; currency: string };
  currency: string;
  state: string;
  key_id?: string;
  created_at: string;
}

interface CompleteResponse {
  transaction_id: string;
  intent_id: string;
  order_id: string;
  payment_id: string;
  state: string;
  integrity_status: "PASS" | "DRIFT" | "UNKNOWN";
  rule_results: Record<string, boolean>;
  violations: string[];
  evidence_ids: string[];
  mrdp?: {
    protocol: string;
    version: string;
    mrdp_id: string;
    error_code: string;
    status: string;
    violation: string;
    drift_source: string;
    expected_value: any;
    observed_value: any;
    discrepancy_amount?: { amount: number; currency: string };
    remediation?: string;
    proof_digest: string;
  };
  verified_at: string;
}

export default function Home() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  // Intent State
  const [naturalLanguage, setNaturalLanguage] = useState(
    "Authorize 1 dedicated server SERVER-256GB for up to ₹50,000 INR"
  );
  const [isInitializing, setIsInitializing] = useState(false);
  const [isVerifying, setIsVerifying] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Active Transaction Context
  const [createdTx, setCreatedTx] = useState<CreateResponse | null>(null);
  const [verificationResult, setVerificationResult] = useState<CompleteResponse | null>(null);

  // Simulation mode for payment
  const [simMode, setSimMode] = useState<"pass" | "drift" | "forgery">("pass");

  // Step 1: Initialize Protected Transaction
  const handleCreateTransaction = async () => {
    setIsInitializing(true);
    setErrorMessage(null);
    setVerificationResult(null);

    try {
      const res = await fetch(`${apiUrl}/api/v1/transaction/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          natural_language_intent: naturalLanguage,
          issued_by: "demo_user",
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to initialize transaction");
      }

      const data: CreateResponse = await res.json();
      setCreatedTx(data);
    } catch (err: any) {
      setErrorMessage(err.message);
    } finally {
      setIsInitializing(false);
    }
  };

  // Step 2: Complete and Verify Transaction
  const handleCompleteTransaction = async () => {
    if (!createdTx) return;
    setIsVerifying(true);
    setErrorMessage(null);

    try {
      let paymentId = "pay_demo_" + Math.random().toString(36).substring(2, 9);
      let signature = "valid_signature_placeholder";

      if (simMode === "forgery") {
        signature = "forged_signature_attack_string";
      }

      const res = await fetch(`${apiUrl}/api/v1/transaction/complete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          transaction_id: createdTx.transaction_id,
          order_id: createdTx.order_id,
          payment_id: paymentId,
          signature: signature,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || `Server returned ${res.status}`);
      }

      const data: CompleteResponse = await res.json();
      setVerificationResult(data);
    } catch (err: any) {
      setErrorMessage(err.message);
    } finally {
      setIsVerifying(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6 sm:p-12 font-sans selection:bg-cyan-500 selection:text-black">
      <div className="max-w-5xl mx-auto space-y-8">
        
        {/* Header */}
        <header className="border-b border-slate-800 pb-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
          <div>
            <div className="flex items-center gap-3">
              <span className="text-2xl font-bold bg-gradient-to-r from-cyan-400 via-indigo-400 to-purple-400 bg-clip-text text-transparent">
                TarkaRaksha (तर्क रक्षा)
              </span>
              <span className="text-xs px-2.5 py-0.5 rounded-full bg-cyan-950/80 text-cyan-400 border border-cyan-800/60 font-mono">
                T10 REAL SLICE
              </span>
            </div>
            <p className="text-sm text-slate-400 mt-1">
              Agentic Transaction Integrity & Recovery Control Plane
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs font-mono text-slate-400 bg-slate-900/90 px-3 py-1.5 rounded-lg border border-slate-800">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            Control Plane Ready
          </div>
        </header>

        {/* Safety Rule Banner */}
        <div className="bg-gradient-to-r from-indigo-950/60 via-purple-950/40 to-slate-900 border border-indigo-800/40 rounded-xl p-4 text-xs sm:text-sm text-slate-300 flex items-center gap-3 shadow-lg">
          <span className="text-lg">🛡️</span>
          <span>
            <strong>Architectural Invariant:</strong> AI is advisory. Deterministic verification is authoritative. Gateway data is treated as untrusted evidence until verified.
          </span>
        </div>

        {/* Error Alert */}
        {errorMessage && (
          <div className="bg-rose-950/70 border border-rose-800/70 rounded-xl p-4 text-rose-300 text-sm flex items-start gap-3 animate-shake">
            <span className="text-lg">⚠️</span>
            <div className="flex-1">
              <p className="font-semibold">Security / Validation Alert</p>
              <p className="font-mono text-xs mt-0.5">{errorMessage}</p>
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          
          {/* Left Column: Transaction Input & Execution Controls */}
          <div className="lg:col-span-6 space-y-6">
            
            {/* Step 1: Authorized Intent */}
            <div className="bg-slate-900/70 border border-slate-800/90 rounded-2xl p-6 shadow-xl space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold text-cyan-400 uppercase tracking-wider font-mono">
                  1. Authorized Intent Baseline
                </h2>
                <span className="text-xs text-slate-500 font-mono">T08 NLP Parser</span>
              </div>
              <div>
                <label className="text-xs text-slate-400 block mb-1.5">
                  Natural Language Intent Instruction:
                </label>
                <textarea
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-xs sm:text-sm text-slate-200 focus:outline-none focus:border-cyan-500 transition-colors font-mono resize-none h-20"
                  value={naturalLanguage}
                  onChange={(e) => setNaturalLanguage(e.target.value)}
                  disabled={isInitializing || !!createdTx}
                />
              </div>

              <div className="bg-slate-950/80 p-3 rounded-xl border border-slate-800/70 text-xs space-y-1 font-mono text-slate-400">
                <div className="flex justify-between">
                  <span>Authorized Limit:</span>
                  <span className="text-slate-200 font-semibold">₹50,000.00 (5,000,000 paise)</span>
                </div>
                <div className="flex justify-between">
                  <span>Target Product:</span>
                  <span className="text-slate-200">SERVER-256GB (Qty: 1)</span>
                </div>
                <div className="flex justify-between">
                  <span>Currency:</span>
                  <span className="text-slate-200">INR</span>
                </div>
              </div>

              <button
                id="btn-initiate-transaction"
                onClick={handleCreateTransaction}
                disabled={isInitializing || !naturalLanguage || !!createdTx}
                className="w-full py-2.5 px-4 bg-gradient-to-r from-cyan-600 to-indigo-600 hover:from-cyan-500 hover:to-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-xs sm:text-sm font-medium rounded-xl transition-all shadow-md active:scale-[0.98]"
              >
                {isInitializing ? "Creating Gateway Order..." : "Initiate Protected Transaction"}
              </button>
            </div>

            {/* Step 2: Payment Execution & Gateway Checkout */}
            {createdTx && (
              <div className="bg-slate-900/70 border border-slate-800/90 rounded-2xl p-6 shadow-xl space-y-4 animate-fadeIn">
                <div className="flex items-center justify-between">
                  <h2 className="text-sm font-semibold text-indigo-400 uppercase tracking-wider font-mono">
                    2. Razorpay Gateway Checkout
                  </h2>
                  <span className="text-xs text-slate-500 font-mono">T09 Adapter</span>
                </div>

                <div className="bg-slate-950 p-3.5 rounded-xl border border-slate-800 font-mono text-xs space-y-1.5 text-slate-300">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Order ID:</span>
                    <span className="text-indigo-300">{createdTx.order_id}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Transaction ID:</span>
                    <span className="text-slate-300">{createdTx.transaction_id}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Current State:</span>
                    <span className="text-amber-400 font-semibold">{createdTx.state}</span>
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-xs text-slate-400 block font-mono">
                    Test Mode Verification Scenario:
                  </label>
                  <div className="grid grid-cols-3 gap-2">
                    <button
                      type="button"
                      onClick={() => setSimMode("pass")}
                      className={`py-2 px-3 text-xs rounded-xl border font-mono transition-colors ${
                        simMode === "pass"
                          ? "bg-emerald-950/70 border-emerald-500 text-emerald-300 font-semibold"
                          : "bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700"
                      }`}
                    >
                      Safe ₹50k
                    </button>
                    <button
                      type="button"
                      onClick={() => setSimMode("drift")}
                      className={`py-2 px-3 text-xs rounded-xl border font-mono transition-colors ${
                        simMode === "drift"
                          ? "bg-amber-950/70 border-amber-500 text-amber-300 font-semibold"
                          : "bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700"
                      }`}
                    >
                      Overcharge ₹55k
                    </button>
                    <button
                      type="button"
                      onClick={() => setSimMode("forgery")}
                      className={`py-2 px-3 text-xs rounded-xl border font-mono transition-colors ${
                        simMode === "forgery"
                          ? "bg-rose-950/70 border-rose-500 text-rose-300 font-semibold"
                          : "bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700"
                      }`}
                    >
                      Forged Signature
                    </button>
                  </div>
                </div>

                <button
                  id="btn-complete-verification"
                  onClick={handleCompleteTransaction}
                  disabled={isVerifying || !!verificationResult}
                  className="w-full py-2.5 px-4 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-xs sm:text-sm font-medium rounded-xl transition-all shadow-md active:scale-[0.98]"
                >
                  {isVerifying ? "Verifying with Gateway..." : "Verify Transaction with Control Plane"}
                </button>
              </div>
            )}
          </div>

          {/* Right Column: Control Plane State & Evidence Verification */}
          <div className="lg:col-span-6 space-y-6">
            <div className="bg-slate-900/70 border border-slate-800/90 rounded-2xl p-6 shadow-xl space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold text-purple-400 uppercase tracking-wider font-mono">
                  3. Deterministic Verification & MRDP
                </h2>
                <span className="text-xs text-slate-500 font-mono">T04 / T05 / T07</span>
              </div>

              {/* State Machine Status */}
              <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 text-xs font-mono space-y-2">
                <div className="flex items-center justify-between text-slate-400 pb-2 border-b border-slate-800/80">
                  <span>State Machine Lifecycle:</span>
                  <span className="font-semibold text-slate-200">
                    {verificationResult ? verificationResult.state : createdTx ? createdTx.state : "IDLE"}
                  </span>
                </div>
                <div className="flex justify-between items-center text-xs">
                  <span className="text-slate-500">Integrity Outcome:</span>
                  {verificationResult ? (
                    <span
                      className={`font-bold px-2.5 py-0.5 rounded-full text-xs ${
                        verificationResult.integrity_status === "PASS"
                          ? "bg-emerald-950 text-emerald-400 border border-emerald-800"
                          : verificationResult.integrity_status === "DRIFT"
                          ? "bg-amber-950 text-amber-400 border border-amber-800"
                          : "bg-slate-800 text-slate-300"
                      }`}
                    >
                      {verificationResult.integrity_status}
                    </span>
                  ) : (
                    <span className="text-slate-600">AWAITING_VERIFICATION</span>
                  )}
                </div>
              </div>

              {/* Rule Results */}
              {verificationResult && (
                <div className="space-y-3 font-mono text-xs">
                  <div className="bg-slate-950 p-3.5 rounded-xl border border-slate-800 space-y-2">
                    <p className="text-slate-400 font-semibold uppercase text-[11px] tracking-wider">
                      Authoritative Rule Verdicts
                    </p>
                    <div className="grid grid-cols-3 gap-2 text-center">
                      <div className="p-2 rounded-lg bg-slate-900 border border-slate-800/60">
                        <span className="text-slate-400 text-[10px] block">Economic</span>
                        <span
                          className={`font-bold ${
                            verificationResult.rule_results["economic"] ? "text-emerald-400" : "text-rose-400"
                          }`}
                        >
                          {verificationResult.rule_results["economic"] ? "PASS" : "DRIFT"}
                        </span>
                      </div>
                      <div className="p-2 rounded-lg bg-slate-900 border border-slate-800/60">
                        <span className="text-slate-400 text-[10px] block">Semantic</span>
                        <span
                          className={`font-bold ${
                            verificationResult.rule_results["semantic"] ? "text-emerald-400" : "text-rose-400"
                          }`}
                        >
                          {verificationResult.rule_results["semantic"] ? "PASS" : "DRIFT"}
                        </span>
                      </div>
                      <div className="p-2 rounded-lg bg-slate-900 border border-slate-800/60">
                        <span className="text-slate-400 text-[10px] block">Temporal</span>
                        <span
                          className={`font-bold ${
                            verificationResult.rule_results["temporal"] ? "text-emerald-400" : "text-rose-400"
                          }`}
                        >
                          {verificationResult.rule_results["temporal"] ? "PASS" : "DRIFT"}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Violations */}
                  {verificationResult.violations.length > 0 && (
                    <div className="bg-amber-950/40 p-3.5 rounded-xl border border-amber-800/50 space-y-1 text-amber-300">
                      <p className="font-semibold text-amber-200">Violation Detected:</p>
                      {verificationResult.violations.map((v, i) => (
                        <p key={i} className="text-xs">
                          • {v}
                        </p>
                      ))}
                    </div>
                  )}

                  {/* Machine-Readable Drift Proof (MRDP) */}
                  {verificationResult.mrdp && (
                    <div className="bg-slate-950 p-4 rounded-xl border border-indigo-900/60 space-y-2 text-xs">
                      <div className="flex items-center justify-between text-indigo-400 font-semibold border-b border-indigo-950 pb-1.5">
                        <span>Machine-Readable Drift Proof (MRDP)</span>
                        <span className="text-[10px] bg-indigo-950/80 px-2 py-0.5 rounded text-indigo-300 border border-indigo-800/40">
                          {verificationResult.mrdp.protocol} v{verificationResult.mrdp.version}
                        </span>
                      </div>
                      <div className="space-y-1 text-slate-400 text-[11px]">
                        <div>
                          <span className="text-slate-500">Error Code: </span>
                          <span className="text-amber-300 font-semibold">{verificationResult.mrdp.error_code}</span>
                        </div>
                        <div>
                          <span className="text-slate-500">Drift Source: </span>
                          <span className="text-slate-200">{verificationResult.mrdp.drift_source}</span>
                        </div>
                        <div>
                          <span className="text-slate-500">Discrepancy: </span>
                          <span className="text-rose-300 font-semibold">
                            {verificationResult.mrdp.discrepancy_amount?.amount} paise
                          </span>
                        </div>
                        <div>
                          <span className="text-slate-500">Remediation: </span>
                          <span className="text-slate-300">{verificationResult.mrdp.remediation}</span>
                        </div>
                        <div className="pt-1 text-[10px] text-slate-500 break-all">
                          SHA-256 Digest: {verificationResult.mrdp.proof_digest}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Reset Button */}
                  <button
                    onClick={() => {
                      setCreatedTx(null);
                      setVerificationResult(null);
                      setErrorMessage(null);
                    }}
                    className="w-full py-2 px-3 bg-slate-950 hover:bg-slate-900 border border-slate-800 text-slate-400 text-xs rounded-xl transition-colors font-mono"
                  >
                    Reset Transaction Slice
                  </button>
                </div>
              )}
            </div>
          </div>

        </div>

      </div>
    </div>
  );
}
