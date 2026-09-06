"use client";

import React, { useState } from "react";
import { Shield, Lock, ArrowRight, CheckCircle2, User, Key, Building2 } from "lucide-react";

interface LoginPageProps {
  onSuccessLogin: (role?: string) => void;
  onNavigateHome: () => void;
}

export const LoginPage: React.FC<LoginPageProps> = ({
  onSuccessLogin,
  onNavigateHome,
}) => {
  const [email, setEmail] = useState("auditor.demo@tarkaraksha.io");
  const [password, setPassword] = useState("••••••••••••");
  const [selectedRole, setSelectedRole] = useState<"Auditor" | "Agent Developer" | "Merchant">("Auditor");
  const [isLoggingIn, setIsLoggingIn] = useState<boolean>(false);

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoggingIn(true);
    setTimeout(() => {
      setIsLoggingIn(false);
      onSuccessLogin(selectedRole);
    }, 400);
  };

  const handleQuickDemoLogin = (role: "Auditor" | "Agent Developer" | "Merchant") => {
    setSelectedRole(role);
    setIsLoggingIn(true);
    setTimeout(() => {
      setIsLoggingIn(false);
      onSuccessLogin(role);
    }, 300);
  };

  return (
    <div className="min-h-[82vh] flex items-center justify-center p-4 font-sans text-neutral-900 bg-neutral-50/40">
      <div className="w-full max-w-md rounded-3xl border border-neutral-200 bg-white p-8 shadow-xl space-y-6">
        {/* Brand Header */}
        <div className="text-center space-y-2">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-neutral-900 text-white mx-auto shadow-md">
            <Shield className="h-7 w-7 text-emerald-400" />
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-neutral-900">
            Sign In to TarkaRaksha
          </h1>
          <p className="text-sm text-neutral-600">
            Enterprise authentication required to execute transactions, run live simulators, and view telemetry.
          </p>
        </div>

        {/* 1-Click Presentation Demo Sign-In Card */}
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50/70 p-4 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono font-bold uppercase tracking-wider text-emerald-800 flex items-center gap-1.5">
              <Key className="h-3.5 w-3.5" /> Instant Enterprise Demo Access
            </span>
            <span className="text-[10px] font-mono bg-emerald-200/80 text-emerald-900 px-2 py-0.5 rounded-full font-bold">
              Instant Access
            </span>
          </div>
          <p className="text-xs text-neutral-700">
            Click below to instantly authenticate with pre-verified cryptographic capabilities:
          </p>
          <div className="grid grid-cols-3 gap-2 pt-1">
            <button
              type="button"
              onClick={() => handleQuickDemoLogin("Auditor")}
              className="rounded-xl bg-neutral-900 hover:bg-neutral-800 text-white py-2 text-xs font-bold transition text-center shadow-xs"
            >
              Auditor
            </button>
            <button
              type="button"
              onClick={() => handleQuickDemoLogin("Agent Developer")}
              className="rounded-xl bg-white hover:bg-neutral-100 text-neutral-900 border border-neutral-300 py-2 text-xs font-bold transition text-center"
            >
              Agent Dev
            </button>
            <button
              type="button"
              onClick={() => handleQuickDemoLogin("Merchant")}
              className="rounded-xl bg-white hover:bg-neutral-100 text-neutral-900 border border-neutral-300 py-2 text-xs font-bold transition text-center"
            >
              Merchant
            </button>
          </div>
        </div>

        {/* Or Manual Sign In */}
        <div className="relative flex items-center justify-center">
          <div className="border-t border-neutral-200 w-full" />
          <span className="bg-white px-3 text-xs text-neutral-400 font-mono uppercase tracking-wider">
            Or Standard Form
          </span>
        </div>

        {/* Role Selector Tabs */}
        <div className="flex rounded-xl bg-neutral-100 p-1 text-xs font-medium border border-neutral-200">
          {(["Auditor", "Agent Developer", "Merchant"] as const).map((role) => (
            <button
              key={role}
              type="button"
              onClick={() => setSelectedRole(role)}
              className={`flex-1 py-1.5 rounded-lg transition text-xs ${
                selectedRole === role
                  ? "bg-white text-neutral-900 shadow-2xs font-bold"
                  : "text-neutral-500 hover:text-neutral-900"
              }`}
            >
              {role === "Agent Developer" ? "Agent Dev" : role}
            </button>
          ))}
        </div>

        {/* Form */}
        <form onSubmit={handleLogin} className="space-y-4 text-sm">
          <div>
            <label className="block text-xs font-semibold text-neutral-700 mb-1.5">
              Work Email Address
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full rounded-xl border border-neutral-300 px-3.5 py-2.5 text-sm text-neutral-900 focus:border-neutral-900 focus:outline-none"
            />
          </div>

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="block text-xs font-semibold text-neutral-700">
                Security Key / Password
              </label>
              <a href="#forgot" onClick={(e) => e.preventDefault()} className="text-xs text-neutral-400 hover:underline">
                Demo Auto-fill
              </a>
            </div>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full rounded-xl border border-neutral-300 px-3.5 py-2.5 text-sm text-neutral-900 focus:border-neutral-900 focus:outline-none"
            />
          </div>

          {/* Role Boundary Guarantee */}
          <div className="rounded-xl bg-neutral-50 p-3 border border-neutral-200 text-xs text-neutral-600 leading-relaxed flex items-start space-x-2">
            <Lock className="h-4 w-4 text-neutral-400 shrink-0 mt-0.5" />
            <span>
              Signed sessions enforce cryptographic nonces, stopping unauthorized replays and protecting transaction ceilings.
            </span>
          </div>

          <button
            type="submit"
            disabled={isLoggingIn}
            className="w-full rounded-xl bg-neutral-900 hover:bg-neutral-800 text-white py-3.5 text-xs font-bold uppercase tracking-wider flex items-center justify-center space-x-2 shadow-md active:scale-[0.98] transition disabled:opacity-50"
          >
            {isLoggingIn ? (
              <span>Authenticating Session...</span>
            ) : (
              <>
                <span>Sign In as {selectedRole}</span>
                <ArrowRight className="h-4 w-4" />
              </>
            )}
          </button>
        </form>

        <div className="pt-2 text-center text-xs text-neutral-500">
          <button onClick={onNavigateHome} className="underline text-neutral-700 hover:text-neutral-900">
            ← Return to Landing Page
          </button>
        </div>
      </div>
    </div>
  );
};
