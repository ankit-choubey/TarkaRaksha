"use client";

import React, { useState, useEffect, useRef, useMemo } from "react";
import {
  CheckCircle2,
  AlertOctagon,
  HelpCircle,
  ShieldCheck,
  ShieldAlert,
  ArrowRight,
  Cpu,
  Database,
  Lock,
  Clock,
  RotateCcw,
  Sparkles,
  ExternalLink,
  ChevronRight,
  Layers,
  FileCode2,
  FileCheck2,
  Check,
  Copy,
  Play,
  Pause,
  RefreshCw,
  Radio,
  AlertTriangle,
  X,
  BellRing,
  Info,
  Sliders,
  DollarSign,
  TrendingUp,
} from "lucide-react";
import { ControlRoomSnapshot, DrawerType, MoneyValue } from "../../lib/types";
import { formatMoney, truncateHash } from "../../lib/formatters";

export interface VerificationStageInfo {
  stepNumber: number;
  stageCode: string;
  stageName: string;
  actor: string;
  authority: "AUTHORITATIVE" | "ADVISORY" | "PROVIDER" | "MERCHANT";
  status: "PENDING" | "ACTIVE" | "COMPLETED" | "DRIFT_FLAGGED" | "BLOCKED" | "UNKNOWN";
  durationSeconds: number; // 4-5s per step
  innovationTag: string;
  detectedFact: string;
  decisionExplanation: string;
  keyTakeaway: string;
  evidenceSnippet: Record<string, any>;
  popupMessage: {
    title: string;
    description: string;
    impact: string;
    type: "info" | "warning" | "success" | "recovery";
  };
}

interface RealTimeVerificationFlowProps {
  scenarioId: string;
  itemTitle: string;
  authorizedMax: MoneyValue;
  chargedAmount: MoneyValue;
  paymentId: string;
  orderId: string;
  signature: string;
  onOpenDrawer: (drawer: DrawerType) => void;
  onResetOrder: () => void;
  onViewInControlRoom: () => void;
  initialIsAutonomous?: boolean;
}

