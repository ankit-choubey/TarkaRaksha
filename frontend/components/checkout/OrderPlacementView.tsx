"use client";

import React, { useState } from "react";
import {
  ShoppingCart,
  ShieldCheck,
  CreditCard,
  Tag,
  ArrowRight,
  AlertTriangle,
  RotateCcw,
  Sparkles,
  Bot,
  Store,
  Clock,
  Layers,
  Settings2,
  Sliders,
  Cpu,
  GitBranch,
  FileCheck2,
  Lock,
  Play,
  Pause,
} from "lucide-react";
import { MoneyValue, DrawerType } from "../../lib/types";
import { formatMoney } from "../../lib/formatters";
import { RazorpayModal } from "./RazorpayModal";
import { RealTimeVerificationFlow } from "./RealTimeVerificationFlow";
import { E6ExplainerModal } from "../control-room/drawers/E6ExplainerModal";

export type ScenarioType =
  | "surge_drift"
  | "clean_pass"
  | "sku_sub"
  | "double_webhook"
  | "timeout"
  | "tax_drift"
  | "quality_tradeoff";

interface CatalogProduct {
  id: string;
  title: string;
  sku: string;
  category: string;
  authorizedMaxPaise: number;
  normalPricePaise: number;
  surgePricePaise: number;
  refurbSku: string;
  description: string;
  badge: string;
  suggestedPrompt: string;
}

const CATALOG: CatalogProduct[] = [
  {
    id: "prod_monitor_4k",
    title: '27" 4K Color-Accurate Studio Display',
    sku: "SKU-MON-4K-27",
    category: "Displays",
    authorizedMaxPaise: 5000000, // ₹50,000 max
    normalPricePaise: 4800000, // ₹48,000
    surgePricePaise: 5500000, // ₹55,000 (+₹5,000 drift)
    refurbSku: "SKU-MON-4K-REFURB",
    description: "High-density UHD display for autonomous workstation environments. Subject to merchant dynamic surge fee.",
    badge: "Canonical E6 Demo",
    suggestedPrompt: "Procure high-performance 4K monitor for developer workstation under ₹50,000 with 100% sRGB accuracy.",
  },
  {
    id: "prod_ssd_1tb",
    title: "1TB Ultra-Fast NVMe Storage Unit",
    sku: "SKU-SSD-1TB",
    category: "Storage",
    authorizedMaxPaise: 800000, // ₹8,000 max
    normalPricePaise: 750000, // ₹7,500
    surgePricePaise: 920000, // ₹9,200 (+₹1,200 drift)
    refurbSku: "SKU-SSD-REFURB",
    description: "High IOPS external storage unit. Baseline happy path test purchase.",
    badge: "Clean Pass",
    suggestedPrompt: "Buy genuine 1TB NVMe storage unit for offline transaction backups with ceiling ₹8,000.",
  },
  {
    id: "prod_laptop_pro",
    title: 'Laptop Pro 16" (Silicon Chip, 32GB RAM)',
    sku: "SKU-LAPTOP-PRO-16",
    category: "Laptops",
    authorizedMaxPaise: 16000000, // ₹1,60,000 max
    normalPricePaise: 15500000,
    surgePricePaise: 17500000,
    refurbSku: "SKU-LAPTOP-REFURB-16",
    description: "Flagship developer workstation. Demonstrates semantic unauthorized substitution detection.",
    badge: "Semantic Drift Test",
    suggestedPrompt: "Acquire brand new sealed 16-inch developer laptop under ₹1,60,000. Reject refurbished hardware.",
  },
];

interface OrderPlacementViewProps {
  onOpenDrawer: (drawer: DrawerType) => void;
  onViewInControlRoom: () => void;
}

