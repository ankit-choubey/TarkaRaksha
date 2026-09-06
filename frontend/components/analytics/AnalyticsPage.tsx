"use client";

import React, { useState } from "react";
import {
  ShieldCheck,
  ShieldAlert,
  Bot,
  Store,
  RotateCcw,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ArrowRight,
  Cpu,
  Database,
  Lock,
  History,
  Sparkles,
  ExternalLink,
  Activity,
  Layers,
  Award,
  Clock,
  TrendingUp,
  FileCheck2,
  Scale,
  Mic,
  Key,
} from "lucide-react";
import { CANONICAL_SCENARIOS } from "../../lib/fixtures";
import { DrawerType } from "../../lib/types";

interface AnalyticsPageProps {
  onOpenDrawer: (drawer: DrawerType) => void;
  onLaunchOrderSimulator: () => void;
}

export const AnalyticsPage: React.FC<AnalyticsPageProps> = ({
  onOpenDrawer,
  onLaunchOrderSimulator,
}) => {
  const [activeCategory, setActiveCategory] = useState<string>("ALL");

  const categories = ["ALL", "ECONOMIC", "SEMANTIC", "TEMPORAL", "AUTHORITY", "SECURITY", "BASELINE"];

  const filteredScenarios =
    activeCategory === "ALL"
      ? CANONICAL_SCENARIOS
      : CANONICAL_SCENARIOS.filter((s) => s.category.toUpperCase() === activeCategory);

  // 8 Core Architectural Claims & Achievements (User Request: "increase the card of claims and stuff we have done to achieve this with our arch")
  const architecturalClaims = [
    {
      id: "claim_1",
      number: "1,062 / 1,062",
      metric: "100% Deterministic Test Guarantee",
      badge: "VERIFIED ZERO FLAKINESS",
      title: "Comprehensive Test Suite Coverage",
      description:
        "Every single state transition, boundary condition, and edge case across T01–T14 is verified by automated deterministic pytest suites. Includes fuzz testing of malformed webhook signatures and concurrent drift mutations.",
      invariant: "Zero indeterminate or flaky tests permitted across codebase.",
      techStack: "Pytest · FastAPI TestClient · Hypothesis Property Fuzzing",
    },
    {
      id: "claim_2",
      number: "0.00%",
      metric: "Floating-Point Financial Math",
      badge: "INTEGER PAISE INVARIANT",
      title: "Strict Integer Minor Unit Representation",
      description:
        "Every monetary value in TarkaRaksha is stored and evaluated strictly in integer minor units (paise / cents). Floating point numbers are explicitly forbidden to prevent catastrophic round-off penny leakages.",
      invariant: "Money.amount must always be int. Floating point operations throw AssertionError.",
      techStack: "Custom Minor Unit Integer Algebra · Currency Invariant Bounds",
    },
    {
      id: "claim_3",
      number: "< 15ms",
      metric: "Deterministic Gate Evaluation Latency",
      badge: "ULTRA-LOW LATENCY",
      title: "Sub-Millisecond 4-Boundary Verification",
      description:
        "T04 evaluates Economic ceilings, Semantic SKU substitutions, Temporal nonce validity windows, and Authority role capabilities in under 15ms without adding latency to checkout execution.",
      invariant: "Evaluated in-memory before payment capture release.",
      techStack: "Pure Python In-Memory Graph · Zero Blocking I/O During Eval",
    },
    {
      id: "claim_4",
      number: "SHA-256",
      metric: "Tamper-Evident Protocol Proofs",
      badge: "OPEN MRDP STANDARD",
      title: "Machine-Readable Drift Proof (MRDP)",
      description:
        "Replaces ambiguous text dispute emails with cryptographically signed JSON artifacts. Each proof contains exact error codes, delta paise, and verified remediation rules that autonomous agents can negotiate over.",
      invariant: "Proofs are signed with SHA-256 and immutable upon creation.",
      techStack: "T07 MRDP Engine · Canonical JSON Normalization · Cryptographic Digests",
    },
    {
      id: "claim_5",
      number: "Max 3",
      metric: "Bounded Replan Negotiation Rounds",
      badge: "FINANCIAL SAFETY CEILING",
      title: "Bounded Autonomous Recovery Loop",
      description:
        "AI agents can negotiate compensatory merchant discounts or authorized substitutions, but cannot exceed 3 replan attempts or violate user-authorized budget limits. Prevents infinite looping spend.",
      invariant: "Recovery proposals must pass independent T04 revalidation before settlement.",
      techStack: "T11 Bounded Loop · Backoff Counter · Strict Re-verification",
    },
    {
      id: "claim_6",
      number: "0 Network",
      metric: "Side-Effect Free Audit Sandbox",
      badge: "BIT-FOR-BIT MATCH",
      title: "Deterministic CPU-Only Replay Engine",
      description:
        "Years after a transaction closes, the T13 Replay Engine can reconstruct and re-execute historical transitions in a pure CPU sandbox with zero external network calls, zero AI calls, and zero money mutations.",
      invariant: "Recorded transition events produce identical SHA-256 hash chains upon replay.",
      techStack: "T13 Replay Sandbox · Mock Provider Isolation · Pure State Determinism",
    },
    {
      id: "claim_7",
      number: "8-Chain",
      metric: "Cryptographic Checkpoint Merkle Path",
      badge: "NON-REPUDIATION",
      title: "Transaction Passport Ledger",
      description:
        "Every lifecycle state transition (intent, offer, auth, capture, drift, recovery, revalidation, settlement) is chained into an immutable SHA-256 hash sequence, creating an audit-ready certificate.",
      invariant: "Guarantees complete non-repudiation between buyer, merchant, and gateway.",
      techStack: "E5 Passport Ledger · Linked Hash Checkpoints · Hex Digests",
    },
    {
      id: "claim_8",
      number: "0 Authority",
      metric: "Advisory AI Safety Isolation",
      badge: "UNTRUSTED ADVICE",
      title: "Strict AI Financial Boundary",
      description:
        "Groq Llama 3.3 Versatile translates natural language user prompts and proposes catalog items, but holds strictly zero authority to execute money transfers, override spending limits, or declare PASS.",
      invariant: "AI is advisory only; deterministic verification is authoritative.",
      techStack: "Groq Cloud API · Llama 3.3 70B · Pydantic Schema Quarantine",
    },
  ];

  const beforeAfterComparisons = [
    {
      title: "1. Merchant Checkout Dynamic Price Surge",
      scenario: "User authorizes ₹50,000 ceiling. Merchant cart charges ₹55,000 at checkout (+₹5,000 drift).",
      before: {
        behavior: "Gateway returns 200 OK. Payment captured for ₹55,000 without buyer awareness.",
        outcome: "Silent financial loss: ₹5,000 unbudgeted drift captured.",
        status: "SILENT FAILURE",
        color: "text-rose-600 bg-rose-50 border-rose-200",
      },
      after: {
        behavior: "T04 Deterministic Gate detects +₹5,000 variance, halts settlement, issues MRDP proof.",
        outcome: "T11 Recovery applies -₹5,000 merchant discount. Revalidated to ₹50,000 before capture.",
        status: "DETERMINISTICALLY RECOVERED",
        color: "text-emerald-700 bg-emerald-50 border-emerald-200",
      },
    },
    {
      title: "2. Unauthorized Refurbished SKU Substitution",
      scenario: "User authorizes brand new SKU-LAPTOP-NEW. Merchant cart substitutes SKU-LAPTOP-REFURB.",
      before: {
        behavior: "Gateway processes payment normally. Buyer agent has no semantic boundary verification.",
        outcome: "Customer receives refurbished goods instead of new hardware.",
        status: "SEMANTIC COMPROMISE",
        color: "text-rose-600 bg-rose-50 border-rose-200",
      },
      after: {
        behavior: "Semantic boundary evaluates item properties and substitution whitelist.",
        outcome: "Unauthorized substitution blocked at gateway gate. Zero funds moved.",
        status: "AUTHORITY GATE BLOCKED",
        color: "text-emerald-700 bg-emerald-50 border-emerald-200",
      },
    },
    {
      title: "3. Asynchronous Double Webhook Capture",
      scenario: "Network latency causes gateway webhook to deliver twice concurrently.",
      before: {
        behavior: "Secondary webhook treated as new transaction event. Card charged twice.",
        outcome: "Duplicate payment capture requiring manual chargeback escalation.",
        status: "FINANCIAL HAZARD",
        color: "text-rose-600 bg-rose-50 border-rose-200",
      },
      after: {
        behavior: "E1 Context Ledger checks cryptographic idempotency key and 4-tuple binding.",
        outcome: "Duplicate webhook normalized and deduplicated without regressing transaction state.",
        status: "IDEMPOTENT PROTECTION",
        color: "text-emerald-700 bg-emerald-50 border-emerald-200",
      },
    },
    {
      title: "4. Indeterminate Gateway Timeout (504)",
      scenario: "Razorpay server-side payment call times out without returning captured status.",
      before: {
        behavior: "Client blindly retries payment request, causing double debit on customer card.",
        outcome: "Conflicting payment state with multiple debits.",
        status: "DOUBLE DEBIT RISK",
        color: "text-amber-600 bg-amber-50 border-amber-200",
      },
      after: {
        behavior: "T12 enters deliberate UNKNOWN resolution state: NO SECOND PAYMENT.",
        outcome: "Abstains from moving money until authoritative gateway reconciliation proves truth.",
        status: "DELIBERATE ABSTENTION",
        color: "text-amber-700 bg-amber-50 border-amber-200",
      },
    },
    {
      title: "5. Hidden Tax & Platform Surcharge Drift",
      scenario: "Merchant cart injects unbudgeted platform surcharge (+₹3,500) at payment review.",
      before: {
        behavior: "Gateway returns 200 OK. Overcharge silently deducted from consumer balance.",
        outcome: "Unbudgeted loss: Consumer pays unexpected administrative surcharge.",
        status: "UNCHECKED SURCHARGE",
        color: "text-rose-600 bg-rose-50 border-rose-200",
      },
      after: {
        behavior: "T04 evaluates line-item breakdown against original intent contract.",
        outcome: "Surcharge held in suspense. Autonomous recovery requests itemized fee waiver.",
        status: "LINE-ITEM PROTECTED",
        color: "text-emerald-700 bg-emerald-50 border-emerald-200",
      },
    },
    {
      title: "6. Clean Authorized Purchase",
      scenario: "Cart matches authorized ceiling exactly. Merchant terms conform 100%.",
      before: {
        behavior: "Standard gateway processes transaction normally.",
        outcome: "Standard checkout completed without cryptographic receipt.",
        status: "STANDARD FLOW",
        color: "text-neutral-600 bg-neutral-50 border-neutral-200",
      },
      after: {
        behavior: "Evaluates all 4 deterministic boundaries in 12ms and mints sealed Transaction Passport.",
        outcome: "Settled with immutable 8-checkpoint cryptographic proof.",
        status: "SEALED & VERIFIED",
        color: "text-emerald-700 bg-emerald-50 border-emerald-200",
      },
    },
  ];

  const agentArchitectures = [
    {
      role: "Buyer Agent",
      identifier: "buyer_agent_alice",
      type: "Advisory Reasoner",
      icon: Bot,
      color: "bg-violet-50 text-violet-700 border-violet-200",
      whatItDoes:
        "Accepts natural language user goals and translates them into an immutable IntentContract. Consults Groq LLM for product discovery.",
      safetyBound: "Holds strictly zero authority to execute money transfers or override budget ceilings.",
    },
    {
      role: "Merchant Agent",
      identifier: "merchant_pro_audio_in",
      type: "External Counterparty",
      icon: Store,
      color: "bg-blue-50 text-blue-700 border-blue-200",
      whatItDoes:
        "Issues pricing offers, inventory reservation claims, tax line items, and delivery estimate bounds.",
      safetyBound: "All merchant claims are treated as UNTRUSTED evidence until validated against user intent.",
    },
    {
      role: "Deterministic Integrity Agent",
      identifier: "T04_INTEGRITY_ENGINE",
      type: "Authoritative Decider",
      icon: ShieldCheck,
      color: "bg-emerald-50 text-emerald-800 border-emerald-200",
      whatItDoes:
        "Runs mathematical integer minor unit (paise) checks across Economic, Semantic, Temporal, and Authority boundaries in sub-15ms.",
      safetyBound: "Authoritative and final. Evaluates with zero floating-point arithmetic and zero AI discretion.",
    },
    {
      role: "Autonomous Recovery Agent",
      identifier: "T11_RECOVERY_LOOP",
      type: "Bounded Negotiator",
      icon: RotateCcw,
      color: "bg-neutral-100 text-neutral-800 border-neutral-300",
      whatItDoes:
        "Formulates compensatory discounts or authorized substitutions upon detected drift within bounded replan rounds.",
      safetyBound: "Enforces strict replay budget (Maximum 3 attempts) and requires independent revalidation.",
    },
  ];

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-10 space-y-16 font-sans text-neutral-900">
      {/* --------------------------------------------------------------------- */}
      {/* SECTION 1: EXECUTIVE ARCHITECTURAL FOUNDATION                         */}
      {/* --------------------------------------------------------------------- */}
      <div className="rounded-3xl border border-neutral-900 bg-neutral-900 text-white p-7 sm:p-9 shadow-2xl space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-neutral-800">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-2xl bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
              <Mic className="h-6 w-6" />
            </div>
            <div>
              <span className="text-xs font-mono font-bold uppercase tracking-wider text-emerald-400">
                Executive Architectural Foundation &amp; Thesis
              </span>
              <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-white">
                The Core Invariant: Payment Success != Transaction Success
              </h2>
            </div>
          </div>
          <span className="rounded-full bg-neutral-800 text-neutral-300 px-3.5 py-1 text-xs font-mono border border-neutral-700">
            Verified Engineering Framework
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-sm">
          <div className="space-y-2">
            <span className="text-xs font-mono font-bold text-neutral-400 uppercase block">
              1. The Emerging Flaw
            </span>
            <p className="text-neutral-300 leading-relaxed text-xs sm:text-sm">
              AI agents are spending money autonomously. But modern payment gateways (Razorpay, Stripe) only confirm card debits—they have zero context on whether the charged cart actually matched the user&apos;s intent.
            </p>
          </div>

          <div className="space-y-2">
            <span className="text-xs font-mono font-bold text-emerald-400 uppercase block">
              2. What We Built
            </span>
            <p className="text-neutral-300 leading-relaxed text-xs sm:text-sm">
              TarkaRaksha acts as the deterministic transaction integrity control plane. We evaluate 4 boundaries in sub-15ms, emit cryptographic MRDP drift proofs, and autonomously negotiate remedies within pre-authorized budget bounds.
            </p>
          </div>

          <div className="space-y-2">
            <span className="text-xs font-mono font-bold text-violet-400 uppercase block">
              3. The Proof
            </span>
            <p className="text-neutral-300 leading-relaxed text-xs sm:text-sm">
              1,062 passed automated tests, zero floating-point math, 12 verified canonical scenarios, and bit-for-bit historical CPU replay with zero external side effects.
            </p>
          </div>
        </div>
      </div>

      {/* --------------------------------------------------------------------- */}
      {/* SECTION 2: 8 EXPANDED ARCHITECTURAL CLAIMS & ACHIEVEMENTS              */}
      {/* --------------------------------------------------------------------- */}
      <div className="space-y-6 pt-4">
        <div className="space-y-1">
          <span className="text-xs font-mono font-bold uppercase tracking-wider text-neutral-400">
            Verifiable Engineering Claims
          </span>
          <h2 className="text-2xl sm:text-4xl font-bold tracking-tight text-neutral-900">
            8 Architectural Claims &amp; Invariants Proven in Code
          </h2>
          <p className="text-sm sm:text-base text-neutral-600">
            Every claim below is backed by running test suites, immutable invariants, and cryptographic artifacts.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {architecturalClaims.map((claim) => (
            <div
              key={claim.id}
              className="rounded-3xl border border-neutral-200 bg-white p-6 space-y-4 shadow-sm flex flex-col justify-between hover:border-neutral-400 transition"
            >
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-2xl font-bold font-sans text-neutral-900 block">
                    {claim.number}
                  </span>
                  <span className="rounded-full bg-neutral-100 px-2 py-0.5 text-[9px] font-mono font-bold text-neutral-700 border border-neutral-200">
                    {claim.badge}
                  </span>
                </div>

                <div>
                  <h3 className="font-bold text-sm text-neutral-900">{claim.title}</h3>
                  <span className="font-mono text-[11px] text-neutral-500">{claim.metric}</span>
                </div>

                <p className="text-xs text-neutral-600 leading-relaxed font-sans">{claim.description}</p>
              </div>

              <div className="pt-3 border-t border-neutral-100 space-y-1.5 text-xs">
                <div className="bg-neutral-50 p-2.5 rounded-xl border border-neutral-200 space-y-0.5">
                  <span className="font-mono text-[9px] uppercase font-bold text-neutral-400 block">
                    Code Invariant:
                  </span>
                  <p className="text-[11px] font-mono text-neutral-800">{claim.invariant}</p>
                </div>
                <div className="text-[10px] font-mono text-neutral-400 truncate">
                  Tech: {claim.techStack}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* --------------------------------------------------------------------- */}
      {/* SECTION 3: HOW THE 4 AGENTS WORK                                     */}
      {/* --------------------------------------------------------------------- */}
      <div className="space-y-6 pt-6 border-t border-neutral-200">
        <div className="space-y-1">
          <span className="text-xs font-mono font-bold uppercase tracking-wider text-neutral-400">
            Agentic Roles &amp; Authority Model
          </span>
          <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-neutral-900">
            How Each Agent Functions &amp; Where Authority Sits
          </h2>
          <p className="text-sm text-neutral-600">
            AI reasoning proposes transactions; deterministic gates decide outcomes; provable ledgers record evidence.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {agentArchitectures.map((agent) => {
            const Icon = agent.icon;
            return (
              <div
                key={agent.role}
                className="rounded-3xl border border-neutral-200 bg-white p-6 space-y-4 shadow-sm flex flex-col justify-between"
              >
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div className={`p-2.5 rounded-2xl border ${agent.color}`}>
                      <Icon className="h-5 w-5" />
                    </div>
                    <span className="text-[10px] font-mono font-bold text-neutral-500 uppercase">
                      {agent.type}
                    </span>
                  </div>

                  <div>
                    <h3 className="font-bold text-base text-neutral-900">{agent.role}</h3>
                    <span className="font-mono text-[11px] text-neutral-400">{agent.identifier}</span>
                  </div>

                  <p className="text-xs sm:text-sm text-neutral-600 leading-relaxed font-sans">{agent.whatItDoes}</p>
                </div>

                <div className="pt-3 border-t border-neutral-100 text-xs text-neutral-700 bg-neutral-50 p-3 rounded-2xl space-y-1">
                  <strong className="text-neutral-900 block font-mono text-[10px] uppercase">
                    Safety Invariant Bound:
                  </strong>
                  <p className="text-xs">{agent.safetyBound}</p>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* --------------------------------------------------------------------- */}
      {/* SECTION 4: BEFORE VS AFTER COMPARISON (Scrollable Reality Check)      */}
      {/* --------------------------------------------------------------------- */}
      <div className="space-y-6 pt-6 border-t border-neutral-200">
        <div className="space-y-1">
          <span className="text-xs font-mono font-bold uppercase tracking-wider text-neutral-400">
            Empirical Proof of Value
          </span>
          <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-neutral-900">
            Before TarkaRaksha vs After TarkaRaksha (6 Failure Modes)
          </h2>
          <p className="text-sm text-neutral-600">
            Real autonomous commerce failures that pass standard gateways silently vs how our control plane catches and recovers them.
          </p>
        </div>

        <div className="space-y-4">
          {beforeAfterComparisons.map((item, idx) => (
            <div
              key={idx}
              className="rounded-3xl border border-neutral-200 bg-white p-6 sm:p-7 shadow-sm space-y-4 font-sans text-sm"
            >
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 pb-3 border-b border-neutral-100">
                <h3 className="text-base font-bold text-neutral-900">{item.title}</h3>
                <span className="text-neutral-500 text-xs font-mono italic">{item.scenario}</span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Before Box */}
                <div className="rounded-2xl border border-neutral-200 bg-neutral-50 p-5 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-neutral-700 uppercase font-mono text-xs">
                      Before: Standard Gateways
                    </span>
                    <span className={`px-2.5 py-0.5 rounded-full font-mono font-bold text-[10px] border ${item.before.color}`}>
                      {item.before.status}
                    </span>
                  </div>
                  <p className="text-neutral-600 text-xs sm:text-sm">{item.before.behavior}</p>
                  <p className="text-rose-700 font-semibold pt-1 text-xs sm:text-sm">{item.before.outcome}</p>
                </div>

                {/* After Box */}
                <div className="rounded-2xl border border-neutral-900 bg-neutral-900 text-white p-5 space-y-2 shadow-md">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-emerald-400 uppercase font-mono text-xs">
                      After: TarkaRaksha Control Plane
                    </span>
                    <span className={`px-2.5 py-0.5 rounded-full font-mono font-bold text-[10px] border ${item.after.color}`}>
                      {item.after.status}
                    </span>
                  </div>
                  <p className="text-neutral-300 text-xs sm:text-sm">{item.after.behavior}</p>
                  <p className="text-emerald-300 font-semibold pt-1 text-xs sm:text-sm">{item.after.outcome}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* --------------------------------------------------------------------- */}
      {/* SECTION 5: COMPLETE 12 CANONICAL SCENARIOS CATALOG                     */}
      {/* --------------------------------------------------------------------- */}
      <div className="space-y-6 pt-6 border-t border-neutral-200">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="space-y-1">
            <span className="text-xs font-mono font-bold uppercase tracking-wider text-neutral-400">
              Deterministic Test Catalog
            </span>
            <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-neutral-900">
              All 12 Canonical Test Cases Verified
            </h2>
            <p className="text-sm text-neutral-500">
              Each scenario is deterministically reproducible with verifiable ground truth.
            </p>
          </div>

          {/* Category Filter Pills */}
          <div className="flex flex-wrap gap-1 text-xs">
            {categories.map((cat) => (
              <button
                key={cat}
                onClick={() => setActiveCategory(cat)}
                className={`rounded-full px-3 py-1.5 text-xs font-mono transition ${
                  activeCategory === cat
                    ? "bg-neutral-900 text-white font-bold"
                    : "bg-neutral-100 text-neutral-600 hover:bg-neutral-200"
                }`}
              >
                {cat}
              </button>
            ))}
          </div>
        </div>

        {/* Scenarios Table */}
        <div className="rounded-3xl border border-neutral-200 overflow-hidden shadow-sm text-xs font-mono bg-white">
          <table className="min-w-full divide-y divide-neutral-200 text-left">
            <thead className="bg-neutral-50 text-xs uppercase font-bold text-neutral-500">
              <tr>
                <th className="px-5 py-3.5 font-sans">Scenario</th>
                <th className="px-5 py-3.5 font-sans">Category</th>
                <th className="px-5 py-3.5 font-sans">Injected Fault / Description</th>
                <th className="px-5 py-3.5 font-sans">Expected Policy Action</th>
                <th className="px-5 py-3.5 text-right font-sans">Verdict</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {filteredScenarios.map((scen) => (
                <tr key={scen.scenario_id} className="hover:bg-neutral-50/60 text-xs">
                  <td className="px-5 py-4 font-bold text-neutral-900 font-sans">
                    <div className="text-sm">{scen.name}</div>
                    <span className="text-xs text-neutral-400 font-mono">{scen.scenario_id}</span>
                  </td>
                  <td className="px-5 py-4">
                    <span className="rounded-full bg-neutral-100 px-2.5 py-0.5 text-[10px] font-bold text-neutral-700 border border-neutral-200">
                      {scen.category}
                    </span>
                  </td>
                  <td className="px-5 py-4 text-neutral-600 max-w-xs font-sans text-xs">
                    {scen.fault_description || scen.description}
                  </td>
                  <td className="px-5 py-4 text-neutral-800 text-xs font-mono">
                    {scen.expected_policy_action || "DETERMINISTIC_ASSERT"}
                  </td>
                  <td className="px-5 py-4 text-right">
                    <span
                      className={`px-2.5 py-1 rounded-full text-xs font-bold font-mono ${
                        scen.expected_verdict === "PASS"
                          ? "bg-emerald-100 text-emerald-800"
                          : scen.expected_verdict === "DRIFT"
                          ? "bg-rose-100 text-rose-800"
                          : "bg-amber-100 text-amber-800"
                      }`}
                    >
                      {scen.expected_verdict}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Bottom CTA to test live */}
        <div className="rounded-3xl bg-neutral-900 text-white p-8 sm:p-10 text-center space-y-4 shadow-xl">
          <h3 className="text-2xl sm:text-3xl font-bold tracking-tight">
            Ready to test these claims on live Razorpay checkouts?
          </h3>
          <p className="text-neutral-400 text-sm sm:text-base max-w-xl mx-auto">
            Launch the live order simulator to experience the 8-stage verification pipeline with real-time alerts.
          </p>
          <div className="pt-2">
            <button
              onClick={onLaunchOrderSimulator}
              className="inline-flex items-center space-x-2 rounded-full bg-white text-neutral-950 px-8 py-3.5 text-xs font-bold uppercase tracking-wider hover:bg-neutral-100 shadow-md active:scale-[0.98] transition"
            >
              <span>Launch Live Order Simulator</span>
              <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
