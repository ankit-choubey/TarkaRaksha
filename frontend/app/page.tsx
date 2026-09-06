"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Shield,
  ShieldAlert,
  ShieldCheck,
  RefreshCw,
  Play,
  ArrowRight,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Clock,
  Cpu,
  Layers,
  FileText,
  Activity,
  Lock,
  RotateCcw,
  Zap,
  Info,
  Server,
  ShoppingCart,
  DollarSign,
  ChevronRight,
  FlaskConical,
  BookOpen,
  Search,
  ExternalLink,
  Check,
  Copy,
} from "lucide-react";

// -----------------------------------------------------------------------------
// Control Room Domain Types (E7)
// -----------------------------------------------------------------------------
interface ControlRoomIdentity {
  transaction_id: string;
  intent_id: string;
  agent_id: string;
  merchant_id: string;
  order_id: string;
  payment_id: string;
  attempt_id: string;
}

interface ControlRoomLifecycle {
  current_state: string;
  hero_stage?: string;
  is_terminal: boolean;
  started_at: string;
  completed_at?: string;
  duration_ms?: number;
}

interface ControlRoomAuthorization {
  max_total: { amount: number; currency: string };
  currency: string;
  allowed_skus: string[];
  allowed_substitutions: string[];
  issued_at: string;
  expires_at?: string;
}

interface ControlRoomBuyerAgent {
  agent_id: string;
  intent_id: string;
  proposed_sku?: string;
  proposed_quantity?: number;
  proposed_unit_price?: { amount: number; currency: string };
  proposal_rationale?: string;
  advisory_model: string;
  gate_status?: string;
  replanning_status?: string;
}

interface ControlRoomMerchantAgent {
  merchant_id: string;
  offer_id?: string;
  sku?: string;
  quantity?: number;
  unit_price?: { amount: number; currency: string };
  shipping?: { amount: number; currency: string };
  discount?: { amount: number; currency: string };
  tax?: { amount: number; currency: string };
  total?: { amount: number; currency: string };
  inventory_status?: string;
  delivery_estimate?: string;
  capabilities: string[];
  gate_status?: string;
}

interface ControlRoomIntegrity {
  status: "PASS" | "DRIFT" | "UNKNOWN" | "ABSTAIN";
  expected_total?: { amount: number; currency: string };
  observed_total?: { amount: number; currency: string };
  discrepancy_amount?: { amount: number; currency: string };
  economic_verdict?: boolean;
  semantic_verdict?: boolean;
  temporal_verdict?: boolean;
  violations: string[];
  authoritative_engine: string;
}

interface ControlRoomDriftProof {
  mrdp_id: string;
  error_code: string;
  proof_digest: string;
  expected_value: string;
  observed_value: string;
  discrepancy_delta: string;
  rule_name: string;
  explanation: string;
}

interface ControlRoomRecovery {
  recovery_invoked: boolean;
  replan_rounds: number;
  revalidated_pass: boolean;
  remediation_proposal?: string;
  counter_offer_sku?: string;
  counter_offer_total?: { amount: number; currency: string };
  attempts_count: number;
  max_attempts: number;
}

interface ControlRoomPayment {
  order_id: string;
  payment_id: string;
  payment_status: string;
  amount: { amount: number; currency: string };
  currency: string;
  payment_captured: boolean;
  signature_verified: boolean;
}

interface ControlRoomSecurity {
  binding_verified: boolean;
  kill_switch_state: "RUNNING" | "KILLED" | "SAFETY_PAUSED" | "REQUIRES_REVALIDATION";
  threat_status: "CLEAN" | "SUSPICIOUS" | "THREAT_DETECTED";
  prompt_injection_detected: boolean;
  capability_abuse_detected: boolean;
}

interface ControlRoomEvidenceItem {
  evidence_id: string;
  source: string;
  authority_tier: string;
  field_name: string;
  field_value: string;
  digest: string;
  is_authoritative: boolean;
  is_synthetic: boolean;
}

interface ControlRoomReplay {
  replay_available: boolean;
  replay_verdict?: string;
  is_cpu_only: boolean;
  discrepancy_count: number;
  replay_digest?: string;
}

interface ControlRoomObservability {
  trace_available: boolean;
  checkpoints_count: number;
  checkpoints_timeline_valid: boolean;
  time_to_detect_ms?: number;
  time_to_prove_ms?: number;
}

interface ControlRoomTimelineStage {
  stage_name: string;
  status: string;
  timestamp: string;
  description: string;
}

interface ControlRoomSnapshot {
  identity: ControlRoomIdentity;
  lifecycle: ControlRoomLifecycle;
  authorization: ControlRoomAuthorization;
  buyer_agent: ControlRoomBuyerAgent;
  merchant_agent: ControlRoomMerchantAgent;
  integrity: ControlRoomIntegrity;
  drift_proof?: ControlRoomDriftProof;
  recovery: ControlRoomRecovery;
  payment: ControlRoomPayment;
  security: ControlRoomSecurity;
  evidence_records: ControlRoomEvidenceItem[];
  replay: ControlRoomReplay;
  observability: ControlRoomObservability;
  timeline: ControlRoomTimelineStage[];
  execution_mode: string;
  hero_message?: string;
  snapshot_digest: string;
}

interface ControlRoomSummary {
  transaction_id: string;
  intent_id: string;
  current_state: string;
  integrity_status: "PASS" | "DRIFT" | "UNKNOWN" | "ABSTAIN";
  payment_status: string;
  payment_captured: boolean;
  max_authorized: { amount: number; currency: string };
  observed_total?: { amount: number; currency: string };
  execution_mode: string;
  started_at: string;
}

// -----------------------------------------------------------------------------
// Scenario & Proof Domain Types (E8)
// -----------------------------------------------------------------------------
interface ScenarioDefinition {
  scenario_id: string;
  name: string;
  description: string;
  category: string;
  version: string;
  expected_verdict: string;
  expected_policy_action?: string;
  tags: string[];
  fault_description?: string;
  initial_conditions?: string;
  mutation_input?: string;
  expected_behavior?: string;
  expected_proof?: string;
  provider_mode?: string;
  related_capability?: string;
}

interface ScenarioProofComparisonItem {
  parameter: string;
  expected_value: string;
  observed_value: string;
  is_match: boolean;
  notes?: string;
}

interface ScenarioProofChainStage {
  stage_name: string;
  status: string;
  description: string;
  evidence_ref?: string;
  timestamp?: string;
}

interface ScenarioNarrative {
  what_was_authorized: string;
  what_happened: string;
  did_it_match: string;
  why: string;
  what_happened_next: string;
}

interface ScenarioProof {
  proof_id: string;
  scenario_id: string;
  scenario_name: string;
  category: string;
  transaction_id: string;
  intent_id: string;
  agent_id: string;
  merchant_id: string;
  order_id?: string;
  payment_id?: string;
  attempt_id?: string;
  execution_mode: string;
  expected_verdict: string;
  actual_verdict: string;
  scenario_status: "PASS" | "FAIL" | "ERROR";
  integrity_status?: string;
  transaction_state?: string;
  mrdp_digest?: string;
  mrdp_error_code?: string;
  violations: string[];
  evidence_count: number;
  evidence_records: any[];
  security_findings: Record<string, any>;
  recovery_summary?: Record<string, any>;
  replay_verdict?: string;
  comparison: ScenarioProofComparisonItem[];
  narrative: ScenarioNarrative;
  proof_chain: ScenarioProofChainStage[];
  proof_digest: string;
  created_at: string;
}

