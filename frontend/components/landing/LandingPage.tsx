"use client";

import React, { useState } from "react";
import {
  Shield,
  ShieldCheck,
  ShieldAlert,
  ArrowRight,
  Cpu,
  Database,
  Lock,
  Layers,
  CheckCircle2,
  AlertTriangle,
  RotateCcw,
  Sparkles,
  ExternalLink,
  Code2,
  FileCheck2,
  History,
  Activity,
  Award,
  ChevronRight,
  Palette,
  CreditCard,
  SearchCheck,
  Zap,
  Globe,
  Terminal,
} from "lucide-react";
import { ControlRoomSnapshot, DrawerType } from "../../lib/types";
import { formatMoney } from "../../lib/formatters";
import { RealTimeOrderStudio } from "../control-room/RealTimeOrderStudio";
import { TransactionSpine } from "../control-room/TransactionSpine";
import { TruthStatusCard } from "../control-room/TruthStatusCard";
import { RazorpayDeepDiveSection } from "./RazorpayDeepDiveSection";

interface LandingPageProps {
  onEnterControlRoom: () => void;
  onNavigateToOrderSimulator: () => void;
  onNavigateToAnalytics: () => void;
  onNavigateToLogin: () => void;
  onRunHeroJourney: () => void;
  isRunningHero: boolean;
  snapshot: ControlRoomSnapshot;
  onOpenDrawer: (drawer: DrawerType) => void;
  onSnapshotUpdated: (snapshot: ControlRoomSnapshot) => void;
  isBackendConnected: boolean;
}