export const RealTimeVerificationFlow: React.FC<RealTimeVerificationFlowProps> = ({
  scenarioId,
  itemTitle,
  authorizedMax,
  chargedAmount,
  paymentId,
  orderId,
  signature,
  onOpenDrawer,
  onResetOrder,
  onViewInControlRoom,
  initialIsAutonomous = true,
}) => {
  const isDriftScenario =
    scenarioId === "surge_drift" || scenarioId === "tax_drift" || chargedAmount.amount > authorizedMax.amount;
  const isBlockedScenario = scenarioId === "sku_sub";
  const isDoubleWebhookScenario = scenarioId === "double_webhook";
  const isTimeoutScenario = scenarioId === "timeout";
  const isQualityTradeoff = scenarioId === "quality_tradeoff";

  // Quality Tradeoff Policy Adjustment State
  const [qualityChoice, setQualityChoice] = useState<
    "pending" | "approved_upgrade" | "enforce_discount" | "revert_base"
  >("pending");

  // Mode: manual step confirmation vs autonomous 4-second stepping
  const [isAutonomous, setIsAutonomous] = useState<boolean>(initialIsAutonomous);
  const [currentStep, setCurrentStep] = useState<number>(0);
  const [isPaused, setIsPaused] = useState<boolean>(false);
  const [countdown, setCountdown] = useState<number>(4);
  const [copied, setCopied] = useState<boolean>(false);

  // Floating Pop-Up Alert Text Box State (User Request: "pop msg to appear for only a problem or issue is detected")
  const [isAlertModalOpen, setIsAlertModalOpen] = useState<boolean>(false);
  const [userClickedAction, setUserClickedAction] = useState<string | null>(null);
  const [postClickCountdown, setPostClickCountdown] = useState<number | null>(null);

  // Pipeline Completion & Auto-Redirect to Control Room (User Request: "control panel shall open right after auto and manual mode completes")
  const [completionModalOpen, setCompletionModalOpen] = useState<boolean>(false);
  const [redirectCountdown, setRedirectCountdown] = useState<number>(5);

  // Handle completion auto-redirect when reaching Step 8
  useEffect(() => {
    if (currentStep === 7) {
      setCompletionModalOpen(true);
      const redirectTimer = setInterval(() => {
        setRedirectCountdown((prev) => {
          if (prev <= 1) {
            clearInterval(redirectTimer);
            onViewInControlRoom();
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
      return () => clearInterval(redirectTimer);
    }
  }, [currentStep, onViewInControlRoom]);

  // Define the comprehensive 8-step verification pipeline (memoized for stable references)
  const stages: VerificationStageInfo[] = useMemo(() => [
    {
      stepNumber: 1,
      stageCode: "E1_CONTEXT_BINDING",
      stageName: "Context 4-Tuple Binding Audit",
      actor: "E1 Context Ledger",
      authority: "AUTHORITATIVE",
      status: "COMPLETED",
      durationSeconds: 4,
      innovationTag: "E1 Context Architecture",
      detectedFact: `Session locked: (tx_${orderId.slice(0, 8)}, intent_alice, buyer_agent, merchant_pro).`,
      decisionExplanation:
        "Verified that incoming payment webhook belongs to the active, signed intent session. Cryptographic nonces match without reuse.",
      keyTakeaway:
        "Razorpay knows only payment ID; TarkaRaksha binds the payment to the exact intent session to prevent session hijacking and replay attacks.",
      evidenceSnippet: {
        order_id: orderId,
        payment_id: paymentId,
        binding_status: "BOUND_AND_LOCKED",
        nonce_freshness: "VALID",
        session_fingerprint: "sha256:7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069",
      },
      popupMessage: {
        title: "Context Verified & Nonce Locked",
        description: "Payment order is tightly bound to Buyer Agent intent. Replay attacks and session hijacking prevented.",
        impact: "Zero session ambiguity.",
        type: "success",
      },
    },
    {
      stepNumber: 2,
      stageCode: "T08_ADVISORY_CHECK",
      stageName: "Advisory AI Proposal Audit",
      actor: "Groq Llama 3.3 Versatile",
      authority: "ADVISORY",
      status: "COMPLETED",
      durationSeconds: 4,
      innovationTag: "T08 AI Boundary",
      detectedFact: isQualityTradeoff
        ? "AI identified ₹52,000 professional-tier unit delivering 100% AdobeRGB (+₹2,000 above user budget)."
        : "Advisory LLM parsed natural language prompt and recommended catalog selection.",
      decisionExplanation: isQualityTradeoff
        ? "Groq LLM proposes quality trade-off as advisory input only. Strict deterministic policy prevents AI from unilaterally raising budget."
        : "The AI proposal was ingested as UNTRUSTED advice. Strict policy prevents the LLM from modifying spending limits or declaring PASS.",
      keyTakeaway:
        "AI is advisory; deterministic verification is authoritative. The LLM can never authorize money transfers or alter spending limits.",
      evidenceSnippet: {
        advisory_model: "llama-3.3-70b-versatile (Groq)",
        llm_financial_authority: "ZERO_PERMITTED",
        intent_status: "VALID_INPUT",
        quality_tradeoff_detected: isQualityTradeoff,
      },
      popupMessage: {
        title: "AI Is Advisory · Not Authoritative",
        description: isQualityTradeoff
          ? "AI spotted a superior display at ₹52,000. Deterministic rules hold financial authority at 0."
          : "Groq LLM formulated purchase intent. Deterministic boundary verifies all numbers before gateway lock.",
        impact: "Guards against hallucinated spending.",
        type: "info",
      },
    },
    {
      stepNumber: 3,
      stageCode: "T04_INTEGRITY_EVALUATION",
      stageName: "Deterministic 4-Pillar Evaluation",
      actor: "T04 Deterministic Integrity Engine",
      authority: "AUTHORITATIVE",
      status:
        qualityChoice === "approved_upgrade"
          ? "COMPLETED"
          : isDriftScenario || (isQualityTradeoff && qualityChoice === "pending")
          ? "DRIFT_FLAGGED"
          : isBlockedScenario
          ? "BLOCKED"
          : isTimeoutScenario
          ? "UNKNOWN"
          : "COMPLETED",
      durationSeconds: 5,
      innovationTag: "T04 Deterministic Core",
      detectedFact: isQualityTradeoff
        ? qualityChoice === "approved_upgrade"
          ? "POLICY AMENDMENT APPLIED: User authorized ceiling updated to ₹52,000. Zero violations remain."
          : "DISCREPANCY DETECTED: Item price ₹52,000 exceeds user baseline budget ceiling ₹50,000 by +₹2,000."
        : isDriftScenario
        ? `DISCREPANCY DETECTED: Checkout cart charged ${formatMoney(chargedAmount)} exceeding authorized ceiling ${formatMoney(authorizedMax)}.`
        : isBlockedScenario
        ? "SEMANTIC DRIFT: Offered SKU does not match authorized SKU contract."
        : isTimeoutScenario
        ? "INDETERMINATE TIMEOUT: Gateway returned 504. Authoritative evidence delayed."
        : isDoubleWebhookScenario
        ? "DUPLICATE WEBHOOK: Cryptographic idempotency key already observed in current session."
        : `MATCH: Charged amount ${formatMoney(chargedAmount)} is strictly within ceiling ${formatMoney(authorizedMax)}.`,
      decisionExplanation: isQualityTradeoff
        ? qualityChoice === "approved_upgrade"
          ? "Authorized ceiling formally raised to 5,200,000 paise via cryptographic intent amendment."
          : "Integer minor unit check: 5,000,000 paise budget ceiling < 5,200,000 paise charged. Gate held in 11ms."
        : isDriftScenario
        ? `T04 evaluated authorized minor units (${authorizedMax.amount} paise) vs observed (${chargedAmount.amount} paise). Delta: +${chargedAmount.amount - authorizedMax.amount} paise. Gateway settlement held.`
        : isBlockedScenario
        ? "Semantic boundary evaluated item properties. Substitution violates user's explicit policy constraint. Settlement blocked."
        : isTimeoutScenario
        ? "Triggered first-class UNKNOWN state. No second payment debit allowed until authoritative reconciliation."
        : isDoubleWebhookScenario
        ? "Normalized idempotency key. Webhook ingested without duplicate payment state progression."
        : "All 4 boundaries (Economic, Semantic, Temporal, Authority) evaluated in 12ms. Zero discrepancy found.",
      keyTakeaway: isQualityTradeoff
        ? "When an AI suggests higher quality at a higher price, our deterministic engine prevents unauthorized spend while offering controlled policy adjustment."
        : isDriftScenario
        ? "Despite Razorpay returning 200 OK, our deterministic integer math detected the unbudgeted surcharge in 11ms before final release."
        : isBlockedScenario
        ? "Semantic boundary strictly prevents counterfeit or refurbished goods substitution without human intervention."
        : "Sub-15ms integer evaluation holds all financial limits inviolate without adding checkout latency.",
      evidenceSnippet: {
        authorized_max_paise: qualityChoice === "approved_upgrade" ? 5200000 : authorizedMax.amount,
        observed_charged_paise: chargedAmount.amount,
        delta_paise:
          qualityChoice === "approved_upgrade"
            ? 0
            : isQualityTradeoff
            ? 200000
            : isDriftScenario
            ? chargedAmount.amount - authorizedMax.amount
            : 0,
        economic_verdict: qualityChoice === "approved_upgrade" ? true : !isDriftScenario && !isQualityTradeoff,
        semantic_verdict: !isBlockedScenario,
      },
      popupMessage: isQualityTradeoff
        ? {
            title:
              qualityChoice === "approved_upgrade"
                ? "Quality Amendment Approved: PASS"
                : "Quality vs Budget Tradeoff Flagged!",
            description:
              qualityChoice === "approved_upgrade"
                ? "Budget ceiling updated to ₹52,000. Display matches pro color accuracy specs."
                : "Display cost ₹52,000 exceeds ₹50,000 budget by ₹2,000. Decision required.",
            impact: "Ensures AI cannot overspend without command.",
            type: qualityChoice === "approved_upgrade" ? "success" : "warning",
          }
        : isDriftScenario
        ? {
            title: "Economic Price Drift Flagged!",
            description: `Merchant checkout surged by ₹${((chargedAmount.amount - authorizedMax.amount) / 100).toLocaleString()}. Gateway capture held in suspense.`,
            impact: "Prevents silent checkout overcharges.",
            type: "warning",
          }
        : isBlockedScenario
        ? {
            title: "Semantic Substitution Blocked!",
            description: "Merchant offered refurbished product instead of authorized new SKU. Transaction safely halted.",
            impact: "Blocks counterfeit/swapped goods.",
            type: "warning",
          }
        : isTimeoutScenario
        ? {
            title: "Indeterminate 504 Timeout: UNKNOWN",
            description: "Gateway connection dropped. T12 enters deliberate abstention: NO SECOND PAYMENT.",
            impact: "Prevents accidental double charging.",
            type: "warning",
          }
        : {
            title: "Deterministic Verification Passed!",
            description: "All 4 integrity boundaries held with zero variance.",
            impact: "Transaction verified authentic.",
            type: "success",
          },
    },
    {
      stepNumber: 4,
      stageCode: "T07_MRDP_DRIFT_PROOF",
      stageName: "Machine-Readable Drift Proof (MRDP)",
      actor: "T07 MRDP Protocol Generator",
      authority: "AUTHORITATIVE",
      status: "COMPLETED",
      durationSeconds: 4,
      innovationTag: "T07 MRDP Protocol",
      detectedFact: isQualityTradeoff
        ? "Emitted MRDP artifact #mrdp_tradeoff with delta +200,000 paise."
        : isDriftScenario
        ? "Emitted MRDP proof #mrdp_e6 with error code E_ECONOMIC_PRICE_DRIFT_RESOLVED."
        : isBlockedScenario
        ? "Emitted MRDP proof with error code E_SEMANTIC_SUBSTITUTION_BLOCKED."
        : "Clean Proof signed with zero violation codes.",
      decisionExplanation:
        "Signed tamper-evident SHA-256 MRDP artifact. Rather than ambiguous text logs, this machine-readable proof provides irrefutable evidence of the discrepancy.",
      keyTakeaway:
        "MRDP is our open protocol innovation: instead of human dispute emails, it creates an irrefutable cryptographic proof that autonomous systems can negotiate over.",
      evidenceSnippet: {
        mrdp_id: "mrdp_e6_checkout_surge",
        error_code: isQualityTradeoff
          ? "E_QUALITY_BUDGET_ADJUSTMENT"
          : isDriftScenario
          ? "E_ECONOMIC_PRICE_DRIFT_RESOLVED"
          : "E_CLEAN_PASS",
        proof_digest: "9b7c84a821df2a4901f41ceeb14c81829e01db918c5719bc44ff23315a676b91",
        rule_violated: isQualityTradeoff ? "BUDGET_UPGRADE_PENDING" : isDriftScenario ? "MAX_TOTAL_CEILING_EXCEEDED" : "NONE",
      },
      popupMessage: {
        title: "MRDP Cryptographic Proof Generated",
        description: "Tamper-evident proof digest generated. Holds merchant accountable and guides autonomous remediation.",
        impact: "Irrefutable proof of drift.",
        type: "info",
      },
    },
    {
      stepNumber: 5,
      stageCode: "T11_AUTONOMOUS_RECOVERY",
      stageName: "Bounded Autonomous Recovery Negotiation",
      actor: "T11 Recovery Negotiator",
      authority: "AUTHORITATIVE",
      status: "COMPLETED",
      durationSeconds: 5,
      innovationTag: "T11 Recovery Loop",
      detectedFact: isQualityTradeoff
        ? qualityChoice === "approved_upgrade"
          ? "Policy upgrade accepted: Bypassed compensatory discount negotiation."
          : "Negotiated merchant loyalty credit: -₹2,000 discount applied to meet original ₹50,000 budget."
        : isDriftScenario
        ? `Negotiated compensatory remedy: Applied merchant price match discount (-₹${((chargedAmount.amount - authorizedMax.amount) / 100).toLocaleString()}) within Attempt 1 of 3.`
        : isBlockedScenario
        ? "Recovery rejected: Merchant has no authorized substitution in stock. Order safely rolled back."
        : "Recovery bypassed: Direct pass path.",
      decisionExplanation:
        "The recovery engine evaluated candidate proposals against user's pre-authorized spending policy. Only remedies that bring the net total under authorized limit are accepted.",
      keyTakeaway:
        "Recovery is bounded to 3 attempts and strictly constrained by the user's pre-authorized budget. Zero human escalation needed.",
      evidenceSnippet: {
        recovery_invoked: isDriftScenario || isQualityTradeoff,
        replan_round: 1,
        max_attempts_allowed: 3,
        compensation_amount_paise:
          qualityChoice === "approved_upgrade"
            ? 0
            : isQualityTradeoff
            ? 200000
            : isDriftScenario
            ? chargedAmount.amount - authorizedMax.amount
            : 0,
        action_type: qualityChoice === "approved_upgrade" ? "AMEND_USER_POLICY" : "APPLY_MERCHANT_DISCOUNT",
      },
      popupMessage: isDriftScenario || (isQualityTradeoff && qualityChoice !== "approved_upgrade")
        ? {
            title: "Autonomous Recovery Applied!",
            description: "Compensatory discount applied. Net payable adjusted back to authorized ceiling.",
            impact: "Zero human escalation required.",
            type: "recovery",
          }
        : {
            title: "Policy Aligned",
            description: "Transaction cleanly executed within policy constraints.",
            impact: "Direct path execution.",
            type: "success",
          },
    },
    {
      stepNumber: 6,
      stageCode: "T04_REVALIDATION",
      stageName: "Deterministic Revalidation Check",
      actor: "Deterministic Re-evaluator",
      authority: "AUTHORITATIVE",
      status: "COMPLETED",
      durationSeconds: 4,
      innovationTag: "Independent Revalidation",
      detectedFact: "Re-evaluation confirms net total matches ceiling. Zero violations remaining.",
      decisionExplanation:
        "No recovery proposal is trusted blindly. The deterministic engine re-runs all rules from scratch. Only after 0 violations are confirmed is the gate opened.",
      keyTakeaway:
        "Recovery proposals are untrusted until independently revalidated by the core mathematical engine from scratch.",
      evidenceSnippet: {
        revalidation_verdict: "PASS",
        violations_remaining: 0,
        settlement_authorization: "GRANTED",
      },
      popupMessage: {
        title: "Revalidation Confirmed: PASS",
        description: "All rules re-checked. Zero violations remain. The transaction is now formally declared safe.",
        impact: "Trust through verification.",
        type: "success",
      },
    },
    {
      stepNumber: 7,
      stageCode: "E5_PASSPORT_SEALED",
      stageName: "Transaction Passport Sealed",
      actor: "E5 Ledger Notary",
      authority: "AUTHORITATIVE",
      status: "COMPLETED",
      durationSeconds: 4,
      innovationTag: "E5 Passport & Checkpoints",
      detectedFact: "Passport sealed with 8-checkpoint cryptographic hash chain.",
      decisionExplanation:
        "Every lifecycle state transition has been cryptographically signed into an immutable ledger certificate. Guaranteed non-repudiation.",
      keyTakeaway:
        "The sealed passport guarantees audit-ready non-repudiation between the buyer agent, merchant gateway, and ledger.",
      evidenceSnippet: {
        passport_id: `pass_${orderId.slice(0, 12)}`,
        checkpoints_verified: 8,
        hash_chain_seal: "d41d8cd98f00b204e9800998ecf8427e0123456789abcdef0123456789abcdef",
      },
      popupMessage: {
        title: "Transaction Passport Sealed",
        description: "Complete lifecycle certificate minted with verified checkpoints from intent to settlement.",
        impact: "Audit-ready verifiable record.",
        type: "success",
      },
    },
    {
      stepNumber: 8,
      stageCode: "T13_REPLAY_AUDIT",
      stageName: "Deterministic CPU-Only Replay Audit",
      actor: "T13 Replay Engine",
      authority: "AUTHORITATIVE",
      status: "COMPLETED",
      durationSeconds: 4,
      innovationTag: "T13 Replay Isolation",
      detectedFact: "Bit-for-bit replay comparison verdict: MATCH (0 discrepancies).",
      decisionExplanation:
        "Audited the transaction by re-executing state transitions in a pure CPU sandbox with 0 external calls and 0 financial mutations. Results matched historical execution 100%.",
      keyTakeaway:
        "Bit-for-bit replay proves that years from now, any auditor can re-execute this transaction with zero side-effects and get the identical outcome.",
      evidenceSnippet: {
        replay_verdict: "MATCH",
        external_calls_made: 0,
        financial_mutations: 0,
        isolation_mode: "STRICT_CPU_ONLY",
      },
      popupMessage: {
        title: "Replay Audit: Bit-for-Bit MATCH",
        description: "Reconstructed state matches recorded history perfectly with zero side effects.",
        impact: "Deterministic reproducibility proven.",
        type: "success",
      },
    },
  ], [
    orderId,
    paymentId,
    authorizedMax,
    chargedAmount,
    qualityChoice,
    isDriftScenario,
    isBlockedScenario,
    isTimeoutScenario,
    isDoubleWebhookScenario,
    isQualityTradeoff,
  ]);

  // Track which step has already been evaluated for problem popup (avoids re-trigger loop on re-renders)
  const lastPromptedStepRef = useRef<number | null>(null);

  // Helper to check if current stage is an actual problem / issue (User Request: "pop msg to appear for only a problem of issue is detected")
  // Problems and discrepancies are intercepted strictly at Step 3 (T04 Deterministic Integrity Evaluation)
  const isProblemStage = (stage: VerificationStageInfo) => {
    if (!stage) return false;
    if (stage.stepNumber !== 3) return false;

    return (
      stage.status === "DRIFT_FLAGGED" ||
      stage.status === "BLOCKED" ||
      stage.status === "UNKNOWN" ||
      stage.popupMessage.type === "warning" ||
      isQualityTradeoff
    );
  };

  // Prevent background scroll when pop box or completion modal is open so txn items at bottom don't scroll/show through
  useEffect(() => {
    if (isAlertModalOpen || completionModalOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [isAlertModalOpen, completionModalOpen]);

  // Only pop up message when an issue/problem is detected on step change!
  useEffect(() => {
    if (lastPromptedStepRef.current === currentStep) return;
    lastPromptedStepRef.current = currentStep;

    const stage = stages[currentStep];
    if (stage && isProblemStage(stage)) {
      setIsAlertModalOpen(true);
      setIsPaused(true); // pause auto-stepper so user can click
      setUserClickedAction(null);
      setPostClickCountdown(null);
    } else {
      setIsAlertModalOpen(false);
      setUserClickedAction(null);
      setPostClickCountdown(null);
    }
  }, [currentStep, stages]);

  // Handle 5-second post-click countdown: waits 5s only, then pop box disappears and moves to next step automatically (User Request)
  useEffect(() => {
    if (postClickCountdown === null) return;

    if (postClickCountdown <= 0) {
      setIsAlertModalOpen(false);
      setPostClickCountdown(null);
      setUserClickedAction(null);
      setIsPaused(false);
      setCountdown(4);
      setCurrentStep((s) => Math.min(s + 1, stages.length - 1));
      return;
    }

    const timer = setInterval(() => {
      setPostClickCountdown((prev) => (prev !== null && prev > 0 ? prev - 1 : 0));
    }, 1000);

    return () => clearInterval(timer);
  }, [postClickCountdown, stages.length]);

  const handleUserClickAction = (actionLabel: string, onExecute?: () => void) => {
    if (onExecute) onExecute();
    setUserClickedAction(actionLabel);
    setPostClickCountdown(5);
  };

  const handleProceedImmediately = () => {
    setIsAlertModalOpen(false);
    setPostClickCountdown(null);
    setUserClickedAction(null);
    setIsPaused(false);
    setCountdown(4);
    setCurrentStep((s) => Math.min(s + 1, stages.length - 1));
  };

  const handleDismissModal = () => {
    setIsAlertModalOpen(false);
    setPostClickCountdown(null);
    setUserClickedAction(null);
    setIsPaused(false);
  };

  // Progressive timer: 4 seconds per step
  useEffect(() => {
    if (!isAutonomous || isPaused || currentStep >= stages.length - 1) return;

    const timer = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          setCurrentStep((s) => Math.min(s + 1, stages.length - 1));
          return 4;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [isAutonomous, isPaused, currentStep, stages.length]);

  const handleManualNextStep = () => {
    if (currentStep < stages.length - 1) {
      setIsAlertModalOpen(false);
      setUserClickedAction(null);
      setPostClickCountdown(null);
      setCurrentStep(currentStep + 1);
      setCountdown(4);
    }
  };

  const handleManualPrevStep = () => {
    if (currentStep > 0) {
      setIsAlertModalOpen(false);
      setUserClickedAction(null);
      setPostClickCountdown(null);
      setCurrentStep(currentStep - 1);
      setCountdown(4);
    }
  };

  // Reset Back to Zero (User Request: "for manual mode auto checkout page one it should reset back to zero again")
  const handleResetToZero = () => {
    lastPromptedStepRef.current = null;
    setCurrentStep(0);
    setCountdown(4);
    setIsPaused(false);
    setQualityChoice("pending");
    setCompletionModalOpen(false);
    setIsAlertModalOpen(false);
    setUserClickedAction(null);
    setPostClickCountdown(null);
    setRedirectCountdown(5);
  };

  const activeStage = stages[currentStep];

  const copyProof = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-8 font-sans">
      {/* --------------------------------------------------------------------- */}
      {/* 1. TOP CONTROL BAR WITH RESET TO ZERO & STEPPING BUTTONS              */}
      {/* --------------------------------------------------------------------- */}
      <div className="rounded-3xl border border-neutral-200 bg-white p-5 shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-3 border-b border-neutral-100">
          <div className="flex items-center space-x-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-blue-50 text-[#3395ff] border border-blue-200 shrink-0 shadow-xs">
              <Database className="h-6 w-6" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-bold text-neutral-900 text-lg tracking-tight">
                  Razorpay Payment Captured
                </span>
                <span className="rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-mono font-bold text-emerald-800 border border-emerald-200">
                  STATUS: 200 OK
                </span>
              </div>
              <p className="text-xs text-neutral-500 font-mono pt-0.5">
                Payment: {paymentId} · Order: {orderId} · HMAC Verified
              </p>
            </div>
          </div>

          {/* Stepping Controls & Reset Button */}
          <div className="flex items-center space-x-2.5 flex-wrap gap-y-2">
            {/* Reset to Zero Button */}
            <button
              onClick={handleResetToZero}
              className="rounded-full bg-neutral-100 hover:bg-neutral-200 text-neutral-800 px-3.5 py-2 text-xs font-bold flex items-center space-x-1.5 transition shadow-2xs"
              title="Reset verification pipeline back to Step 0"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              <span>Reset to Step 0</span>
            </button>

            {/* Auto / Manual Stepping Toggle */}
            <button
              onClick={() => setIsAutonomous(!isAutonomous)}
              className={`rounded-full px-4 py-2 text-xs font-bold flex items-center space-x-2 transition shadow-xs ${
                isAutonomous
                  ? "bg-neutral-900 text-white"
                  : "bg-white text-neutral-800 border border-neutral-300 hover:bg-neutral-100"
              }`}
            >
              {isAutonomous ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
              <span>{isAutonomous ? `Auto (${countdown}s)` : "Manual Mode"}</span>
            </button>

            <button
              onClick={handleManualNextStep}
              disabled={currentStep >= stages.length - 1}
              className="rounded-full bg-neutral-900 px-5 py-2 text-xs font-bold text-white hover:bg-neutral-800 active:scale-[0.98] transition disabled:opacity-40 flex items-center space-x-1.5 shadow-sm"
            >
              <span>Proceed to Next Step</span>
              <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Core Invariant Bar */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between text-xs text-neutral-600 bg-neutral-50 p-3 rounded-2xl font-mono gap-2">
          <span className="flex items-center gap-2 text-neutral-900 font-semibold">
            <ShieldCheck className="h-4 w-4 text-emerald-600 shrink-0" />
            <span>Core Principle: Payment success does not mean transaction success.</span>
          </span>
          <span className="text-neutral-500">
            Stage {currentStep + 1} of {stages.length} Active · Latency: 12ms
          </span>
        </div>
      </div>

      {/* --------------------------------------------------------------------- */}
      {/* 2. HIGH-IMPACT PROMINENT POP-UP ALERT TEXT BOX (FIXED MODAL DIALOG)   */}
      {/*    (User Request: "pop up message as text box is not appearing")      */}
      {/* --------------------------------------------------------------------- */}
      {isAlertModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4 sm:p-6 overflow-y-auto animate-in fade-in duration-200">
          <div
            className={`w-full max-w-2xl rounded-3xl border-2 p-6 sm:p-7 shadow-2xl transition-all relative ${
              activeStage.popupMessage.type === "warning"
                ? "border-rose-500 bg-rose-50/95 text-rose-950"
                : activeStage.popupMessage.type === "recovery"
                ? "border-violet-500 bg-violet-50/95 text-violet-950"
                : "border-emerald-500 bg-emerald-50/95 text-emerald-950"
            }`}
          >
            {/* Close Pop-up Button */}
            <button
              onClick={handleDismissModal}
              className="absolute top-4 right-4 p-1.5 rounded-full text-neutral-500 hover:text-neutral-900 hover:bg-white/80 transition cursor-pointer"
              title="Close Pop-up Box"
            >
              <X className="h-5 w-5" />
            </button>

            <div className="space-y-4">
              {/* Header Tag */}
              <div className="flex items-center space-x-3">
                <div
                  className={`p-2.5 rounded-2xl text-white shadow-xs shrink-0 ${
                    activeStage.popupMessage.type === "warning"
                      ? "bg-rose-600"
                      : activeStage.popupMessage.type === "recovery"
                      ? "bg-violet-600"
                      : "bg-emerald-600"
                  }`}
                >
                  {activeStage.popupMessage.type === "warning" ? (
                    <AlertTriangle className="h-6 w-6 animate-pulse" />
                  ) : activeStage.popupMessage.type === "recovery" ? (
                    <RotateCcw className="h-6 w-6 animate-spin" />
                  ) : (
                    <ShieldCheck className="h-6 w-6" />
                  )}
                </div>

                <div>
                  <div className="flex items-center space-x-2">
                    <span className="text-xs font-mono font-bold uppercase tracking-wider block">
                      Stage 0{activeStage.stepNumber} Assertion &amp; Discrepancy Alert
                    </span>
                    <span className="rounded-full bg-white/80 px-2 py-0.5 text-[10px] font-mono font-bold uppercase text-neutral-800 border">
                      {activeStage.authority}
                    </span>
                  </div>
                  <h3 className="text-xl sm:text-2xl font-bold tracking-tight">
                    {activeStage.popupMessage.title}
                  </h3>
                </div>
              </div>

              {/* The High-Impact Text Box Content */}
              <div className="rounded-2xl bg-white p-5 border border-neutral-200/80 shadow-xs space-y-3 text-neutral-900 text-sm">
                <div className="space-y-1">
                  <span className="text-xs font-mono font-bold text-neutral-400 uppercase block">
                    Observed Pipeline Fact:
                  </span>
                  <p className="font-semibold text-base text-neutral-900 leading-snug">
                    {activeStage.detectedFact}
                  </p>
                </div>

                <div className="p-3.5 rounded-xl bg-neutral-50 border border-neutral-200 text-xs sm:text-sm space-y-1">
                  <span className="font-bold text-neutral-900 block font-mono text-xs uppercase">
                    Why System Decided / Enforced:
                  </span>
                  <p className="text-neutral-700 leading-relaxed">{activeStage.decisionExplanation}</p>
                </div>

                {/* When User has clicked an action: show 5-second auto-advance countdown (User Request) */}
                {postClickCountdown !== null ? (
                  <div className="rounded-2xl bg-emerald-950 text-white p-5 border-2 border-emerald-500 space-y-3 animate-in zoom-in-95">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs uppercase tracking-wider text-emerald-400 font-bold flex items-center gap-2">
                        <CheckCircle2 className="h-5 w-5 text-emerald-400 shrink-0" />
                        <span>User Command Confirmed &amp; Ingested</span>
                      </span>
                      <span className="rounded-full bg-emerald-500 text-neutral-950 px-3 py-1 text-xs font-mono font-bold shrink-0">
                        Auto-advancing in {postClickCountdown}s...
                      </span>
                    </div>
                    <p className="text-sm font-semibold text-emerald-200">
                      {userClickedAction}
                    </p>
                    <p className="text-xs text-neutral-400 font-mono">
                      Pop-up box will automatically disappear in {postClickCountdown} seconds and move to the next step.
                    </p>
                    <div className="flex items-center justify-between pt-1 border-t border-emerald-900/60">
                      <span className="text-[11px] font-mono text-neutral-400">
                        Applies automatically on both manual and auto modes
                      </span>
                      <button
                        onClick={handleProceedImmediately}
                        className="px-4 py-2 rounded-xl bg-white text-neutral-950 text-xs font-bold hover:bg-neutral-100 flex items-center space-x-1.5 shadow-md active:scale-95 transition cursor-pointer"
                      >
                        <span>Close &amp; Proceed Now</span>
                        <ArrowRight className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                ) : (
                  <>
                    {/* SPECIAL CASE: AI Quality vs Budget Tradeoff Interactive Choices (User Request: "budget 50k but 52k is delivering quality") */}
                    {isQualityTradeoff && currentStep >= 2 && currentStep <= 4 && (
                      <div className="rounded-2xl border-2 border-violet-400 bg-violet-50/90 p-5 space-y-3 shadow-sm">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-mono font-bold uppercase text-violet-900 flex items-center gap-1.5">
                            <Sparkles className="h-4 w-4 text-violet-600" />
                            Interactive AI Quality Tradeoff Suggestion
                          </span>
                          <span className="text-xs font-mono font-bold bg-violet-200 text-violet-900 px-2.5 py-0.5 rounded-full">
                            User Command Required
                          </span>
                        </div>
                        <div className="text-xs text-neutral-800 space-y-1.5">
                          <p className="font-semibold text-violet-950">
                            Budget Ceiling: ₹50,000 (5,000,000 paise) · Observed Product: ₹52,000 (+₹2,000 delta)
                          </p>
                          <p className="text-neutral-600">
                            The AI discovered a premium display delivering 100% AdobeRGB + 120Hz at ₹52,000. Under TarkaRaksha invariants, <strong className="text-neutral-900">AI has ZERO financial authority</strong> and cannot authorize money without explicit user command.
                          </p>
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 pt-2">
                          <button
                            onClick={() => {
                              handleUserClickAction("✓ Quality Amendment Approved: Authorized ceiling raised to ₹52,000.", () =>
                                setQualityChoice("approved_upgrade")
                              );
                            }}
                            className={`rounded-xl p-3 text-xs font-bold text-left shadow-xs transition space-y-1 ${
                              qualityChoice === "approved_upgrade"
                                ? "bg-emerald-600 text-white ring-2 ring-emerald-700"
                                : "bg-violet-600 hover:bg-violet-700 text-white"
                            }`}
                          >
                            <span className="block text-[10px] font-mono uppercase text-violet-200">
                              {qualityChoice === "approved_upgrade" ? "✓ Command Applied" : "Option 1 (Approve)"}
                            </span>
                            <span className="block leading-tight">✓ Approve ₹52,000 Quality Amendment</span>
                          </button>

                          <button
                            onClick={() => {
                              handleUserClickAction("✓ Policy Enforced: Demanded ₹2,000 merchant discount voucher.", () =>
                                setQualityChoice("enforce_discount")
                              );
                            }}
                            className={`rounded-xl p-3 text-xs font-bold text-left shadow-xs transition space-y-1 ${
                              qualityChoice === "enforce_discount"
                                ? "bg-emerald-600 text-white ring-2 ring-emerald-700"
                                : "bg-neutral-900 hover:bg-neutral-800 text-white"
                            }`}
                          >
                            <span className="block text-[10px] font-mono uppercase text-neutral-400">
                              {qualityChoice === "enforce_discount" ? "✓ Command Applied" : "Option 2 (Enforce & Coupon)"}
                            </span>
                            <span className="block leading-tight">Enforce ₹50,000 &amp; Request Discount</span>
                          </button>

                          <button
                            onClick={() => {
                              handleUserClickAction("✓ Upgrade Rejected: Reverted to baseline ₹48,000 SKU.", () =>
                                setQualityChoice("revert_base")
                              );
                            }}
                            className={`rounded-xl p-3 text-xs font-bold text-left shadow-2xs transition space-y-1 ${
                              qualityChoice === "revert_base"
                                ? "bg-neutral-800 text-white"
                                : "bg-white hover:bg-neutral-100 text-neutral-900 border border-neutral-300"
                            }`}
                          >
                            <span className="block text-[10px] font-mono uppercase text-neutral-500">
                              {qualityChoice === "revert_base" ? "✓ Command Applied" : "Option 3 (Reject)"}
                            </span>
                            <span className="block leading-tight">Reject: Revert to ₹48,000 Base</span>
                          </button>
                        </div>
                      </div>
                    )}

                    {/* Problem Action Buttons for Non-Tradeoff Scenarios */}
                    {!isQualityTradeoff && isDriftScenario && (
                      <div className="rounded-2xl border-2 border-rose-400 bg-rose-50/90 p-4 space-y-2.5">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-mono font-bold uppercase text-rose-900 flex items-center gap-1.5">
                            <AlertTriangle className="h-4 w-4 text-rose-600" />
                            Unbudgeted Price Surge Detected (+₹5,000 Drift)
                          </span>
                          <span className="text-xs font-mono font-bold bg-rose-200 text-rose-900 px-2.5 py-0.5 rounded-full">
                            Click Required
                          </span>
                        </div>
                        <p className="text-xs text-neutral-700">
                          Merchant checkout charged ₹55,000 against authorized ₹50,000 ceiling. Click to authorize T11 autonomous partial refund recovery:
                        </p>
                        <button
                          onClick={() => handleUserClickAction("✓ Recovery Authorized: T11 loop engaged to refund +₹5,000 unbudgeted drift.")}
                          className="w-full sm:w-auto rounded-xl bg-rose-600 hover:bg-rose-700 text-white px-5 py-2.5 text-xs font-bold flex items-center justify-center space-x-1.5 shadow-sm active:scale-95 transition cursor-pointer"
                        >
                          <RotateCcw className="h-3.5 w-3.5" />
                          <span>✓ Authorize T11 Recovery &amp; Compensatory Partial Refund</span>
                        </button>
                      </div>
                    )}

                    {!isQualityTradeoff && isBlockedScenario && (
                      <div className="rounded-2xl border-2 border-neutral-700 bg-neutral-100 p-4 space-y-2.5">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-mono font-bold uppercase text-neutral-900 flex items-center gap-1.5">
                            <AlertTriangle className="h-4 w-4 text-neutral-800" />
                            Unauthorized Refurbished SKU Blocked
                          </span>
                          <span className="text-xs font-mono font-bold bg-neutral-300 text-neutral-900 px-2.5 py-0.5 rounded-full">
                            Click Required
                          </span>
                        </div>
                        <p className="text-xs text-neutral-700">
                          Merchant substituted authorized SKU with refurbished SKU-MON-4K-REFURB. Click to confirm settlement blockage:
                        </p>
                        <button
                          onClick={() => handleUserClickAction("✓ Boundary Enforced: Refurbished SKU substitution blocked, settlement safely aborted.")}
                          className="w-full sm:w-auto rounded-xl bg-neutral-900 hover:bg-neutral-800 text-white px-5 py-2.5 text-xs font-bold flex items-center justify-center space-x-1.5 shadow-sm active:scale-95 transition cursor-pointer"
                        >
                          <span>✓ Enforce Semantic Boundary &amp; Abort Settlement</span>
                        </button>
                      </div>
                    )}

                    {!isQualityTradeoff && isTimeoutScenario && (
                      <div className="rounded-2xl border-2 border-amber-400 bg-amber-50/90 p-4 space-y-2.5">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-mono font-bold uppercase text-amber-900 flex items-center gap-1.5">
                            <HelpCircle className="h-4 w-4 text-amber-600" />
                            Indeterminate Gateway 504 Timeout
                          </span>
                          <span className="text-xs font-mono font-bold bg-amber-200 text-amber-900 px-2.5 py-0.5 rounded-full">
                            Click Required
                          </span>
                        </div>
                        <p className="text-xs text-neutral-700">
                          Gateway connection dropped. Click to enforce deliberate abstention (NO SECOND PAYMENT debit):
                        </p>
                        <button
                          onClick={() => handleUserClickAction("✓ Abstention Enforced: No second debit permitted. Reconciling gateway.")}
                          className="w-full sm:w-auto rounded-xl bg-amber-600 hover:bg-amber-700 text-white px-5 py-2.5 text-xs font-bold flex items-center justify-center space-x-1.5 shadow-sm active:scale-95 transition cursor-pointer"
                        >
                          <span>✓ Enforce Deliberate Abstention (No Second Payment)</span>
                        </button>
                      </div>
                    )}
                  </>
                )}
              </div>

              {/* Key Verified Takeaway */}
              <div className="rounded-2xl bg-white/90 p-4 border border-neutral-200/80 text-sm space-y-1">
                <span className="font-mono uppercase text-xs font-bold text-neutral-900 block">
                  Key Verified Takeaway:
                </span>
                <p className="text-neutral-700 font-medium leading-relaxed">
                  {activeStage.keyTakeaway}
                </p>
              </div>

              {/* Action Buttons in Pop-up */}
              <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-2">
                <button
                  onClick={handleResetToZero}
                  className="text-xs font-mono text-neutral-500 hover:text-neutral-900 flex items-center gap-1 underline cursor-pointer"
                >
                  <RotateCcw className="h-3.5 w-3.5" />
                  <span>Reset to Step 0</span>
                </button>

                <div className="flex items-center space-x-2">
                  <button
                    onClick={handleDismissModal}
                    className="px-4 py-2 rounded-xl bg-white border border-neutral-300 text-xs font-semibold text-neutral-700 hover:bg-neutral-100 transition shadow-2xs cursor-pointer"
                  >
                    Close Pop-up Box
                  </button>
                  {postClickCountdown !== null ? (
                    <button
                      onClick={handleProceedImmediately}
                      className="px-5 py-2 rounded-xl bg-emerald-600 text-white text-xs font-bold hover:bg-emerald-700 flex items-center space-x-1.5 shadow-sm active:scale-95 transition cursor-pointer"
                    >
                      <span>Close &amp; Proceed Now</span>
                      <ArrowRight className="h-4 w-4" />
                    </button>
                  ) : (
                    !isQualityTradeoff && !isDriftScenario && !isBlockedScenario && !isTimeoutScenario && (
                      <button
                        onClick={() => handleUserClickAction(`✓ Issue Acknowledged: ${activeStage.popupMessage.title}`)}
                        className="px-5 py-2 rounded-xl bg-neutral-900 text-white text-xs font-bold hover:bg-neutral-800 flex items-center space-x-1.5 shadow-sm cursor-pointer"
                      >
                        <span>Acknowledge Issue &amp; Continue (5s Timer)</span>
                        <ArrowRight className="h-4 w-4" />
                      </button>
                    )
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Persistent Floating Trigger Button (Always visible when alert box is closed) */}
      {!isAlertModalOpen && !completionModalOpen && (
        <div className="fixed bottom-6 right-6 z-40 animate-in slide-in-from-bottom-5">
          <button
            onClick={() => setIsAlertModalOpen(true)}
            className="flex items-center space-x-2.5 rounded-full bg-neutral-900 text-white px-5 py-3 text-xs font-bold shadow-2xl hover:bg-neutral-800 border border-neutral-700 transition active:scale-95 group"
          >
            <BellRing className="h-4 w-4 text-amber-400 group-hover:rotate-12 transition-transform" />
            <span>Open Step 0{activeStage.stepNumber} Alert Box</span>
            <span className="rounded-full bg-white/20 px-2 py-0.5 text-[10px] font-mono">
              {activeStage.authority}
            </span>
          </button>
        </div>
      )}

      {/* --------------------------------------------------------------------- */}
      {/* 3. PIPELINE COMPLETION AUTO-REDIRECT MODAL (CENTRAL MODAL DIALOG)     */}
      {/*    (User Request: "control panel shall open right after auto and      */}
      {/*     manual mode completes with problem pop up message")               */}
      {/* --------------------------------------------------------------------- */}
      {completionModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 animate-in fade-in zoom-in-95">
          <div className="w-full max-w-2xl rounded-3xl border-2 border-emerald-500 bg-neutral-900 text-white p-7 sm:p-9 shadow-2xl space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-neutral-800">
              <div className="flex items-center space-x-3">
                <div className="p-3 rounded-2xl bg-emerald-500 text-neutral-950 font-bold shadow-md">
                  <CheckCircle2 className="h-7 w-7" />
                </div>
                <div>
                  <span className="text-xs font-mono font-bold uppercase tracking-wider text-emerald-400">
                    Verification Lifecycle Complete
                  </span>
                  <h3 className="text-xl sm:text-2xl font-bold tracking-tight">
                    Transaction Authenticated &amp; Audited
                  </h3>
                </div>
              </div>
              <div className="rounded-2xl bg-neutral-800 px-4 py-2 border border-neutral-700 font-mono text-xs text-right">
                <span className="text-neutral-400 block text-[10px] uppercase">Control Panel Auto-Launch</span>
                <span className="text-emerald-400 font-bold text-sm">In {redirectCountdown}s...</span>
              </div>
            </div>

            {/* Problem Audit Summary Card */}
            <div className="rounded-2xl bg-neutral-950 p-5 border border-neutral-800 space-y-3 font-sans text-xs">
              <div className="flex items-center justify-between">
                <span className="font-mono text-[11px] uppercase tracking-wider text-amber-400 font-bold">
                  Problem Tested &amp; Autonomously Governed:
                </span>
                <span className="rounded-full bg-emerald-950 text-emerald-300 border border-emerald-800 px-2.5 py-0.5 font-mono text-[10px] font-bold">
                  PASS / ZERO VIOLATIONS
                </span>
              </div>

              <div className="space-y-2 text-neutral-300 leading-relaxed text-sm">
                {isQualityTradeoff ? (
                  <>
                    <p className="font-semibold text-white">
                      Scenario: AI Quality vs. Budget Tradeoff (₹50,000 Budget vs. ₹52,000 Superior Display)
                    </p>
                    <p className="text-neutral-400 text-xs">
                      {qualityChoice === "approved_upgrade"
                        ? "User issued explicit policy amendment command approving ₹52,000 ceiling. Deterministic gate updated and verified PASS."
                        : qualityChoice === "enforce_discount"
                        ? "User commanded strict ₹50,000 limit. T11 recovery loop applied ₹2,000 compensatory coupon."
                        : "User rejected upgrade. System held budget ceiling and reverted to base SKU."}
                    </p>
                  </>
                ) : isDriftScenario ? (
                  <>
                    <p className="font-semibold text-white">
                      Scenario: Unbudgeted Dynamic Price Surge (+₹5,000 Drift)
                    </p>
                    <p className="text-neutral-400 text-xs">
                      Merchant cart surged by ₹5,000 above authorized ceiling. T04 Deterministic Gate intercepted in 11ms, generated SHA-256 MRDP Proof #mrdp_e6, and T11 Recovery Loop secured a -₹5,000 partial refund, restoring net debit to exactly ₹50,000.
                    </p>
                  </>
                ) : isBlockedScenario ? (
                  <>
                    <p className="font-semibold text-white">
                      Scenario: Unauthorized Refurbished SKU Substitution
                    </p>
                    <p className="text-neutral-400 text-xs">
                      Merchant cart attempted to substitute a refurbished unit. T04 Semantic Boundary blocked settlement immediately with zero financial leakage.
                    </p>
                  </>
                ) : isTimeoutScenario ? (
                  <>
                    <p className="font-semibold text-white">
                      Scenario: Indeterminate Gateway 504 Timeout
                    </p>
                    <p className="text-neutral-400 text-xs">
                      Gateway connection dropped. T12 UNKNOWN Resolution Engine entered deliberate abstention (NO SECOND PAYMENT), eliminating accidental double debit risk.
                    </p>
                  </>
                ) : (
                  <>
                    <p className="font-semibold text-white">
                      Scenario: Clean Authorized Purchase Path
                    </p>
                    <p className="text-neutral-400 text-xs">
                      All 4 deterministic integrity boundaries (Economic, Semantic, Temporal, Authority) evaluated in 12ms with zero violations. Sealed in audit passport.
                    </p>
                  </>
                )}
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs font-mono">
              <div className="rounded-2xl bg-neutral-950 p-4 border border-neutral-800 space-y-1">
                <span className="text-neutral-500 block uppercase">Final Gate Verdict</span>
                <span className="text-emerald-400 font-bold text-sm">DETERMINISTIC PASS</span>
              </div>
              <div className="rounded-2xl bg-neutral-950 p-4 border border-neutral-800 space-y-1">
                <span className="text-neutral-500 block uppercase">Replay Verdict</span>
                <span className="text-emerald-400 font-bold text-sm">MATCH (0 Discrepancies)</span>
              </div>
              <div className="rounded-2xl bg-neutral-950 p-4 border border-neutral-800 space-y-1">
                <span className="text-neutral-500 block uppercase">Passport Seal</span>
                <span className="text-neutral-300 font-bold truncate block">9b7c84a821df2a4901...</span>
              </div>
            </div>

            <div className="flex flex-col sm:flex-row items-center justify-end gap-3 pt-2">
              <button
                onClick={handleResetToZero}
                className="w-full sm:w-auto px-5 py-2.5 rounded-xl border border-neutral-700 bg-neutral-800 text-xs font-semibold hover:bg-neutral-700"
              >
                ↺ Reset to Step 0 / Run Another
              </button>
              <button
                onClick={onViewInControlRoom}
                className="w-full sm:w-auto px-7 py-3 rounded-xl bg-white text-neutral-950 text-xs font-bold uppercase tracking-wider hover:bg-neutral-100 flex items-center justify-center space-x-2 shadow-lg"
              >
                <span>Open Control Panel Now</span>
                <ArrowRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* --------------------------------------------------------------------- */}
      {/* 4. MAIN GRID: DOT + LINE PARALLEL STAGES & EVIDENCE INSPECTOR         */}
      {/* --------------------------------------------------------------------- */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left 2 Cols: Step-by-Step Chain with Animated Connector Line */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono font-bold uppercase tracking-wider text-neutral-400">
              Parallel Verification Flow (Dot + Line Progression)
            </span>
            <span className="text-xs font-mono text-neutral-500">
              Active Stage: {stages[currentStep].stageCode}
            </span>
          </div>

          <div className="relative pl-6 space-y-3">
            {/* Animated Vertical Line Spine */}
            <div className="absolute left-2.5 top-4 bottom-4 w-0.5 bg-neutral-200" />
            <div
              className="absolute left-2.5 top-4 w-0.5 bg-neutral-900 transition-all duration-500"
              style={{
                height: `${(currentStep / (stages.length - 1)) * 100}%`,
              }}
            />

            {stages.map((stage, idx) => {
              const isCurrent = currentStep === idx;
              const isPassedBefore = idx < currentStep;

              return (
                <div
                  key={stage.stageCode}
                  onClick={() => {
                    setCurrentStep(idx);
                    setCountdown(4);
                    setIsAlertModalOpen(true);
                  }}
                  className={`relative cursor-pointer rounded-2xl border p-5 transition-all space-y-2 ${
                    isCurrent
                      ? "bg-white border-neutral-900 shadow-md ring-2 ring-neutral-900"
                      : isPassedBefore
                      ? "bg-neutral-50/80 border-neutral-200 text-neutral-700 hover:bg-white"
                      : "bg-white/40 border-neutral-200/60 opacity-60 hover:opacity-80"
                  }`}
                >
                  {/* Glowing Node Dot on Timeline */}
                  <div
                    className={`absolute -left-[27px] top-6 h-4 w-4 rounded-full border-2 transition-all ${
                      isCurrent
                        ? "bg-emerald-500 border-neutral-900 ring-4 ring-emerald-100 animate-pulse"
                        : isPassedBefore
                        ? "bg-neutral-900 border-neutral-900 text-white"
                        : "bg-white border-neutral-300"
                    }`}
                  />

                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2.5">
                      <span className="text-xs font-mono text-neutral-400 font-bold">
                        0{stage.stepNumber}
                      </span>
                      <h3 className="font-bold text-sm sm:text-base text-neutral-900">
                        {stage.stageName}
                      </h3>
                      <span className="rounded-md bg-neutral-100 px-2 py-0.5 text-[10px] font-mono text-neutral-600 border border-neutral-200">
                        {stage.innovationTag}
                      </span>
                    </div>

                    <div className="flex items-center space-x-2">
                      {stage.status === "DRIFT_FLAGGED" ? (
                        <span className="rounded-full bg-rose-100 text-rose-800 text-[10px] font-mono font-bold px-2.5 py-0.5 border border-rose-200">
                          DRIFT FLAGGED
                        </span>
                      ) : stage.status === "BLOCKED" ? (
                        <span className="rounded-full bg-neutral-800 text-white text-[10px] font-mono font-bold px-2.5 py-0.5">
                          BLOCKED
                        </span>
                      ) : stage.status === "UNKNOWN" ? (
                        <span className="rounded-full bg-amber-100 text-amber-800 text-[10px] font-mono font-bold px-2.5 py-0.5 border border-amber-200">
                          UNKNOWN
                        </span>
                      ) : (
                        <span className="rounded-full bg-emerald-100 text-emerald-800 text-[10px] font-mono font-bold px-2.5 py-0.5 border border-emerald-200">
                          PASS
                        </span>
                      )}

                      {isPassedBefore && <CheckCircle2 className="h-4 w-4 text-emerald-600" />}
                    </div>
                  </div>

                  <p className="text-xs sm:text-sm text-neutral-600 font-sans leading-relaxed">
                    {stage.detectedFact}
                  </p>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right Col: Decision & Evidence Inspector Card */}
        <div className="space-y-4">
          <span className="text-xs font-mono font-bold uppercase tracking-wider text-neutral-400 block">
            Real-Time Decision &amp; Detection Inspector
          </span>

          <div className="rounded-3xl border border-neutral-200 bg-white p-7 shadow-xl space-y-5 font-sans text-sm">
            {/* Header */}
            <div className="flex items-start justify-between pb-4 border-b border-neutral-100">
              <div className="space-y-1">
                <span className="text-xs font-mono font-bold text-neutral-400 uppercase">
                  Active Boundary: Step 0{activeStage.stepNumber}
                </span>
                <h3 className="text-lg font-bold text-neutral-900 tracking-tight">
                  {activeStage.popupMessage.title}
                </h3>
              </div>
              <span
                className={`rounded-full px-3 py-1 text-xs font-mono font-bold uppercase ${
                  activeStage.popupMessage.type === "warning"
                    ? "bg-rose-100 text-rose-800 border border-rose-200"
                    : activeStage.popupMessage.type === "recovery"
                    ? "bg-violet-100 text-violet-800 border border-violet-200"
                    : "bg-emerald-100 text-emerald-800 border border-emerald-200"
                }`}
              >
                {activeStage.authority}
              </span>
            </div>

            {/* Description & Impact */}
            <div className="space-y-3 text-neutral-700 leading-relaxed text-sm">
              <p>{activeStage.popupMessage.description}</p>
              <div className="p-3.5 rounded-2xl bg-neutral-50 border border-neutral-200 text-xs space-y-1">
                <span className="font-bold text-neutral-900 block font-mono uppercase text-[10px]">
                  Why System Decided / Advanced:
                </span>
                <p className="text-neutral-600 leading-relaxed">{activeStage.decisionExplanation}</p>
              </div>
            </div>

            {/* Evidence Payload Inspector */}
            <div className="rounded-2xl bg-neutral-950 text-neutral-300 p-4 font-mono text-xs space-y-2 border border-neutral-800 shadow-inner">
              <div className="flex items-center justify-between text-neutral-400 pb-1.5 border-b border-neutral-800">
                <span className="text-[11px] font-bold uppercase">Observed Facts &amp; Payload</span>
                <button
                  onClick={() => copyProof(JSON.stringify(activeStage.evidenceSnippet, null, 2))}
                  className="text-neutral-400 hover:text-white flex items-center gap-1 text-[11px] font-sans"
                >
                  {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                  <span>{copied ? "Copied" : "Copy Proof"}</span>
                </button>
              </div>
              <pre className="overflow-x-auto text-[11px] text-emerald-400 max-h-48 leading-tight">
                {JSON.stringify(activeStage.evidenceSnippet, null, 2)}
              </pre>
            </div>

            {/* Action Bar */}
            <div className="pt-3 flex items-center justify-between gap-3 border-t border-neutral-100">
              <button
                onClick={handleManualPrevStep}
                disabled={currentStep === 0}
                className="rounded-xl px-4 py-2 text-xs font-semibold text-neutral-600 border border-neutral-300 hover:bg-neutral-50 disabled:opacity-40"
              >
                ← Back
              </button>

              <button
                onClick={handleManualNextStep}
                disabled={currentStep >= stages.length - 1}
                className="rounded-xl bg-neutral-900 text-white px-5 py-2 text-xs font-bold hover:bg-neutral-800 disabled:opacity-40 flex items-center space-x-1.5 shadow-sm"
              >
                <span>Proceed to Next Step</span>
                <ArrowRight className="h-4 w-4" />
              </button>
            </div>
          </div>

          {/* Quick Action to Open Control Room */}
          <div className="rounded-2xl bg-neutral-50 p-5 border border-neutral-200 text-xs space-y-2.5">
            <span className="font-bold text-neutral-900 block text-sm">Need deep diagnostics?</span>
            <p className="text-neutral-500 text-xs leading-relaxed">
              Open the full Transaction Control Room to inspect raw TIX messages, the cryptographic hash chain, or run CPU replay.
            </p>
            <div className="flex items-center gap-2 pt-1">
              <button
                onClick={onViewInControlRoom}
                className="rounded-xl bg-white border border-neutral-300 px-4 py-2 text-xs font-semibold text-neutral-800 hover:bg-neutral-100 shadow-2xs"
              >
                Open Full Control Room
              </button>
              <button
                onClick={onResetOrder}
                className="rounded-xl bg-white border border-neutral-300 px-4 py-2 text-xs font-semibold text-neutral-800 hover:bg-neutral-100 shadow-2xs"
              >
                Place New Order
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