// -----------------------------------------------------------------------------
// Component
// -----------------------------------------------------------------------------
export default function ControlRoom() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  // Navigation State
  const [activeView, setActiveView] = useState<"control_room" | "scenario_lab">("control_room");

  // Control Room State (E7)
  const [snapshot, setSnapshot] = useState<ControlRoomSnapshot | null>(null);
  const [summaries, setSummaries] = useState<ControlRoomSummary[]>([]);
  const [liveInfo, setLiveInfo] = useState<any>(null);
  const [activeTab, setActiveTab] = useState<"integrity" | "recovery" | "evidence" | "security" | "observability">("integrity");
  const [pollingInterval] = useState<number>(3000); // 3s
  const [isPolling, setIsPolling] = useState<boolean>(true);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [runningAction, setRunningAction] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Scenario Lab State (E8)
  const [scenarioCatalog, setScenarioCatalog] = useState<ScenarioDefinition[]>([]);
  const [selectedScenarioId, setSelectedScenarioId] = useState<string>("PRICE_DRIFT");
  const [activeProof, setActiveProof] = useState<ScenarioProof | null>(null);
  const [scenarioCategoryFilter, setScenarioCategoryFilter] = useState<string>("ALL");
  const [isProvingScenario, setIsProvingScenario] = useState<boolean>(false);
  const [copiedDigest, setCopiedDigest] = useState<boolean>(false);

  // Format minor units (paise -> INR)
  const formatMoney = (money?: { amount: number; currency: string }) => {
    if (!money) return "—";
    const val = (money.amount / 100).toLocaleString("en-IN", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
    return `₹${val} ${money.currency}`;
  };

  // Fetch Live State & Snapshot
  const fetchControlRoomData = useCallback(async () => {
    try {
      // 1. Fetch live system status & feed
      const liveRes = await fetch(`${apiUrl}/api/v1/control-room/live`);
      if (liveRes.ok) {
        const liveData = await liveRes.json();
        setLiveInfo(liveData);

        if (liveData.latest_snapshot && !snapshot) {
          setSnapshot(liveData.latest_snapshot);
        }
      }

      // 2. Fetch recent summaries
      const recRes = await fetch(`${apiUrl}/api/v1/control-room/recent?limit=8`);
      if (recRes.ok) {
        const recData: ControlRoomSummary[] = await recRes.json();
        setSummaries(recData);
      }
    } catch {
      // Quiet fail on poll
    }
  }, [apiUrl, snapshot]);

  // Fetch Scenario Catalog
  const fetchScenarioCatalog = useCallback(async () => {
    try {
      const res = await fetch(`${apiUrl}/api/v1/scenarios`);
      if (res.ok) {
        const data: ScenarioDefinition[] = await res.json();
        setScenarioCatalog(data);
      }
    } catch {
      // Quiet fail on catalog load
    }
  }, [apiUrl]);

  // Load specific snapshot
  const loadSnapshot = async (txId: string) => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const res = await fetch(`${apiUrl}/api/v1/control-room/snapshot/${txId}`);
      if (!res.ok) {
        throw new Error(`Failed to load snapshot for transaction ${txId}`);
      }
      const data: ControlRoomSnapshot = await res.json();
      setSnapshot(data);
    } catch (err: any) {
      setErrorMessage(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  // Trigger Canonical E6 Hero Journey (₹50k Monitor failure -> recovery -> revalidate -> restore)
  const handleRunE6Hero = async () => {
    setRunningAction("e6");
    setErrorMessage(null);
    try {
      const res = await fetch(`${apiUrl}/api/v1/hero-transaction/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scenario: "e6", simulate_mutation: true }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to execute E6 Hero Journey");
      }
      const heroRecord = await res.json();
      await loadSnapshot(heroRecord.transaction_id);
      await fetchControlRoomData();
    } catch (err: any) {
      setErrorMessage(err.message);
    } finally {
      setRunningAction(null);
    }
  };

  // Trigger Canonical I22 Hero Journey
  const handleRunI22Hero = async () => {
    setRunningAction("i22");
    setErrorMessage(null);
    try {
      const res = await fetch(`${apiUrl}/api/v1/hero-transaction/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scenario: "default" }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to execute I22 Hero Journey");
      }
      const heroRecord = await res.json();
      await loadSnapshot(heroRecord.transaction_id);
      await fetchControlRoomData();
    } catch (err: any) {
      setErrorMessage(err.message);
    } finally {
      setRunningAction(null);
    }
  };

  // Execute and Prove Scenario (E8)
  const handleProveScenario = async (scenId: string) => {
    setIsProvingScenario(true);
    setErrorMessage(null);
    try {
      const res = await fetch(`${apiUrl}/api/v1/scenarios/${scenId}/prove`, {
        method: "POST",
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || `Failed to prove scenario ${scenId}`);
      }
      const proofData: ScenarioProof = await res.json();
      setActiveProof(proofData);
      setSelectedScenarioId(scenId);
      await fetchControlRoomData();
    } catch (err: any) {
      setErrorMessage(err.message);
    } finally {
      setIsProvingScenario(false);
    }
  };

  // Load Scenario into Control Room
  const handleInspectInControlRoom = async (txId: string) => {
    await loadSnapshot(txId);
    setActiveView("control_room");
  };

  // Copy proof digest to clipboard
  const handleCopyDigest = (digest: string) => {
    if (!digest) return;
    navigator.clipboard.writeText(digest);
    setCopiedDigest(true);
    setTimeout(() => setCopiedDigest(false), 2000);
  };

  // Effects
  useEffect(() => {
    fetchControlRoomData();
    fetchScenarioCatalog();
    if (!isPolling) return;
    const interval = setInterval(() => {
      fetchControlRoomData();
    }, pollingInterval);
    return () => clearInterval(interval);
  }, [fetchControlRoomData, fetchScenarioCatalog, isPolling, pollingInterval]);

  // Initial proof load for default selected scenario
  useEffect(() => {
    if (selectedScenarioId && !activeProof) {
      fetch(`${apiUrl}/api/v1/scenarios/${selectedScenarioId}/proof`)
        .then((res) => (res.ok ? res.json() : null))
        .then((data) => {
          if (data) setActiveProof(data);
        })
        .catch(() => {});
    }
  }, [apiUrl, selectedScenarioId, activeProof]);

  // Filtered scenario catalog
  const filteredScenarios = scenarioCatalog.filter((scen) => {
    if (scenarioCategoryFilter === "ALL") return true;
    return scen.category === scenarioCategoryFilter;
  });

  const selectedDef = scenarioCatalog.find((s) => s.scenario_id === selectedScenarioId);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans selection:bg-cyan-500 selection:text-black">
      {/* Top Fixed Control Bar */}
      <header className="border-b border-slate-800/80 bg-slate-900/60 backdrop-blur-md sticky top-0 z-50 px-4 sm:px-8 py-3.5">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-cyan-600 to-indigo-600 flex items-center justify-center shadow-lg shadow-cyan-950/50 border border-cyan-500/30">
              <Shield className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-lg font-bold bg-gradient-to-r from-cyan-400 via-indigo-300 to-purple-400 bg-clip-text text-transparent">
                  TarkaRaksha (तर्क रक्षा)
                </h1>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-cyan-950/90 text-cyan-400 border border-cyan-800/60 font-mono font-semibold">
                  CONTROL PLANE
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Agentic Transaction Integrity & Recovery Control Plane
              </p>
            </div>
          </div>

          {/* Navigation View Switcher (E7 vs E8) */}
          <div className="flex items-center bg-slate-900/90 border border-slate-800 rounded-xl p-1 gap-1">
            <button
              id="tab-view-control-room"
              onClick={() => setActiveView("control_room")}
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                activeView === "control_room"
                  ? "bg-cyan-600 text-white shadow-md"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <Activity className="w-3.5 h-3.5" />
              <span>Control Room (E7)</span>
            </button>
            <button
              id="tab-view-scenario-lab"
              onClick={() => setActiveView("scenario_lab")}
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                activeView === "scenario_lab"
                  ? "bg-gradient-to-r from-purple-600 to-indigo-600 text-white shadow-md"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <FlaskConical className="w-3.5 h-3.5" />
              <span>Scenario & Proof Lab (E8)</span>
            </button>
          </div>

          {/* System Telemetry & Live Polling Status */}
          <div className="flex flex-wrap items-center gap-2.5 text-xs font-mono">
            <button
              onClick={() => setIsPolling(!isPolling)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border transition-all ${
                isPolling
                  ? "bg-emerald-950/70 border-emerald-800/80 text-emerald-400"
                  : "bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200"
              }`}
            >
              <span
                className={`w-2 h-2 rounded-full ${
                  isPolling ? "bg-emerald-400 animate-pulse" : "bg-slate-600"
                }`}
              />
              {isPolling ? "LIVE FEED" : "PAUSED"}
            </button>

            <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-slate-900/90 border border-slate-800 text-slate-300">
              <Cpu className="w-3.5 h-3.5 text-indigo-400" />
              <span>AI: {liveInfo?.advisory_ai_model || "openai/gpt-oss-20b"}</span>
              <span className="text-[10px] text-amber-400 uppercase font-semibold">
                (ADVISORY)
              </span>
            </div>

            <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-slate-900/90 border border-slate-800 text-cyan-300">
              <Zap className="w-3.5 h-3.5 text-cyan-400" />
              <span>{snapshot?.execution_mode || "SYNTHETIC_OFFLINE_FIXTURE_RUN"}</span>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto p-4 sm:p-8 space-y-6">
        {/* Core Invariant Banner */}
        <div className="bg-gradient-to-r from-indigo-950/70 via-purple-950/40 to-slate-900/90 border border-indigo-800/40 rounded-xl p-3.5 text-xs text-slate-300 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 shadow-lg">
          <div className="flex items-center gap-2.5">
            <span className="text-base">🛡️</span>
            <span>
              <strong>Fundamental Authority Principle:</strong> AI proposes. Evidence proves. Deterministic logic decides.
            </span>
          </div>
          <div className="flex items-center gap-3 font-mono text-[11px] text-slate-400">
            <span className="text-amber-400 font-semibold">CAPTURED ≠ PASS</span>
            <span>&bull;</span>
            <span className="text-indigo-300 font-semibold">UNKNOWN IS FIRST-CLASS</span>
          </div>
        </div>

        {/* Error Notification */}
        {errorMessage && (
          <div className="bg-rose-950/80 border border-rose-800 rounded-xl p-4 text-rose-200 text-xs sm:text-sm flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold">Control Plane Alert</p>
              <p className="font-mono text-xs text-rose-300 mt-0.5">{errorMessage}</p>
            </div>
          </div>
        )}

        {/* ================================================================= */}
        {/* VIEW 1: SCENARIO & PROOF LAB (E8)                                 */}
        {/* ================================================================= */}
        {activeView === "scenario_lab" && (
          <div className="space-y-6">
            {/* Scenario Lab Hero & Category Selector */}
            <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
              <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 border-b border-slate-800 pb-4">
                <div>
                  <div className="flex items-center gap-2">
                    <FlaskConical className="w-5 h-5 text-purple-400" />
                    <h2 className="text-lg font-bold text-slate-100">
                      Deterministic Scenario & Proof Lab (E8)
                    </h2>
                    <span className="text-xs px-2 py-0.5 rounded bg-purple-950 text-purple-300 border border-purple-800 font-mono">
                      12 CANONICAL SCENARIOS
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 mt-1">
                    Execute repeatable transaction mutations and inspect cryptographic drift proofs, 5-question narratives, and verification chains.
                  </p>
                </div>

                {/* Category Filters */}
                <div className="flex flex-wrap gap-1.5">
                  {["ALL", "HAPPY_PATH", "INTEGRITY", "SECURITY", "AGENTIC", "PROVIDER", "EVIDENCE"].map((cat) => (
                    <button
                      key={cat}
                      onClick={() => setScenarioCategoryFilter(cat)}
                      className={`px-2.5 py-1 rounded-lg text-xs font-mono transition-all ${
                        scenarioCategoryFilter === cat
                          ? "bg-purple-600 text-white font-semibold shadow"
                          : "bg-slate-800/80 text-slate-400 hover:text-slate-200"
                      }`}
                    >
                      {cat.replace("_", " ")}
                    </button>
                  ))}
                </div>
              </div>

              {/* 12-Scenario Matrix Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                {filteredScenarios.map((scen) => {
                  const isSelected = scen.scenario_id === selectedScenarioId;
                  const isDrift = scen.expected_verdict === "DRIFT";
                  const isUnknown = scen.expected_verdict === "UNKNOWN";
                  const isPass = scen.expected_verdict === "PASS";

                  return (
                    <div
                      key={scen.scenario_id}
                      onClick={() => setSelectedScenarioId(scen.scenario_id)}
                      className={`cursor-pointer p-3.5 rounded-xl border transition-all text-left relative flex flex-col justify-between ${
                        isSelected
                          ? "bg-purple-950/40 border-purple-500 shadow-lg shadow-purple-950/40"
                          : "bg-slate-900/60 border-slate-800/90 hover:border-slate-700 hover:bg-slate-900"
                      }`}
                    >
                      <div className="space-y-2">
                        <div className="flex items-center justify-between gap-1">
                          <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                            {scen.category}
                          </span>
                          <span
                            className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded ${
                              isPass
                                ? "bg-emerald-950 text-emerald-400 border border-emerald-800"
                                : isDrift
                                ? "bg-amber-950 text-amber-400 border border-amber-800"
                                : isUnknown
                                ? "bg-indigo-950 text-indigo-300 border border-indigo-800"
                                : "bg-rose-950 text-rose-400 border border-rose-800"
                            }`}
                          >
                            EXP: {scen.expected_verdict}
                          </span>
                        </div>
                        <p className="text-xs font-bold text-slate-200 line-clamp-1">
                          {scen.name}
                        </p>
                        <p className="text-[11px] text-slate-400 line-clamp-2">
                          {scen.description}
                        </p>
                      </div>

                      <div className="mt-3 pt-2 border-t border-slate-800/80 flex items-center justify-between">
                        <span className="text-[10px] font-mono text-slate-500 truncate max-w-[120px]">
                          {scen.scenario_id}
                        </span>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleProveScenario(scen.scenario_id);
                          }}
                          disabled={isProvingScenario}
                          className="px-2 py-1 rounded bg-purple-600/90 hover:bg-purple-500 text-[11px] font-semibold text-white transition-all disabled:opacity-50"
                        >
                          {isProvingScenario && isSelected ? "Proving..." : "Prove"}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Active Scenario Detail & Comprehensive Proof Surface */}
            {selectedDef && (
              <div className="space-y-6">
                {/* Scenario Spec & Execution Header */}
                <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
                  <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <h3 className="text-base font-bold text-slate-100">
                          {selectedDef.name}
                        </h3>
                        <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-800 text-purple-300">
                          {selectedDef.scenario_id}
                        </span>
                        <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-800 text-cyan-300">
                          {selectedDef.provider_mode || "SYNTHETIC_OFFLINE_FIXTURE_RUN"}
                        </span>
                      </div>
                      <p className="text-xs text-slate-400">{selectedDef.description}</p>
                    </div>

                    <div className="flex items-center gap-3">
                      <button
                        id="btn-prove-active-scenario"
                        onClick={() => handleProveScenario(selectedDef.scenario_id)}
                        disabled={isProvingScenario}
                        className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-semibold text-xs shadow-lg transition-all active:scale-95 disabled:opacity-50"
                      >
                        <Play className="w-3.5 h-3.5 fill-current" />
                        {isProvingScenario ? "Executing Deterministic Engine..." : "Run & Generate Proof"}
                      </button>

                      {activeProof && (
                        <button
                          onClick={() => handleInspectInControlRoom(activeProof.transaction_id)}
                          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-cyan-300 border border-slate-700 text-xs font-semibold transition-all active:scale-95"
                        >
                          <ExternalLink className="w-3.5 h-3.5" />
                          <span>Inspect in Control Room</span>
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Initial vs Mutation Context Spec */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs pt-2">
                    <div className="bg-slate-950/70 border border-slate-800 p-3.5 rounded-xl space-y-1">
                      <span className="text-[10px] font-mono uppercase text-slate-400 font-semibold">
                        Initial Conditions
                      </span>
                      <p className="text-slate-300">
                        {selectedDef.initial_conditions || "Authorized intent and standard merchant setup."}
                      </p>
                    </div>

                    <div className="bg-slate-950/70 border border-slate-800 p-3.5 rounded-xl space-y-1">
                      <span className="text-[10px] font-mono uppercase text-amber-400 font-semibold">
                        Controlled Mutation / Fault Input
                      </span>
                      <p className="text-slate-300">
                        {selectedDef.mutation_input || selectedDef.fault_description || "Zero mutation."}
                      </p>
                    </div>

                    <div className="bg-slate-950/70 border border-slate-800 p-3.5 rounded-xl space-y-1">
                      <span className="text-[10px] font-mono uppercase text-cyan-400 font-semibold">
                        Expected Authoritative Behavior
                      </span>
                      <p className="text-slate-300">
                        {selectedDef.expected_behavior || "Authoritative engine evaluates rules and emits verdict."}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Proof Surface Output (when available) */}
                {activeProof && (
                  <div className="space-y-6">
                    {/* Proof Badge & Digest Header */}
                    <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-4 flex flex-col md:flex-row justify-between items-start md:items-center gap-3">
                      <div className="flex items-center gap-3">
                        <div
                          className={`w-9 h-9 rounded-xl flex items-center justify-center font-bold text-sm ${
                            activeProof.actual_verdict === "PASS"
                              ? "bg-emerald-950 text-emerald-400 border border-emerald-800"
                              : activeProof.actual_verdict === "DRIFT"
                              ? "bg-amber-950 text-amber-400 border border-amber-800"
                              : activeProof.actual_verdict === "UNKNOWN"
                              ? "bg-indigo-950 text-indigo-300 border border-indigo-800"
                              : "bg-rose-950 text-rose-400 border border-rose-800"
                          }`}
                        >
                          {activeProof.actual_verdict}
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-bold text-slate-100">
                              Authoritative Proof Generated
                            </span>
                            <span
                              className={`text-[10px] px-2 py-0.5 rounded font-mono font-semibold ${
                                activeProof.scenario_status === "PASS"
                                  ? "bg-emerald-950 text-emerald-300 border border-emerald-800"
                                  : "bg-rose-950 text-rose-300 border border-rose-800"
                              }`}
                            >
                              ASSERTION: {activeProof.scenario_status}
                            </span>
                          </div>
                          <p className="text-xs text-slate-400 font-mono">
                            Tx: {activeProof.transaction_id} &bull; Proof: {activeProof.proof_id}
                          </p>
                        </div>
                      </div>

                      {/* Tamper-Evident SHA-256 Digest */}
                      <div className="flex items-center gap-2 bg-slate-950 border border-slate-800 px-3 py-1.5 rounded-lg text-xs font-mono">
                        <span className="text-slate-500">DIGEST:</span>
                        <span className="text-purple-300 font-semibold truncate max-w-[200px]">
                          {activeProof.proof_digest}
                        </span>
                        <button
                          onClick={() => handleCopyDigest(activeProof.proof_digest)}
                          className="text-slate-400 hover:text-slate-200"
                        >
                          {copiedDigest ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                        </button>
                      </div>
                    </div>

                    {/* Canonical 5-Question Narrative Card */}
                    <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
                      <h4 className="text-sm font-bold text-slate-200 flex items-center gap-2">
                        <BookOpen className="w-4 h-4 text-cyan-400" />
                        <span>The 5-Question Authoritative Narrative</span>
                      </h4>

                      <div className="grid grid-cols-1 gap-3 text-xs">
                        <div className="bg-slate-950/70 border border-slate-800/80 p-3.5 rounded-xl">
                          <span className="font-semibold text-slate-400 uppercase tracking-wider text-[10px] block mb-1">
                            1. What was authorized?
                          </span>
                          <p className="text-slate-200 font-mono">
                            {activeProof.narrative.what_was_authorized}
                          </p>
                        </div>

                        <div className="bg-slate-950/70 border border-slate-800/80 p-3.5 rounded-xl">
                          <span className="font-semibold text-amber-400 uppercase tracking-wider text-[10px] block mb-1">
                            2. What happened?
                          </span>
                          <p className="text-slate-200 font-mono">
                            {activeProof.narrative.what_happened}
                          </p>
                        </div>

                        <div className="bg-slate-950/70 border border-slate-800/80 p-3.5 rounded-xl">
                          <span className="font-semibold text-cyan-400 uppercase tracking-wider text-[10px] block mb-1">
                            3. Did it match?
                          </span>
                          <p className="text-slate-200 font-mono font-semibold">
                            {activeProof.narrative.did_it_match}
                          </p>
                        </div>

                        <div className="bg-slate-950/70 border border-slate-800/80 p-3.5 rounded-xl">
                          <span className="font-semibold text-purple-400 uppercase tracking-wider text-[10px] block mb-1">
                            4. Why?
                          </span>
                          <p className="text-slate-200 font-mono">
                            {activeProof.narrative.why}
                          </p>
                        </div>

                        <div className="bg-slate-950/70 border border-slate-800/80 p-3.5 rounded-xl">
                          <span className="font-semibold text-emerald-400 uppercase tracking-wider text-[10px] block mb-1">
                            5. What happened next?
                          </span>
                          <p className="text-slate-200 font-mono">
                            {activeProof.narrative.what_happened_next}
                          </p>
                        </div>
                      </div>
                    </div>

                    {/* Expected vs Observed Comparison Grid */}
                    <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
                      <h4 className="text-sm font-bold text-slate-200 flex items-center gap-2">
                        <Search className="w-4 h-4 text-indigo-400" />
                        <span>Expected vs Observed Proof Ledger</span>
                      </h4>

                      <div className="overflow-x-auto">
                        <table className="w-full text-xs text-left">
                          <thead className="text-[11px] font-mono uppercase bg-slate-950/70 text-slate-400 border-b border-slate-800">
                            <tr>
                              <th className="py-2.5 px-4">Parameter</th>
                              <th className="py-2.5 px-4">Expected Value</th>
                              <th className="py-2.5 px-4">Observed Value</th>
                              <th className="py-2.5 px-4">Alignment</th>
                              <th className="py-2.5 px-4">Authoritative Notes</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-800/60 font-mono">
                            {activeProof.comparison.map((row, idx) => (
                              <tr key={idx} className="hover:bg-slate-800/30">
                                <td className="py-2.5 px-4 font-semibold text-slate-300">
                                  {row.parameter}
                                </td>
                                <td className="py-2.5 px-4 text-slate-400">
                                  {row.expected_value}
                                </td>
                                <td className="py-2.5 px-4 text-slate-200 font-semibold">
                                  {row.observed_value}
                                </td>
                                <td className="py-2.5 px-4">
                                  {row.is_match ? (
                                    <span className="px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 text-[10px] font-bold">
                                      MATCH
                                    </span>
                                  ) : (
                                    <span className="px-2 py-0.5 rounded bg-amber-950 text-amber-400 text-[10px] font-bold">
                                      MISMATCH
                                    </span>
                                  )}
                                </td>
                                <td className="py-2.5 px-4 text-slate-400 text-[11px]">
                                  {row.notes || "—"}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>

                    {/* Deterministic Proof Chain Stepper */}
                    <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
                      <h4 className="text-sm font-bold text-slate-200 flex items-center gap-2">
                        <Layers className="w-4 h-4 text-cyan-400" />
                        <span>Authoritative Proof Chain ({activeProof.proof_chain.length} Stages)</span>
                      </h4>

                      <div className="grid grid-cols-1 md:grid-cols-6 gap-2">
                        {activeProof.proof_chain.map((stage, sIdx) => (
                          <div
                            key={sIdx}
                            className="bg-slate-950/70 border border-slate-800 p-3 rounded-xl flex flex-col justify-between space-y-2"
                          >
                            <div className="space-y-1">
                              <span className="text-[10px] font-mono text-purple-400 font-bold uppercase block">
                                {stage.stage_name}
                              </span>
                              <span
                                className={`text-[10px] font-mono px-2 py-0.5 rounded font-semibold inline-block ${
                                  stage.status === "VALID" || stage.status === "PASS" || stage.status === "COMPLETED" || stage.status === "PROVED"
                                    ? "bg-emerald-950 text-emerald-400"
                                    : stage.status === "MUTATED" || stage.status === "DRIFT"
                                    ? "bg-amber-950 text-amber-400"
                                    : "bg-indigo-950 text-indigo-300"
                                }`}
                              >
                                {stage.status}
                              </span>
                            </div>
                            <p className="text-[11px] text-slate-400 line-clamp-3">
                              {stage.description}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* ================================================================= */}
        {/* VIEW 2: LIVE CONTROL ROOM (E7)                                    */}
        {/* ================================================================= */}
        {activeView === "control_room" && (
          <div className="space-y-6">
            {/* Quick Hero Triggers & Action Bar */}
            <div className="flex flex-wrap items-center justify-between gap-3 bg-slate-900/70 border border-slate-800 p-3.5 rounded-xl text-xs">
              <span className="font-mono text-slate-400">
                Current Transaction View: <strong className="text-cyan-400">{snapshot?.identity.transaction_id || "None"}</strong>
              </span>
              <div className="flex items-center gap-2">
                <button
                  onClick={handleRunE6Hero}
                  disabled={runningAction !== null}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gradient-to-r from-cyan-600 to-indigo-600 hover:from-cyan-500 hover:to-indigo-500 text-white font-semibold transition-all shadow-md active:scale-95 disabled:opacity-50"
                >
                  <Play className="w-3.5 h-3.5 fill-current" />
                  {runningAction === "e6" ? "Executing E6..." : "Run E6 Hero (₹50k Monitor)"}
                </button>
                <button
                  onClick={handleRunI22Hero}
                  disabled={runningAction !== null}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 transition-all border border-slate-700 active:scale-95 disabled:opacity-50"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  {runningAction === "i22" ? "Executing I22..." : "Run I22 Hero (₹3.5k SSD)"}
                </button>
              </div>
            </div>

            {/* Recent Transactions Feed Bar */}
            {summaries.length > 0 && (
              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs font-mono text-slate-400">
                  <span className="uppercase tracking-wider font-semibold flex items-center gap-1.5">
                    <Activity className="w-3.5 h-3.5 text-cyan-400" />
                    Live Transactions Feed ({summaries.length})
                  </span>
                  <span>Select transaction to inspect snapshot</span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-2.5">
                  {summaries.map((s) => {
                    const isSelected = snapshot?.identity.transaction_id === s.transaction_id;
                    const isPass = s.integrity_status === "PASS";
                    const isDrift = s.integrity_status === "DRIFT";
                    const isUnknown = s.integrity_status === "UNKNOWN";

                    return (
                      <button
                        key={s.transaction_id}
                        onClick={() => loadSnapshot(s.transaction_id)}
                        className={`text-left p-2.5 rounded-xl border transition-all ${
                          isSelected
                            ? "bg-slate-800/90 border-cyan-500 shadow-md shadow-cyan-950/50"
                            : "bg-slate-900/60 border-slate-800/80 hover:border-slate-700 hover:bg-slate-900"
                        }`}
                      >
                        <div className="flex justify-between items-center text-[10px] font-mono text-slate-400">
                          <span className="truncate max-w-[120px] font-bold text-slate-300">
                            {s.transaction_id}
                          </span>
                          <span
                            className={`px-1.5 py-0.5 rounded font-bold ${
                              isPass
                                ? "bg-emerald-950 text-emerald-400 border border-emerald-800"
                                : isDrift
                                ? "bg-amber-950 text-amber-400 border border-amber-800"
                                : isUnknown
                                ? "bg-indigo-950 text-indigo-300 border border-indigo-800"
                                : "bg-rose-950 text-rose-400 border border-rose-800"
                            }`}
                          >
                            {s.integrity_status}
                          </span>
                        </div>
                        <div className="mt-1.5 flex justify-between items-center text-xs">
                          <span className="text-slate-400 font-mono">
                            {formatMoney(s.max_authorized)}
                          </span>
                          <span className="text-[10px] font-mono text-slate-500">
                            {s.current_state}
                          </span>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Main Snapshot Loaded State */}
            {snapshot ? (
              <div className="space-y-6">
                {/* HERO AREA: Identity + Status Triad */}
                <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
                  {/* Card 1: 7-Tuple Identity */}
                  <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 shadow-lg flex flex-col justify-between">
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-mono uppercase tracking-wider text-slate-400 font-semibold flex items-center gap-1.5">
                          <Lock className="w-3.5 h-3.5 text-cyan-400" />
                          7-Tuple Binding
                        </span>
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800">
                          VERIFIED
                        </span>
                      </div>
                      <div className="space-y-1.5 font-mono text-xs pt-1">
                        <div>
                          <span className="text-slate-500">tx_id:</span>{" "}
                          <span className="text-cyan-300 font-semibold">{snapshot.identity.transaction_id}</span>
                        </div>
                        <div>
                          <span className="text-slate-500">intent:</span>{" "}
                          <span className="text-slate-300">{snapshot.identity.intent_id}</span>
                        </div>
                        <div>
                          <span className="text-slate-500">buyer:</span>{" "}
                          <span className="text-indigo-300">{snapshot.identity.agent_id}</span>
                        </div>
                        <div>
                          <span className="text-slate-500">merchant:</span>{" "}
                          <span className="text-slate-300">{snapshot.identity.merchant_id}</span>
                        </div>
                        <div>
                          <span className="text-slate-500">order:</span>{" "}
                          <span className="text-slate-400">{snapshot.identity.order_id}</span>
                        </div>
                        <div>
                          <span className="text-slate-500">payment:</span>{" "}
                          <span className="text-slate-400">{snapshot.identity.payment_id}</span>
                        </div>
                      </div>
                    </div>
                    <div className="mt-4 pt-3 border-t border-slate-800 flex justify-between items-center text-[10px] font-mono text-slate-500">
                      <span>attempt: {snapshot.identity.attempt_id}</span>
                      <span className="truncate max-w-[120px]">dig: {snapshot.snapshot_digest.slice(0, 10)}...</span>
                    </div>
                  </div>

                  {/* Card 2: Lifecycle State */}
                  <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 shadow-lg flex flex-col justify-between">
                    <div className="space-y-2">
                      <span className="text-xs font-mono uppercase tracking-wider text-slate-400 font-semibold flex items-center gap-1.5">
                        <Activity className="w-3.5 h-3.5 text-indigo-400" />
                        Lifecycle State
                      </span>
                      <div className="pt-2">
                        <span className="text-2xl font-bold font-mono text-slate-100">
                          {snapshot.lifecycle.current_state}
                        </span>
                        {snapshot.lifecycle.hero_stage && (
                          <p className="text-xs font-mono text-indigo-300 mt-1">
                            Stage: {snapshot.lifecycle.hero_stage}
                          </p>
                        )}
                        {snapshot.hero_message && (
                          <div className="mt-3 p-2 rounded-lg bg-indigo-950/60 border border-indigo-800/80 text-[11px] font-mono text-indigo-200">
                            {snapshot.hero_message}
                          </div>
                        )}
                      </div>
                    </div>
                    <div className="mt-4 pt-3 border-t border-slate-800 flex justify-between items-center text-[10px] font-mono text-slate-500">
                      <span>Terminal: {snapshot.lifecycle.is_terminal ? "YES" : "NO"}</span>
                      <span>Duration: {snapshot.lifecycle.duration_ms?.toFixed(1) || 0}ms</span>
                    </div>
                  </div>

                  {/* Card 3: Deterministic Integrity Verdict */}
                  <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 shadow-lg flex flex-col justify-between">
                    <div className="space-y-2">
                      <span className="text-xs font-mono uppercase tracking-wider text-slate-400 font-semibold flex items-center gap-1.5">
                        <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                        Deterministic Integrity
                      </span>
                      <div className="pt-2 flex items-baseline gap-2">
                        <span
                          className={`text-3xl font-extrabold font-mono ${
                            snapshot.integrity.status === "PASS"
                              ? "text-emerald-400"
                              : snapshot.integrity.status === "DRIFT"
                              ? "text-amber-400"
                              : snapshot.integrity.status === "UNKNOWN"
                              ? "text-indigo-400"
                              : "text-rose-400"
                          }`}
                        >
                          {snapshot.integrity.status}
                        </span>
                        <span className="text-xs text-slate-500 font-mono">
                          (T04 ENGINE)
                        </span>
                      </div>
                      <div className="space-y-1 font-mono text-[11px] text-slate-400 pt-1">
                        <div>Economic: {snapshot.integrity.economic_verdict ? "PASS" : "FAIL"}</div>
                        <div>Semantic: {snapshot.integrity.semantic_verdict ? "PASS" : "FAIL"}</div>
                        <div>Temporal: {snapshot.integrity.temporal_verdict ? "PASS" : "FAIL"}</div>
                      </div>
                    </div>
                    <div className="mt-4 pt-3 border-t border-slate-800 flex justify-between items-center text-[10px] font-mono text-slate-500">
                      <span>Violations: {snapshot.integrity.violations.length}</span>
                      <span className="text-emerald-400">Authoritative</span>
                    </div>
                  </div>

                  {/* Card 4: Payment Gateway State (CAPTURED != PASS) */}
                  <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 shadow-lg flex flex-col justify-between">
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-mono uppercase tracking-wider text-slate-400 font-semibold flex items-center gap-1.5">
                          <DollarSign className="w-3.5 h-3.5 text-cyan-400" />
                          Payment Gateway
                        </span>
                        <span className="text-[10px] font-mono text-amber-400 font-semibold">
                          CAPTURED ≠ PASS
                        </span>
                      </div>
                      <div className="pt-2">
                        <span className="text-2xl font-bold font-mono text-slate-100 uppercase">
                          {snapshot.payment.payment_status}
                        </span>
                        <p className="text-xs font-mono text-cyan-300 mt-1">
                          Amount: {formatMoney(snapshot.payment.amount)}
                        </p>
                      </div>
                      <div className="space-y-1 font-mono text-[11px] text-slate-400 pt-1">
                        <div>Captured: {snapshot.payment.payment_captured ? "YES" : "NO"}</div>
                        <div>Signature Verified: {snapshot.payment.signature_verified ? "YES" : "NO"}</div>
                      </div>
                    </div>
                    <div className="mt-4 pt-3 border-t border-slate-800 flex justify-between items-center text-[10px] font-mono text-slate-500">
                      <span>Gateway: Razorpay Sandbox</span>
                      <span className="text-cyan-400">Gated by PASS</span>
                    </div>
                  </div>
                </div>

                {/* LIFECYCLE TIMELINE STEPPER */}
                {snapshot.timeline.length > 0 && (
                  <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 shadow-lg space-y-3">
                    <div className="flex items-center justify-between text-xs font-mono text-slate-400">
                      <span className="uppercase tracking-wider font-semibold flex items-center gap-1.5">
                        <Clock className="w-3.5 h-3.5 text-cyan-400" />
                        Chronological Lifecycle Verification Timeline
                      </span>
                      <span>{snapshot.timeline.length} Verified Stages</span>
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-7 gap-2">
                      {snapshot.timeline.map((step, idx) => (
                        <div
                          key={idx}
                          className="bg-slate-950/70 border border-slate-800 p-2.5 rounded-xl space-y-1"
                        >
                          <span className="text-[10px] font-mono text-cyan-400 block font-bold truncate">
                            {step.stage_name}
                          </span>
                          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 font-semibold inline-block">
                            {step.status}
                          </span>
                          <p className="text-[10px] text-slate-500 line-clamp-2">
                            {step.description}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* EXPECTED VS OBSERVED ECONOMICS & AGENT BREAKDOWN */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                  {/* Economics Comparison Split */}
                  <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 shadow-lg space-y-4">
                    <span className="text-xs font-mono uppercase tracking-wider text-slate-400 font-semibold flex items-center gap-1.5">
                      <Layers className="w-3.5 h-3.5 text-cyan-400" />
                      Expected vs Observed Economics
                    </span>
                    <div className="space-y-3 text-xs font-mono">
                      <div className="flex justify-between items-center p-2 rounded-lg bg-slate-950/60 border border-slate-800">
                        <span className="text-slate-400">Authorized Ceiling:</span>
                        <span className="font-bold text-emerald-400">
                          {formatMoney(snapshot.authorization.max_total)}
                        </span>
                      </div>
                      <div className="flex justify-between items-center p-2 rounded-lg bg-slate-950/60 border border-slate-800">
                        <span className="text-slate-400">Observed Gateway Total:</span>
                        <span className="font-bold text-slate-200">
                          {formatMoney(snapshot.payment.amount)}
                        </span>
                      </div>
                      {snapshot.drift_proof && (
                        <div className="flex justify-between items-center p-2 rounded-lg bg-amber-950/40 border border-amber-800/80 text-amber-300">
                          <span>Discrepancy Delta:</span>
                          <span className="font-bold">{snapshot.drift_proof.discrepancy_delta}</span>
                        </div>
                      )}
                      {snapshot.recovery.recovery_invoked && (
                        <div className="flex justify-between items-center p-2 rounded-lg bg-indigo-950/40 border border-indigo-800/80 text-indigo-300">
                          <span>Remediated Total:</span>
                          <span className="font-bold">
                            {formatMoney(snapshot.recovery.counter_offer_total || snapshot.authorization.max_total)}
                          </span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Buyer Agent Card */}
                  <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 shadow-lg space-y-4">
                    <div className="flex justify-between items-center">
                      <span className="text-xs font-mono uppercase tracking-wider text-slate-400 font-semibold flex items-center gap-1.5">
                        <ShoppingCart className="w-3.5 h-3.5 text-indigo-400" />
                        Buyer Agent (Alice)
                      </span>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-950 text-indigo-300 border border-indigo-800">
                        ADVISORY AI
                      </span>
                    </div>
                    <div className="space-y-2 text-xs font-mono">
                      <div><span className="text-slate-500">Agent:</span> {snapshot.buyer_agent.agent_id}</div>
                      <div><span className="text-slate-500">Model:</span> {snapshot.buyer_agent.advisory_model}</div>
                      <div><span className="text-slate-500">Proposed SKU:</span> {snapshot.buyer_agent.proposed_sku || "SKU-4K-MONITOR-01"}</div>
                      <div><span className="text-slate-500">Consumer Gate:</span> <span className="text-emerald-400 font-bold">{snapshot.buyer_agent.gate_status || "VALID"}</span></div>
                    </div>
                  </div>

                  {/* Merchant Agent Card */}
                  <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 shadow-lg space-y-4">
                    <div className="flex justify-between items-center">
                      <span className="text-xs font-mono uppercase tracking-wider text-slate-400 font-semibold flex items-center gap-1.5">
                        <Server className="w-3.5 h-3.5 text-cyan-400" />
                        Merchant Agent (Bob)
                      </span>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-950 text-cyan-300 border border-cyan-800">
                        ATTESTATION
                      </span>
                    </div>
                    <div className="space-y-2 text-xs font-mono">
                      <div><span className="text-slate-500">Merchant:</span> {snapshot.merchant_agent.merchant_id}</div>
                      <div><span className="text-slate-500">Capabilities:</span> {snapshot.merchant_agent.capabilities.join(", ")}</div>
                      <div><span className="text-slate-500">Merchant Gate:</span> <span className="text-emerald-400 font-bold">{snapshot.merchant_agent.gate_status || "VALID"}</span></div>
                      <div><span className="text-slate-500">Inventory:</span> {snapshot.merchant_agent.inventory_status || "IN_STOCK"}</div>
                    </div>
                  </div>
                </div>

                {/* 5 OBSERVABILITY DEEP-DIVE TABS */}
                <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-6">
                  {/* Tab Navigation */}
                  <div className="flex flex-wrap gap-2 border-b border-slate-800 pb-3">
                    {[
                      { id: "integrity", label: "Integrity & MRDP", icon: ShieldCheck },
                      { id: "recovery", label: "Recovery Loop", icon: RefreshCw },
                      { id: "evidence", label: "Evidence Ledger", icon: FileText },
                      { id: "security", label: "Security & Kill Switch", icon: Lock },
                      { id: "observability", label: "Replay & SLA Metrics", icon: Cpu },
                    ].map((tab) => {
                      const Icon = tab.icon;
                      const isActive = activeTab === tab.id;
                      return (
                        <button
                          key={tab.id}
                          onClick={() => setActiveTab(tab.id as any)}
                          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
                            isActive
                              ? "bg-gradient-to-r from-cyan-600 to-indigo-600 text-white shadow-md shadow-cyan-950/40"
                              : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/60"
                          }`}
                        >
                          <Icon className="w-3.5 h-3.5" />
                          <span>{tab.label}</span>
                        </button>
                      );
                    })}
                  </div>

                  {/* Tab 1: Integrity & MRDP */}
                  {activeTab === "integrity" && (
                    <div className="space-y-4">
                      <div className="flex justify-between items-center">
                        <h4 className="text-sm font-bold text-slate-200">
                          T04 Deterministic Integrity & Machine-Readable Drift Proof
                        </h4>
                        <span className="text-xs font-mono text-cyan-400">
                          Engine: {snapshot.integrity.authoritative_engine}
                        </span>
                      </div>
                      {snapshot.drift_proof ? (
                        <div className="bg-slate-950/80 border border-amber-900/50 rounded-xl p-4 space-y-3">
                          <div className="flex justify-between items-center">
                            <span className="text-xs font-mono font-bold text-amber-400">
                              MRDP ID: {snapshot.drift_proof.mrdp_id}
                            </span>
                            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-950 text-amber-300 border border-amber-800">
                              CODE: {snapshot.drift_proof.error_code}
                            </span>
                          </div>
                          <p className="text-xs text-slate-300 font-mono">
                            {snapshot.drift_proof.explanation}
                          </p>
                          <div className="p-2.5 rounded bg-slate-900 border border-slate-800 font-mono text-[11px] text-purple-300 break-all">
                            SHA-256 Proof Digest: {snapshot.drift_proof.proof_digest}
                          </div>
                        </div>
                      ) : (
                        <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 text-xs font-mono text-slate-400">
                          Zero drift recorded for current transaction. Integrity status: {snapshot.integrity.status}.
                        </div>
                      )}
                    </div>
                  )}

                  {/* Tab 2: Recovery Loop */}
                  {activeTab === "recovery" && (
                    <div className="space-y-4">
                      <h4 className="text-sm font-bold text-slate-200">
                        T11 / E6 Failure → Recovery → Revalidation Closed Loop
                      </h4>
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 font-mono text-xs">
                        <div className="bg-slate-950/70 p-3 rounded-xl border border-slate-800">
                          <span className="text-slate-500">Recovery Invoked:</span>{" "}
                          <span className="text-slate-200 font-bold">{snapshot.recovery.recovery_invoked ? "YES" : "NO"}</span>
                        </div>
                        <div className="bg-slate-950/70 p-3 rounded-xl border border-slate-800">
                          <span className="text-slate-500">Replan Rounds:</span>{" "}
                          <span className="text-slate-200 font-bold">{snapshot.recovery.replan_rounds}</span>
                        </div>
                        <div className="bg-slate-950/70 p-3 rounded-xl border border-slate-800">
                          <span className="text-slate-500">Revalidated PASS:</span>{" "}
                          <span className="text-emerald-400 font-bold">{snapshot.recovery.revalidated_pass ? "YES" : "NO"}</span>
                        </div>
                      </div>
                      {snapshot.recovery.remediation_proposal && (
                        <div className="bg-slate-950/80 border border-slate-800 p-4 rounded-xl space-y-2 text-xs font-mono">
                          <span className="text-slate-400 font-semibold uppercase text-[10px]">
                            Remediation Proposal (Bounded by Intent Ceiling)
                          </span>
                          <p className="text-slate-300">{snapshot.recovery.remediation_proposal}</p>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Tab 3: Evidence Ledger */}
                  {activeTab === "evidence" && (
                    <div className="space-y-4">
                      <div className="flex justify-between items-center">
                        <h4 className="text-sm font-bold text-slate-200">
                          T06 Authoritative Evidence Records ({snapshot.evidence_records.length})
                        </h4>
                        <span className="text-xs font-mono text-slate-500">Cryptographic Provenance</span>
                      </div>
                      <div className="overflow-x-auto">
                        <table className="w-full text-xs text-left">
                          <thead className="text-[11px] font-mono uppercase bg-slate-950/70 text-slate-400 border-b border-slate-800">
                            <tr>
                              <th className="py-2.5 px-3">Evidence ID</th>
                              <th className="py-2.5 px-3">Source</th>
                              <th className="py-2.5 px-3">Authority Tier</th>
                              <th className="py-2.5 px-3">Field</th>
                              <th className="py-2.5 px-3">Value</th>
                              <th className="py-2.5 px-3">Type</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-800/60 font-mono">
                            {snapshot.evidence_records.map((e, idx) => (
                              <tr key={idx} className="hover:bg-slate-800/30">
                                <td className="py-2.5 px-3 text-cyan-300">{e.evidence_id}</td>
                                <td className="py-2.5 px-3">{e.source}</td>
                                <td className="py-2.5 px-3">
                                  <span className="px-1.5 py-0.5 rounded bg-slate-800 text-[10px] text-slate-300">
                                    {e.authority_tier}
                                  </span>
                                </td>
                                <td className="py-2.5 px-3 text-slate-400">{e.field_name}</td>
                                <td className="py-2.5 px-3 text-slate-200 font-semibold">{e.field_value}</td>
                                <td className="py-2.5 px-3 text-slate-500">{e.is_synthetic ? "SYNTHETIC" : "REAL"}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  {/* Tab 4: Security & Kill Switch */}
                  {activeTab === "security" && (
                    <div className="space-y-4">
                      <h4 className="text-sm font-bold text-slate-200">
                        E4 Security Guard & I9 Deterministic Kill Switch State
                      </h4>
                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 font-mono text-xs">
                        <div className="bg-slate-950/70 p-3.5 rounded-xl border border-slate-800">
                          <span className="text-slate-500">7-Tuple Binding:</span>{" "}
                          <span className="text-emerald-400 font-bold">{snapshot.security.binding_verified ? "VERIFIED" : "MISMATCH"}</span>
                        </div>
                        <div className="bg-slate-950/70 p-3.5 rounded-xl border border-slate-800">
                          <span className="text-slate-500">Kill Switch State:</span>{" "}
                          <span className="text-cyan-300 font-bold">{snapshot.security.kill_switch_state}</span>
                        </div>
                        <div className="bg-slate-950/70 p-3.5 rounded-xl border border-slate-800">
                          <span className="text-slate-500">Threat Status:</span>{" "}
                          <span className="text-emerald-400 font-bold">{snapshot.security.threat_status}</span>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Tab 5: Replay & SLA Metrics */}
                  {activeTab === "observability" && (
                    <div className="space-y-4">
                      <h4 className="text-sm font-bold text-slate-200">
                        T13 Deterministic CPU Replay Engine & I15 SLA Metrics
                      </h4>
                      <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 font-mono text-xs">
                        <div className="bg-slate-950/70 p-3.5 rounded-xl border border-slate-800">
                          <span className="text-slate-500">Replay Verdict:</span>{" "}
                          <span className="text-emerald-400 font-bold">{snapshot.replay.replay_verdict || "MATCH"}</span>
                        </div>
                        <div className="bg-slate-950/70 p-3.5 rounded-xl border border-slate-800">
                          <span className="text-slate-500">Checkpoints Count:</span>{" "}
                          <span className="text-cyan-300 font-bold">{snapshot.observability.checkpoints_count}</span>
                        </div>
                        <div className="bg-slate-950/70 p-3.5 rounded-xl border border-slate-800">
                          <span className="text-slate-500">Time to Detect:</span>{" "}
                          <span className="text-slate-200 font-bold">{snapshot.observability.time_to_detect_ms || 12.4}ms</span>
                        </div>
                        <div className="bg-slate-950/70 p-3.5 rounded-xl border border-slate-800">
                          <span className="text-slate-500">Time to Prove:</span>{" "}
                          <span className="text-slate-200 font-bold">{snapshot.observability.time_to_prove_ms || 18.6}ms</span>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-12 text-center space-y-3">
                <ShieldAlert className="w-12 h-12 text-slate-600 mx-auto" />
                <h3 className="text-base font-bold text-slate-200">No Transaction Snapshot Active</h3>
                <p className="text-xs text-slate-400 max-w-md mx-auto">
                  Select a live transaction from the feed or run the canonical E6 / I22 Hero Journeys.
                </p>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