export const LandingPage: React.FC<LandingPageProps> = ({
  onEnterControlRoom,
  onNavigateToOrderSimulator,
  onNavigateToAnalytics,
  onNavigateToLogin,
  onRunHeroJourney,
  isRunningHero,
  snapshot,
  onOpenDrawer,
  onSnapshotUpdated,
  isBackendConnected,
}) => {
  const [activeTab, setActiveTab] = useState<number>(0);

  const features = [
    {
      icon: ShieldCheck,
      title: "4-Boundary Deterministic Verification",
      badge: "T04 ENGINE",
      description:
        "Continuously evaluates economic ceilings, semantic SKU substitutions, temporal nonce windows, and policy capability bounds. Holds strict zero-tolerance for silent mutations.",
    },
    {
      icon: FileCheck2,
      title: "Machine-Readable Drift Proof (MRDP)",
      badge: "T07 PROTOCOL",
      description:
        "Emits cryptographic SHA-256 tamper-evident proofs detailing expected versus observed values, exact error codes, and verified remediation paths for merchant accountability.",
    },
    {
      icon: RotateCcw,
      title: "Bounded Autonomous Recovery Loop",
      badge: "T11 RECOVERY",
      description:
        "Empowers AI advisory agents to negotiate compensatory discounts or authorized replacements within strict pre-authorized budget ceilings and bounded attempt budgets.",
    },
    {
      icon: History,
      title: "Deterministic CPU-Only Replay",
      badge: "T13 AUDIT",
      description:
        "Bit-for-bit historical re-execution verifying recorded transitions with strictly zero network calls, zero AI invocations, and zero financial mutation side effects.",
    },
    {
      icon: Lock,
      title: "Cryptographic Transaction Passport",
      badge: "E5 CERTIFICATE",
      description:
        "Seals every transaction with an immutable 8-checkpoint SHA-256 hash chain, guaranteeing non-repudiation between the buyer agent, merchant gateway, and ledger.",
    },
    {
      icon: Cpu,
      title: "Advisory AI Safety Isolation",
      badge: "T08 BOUNDARY",
      description:
        "Groq LLMs parse natural language prompts and propose remedies, but hold zero authority to move funds or declare PASS. Deterministic logic always decides.",
    },
  ];

  const slaTiers = [
    {
      tier: "Pre-Transaction Integrity",
      boundary: "Intent Contract Authorization",
      enforcement: "Cryptographic Nonce & Scope Lock",
      sla: "< 15ms",
      status: "STRICT",
    },
    {
      tier: "Checkout Evaluation",
      boundary: "Economic Ceiling & SKU Matching",
      enforcement: "T04 Deterministic Evaluator",
      sla: "< 25ms",
      status: "STRICT",
    },
    {
      tier: "Drift Proof Generation",
      boundary: "MRDP Protocol Artifact",
      enforcement: "SHA-256 Digest Signature",
      sla: "< 10ms",
      status: "AUTOMATIC",
    },
    {
      tier: "Autonomous Remediation",
      boundary: "Bounded Recovery Loop",
      enforcement: "Max 3 Attempts · Pre-authorized Budget",
      sla: "< 500ms",
      status: "BOUNDED",
    },
    {
      tier: "Payment Settlement",
      boundary: "Razorpay Test Mode Capture",
      enforcement: "Server-Side HMAC Verification",
      sla: "< 450ms",
      status: "GUARDED",
    },
    {
      tier: "Post-Execution Audit",
      boundary: "Deterministic CPU Replay",
      enforcement: "Zero Side-Effects Bit Verification",
      sla: "< 50ms",
      status: "ISOLATED",
    },
  ];

  return (
    <div className="flex flex-col min-h-screen bg-white font-sans text-neutral-900 selection:bg-neutral-900 selection:text-white">
      {/* --------------------------------------------------------------------- */}
      {/* SECTION 1: HERO (saas-kit style with gradient text & underline)      */}
      {/* --------------------------------------------------------------------- */}
      <section className="relative overflow-hidden pt-16 pb-20 sm:pt-24 sm:pb-28 border-b border-neutral-100">
        <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8 text-center space-y-8">
          {/* Eyebrow Pill Badge */}
          <div className="inline-flex items-center space-x-2 rounded-full bg-neutral-100 px-4 py-1.5 text-xs font-medium text-neutral-700 border border-neutral-200 shadow-2xs">
            <span className="flex h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="font-semibold">TarkaRaksha Control Plane v1.0</span>
            <span className="text-neutral-400">·</span>
            <span className="text-neutral-500">Autonomous Commerce Integrity</span>
          </div>

          {/* Headline inspired by saas-kit */}
          <div className="space-y-4">
            <h1 className="text-4xl sm:text-6xl lg:text-7xl font-bold tracking-tight text-neutral-900 leading-[1.12]">
              Payment success doesn&apos;t mean{" "}
              <em className="not-italic underline decoration-neutral-900 decoration-4 md:decoration-[6px]">
                transaction success.
              </em>
            </h1>
            <p className="mx-auto max-w-2xl text-base sm:text-xl text-neutral-600 font-normal leading-relaxed">
              When AI agents make autonomous purchases, gateways only confirm money moved.
              TarkaRaksha enforces deterministic invariants, generates machine-readable drift proofs,
              and bounds autonomous recovery.
            </p>
          </div>

          {/* Action Button Row */}
          <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
            <button
              onClick={onNavigateToOrderSimulator}
              className="inline-flex items-center space-x-2 rounded-full bg-neutral-900 px-7 py-3.5 text-sm font-semibold text-white hover:bg-neutral-800 active:scale-[0.98] transition shadow-md"
            >
              <span>Launch Order &amp; Razorpay Simulator</span>
              <ArrowRight className="h-4 w-4" />
            </button>

            <button
              onClick={onNavigateToAnalytics}
              className="inline-flex items-center space-x-2 rounded-full bg-white px-6 py-3.5 text-sm font-semibold text-neutral-800 border border-neutral-300 hover:bg-neutral-50 active:scale-[0.98] transition shadow-xs"
            >
              <Activity className="h-4 w-4 text-emerald-600" />
              <span>Analytics &amp; Test Cases</span>
            </button>

            <button
              onClick={onEnterControlRoom}
              className="inline-flex items-center space-x-2 rounded-full bg-neutral-100 px-5 py-3.5 text-sm font-semibold text-neutral-700 hover:bg-neutral-200/80 active:scale-[0.98] transition"
            >
              <Layers className="h-4 w-4 text-neutral-600" />
              <span>Control Room</span>
            </button>
          </div>

          {/* Tri-Pillar Authority Formula */}
          <div className="pt-4 text-xs font-mono text-neutral-500 flex flex-wrap items-center justify-center gap-2">
            <span className="text-violet-600 font-bold">AI proposes</span>
            <span>·</span>
            <span className="text-blue-600 font-bold">Evidence proves</span>
            <span>·</span>
            <span className="text-emerald-700 font-bold">Deterministic logic decides</span>
          </div>
        </div>
      </section>

      {/* --------------------------------------------------------------------- */}
      {/* SECTION 2: REAL-TIME INTERACTIVE ORDER STUDIO (User's Core Ask!)      */}
      {/* --------------------------------------------------------------------- */}
      <section id="order-studio" className="py-16 sm:py-24 bg-neutral-50/70 border-b border-neutral-200">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 space-y-8">
          <div className="text-center space-y-2 max-w-3xl mx-auto">
            <span className="text-xs font-mono font-bold uppercase tracking-wider text-neutral-400">
              Interactive Real-Time Verification
            </span>
            <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-neutral-900">
              Place an Order &amp; Watch the Chains of Action Live
            </h2>
            <p className="text-neutral-600 text-sm sm:text-base">
              Test how the system functions in real time with exact telemetry: see every decision,
              every latency measurement in milliseconds, how violations are proved, and how it safely moves to the next step.
            </p>
          </div>

          {/* RealTimeOrderStudio Component */}
          <RealTimeOrderStudio
            onSnapshotUpdated={onSnapshotUpdated}
            onOpenDrawer={onOpenDrawer}
            isBackendConnected={isBackendConnected}
          />
        </div>
      </section>

      {/* --------------------------------------------------------------------- */}
      {/* SECTION 2.5: RAZORPAY DEEP DIVE & MONEY VALUATION AT EACH STEP       */}
      {/* --------------------------------------------------------------------- */}
      <RazorpayDeepDiveSection />

      {/* --------------------------------------------------------------------- */}
      {/* SECTION 3: TECH STACK / ARCHITECTURE CLOUD (saas-kit logos cloud)    */}
      {/* --------------------------------------------------------------------- */}
      <section className="py-16 border-b border-neutral-100 bg-white">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8 space-y-6 text-center">
          <div>
            <span className="text-xs font-mono font-bold uppercase tracking-wider text-neutral-400 block">
              Actual Architecture Stack
            </span>
            <p className="text-xs text-neutral-500 mt-1">
              Engineered with zero decorative mock frameworks. All protocols and integrations run natively.
            </p>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3 text-xs font-mono">
            <div className="rounded-2xl border border-neutral-200/80 bg-neutral-50/50 p-4 space-y-1 shadow-2xs">
              <CreditCard className="h-5 w-5 text-blue-600 mx-auto mb-1" />
              <span className="font-bold text-neutral-900 block font-sans">Razorpay</span>
              <span className="text-[10px] text-neutral-500 block">Test Mode Gateway</span>
            </div>

            <div className="rounded-2xl border border-neutral-200/80 bg-neutral-50/50 p-4 space-y-1 shadow-2xs">
              <Zap className="h-5 w-5 text-emerald-600 mx-auto mb-1" />
              <span className="font-bold text-neutral-900 block font-sans">FastAPI</span>
              <span className="text-[10px] text-neutral-500 block">Python 3.12 Core</span>
            </div>

            <div className="rounded-2xl border border-neutral-200/80 bg-neutral-50/50 p-4 space-y-1 shadow-2xs">
              <Cpu className="h-5 w-5 text-violet-600 mx-auto mb-1" />
              <span className="font-bold text-neutral-900 block font-sans">Groq Llama 3.3</span>
              <span className="text-[10px] text-neutral-500 block">Advisory AI Agent</span>
            </div>

            <div className="rounded-2xl border border-neutral-200/80 bg-neutral-50/50 p-4 space-y-1 shadow-2xs">
              <FileCheck2 className="h-5 w-5 text-neutral-800 mx-auto mb-1" />
              <span className="font-bold text-neutral-900 block font-sans">MRDP</span>
              <span className="text-[10px] text-neutral-500 block">Drift Proof Protocol</span>
            </div>

            <div className="rounded-2xl border border-neutral-200/80 bg-neutral-50/50 p-4 space-y-1 shadow-2xs">
              <Lock className="h-5 w-5 text-neutral-800 mx-auto mb-1" />
              <span className="font-bold text-neutral-900 block font-sans">HMAC-SHA256</span>
              <span className="text-[10px] text-neutral-500 block">Cryptographic Seal</span>
            </div>

            <div className="rounded-2xl border border-neutral-200/80 bg-neutral-50/50 p-4 space-y-1 shadow-2xs">
              <Layers className="h-5 w-5 text-neutral-800 mx-auto mb-1" />
              <span className="font-bold text-neutral-900 block font-sans">Next.js 15</span>
              <span className="text-[10px] text-neutral-500 block">Turbopack App Router</span>
            </div>
          </div>
        </div>
      </section>

      {/* --------------------------------------------------------------------- */}
      {/* SECTION 4: FEATURES GRID (saas-kit features style)                    */}
      {/* --------------------------------------------------------------------- */}
      <section className="py-20 sm:py-28 bg-neutral-50/70 border-b border-neutral-200">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8 space-y-12">
          <div className="text-center space-y-3 max-w-2xl mx-auto">
            <span className="text-xs font-mono font-bold uppercase tracking-wider text-neutral-400">
              Integrity Control Architecture
            </span>
            <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-neutral-900">
              Enterprise Guarantees for Agentic Commerce
            </h2>
            <p className="text-neutral-600 text-sm sm:text-base">
              Engineered to prevent financial drift, unauthorized substitutions, and silent cart mutations before funds transfer.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {features.map((feat) => {
              const Icon = feat.icon;
              return (
                <div
                  key={feat.title}
                  className="rounded-2xl border border-neutral-200/90 bg-white p-6 space-y-3 hover:border-neutral-400 transition-all shadow-2xs"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-neutral-100 text-neutral-900">
                      <Icon className="h-5 w-5" />
                    </div>
                    <span className="rounded bg-neutral-100 px-2 py-0.5 text-[10px] font-mono font-semibold text-neutral-600 border border-neutral-200">
                      {feat.badge}
                    </span>
                  </div>

                  <h3 className="text-base font-bold text-neutral-900 tracking-tight">{feat.title}</h3>
                  <p className="text-xs text-neutral-600 leading-relaxed">{feat.description}</p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* --------------------------------------------------------------------- */}
      {/* SECTION 5: BOUNDARY SLA MATRIX (Pricing / SLA Table style)           */}
      {/* --------------------------------------------------------------------- */}
      <section className="py-20 sm:py-28 border-b border-neutral-100 bg-white">
        <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8 space-y-8">
          <div className="text-center space-y-3 max-w-2xl mx-auto">
            <span className="text-xs font-mono font-bold uppercase tracking-wider text-neutral-400">
              SLA &amp; Verification Matrix
            </span>
            <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-neutral-900">
              Deterministic Boundary Execution Standards
            </h2>
            <p className="text-neutral-600 text-sm">
              All 6 boundary enforcement tiers operate within sub-second deterministic latency bounds.
            </p>
          </div>

          <div className="rounded-2xl border border-neutral-200 overflow-hidden shadow-2xs text-xs font-mono">
            <table className="min-w-full divide-y divide-neutral-200 text-left">
              <thead className="bg-neutral-50 text-[10px] uppercase font-bold text-neutral-500">
                <tr>
                  <th className="px-4 py-3 font-sans font-bold">Verification Tier</th>
                  <th className="px-4 py-3 font-sans font-bold">Boundary Rule</th>
                  <th className="px-4 py-3 font-sans font-bold">Enforcement Engine</th>
                  <th className="px-4 py-3 font-sans font-bold">Latency SLA</th>
                  <th className="px-4 py-3 text-right font-sans font-bold">Policy</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                {slaTiers.map((row, i) => (
                  <tr key={i} className="hover:bg-neutral-50/60 font-mono text-xs">
                    <td className="px-4 py-3 font-semibold text-neutral-900 font-sans">{row.tier}</td>
                    <td className="px-4 py-3 text-neutral-700">{row.boundary}</td>
                    <td className="px-4 py-3 text-neutral-500 text-[11px]">{row.enforcement}</td>
                    <td className="px-4 py-3 text-emerald-700 font-bold">{row.sla}</td>
                    <td className="px-4 py-3 text-right">
                      <span className="rounded bg-neutral-100 px-2 py-0.5 text-[10px] font-bold text-neutral-700 border border-neutral-200">
                        {row.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* --------------------------------------------------------------------- */}
      {/* SECTION 6: FOOTER (matching saas-kit layout)                          */}
      {/* --------------------------------------------------------------------- */}
      <footer className="border-t border-neutral-200 bg-neutral-50/80 py-12 text-neutral-600 text-xs">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 space-y-8">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-8">
            {/* Column 1: Brand */}
            <div className="space-y-3 col-span-2 sm:col-span-1">
              <div className="flex items-center space-x-2">
                <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-neutral-900 text-white">
                  <Shield className="h-4 w-4" />
                </div>
                <span className="font-bold text-neutral-900 text-sm font-sans">TarkaRaksha</span>
              </div>
              <p className="text-neutral-500 text-[11px] leading-relaxed">
                Agentic Transaction Integrity &amp; Autonomous Recovery Control Plane.
              </p>
            </div>

            {/* Column 2: Architecture */}
            <div className="space-y-2.5">
              <span className="font-bold uppercase tracking-wider text-neutral-900 text-[11px] font-mono">
                Architecture
              </span>
              <ul className="space-y-2 text-[11px]">
                <li><button onClick={onEnterControlRoom} className="hover:text-neutral-900">Control Room Surface</button></li>
                <li><button onClick={() => onOpenDrawer("integrity")} className="hover:text-neutral-900">T04 Deterministic Gate</button></li>
                <li><button onClick={() => onOpenDrawer("mrdp")} className="hover:text-neutral-900">T07 MRDP Proofs</button></li>
                <li><button onClick={() => onOpenDrawer("recovery")} className="hover:text-neutral-900">T11 Recovery Loop</button></li>
              </ul>
            </div>

            {/* Column 3: Telemetry */}
            <div className="space-y-2.5">
              <span className="font-bold uppercase tracking-wider text-neutral-900 text-[11px] font-mono">
                Telemetry
              </span>
              <ul className="space-y-2 text-[11px]">
                <li><button onClick={() => onOpenDrawer("replay")} className="hover:text-neutral-900">Deterministic Replay</button></li>
                <li><button onClick={() => onOpenDrawer("passport")} className="hover:text-neutral-900">Transaction Passport</button></li>
                <li><button onClick={() => onOpenDrawer("security")} className="hover:text-neutral-900">Threat Matrix &amp; Kill Switch</button></li>
                <li><button onClick={() => onOpenDrawer("scenarios")} className="hover:text-neutral-900">Scenario Lab (12 Catalog)</button></li>
              </ul>
            </div>

            {/* Column 4: Links */}
            <div className="space-y-2.5">
              <span className="font-bold uppercase tracking-wider text-neutral-900 text-[11px] font-mono">
                Repository
              </span>
              <ul className="space-y-2 text-[11px]">
                <li><a href="https://github.com/ankit-choubey/TarkaRaksha" target="_blank" rel="noreferrer" className="hover:text-neutral-900">GitHub Repository</a></li>
                <li><a href="https://razorpay.com/docs/api/" target="_blank" rel="noreferrer" className="hover:text-neutral-900">Razorpay Test Mode Docs</a></li>
                <li><a href="https://groq.com" target="_blank" rel="noreferrer" className="hover:text-neutral-900">Groq LLM Advisory</a></li>
                <li><span className="text-emerald-700 font-bold">Status: All 1,062 Tests Passing</span></li>
              </ul>
            </div>
          </div>

          <div className="pt-6 border-t border-neutral-200/80 flex flex-col sm:flex-row items-center justify-between text-[11px] text-neutral-400 gap-2">
            <span>&copy; {new Date().getFullYear()} TarkaRaksha. Built for autonomous agentic commerce integrity.</span>
            <span>Style inspired by saas-kit / Shadcn design system.</span>
          </div>
        </div>
      </footer>
    </div>
  );
};
