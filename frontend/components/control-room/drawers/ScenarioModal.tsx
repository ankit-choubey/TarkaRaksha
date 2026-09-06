"use client";

import React, { useState } from "react";
import { DrawerContainer } from "./DrawerContainer";
import { ScenarioDefinition } from "../../../lib/types";
import { CANONICAL_SCENARIOS } from "../../../lib/fixtures";
import { FlaskConical, Play, CheckCircle2, AlertOctagon, HelpCircle, ShieldAlert, Sparkles } from "lucide-react";

interface ScenarioModalProps {
  isOpen: boolean;
  onClose: () => void;
  scenarios: ScenarioDefinition[];
  onProveScenario: (scenarioId: string) => Promise<void>;
  isProving: boolean;
  currentScenarioId?: string;
}

export const ScenarioModal: React.FC<ScenarioModalProps> = ({
  isOpen,
  onClose,
  scenarios,
  onProveScenario,
  isProving,
  currentScenarioId,
}) => {
  const [selectedCategory, setSelectedCategory] = useState<string>("ALL");
  const scenarioList = scenarios.length > 0 ? scenarios : CANONICAL_SCENARIOS;

  const categories = ["ALL", "ECONOMIC", "SEMANTIC", "TEMPORAL", "AUTHORITY", "SECURITY", "BASELINE"];

  const filtered = selectedCategory === "ALL"
    ? scenarioList
    : scenarioList.filter((s) => s.category.toUpperCase() === selectedCategory);

  const getVerdictBadge = (verdict: string) => {
    switch (verdict) {
      case "PASS":
        return "bg-emerald-50 text-emerald-800 border-emerald-200";
      case "DRIFT":
        return "bg-rose-50 text-rose-800 border-rose-200";
      case "UNKNOWN":
        return "bg-amber-50 text-amber-800 border-amber-200";
      default:
        return "bg-neutral-100 text-neutral-800 border-neutral-200";
    }
  };

  return (
    <DrawerContainer
      isOpen={isOpen}
      onClose={onClose}
      title="Scenario Lab & Canonical Proofs (I11 / E8)"
      subtitle="Deterministic catalog of 12 canonical agentic commerce test scenarios"
      badge={`${scenarioList.length} CANONICAL`}
      badgeType="neutral"
    >
      {/* Category Filter Pills */}
      <div className="flex flex-wrap gap-1.5 pb-2 border-b border-neutral-200">
        {categories.map((cat) => (
          <button
            key={cat}
            onClick={() => setSelectedCategory(cat)}
            className={`rounded-full px-2.5 py-1 text-xs font-mono transition ${
              selectedCategory === cat
                ? "bg-neutral-900 text-white font-semibold"
                : "bg-neutral-100 text-neutral-600 hover:bg-neutral-200"
            }`}
          >
            {cat}
          </button>
        ))}
      </div>

      {/* Scenarios Grid */}
      <div className="space-y-3">
        {filtered.map((scen) => (
          <div
            key={scen.scenario_id}
            className={`rounded-xl border p-4 transition-all bg-white hover:border-neutral-400 space-y-2 ${
              currentScenarioId === scen.scenario_id ? "ring-2 ring-neutral-900 border-neutral-900" : "border-neutral-200"
            }`}
          >
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="flex items-center space-x-2">
                  <h4 className="font-bold text-neutral-900 text-sm">{scen.name}</h4>
                  <span className="font-mono text-[10px] text-neutral-400">({scen.scenario_id})</span>
                </div>
                <p className="text-xs text-neutral-500 mt-0.5">{scen.description}</p>
              </div>

              <div className="flex items-center space-x-2 shrink-0">
                <span className={`rounded px-2 py-0.5 font-mono text-[10px] font-bold border ${getVerdictBadge(scen.expected_verdict)}`}>
                  {scen.expected_verdict}
                </span>

                <button
                  onClick={async () => {
                    await onProveScenario(scen.scenario_id);
                    onClose();
                  }}
                  disabled={isProving}
                  className="inline-flex items-center space-x-1 rounded-lg bg-neutral-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-neutral-800 active:scale-[0.98] transition disabled:opacity-50"
                >
                  <Play className={`h-3 w-3 ${isProving ? "animate-spin" : ""}`} />
                  <span>Prove & Load</span>
                </button>
              </div>
            </div>

            {scen.fault_description && (
              <div className="rounded-lg bg-neutral-50 p-2.5 text-neutral-700 text-[11px] font-mono border border-neutral-200">
                <strong className="text-neutral-500">Injected Fault:</strong> {scen.fault_description}
              </div>
            )}
          </div>
        ))}
      </div>
    </DrawerContainer>
  );
};
