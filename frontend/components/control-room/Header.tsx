"use client";

import React, { useState } from "react";
import {
  Shield,
  Layers,
  FlaskConical,
  Play,
  RotateCw,
  ExternalLink,
  Zap,
  Radio,
  Cpu,
  ShoppingCart,
  Activity,
  User,
  Menu,
  X,
  HelpCircle,
} from "lucide-react";
import { E6ExplainerModal } from "./drawers/E6ExplainerModal";

export type AppView = "landing" | "order_simulator" | "analytics" | "control_room" | "login";

interface HeaderProps {
  currentView: AppView;
  onSwitchView: (view: AppView) => void;
  onOpenScenarioModal: () => void;
  onRunHeroJourney: () => void;
  isRunningHero: boolean;
  isBackendConnected: boolean;
  executionMode: string;
  advisoryModel?: string;
  isAuthenticated?: boolean;
  userRole?: string;
  onSignOut?: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  currentView,
  onSwitchView,
  onOpenScenarioModal,
  onRunHeroJourney,
  isRunningHero,
  isBackendConnected,
  executionMode,
  advisoryModel = "llama-3.3-70b-versatile (Groq)",
  isAuthenticated = false,
  userRole = "Auditor",
  onSignOut,
}) => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [isE6ModalOpen, setIsE6ModalOpen] = useState(false);

  const navItems: { id: AppView; label: string; icon?: React.ComponentType<{ className?: string }> }[] = [
    { id: "landing", label: "Home" },
    { id: "order_simulator", label: "Order & Razorpay", icon: ShoppingCart },
    { id: "analytics", label: "Analytics & Claims", icon: Activity },
    { id: "control_room", label: "Control Room", icon: Layers },
  ];

  return (
    <header className="sticky top-0 z-40 w-full border-b border-neutral-200/80 bg-white/95 backdrop-blur-md transition-colors font-sans">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Brand identity */}
        <div className="flex items-center space-x-3">
          <button
            onClick={() => onSwitchView("landing")}
            className="flex items-center space-x-2.5 text-left group"
          >
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-neutral-900 text-white shadow-sm ring-1 ring-neutral-800 group-hover:scale-105 transition-transform">
              <Shield className="h-5 w-5 text-emerald-400" />
            </div>
            <div>
              <div className="flex items-center space-x-1.5">
                <span className="font-bold tracking-tight text-neutral-900 text-base">
                  TarkaRaksha
                </span>
                <span className="rounded-full bg-neutral-100 px-1.5 py-0.2 text-[9px] font-mono font-bold text-neutral-600 border border-neutral-200 uppercase">
                  Control Plane
                </span>
              </div>
              <p className="text-[10px] text-neutral-500 font-medium tracking-tight">
                Agentic Transaction Integrity &amp; Recovery
              </p>
            </div>
          </button>
        </div>

        {/* Desktop Navigation Links (saas-kit style with boosted typography) */}
        <nav className="hidden lg:flex items-center space-x-1.5">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentView === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onSwitchView(item.id)}
                className={`rounded-xl px-3.5 py-2 text-sm font-semibold flex items-center space-x-2 transition-all ${
                  isActive
                    ? "bg-neutral-900 text-white shadow-sm"
                    : "text-neutral-600 hover:text-neutral-900 hover:bg-neutral-100"
                }`}
              >
                {Icon && <Icon className={`h-4 w-4 ${isActive ? "text-white" : "text-neutral-500"}`} />}
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        {/* Environment State Badges (Desktop) */}
        <div className="hidden xl:flex items-center space-x-2 text-xs font-mono">
          <div className="flex items-center space-x-1 rounded-full bg-blue-50 px-3 py-1 text-blue-700 border border-blue-200 text-xs">
            <Radio className="h-3.5 w-3.5 animate-pulse text-blue-600" />
            <span>{executionMode.includes("RAZORPAY") ? "Razorpay Test" : "Sim Mode"}</span>
          </div>

          <div
            className={`flex items-center space-x-1.5 rounded-full px-3 py-1 text-xs border ${
              isBackendConnected
                ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                : "bg-amber-50 text-amber-700 border-amber-200"
            }`}
          >
            <span
              className={`h-2 w-2 rounded-full ${
                isBackendConnected ? "bg-emerald-500 animate-ping" : "bg-amber-500"
              }`}
            />
            <span>{isBackendConnected ? "API 8000 Live" : "Offline"}</span>
          </div>
        </div>

        {/* Action buttons & Login */}
        <div className="flex items-center space-x-2.5">
          {/* Quick Scenario Lab trigger */}
          <button
            onClick={onOpenScenarioModal}
            className="hidden sm:inline-flex items-center space-x-1.5 rounded-full bg-white px-3.5 py-1.5 text-xs font-medium text-neutral-700 border border-neutral-300 hover:bg-neutral-50 active:scale-[0.98] transition shadow-2xs"
          >
            <FlaskConical className="h-3.5 w-3.5 text-indigo-600" />
            <span>12 Scenarios</span>
          </button>

          {/* Quick Hero Run trigger with Explainer */}
          <div className="hidden sm:inline-flex items-center rounded-full bg-neutral-900 text-white shadow-sm">
            <button
              onClick={() => setIsE6ModalOpen(true)}
              disabled={isRunningHero}
              className="px-3.5 py-1.5 text-xs font-medium hover:bg-neutral-800 transition flex items-center space-x-1.5 rounded-l-full disabled:opacity-50"
              title="View what E6 does and execute it"
            >
              <Play className={`h-3 w-3 ${isRunningHero ? "animate-spin" : ""}`} />
              <span>{isRunningHero ? "Running..." : "Run E6 Drift"}</span>
            </button>
            <button
              onClick={() => setIsE6ModalOpen(true)}
              className="px-2 py-1.5 text-neutral-400 hover:text-white border-l border-neutral-700 rounded-r-full text-[11px] hover:bg-neutral-800 transition"
              title="What is E6? (Click for full breakdown)"
            >
              <HelpCircle className="h-3.5 w-3.5" />
            </button>
          </div>

          {/* User Auth Session Pill / Login Button */}
          {isAuthenticated ? (
            <div className="flex items-center space-x-2">
              <span className="inline-flex items-center space-x-1.5 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-300 px-3 py-1 text-xs font-mono font-bold">
                <Shield className="h-3.5 w-3.5 text-emerald-600" />
                <span>{userRole}</span>
              </span>
              {onSignOut && (
                <button
                  onClick={onSignOut}
                  className="rounded-full px-2.5 py-1 text-xs text-neutral-500 hover:text-neutral-900 transition"
                  title="Sign out of control plane"
                >
                  Sign Out
                </button>
              )}
            </div>
          ) : (
            <button
              onClick={() => onSwitchView("login")}
              className={`rounded-full px-4 py-1.5 text-xs font-bold flex items-center space-x-1.5 transition ${
                currentView === "login"
                  ? "bg-neutral-900 text-white shadow-sm"
                  : "bg-neutral-100 text-neutral-800 hover:bg-neutral-200"
              }`}
            >
              <User className="h-3.5 w-3.5" />
              <span>Sign In</span>
            </button>
          )}

          {/* Mobile Menu Toggle */}
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="p-1.5 rounded-lg border border-neutral-200 text-neutral-700 lg:hidden"
            aria-label="Toggle mobile menu"
          >
            {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </div>

      {/* Mobile Drawer Navigation */}
      {mobileMenuOpen && (
        <div className="lg:hidden border-b border-neutral-200 bg-white p-4 space-y-2 font-sans animate-in slide-in-from-top-2">
          {navItems.map((item) => (
            <button
              key={item.id}
              onClick={() => {
                onSwitchView(item.id);
                setMobileMenuOpen(false);
              }}
              className={`w-full text-left p-2.5 rounded-xl text-xs font-semibold transition ${
                currentView === item.id ? "bg-neutral-900 text-white" : "text-neutral-700 hover:bg-neutral-50"
              }`}
            >
              {item.label}
            </button>
          ))}
          <div className="pt-2 border-t border-neutral-100 flex items-center justify-between text-xs">
            <button
              onClick={() => {
                onOpenScenarioModal();
                setMobileMenuOpen(false);
              }}
              className="text-neutral-600 font-medium"
            >
              🧪 Scenario Lab
            </button>
            <button
              onClick={() => {
                onSwitchView("login");
                setMobileMenuOpen(false);
              }}
              className="text-neutral-900 font-bold"
            >
              Sign In →
            </button>
          </div>
        </div>
      )}
      {/* E6 Explainer Modal */}
      <E6ExplainerModal
        isOpen={isE6ModalOpen}
        onClose={() => setIsE6ModalOpen(false)}
        onConfirmRun={onRunHeroJourney}
        onRunInSimulator={() => onSwitchView("order_simulator")}
        isRunning={isRunningHero}
      />
    </header>
  );
};