export const OrderPlacementView: React.FC<OrderPlacementViewProps> = ({
  onOpenDrawer,
  onViewInControlRoom,
}) => {
  const [selectedProduct, setSelectedProduct] = useState<CatalogProduct>(CATALOG[0]);
  const [scenarioMode, setScenarioMode] = useState<ScenarioType>("surge_drift");
  const [isAutonomousMode, setIsAutonomousMode] = useState<boolean>(true);
  const [isRazorpayModalOpen, setIsRazorpayModalOpen] = useState<boolean>(false);

  // Custom Criteria Configuration State (user detail customization)
  const [isCustomCriteriaOpen, setIsCustomCriteriaOpen] = useState<boolean>(false);
  const [customTitle, setCustomTitle] = useState<string>('27" 4K Color-Accurate Studio Display');
  const [customSku, setCustomSku] = useState<string>("SKU-MON-4K-27");
  const [customCeilingRupees, setCustomCeilingRupees] = useState<number>(50000);
  const [customMerchantRupees, setCustomMerchantRupees] = useState<number>(55000);
  const [customPrompt, setCustomPrompt] = useState<string>(
    "Procure high-performance 4K monitor for developer workstation under ₹50,000 with 100% sRGB accuracy."
  );

  // Completed Payment State
  const [completedPayment, setCompletedPayment] = useState<{
    paymentId: string;
    orderId: string;
    signature: string;
  } | null>(null);

  // E6 Hero Journey Explainer Modal State
  const [isE6ModalOpen, setIsE6ModalOpen] = useState<boolean>(false);

  // Compute effective pricing values
  const effectiveTitle = isCustomCriteriaOpen ? customTitle : selectedProduct.title;
  const effectiveSku = isCustomCriteriaOpen
    ? customSku
    : scenarioMode === "sku_sub"
    ? selectedProduct.refurbSku
    : selectedProduct.sku;

  const effectiveCeilingPaise = isCustomCriteriaOpen
    ? customCeilingRupees * 100
    : scenarioMode === "quality_tradeoff"
    ? 5000000 // ₹50,000 user budget
    : selectedProduct.authorizedMaxPaise;

  const effectiveChargedPaise = isCustomCriteriaOpen
    ? customMerchantRupees * 100
    : scenarioMode === "surge_drift"
    ? selectedProduct.surgePricePaise
    : scenarioMode === "tax_drift"
    ? selectedProduct.normalPricePaise + 350000 // +₹3,500 tax drift
    : scenarioMode === "quality_tradeoff"
    ? 5200000 // ₹52,000 for superior quality display (+₹2,000)
    : selectedProduct.normalPricePaise;

  const authorizedMax: MoneyValue = { amount: effectiveCeilingPaise, currency: "INR" };
  const checkoutPrice: MoneyValue = { amount: effectiveChargedPaise, currency: "INR" };

  const handleStartCheckout = () => {
    setIsRazorpayModalOpen(true);
  };

  const handlePaymentSuccess = (paymentId: string, orderId: string, signature: string) => {
    setIsRazorpayModalOpen(false);
    setCompletedPayment({ paymentId, orderId, signature });
  };

  const handleReset = () => {
    setCompletedPayment(null);
    setIsCustomCriteriaOpen(false);
    setSelectedProduct(CATALOG[0]);
    setScenarioMode("surge_drift");
  };

  const selectProductPreset = (prod: CatalogProduct) => {
    setSelectedProduct(prod);
    setCustomTitle(prod.title);
    setCustomSku(prod.sku);
    setCustomCeilingRupees(prod.authorizedMaxPaise / 100);
    setCustomMerchantRupees(
      scenarioMode === "surge_drift" ? prod.surgePricePaise / 100 : prod.normalPricePaise / 100
    );
    setCustomPrompt(prod.suggestedPrompt);
  };

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-10 space-y-10 font-sans text-neutral-900">
      {/* Title & Studio Header */}
      <div className="text-center space-y-3 max-w-4xl mx-auto">
        <div className="inline-flex items-center space-x-2 rounded-full bg-neutral-100 px-4 py-1 text-xs font-mono text-neutral-700 border border-neutral-200">
          <Sparkles className="h-3.5 w-3.5 text-emerald-600" />
          <span>Real-Time Autonomous Checkout &amp; Verification Studio</span>
        </div>
        <h1 className="text-3xl sm:text-5xl font-bold tracking-tight text-neutral-900 leading-tight">
          Simulate Autonomous Orders with Live Razorpay Verification
        </h1>
        <p className="text-base text-neutral-600 max-w-2xl mx-auto leading-relaxed">
          See what happens when an AI Buyer Agent executes a checkout on a live payment gateway.
          TarkaRaksha intercepts the transaction, evaluates deterministic boundaries, and recovers drift.
        </p>

        {/* Stepping Mode Selector & Reset Control */}
        <div className="pt-2 flex flex-wrap items-center justify-center gap-3">
          <span className="text-xs font-mono font-bold uppercase text-neutral-400">
            Verification Pipeline Mode:
          </span>
          <div className="inline-flex rounded-2xl bg-neutral-100 p-1 border border-neutral-200 shadow-2xs">
            <button
              onClick={() => setIsAutonomousMode(true)}
              className={`px-4 py-1.5 rounded-xl text-xs font-bold flex items-center space-x-2 transition ${
                isAutonomousMode
                  ? "bg-neutral-900 text-white shadow-xs"
                  : "text-neutral-600 hover:text-neutral-900"
              }`}
            >
              <Play className="h-3.5 w-3.5 text-emerald-400" />
              <span>⚡ Automatic (4-5s Per Step)</span>
            </button>

            <button
              onClick={() => setIsAutonomousMode(false)}
              className={`px-4 py-1.5 rounded-xl text-xs font-bold flex items-center space-x-2 transition ${
                !isAutonomousMode
                  ? "bg-neutral-900 text-white shadow-xs"
                  : "text-neutral-600 hover:text-neutral-900"
              }`}
            >
              <Pause className="h-3.5 w-3.5 text-amber-400" />
              <span>🖐 Manual Guided Stepping</span>
            </button>
          </div>

          {/* Reset Page to Step 0 Button */}
          <button
            onClick={handleReset}
            className="px-4 py-2 rounded-2xl text-xs font-bold text-neutral-700 hover:text-neutral-950 bg-white border border-neutral-300 hover:bg-neutral-50 flex items-center space-x-1.5 transition shadow-2xs"
            title="Reset all settings, criteria, and payment back to Step 0"
          >
            <RotateCcw className="h-3.5 w-3.5 text-neutral-500" />
            <span>↺ Reset Page to Step 0</span>
          </button>
        </div>
      </div>

      {completedPayment ? (
        /* Real-Time Post-Payment Verification Flow */
        <RealTimeVerificationFlow
          scenarioId={scenarioMode}
          itemTitle={effectiveTitle}
          authorizedMax={authorizedMax}
          chargedAmount={checkoutPrice}
          paymentId={completedPayment.paymentId}
          orderId={completedPayment.orderId}
          signature={completedPayment.signature}
          onOpenDrawer={onOpenDrawer}
          onResetOrder={handleReset}
          onViewInControlRoom={onViewInControlRoom}
          initialIsAutonomous={isAutonomousMode}
        />
      ) : (
        /* Step 1: Place Order & Pick Scenario */
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left 2 Cols: Catalog, Scenarios & LLM Routing */}
          <div className="lg:col-span-2 space-y-8">
            {/* 1. Catalog Item Selector */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-mono font-bold uppercase tracking-wider text-neutral-400">
                  1. Select Target Purchase Item
                </span>
                <span className="text-xs text-neutral-500 font-mono">3 Certified Hardware Models</span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5">
                {CATALOG.map((prod) => {
                  const isSelected = selectedProduct.id === prod.id && !isCustomCriteriaOpen;
                  return (
                    <button
                      key={prod.id}
                      onClick={() => {
                        setIsCustomCriteriaOpen(false);
                        selectProductPreset(prod);
                      }}
                      className={`p-5 rounded-2xl border text-left transition-all space-y-2.5 relative ${
                        isSelected
                          ? "bg-neutral-900 text-white border-neutral-900 shadow-md ring-2 ring-neutral-900"
                          : "bg-white text-neutral-800 border-neutral-200 hover:border-neutral-300"
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-mono text-neutral-400 font-bold uppercase">
                          {prod.category}
                        </span>
                        <span
                          className={`rounded px-2 py-0.5 text-[10px] font-mono font-semibold ${
                            isSelected
                              ? "bg-neutral-800 text-emerald-400 border border-neutral-700"
                              : "bg-neutral-100 text-neutral-600 border border-neutral-200"
                          }`}
                        >
                          {prod.badge}
                        </span>
                      </div>

                      <h4 className="font-bold text-sm leading-snug line-clamp-2">{prod.title}</h4>

                      <div className="pt-2 border-t border-neutral-200/40 text-xs font-mono flex items-center justify-between">
                        <span className={isSelected ? "text-neutral-400" : "text-neutral-500"}>
                          Ceiling:
                        </span>
                        <span className="font-bold">
                          {formatMoney({ amount: prod.authorizedMaxPaise, currency: "INR" })}
                        </span>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* 2. Custom Criteria & Details Configuration (User Request: "keep a criteria to add the details there") */}
            <div className="rounded-2xl border border-neutral-200 bg-white p-5 space-y-4 shadow-2xs">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <Sliders className="h-4 w-4 text-neutral-700" />
                  <span className="text-xs font-mono font-bold uppercase tracking-wider text-neutral-900">
                    Custom Criteria &amp; Parameter Details
                  </span>
                </div>
                <button
                  onClick={() => setIsCustomCriteriaOpen(!isCustomCriteriaOpen)}
                  className={`text-xs font-bold px-3 py-1 rounded-full border transition ${
                    isCustomCriteriaOpen
                      ? "bg-neutral-900 text-white border-neutral-900"
                      : "bg-neutral-50 text-neutral-700 border-neutral-300 hover:bg-neutral-100"
                  }`}
                >
                  {isCustomCriteriaOpen ? "Custom Parameters Active" : "Customize Parameters +"}
                </button>
              </div>

              {isCustomCriteriaOpen ? (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 text-xs font-sans">
                  <div>
                    <label className="block text-neutral-600 font-semibold mb-1">
                      Custom Item Title:
                    </label>
                    <input
                      type="text"
                      value={customTitle}
                      onChange={(e) => setCustomTitle(e.target.value)}
                      className="w-full rounded-xl border border-neutral-300 p-2.5 text-sm font-medium focus:outline-none focus:border-neutral-900"
                    />
                  </div>

                  <div>
                    <label className="block text-neutral-600 font-semibold mb-1">
                      Product SKU Identifier:
                    </label>
                    <input
                      type="text"
                      value={customSku}
                      onChange={(e) => setCustomSku(e.target.value)}
                      className="w-full rounded-xl border border-neutral-300 p-2.5 text-sm font-mono focus:outline-none focus:border-neutral-900"
                    />
                  </div>

                  <div>
                    <label className="block text-neutral-600 font-semibold mb-1">
                      Authorized Max Ceiling (₹ INR):
                    </label>
                    <input
                      type="number"
                      value={customCeilingRupees}
                      onChange={(e) => setCustomCeilingRupees(Number(e.target.value))}
                      className="w-full rounded-xl border border-neutral-300 p-2.5 text-sm font-mono font-bold focus:outline-none focus:border-neutral-900"
                    />
                  </div>

                  <div>
                    <label className="block text-neutral-600 font-semibold mb-1">
                      Merchant Cart Charge (₹ INR):
                    </label>
                    <input
                      type="number"
                      value={customMerchantRupees}
                      onChange={(e) => setCustomMerchantRupees(Number(e.target.value))}
                      className="w-full rounded-xl border border-neutral-300 p-2.5 text-sm font-mono font-bold focus:outline-none focus:border-neutral-900"
                    />
                  </div>

                  <div className="sm:col-span-2">
                    <label className="block text-neutral-600 font-semibold mb-1">
                      Natural Language Intent Prompt:
                    </label>
                    <textarea
                      rows={2}
                      value={customPrompt}
                      onChange={(e) => setCustomPrompt(e.target.value)}
                      className="w-full rounded-xl border border-neutral-300 p-2.5 text-sm font-medium focus:outline-none focus:border-neutral-900"
                    />
                  </div>
                </div>
              ) : (
                <p className="text-xs text-neutral-500">
                  Using default catalog thresholds. Click &quot;Customize Parameters&quot; to inject arbitrary financial ceilings, custom prompts, or arbitrary item descriptions.
                </p>
              )}
            </div>

            {/* 3. Injected Execution Scenarios (Expanded to 6 Scenarios) */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-mono font-bold uppercase tracking-wider text-neutral-400">
                  2. Select Injected Execution Scenario
                </span>
                <span className="text-xs text-neutral-500 font-mono">6 Certified Failure &amp; Recovery Modes</span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5 text-xs">
                {/* Scenario 1: Price Drift */}
                <button
                  onClick={() => setScenarioMode("surge_drift")}
                  className={`p-4 rounded-2xl border text-left transition-all space-y-1.5 ${
                    scenarioMode === "surge_drift"
                      ? "bg-neutral-900 text-white border-neutral-900 shadow-sm"
                      : "bg-white text-neutral-800 border-neutral-200 hover:border-neutral-300"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-sm">A. Dynamic Price Surge Drift</span>
                    <span className="rounded bg-rose-100 text-rose-800 text-[10px] font-mono font-bold px-2 py-0.5">
                      DRIFT + RECOVERY
                    </span>
                  </div>
                  <p className={`text-xs ${scenarioMode === "surge_drift" ? "text-neutral-300" : "text-neutral-500"}`}>
                    Merchant cart charges unbudgeted fee (+₹5,000). Triggers MRDP proof and autonomous discount negotiation.
                  </p>
                  <div className="pt-1">
                    <span
                      onClick={(e) => {
                        e.stopPropagation();
                        setIsE6ModalOpen(true);
                      }}
                      className="inline-flex items-center space-x-1.5 text-[11px] font-mono text-emerald-600 hover:text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-lg border border-emerald-200 cursor-pointer transition shadow-2xs font-semibold"
                    >
                      <Sparkles className="h-3 w-3 text-emerald-600" />
                      <span>What does E6 run do? View Story</span>
                    </span>
                  </div>
                </button>

                {/* Scenario 2: Clean Pass */}
                <button
                  onClick={() => setScenarioMode("clean_pass")}
                  className={`p-4 rounded-2xl border text-left transition-all space-y-1.5 ${
                    scenarioMode === "clean_pass"
                      ? "bg-neutral-900 text-white border-neutral-900 shadow-sm"
                      : "bg-white text-neutral-800 border-neutral-200 hover:border-neutral-300"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-sm">B. Clean Authorized Purchase</span>
                    <span className="rounded bg-emerald-100 text-emerald-800 text-[10px] font-mono font-bold px-2 py-0.5">
                      DIRECT PASS
                    </span>
                  </div>
                  <p className={`text-xs ${scenarioMode === "clean_pass" ? "text-neutral-300" : "text-neutral-500"}`}>
                    Cart total is strictly within authorized limit. All 4 deterministic boundaries pass cleanly.
                  </p>
                </button>

                {/* Scenario 3: SKU Substitution */}
                <button
                  onClick={() => setScenarioMode("sku_sub")}
                  className={`p-4 rounded-2xl border text-left transition-all space-y-1.5 ${
                    scenarioMode === "sku_sub"
                      ? "bg-neutral-900 text-white border-neutral-900 shadow-sm"
                      : "bg-white text-neutral-800 border-neutral-200 hover:border-neutral-300"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-sm">C. Refurbished SKU Substitution</span>
                    <span className="rounded bg-neutral-800 text-white text-[10px] font-mono font-bold px-2 py-0.5">
                      SEMANTIC BLOCK
                    </span>
                  </div>
                  <p className={`text-xs ${scenarioMode === "sku_sub" ? "text-neutral-300" : "text-neutral-500"}`}>
                    Merchant cart substitutes authorized item for refurbished SKU. Semantic check blocks settlement.
                  </p>
                </button>

                {/* Scenario 4: Double Webhook */}
                <button
                  onClick={() => setScenarioMode("double_webhook")}
                  className={`p-4 rounded-2xl border text-left transition-all space-y-1.5 ${
                    scenarioMode === "double_webhook"
                      ? "bg-neutral-900 text-white border-neutral-900 shadow-sm"
                      : "bg-white text-neutral-800 border-neutral-200 hover:border-neutral-300"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-sm">D. Asynchronous Double Webhook</span>
                    <span className="rounded bg-blue-100 text-blue-800 text-[10px] font-mono font-bold px-2 py-0.5">
                      IDEMPOTENT LOCK
                    </span>
                  </div>
                  <p className={`text-xs ${scenarioMode === "double_webhook" ? "text-neutral-300" : "text-neutral-500"}`}>
                    Gateway fires duplicate captured webhook. E1 Context Ledger deduplicates without double debit.
                  </p>
                </button>

                {/* Scenario 5: Gateway Timeout */}
                <button
                  onClick={() => setScenarioMode("timeout")}
                  className={`p-4 rounded-2xl border text-left transition-all space-y-1.5 ${
                    scenarioMode === "timeout"
                      ? "bg-neutral-900 text-white border-neutral-900 shadow-sm"
                      : "bg-white text-neutral-800 border-neutral-200 hover:border-neutral-300"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-sm">E. Gateway 504 Timeout</span>
                    <span className="rounded bg-amber-100 text-amber-800 text-[10px] font-mono font-bold px-2 py-0.5">
                      UNKNOWN RESOLUTION
                    </span>
                  </div>
                  <p className={`text-xs ${scenarioMode === "timeout" ? "text-neutral-300" : "text-neutral-500"}`}>
                    Gateway connection dropped. Triggers deliberate abstention state: NO SECOND PAYMENT.
                  </p>
                </button>

                {/* Scenario 6: Tax Surcharge Drift */}
                <button
                  onClick={() => setScenarioMode("tax_drift")}
                  className={`p-4 rounded-2xl border text-left transition-all space-y-1.5 ${
                    scenarioMode === "tax_drift"
                      ? "bg-neutral-900 text-white border-neutral-900 shadow-sm"
                      : "bg-white text-neutral-800 border-neutral-200 hover:border-neutral-300"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-sm">F. Hidden Tax Surcharge Drift</span>
                    <span className="rounded bg-purple-100 text-purple-800 text-[10px] font-mono font-bold px-2 py-0.5">
                      TAX DISCREPANCY
                    </span>
                  </div>
                  <p className={`text-xs ${scenarioMode === "tax_drift" ? "text-neutral-300" : "text-neutral-500"}`}>
                    Checkout injects unexpected platform surcharge (+₹3,500). Held until line-item audit passes.
                  </p>
                </button>

                {/* Scenario 7: AI Quality vs Budget Tradeoff */}
                <button
                  onClick={() => setScenarioMode("quality_tradeoff")}
                  className={`p-4 rounded-2xl border text-left transition-all space-y-1.5 sm:col-span-2 ${
                    scenarioMode === "quality_tradeoff"
                      ? "bg-neutral-900 text-white border-neutral-900 shadow-sm ring-2 ring-neutral-900"
                      : "bg-white text-neutral-800 border-neutral-200 hover:border-neutral-300"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-sm">G. AI Quality vs Budget Tradeoff (₹50k Budget vs ₹52k Superior Quality)</span>
                    <span className="rounded bg-violet-100 text-violet-800 text-[10px] font-mono font-bold px-2.5 py-0.5 border border-violet-200">
                      POLICY ADJUSTMENT
                    </span>
                  </div>
                  <p className={`text-xs ${scenarioMode === "quality_tradeoff" ? "text-neutral-300" : "text-neutral-500"}`}>
                    User budget is ₹50,000. AI identifies higher-tier display delivering 100% AdobeRGB + 120Hz at ₹52,000 (+₹2,000). Triggers interactive pop-up box with options to approve quality upgrade or enforce strict ceiling.
                  </p>
                </button>
              </div>
            </div>

            {/* 4. Live LLM Routing Visualizer Card (User Request: "also add llm routing to all other stuff") */}
            <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm space-y-4 font-sans text-xs">
              <div className="flex items-center justify-between pb-3 border-b border-neutral-100">
                <div className="flex items-center space-x-2.5">
                  <div className="p-2 rounded-xl bg-violet-50 text-violet-700 border border-violet-200">
                    <Cpu className="h-4 w-4" />
                  </div>
                  <div>
                    <h3 className="font-bold text-sm text-neutral-900">
                      Advisory LLM Intent Routing &amp; Schema Extraction
                    </h3>
                    <span className="text-[11px] text-neutral-500 font-mono">
                      Model: llama-3.3-70b-versatile (Groq Cloud) · Zero Financial Authority
                    </span>
                  </div>
                </div>
                <span className="rounded-full bg-violet-100 text-violet-800 border border-violet-200 px-2.5 py-0.5 text-[10px] font-mono font-bold">
                  ADVISORY ONLY
                </span>
              </div>

              {/* Visual Routing Path */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-1">
                <div className="rounded-xl bg-neutral-50 p-3.5 border border-neutral-200 space-y-1.5">
                  <span className="text-[10px] font-mono uppercase font-bold text-neutral-400 block">
                    Step 1: User Natural Language
                  </span>
                  <p className="text-neutral-800 font-medium line-clamp-3 text-xs italic">
                    &quot;{customPrompt}&quot;
                  </p>
                </div>

                <div className="rounded-xl bg-violet-50/60 p-3.5 border border-violet-200 space-y-1.5">
                  <span className="text-[10px] font-mono uppercase font-bold text-violet-700 block">
                    Step 2: Groq Routing Parser
                  </span>
                  <div className="font-mono text-[10px] text-neutral-700 space-y-0.5">
                    <div>intent_type: HARDWARE_PURCHASE</div>
                    <div>max_ceiling: {formatMoney(authorizedMax)}</div>
                    <div>semantic_tag: AUTHENTIC_NEW</div>
                  </div>
                </div>

                <div className="rounded-xl bg-emerald-50/60 p-3.5 border border-emerald-200 space-y-1.5">
                  <span className="text-[10px] font-mono uppercase font-bold text-emerald-700 block">
                    Step 3: Deterministic Gate
                  </span>
                  <div className="font-mono text-[10px] text-emerald-800 space-y-0.5">
                    <div>financial_authority: STRICT_ZERO</div>
                    <div>evaluator: T04_INTEGER_ENGINE</div>
                    <div>settlement: REQUIRES_AUDIT</div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Right Col: Order Summary & Checkout Trigger */}
          <div className="space-y-4">
            <span className="text-xs font-mono font-bold uppercase tracking-wider text-neutral-400 block">
              3. Order Contract Summary
            </span>

            <div className="rounded-3xl border border-neutral-200 bg-white p-7 shadow-xl space-y-6 text-sm">
              <div className="space-y-2 pb-4 border-b border-neutral-100">
                <span className="text-[10px] font-mono font-bold text-neutral-400 uppercase">
                  Item Selected
                </span>
                <h4 className="font-bold text-neutral-900 text-base">{effectiveTitle}</h4>
                <div className="flex items-center justify-between text-neutral-500 font-mono text-xs pt-1">
                  <span>Contract SKU:</span>
                  <span className="font-bold text-neutral-800">{effectiveSku}</span>
                </div>
              </div>

              {/* Economic Ceiling Comparison */}
              <div className="space-y-3">
                <div className="flex items-center justify-between text-neutral-600">
                  <span>User Authorized Ceiling:</span>
                  <span className="font-mono font-bold text-neutral-900 text-base">
                    {formatMoney(authorizedMax)}
                  </span>
                </div>

                <div className="flex items-center justify-between text-neutral-600">
                  <span>Merchant Checkout Cart:</span>
                  <span
                    className={`font-mono font-bold text-base ${
                      checkoutPrice.amount > authorizedMax.amount
                        ? "text-rose-600"
                        : "text-neutral-900"
                    }`}
                  >
                    {formatMoney(checkoutPrice)}
                  </span>
                </div>

                {checkoutPrice.amount > authorizedMax.amount && (
                  <div className="flex items-center justify-between text-rose-600 font-mono text-xs pt-1 bg-rose-50 p-2.5 rounded-xl border border-rose-200">
                    <span className="font-semibold">Detected Drift Variance:</span>
                    <span className="font-bold">
                      + {formatMoney({ amount: checkoutPrice.amount - authorizedMax.amount, currency: "INR" })}
                    </span>
                  </div>
                )}
              </div>

              <div className="rounded-2xl bg-neutral-50 p-3.5 text-xs text-neutral-600 space-y-1.5 border border-neutral-200">
                <span className="font-bold text-neutral-900 block">Target Gateway:</span>
                <p>Razorpay Gateway Test Mode · Server-Side Verification Active</p>
                <div className="flex items-center gap-2 pt-1 font-mono text-[11px] text-neutral-500">
                  <span className="h-2 w-2 rounded-full bg-emerald-500" />
                  <span>Integer paise minor units strictly enforced</span>
                </div>
              </div>

              {/* Place Order & Open Razorpay Button */}
              <button
                onClick={handleStartCheckout}
                className="w-full rounded-2xl bg-neutral-900 hover:bg-neutral-800 text-white py-4 text-xs uppercase font-bold tracking-wider flex items-center justify-center space-x-2 shadow-lg active:scale-[0.98] transition"
              >
                <span>Proceed to Razorpay Checkout</span>
                <ArrowRight className="h-4 w-4" />
              </button>

              {/* Presentation Cue note */}
              <p className="text-[11px] text-neutral-400 text-center font-mono leading-tight">
                Clicking opens authentic Razorpay modal → simulates capture → streams 8-stage verification
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Razorpay Test Mode Checkout Modal */}
      <RazorpayModal
        isOpen={isRazorpayModalOpen}
        onClose={() => setIsRazorpayModalOpen(false)}
        orderId={`order_rzp_${Math.random().toString(36).substring(2, 8)}`}
        itemTitle={effectiveTitle}
        amount={checkoutPrice}
        onPaymentSuccess={handlePaymentSuccess}
      />

      {/* Canonical E6 Hero Journey Visual Explainer Modal */}
      <E6ExplainerModal
        isOpen={isE6ModalOpen}
        onClose={() => setIsE6ModalOpen(false)}
        onConfirmRun={() => {
          setIsE6ModalOpen(false);
          setScenarioMode("surge_drift");
          handleStartCheckout();
        }}
        onRunInSimulator={() => {
          setIsE6ModalOpen(false);
          setScenarioMode("surge_drift");
        }}
      />
    </div>
  );
};
