"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { ControlRoomSnapshot, ControlRoomSummary, ScenarioDefinition, DrawerType } from "../lib/types";
import { CANONICAL_E6_SNAPSHOT, INITIAL_RECENT_SUMMARIES, CANONICAL_SCENARIOS } from "../lib/fixtures";

// Control Room Components
import { Header, AppView } from "../components/control-room/Header";
import { AuthorityStrip } from "../components/control-room/AuthorityStrip";
import { TransactionHeader } from "../components/control-room/TransactionHeader";
import { TransactionSpine } from "../components/control-room/TransactionSpine";
import { TruthStatusCard } from "../components/control-room/TruthStatusCard";
import { RealTimeOrderStudio } from "../components/control-room/RealTimeOrderStudio";
import { LiveActivityStream } from "../components/control-room/LiveActivityStream";

// Checkout & Verification Flow
import { OrderPlacementView } from "../components/checkout/OrderPlacementView";

// Analytics & Scenarios
import { AnalyticsPage } from "../components/analytics/AnalyticsPage";

// Auth Login
import { LoginPage } from "../components/auth/LoginPage";

// Drawers
import { AgentDrawer } from "../components/control-room/drawers/AgentDrawer";
import { OfferDrawer } from "../components/control-room/drawers/OfferDrawer";
import { PaymentDrawer } from "../components/control-room/drawers/PaymentDrawer";
import { IntegrityDrawer } from "../components/control-room/drawers/IntegrityDrawer";
import { RecoveryDrawer } from "../components/control-room/drawers/RecoveryDrawer";
import { EvidenceDrawer } from "../components/control-room/drawers/EvidenceDrawer";
import { PassportDrawer } from "../components/control-room/drawers/PassportDrawer";
import { ReplayDrawer } from "../components/control-room/drawers/ReplayDrawer";
import { SecurityDrawer } from "../components/control-room/drawers/SecurityDrawer";
import { ScenarioModal } from "../components/control-room/drawers/ScenarioModal";

// SaaS-Kit Styled Landing Page
import { LandingPage } from "../components/landing/LandingPage";

export default function Home() {
  const rawApiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const apiUrl = rawApiUrl.startsWith("http://") || rawApiUrl.startsWith("https://")
    ? rawApiUrl.replace(/\/$/, "")
    : `https://${rawApiUrl.replace(/\/$/, "")}`;

  // Multi-View Navigation: "landing" | "order_simulator" | "analytics" | "control_room" | "login"
  const [currentView, setCurrentView] = useState<AppView>("landing");

  // Authentication & Role Session Gate
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [userRole, setUserRole] = useState<string>("Auditor");
  const [pendingTargetView, setPendingTargetView] = useState<AppView | null>(null);

  // Active Transaction Snapshot (defaults to Canonical E6 Hero Journey)
  const [snapshot, setSnapshot] = useState<ControlRoomSnapshot>(CANONICAL_E6_SNAPSHOT);
  const [recentSummaries, setRecentSummaries] = useState<ControlRoomSummary[]>(INITIAL_RECENT_SUMMARIES);
  const [scenarios, setScenarios] = useState<ScenarioDefinition[]>(CANONICAL_SCENARIOS);

  // Connection & Activity State
  const [isBackendConnected, setIsBackendConnected] = useState<boolean>(false);
  const [isRunningHero, setIsRunningHero] = useState<boolean>(false);
  const [isProvingScenario, setIsProvingScenario] = useState<boolean>(false);
  const [currentScenarioId, setCurrentScenarioId] = useState<string>("PRICE_DRIFT");

  // Drawer / Sheet Inspection State
  const [activeDrawer, setActiveDrawer] = useState<DrawerType | null>(null);

  // Keep track of latest digest to only trigger re-render on actual state change
  const lastDigestRef = useRef<string>(snapshot.snapshot_digest);

  // Authenticated View Router Guard
  const handleSwitchView = (view: AppView) => {
    if (view === "landing" || view === "login") {
      setCurrentView(view);
      return;
    }
    if (!isAuthenticated) {
      setPendingTargetView(view);
      setCurrentView("login");
      return;
    }
    setCurrentView(view);
  };

  const handleSuccessLogin = (role?: string) => {
    setIsAuthenticated(true);
    if (role) setUserRole(role);
    const destination = pendingTargetView || "order_simulator";
    setPendingTargetView(null);
    setCurrentView(destination);
  };

  const handleSignOut = () => {
    setIsAuthenticated(false);
    setUserRole("Auditor");
    setCurrentView("landing");
  };

  // ---------------------------------------------------------------------------
  // 1. Live State Polling (1.5s interval)
  // ---------------------------------------------------------------------------
  const fetchLiveTelemetry = useCallback(async () => {
    try {
      const res = await fetch(`${apiUrl}/api/v1/control-room/live`, {
        cache: "no-store",
      });
      if (res.ok) {
        const data = await res.json();
        setIsBackendConnected(true);

        if (data.latest_snapshot) {
          const newDigest = data.latest_snapshot.snapshot_digest;
          if (newDigest !== lastDigestRef.current) {
            lastDigestRef.current = newDigest;
            setSnapshot(data.latest_snapshot);
          }
        }

        if (data.recent_summaries && Array.isArray(data.recent_summaries)) {
          setRecentSummaries(data.recent_summaries);
        }
      } else {
        setIsBackendConnected(false);
      }
    } catch {
      setIsBackendConnected(false);
    }
  }, [apiUrl]);

  // Fetch Scenario Catalog
  const fetchScenarios = useCallback(async () => {
    try {
      const res = await fetch(`${apiUrl}/api/v1/scenarios`);
      if (res.ok) {
        const data: ScenarioDefinition[] = await res.json();
        if (data.length > 0) {
          setScenarios(data);
        }
      }
    } catch {
      // Use fixtures if backend offline
    }
  }, [apiUrl]);

  useEffect(() => {
    fetchLiveTelemetry();
    fetchScenarios();

    // Poll live state every 1.5 seconds
    const interval = setInterval(fetchLiveTelemetry, 1500);
    return () => clearInterval(interval);
  }, [fetchLiveTelemetry, fetchScenarios]);

  // ---------------------------------------------------------------------------
  // 2. Select & Load Specific Transaction Snapshot
  // ---------------------------------------------------------------------------
  const handleSelectTransaction = async (txId: string) => {
    try {
      const res = await fetch(`${apiUrl}/api/v1/control-room/snapshot/${txId}`);
      if (res.ok) {
        const snap: ControlRoomSnapshot = await res.json();
        setSnapshot(snap);
        lastDigestRef.current = snap.snapshot_digest;
      }
    } catch {
      // Fallback
    }
  };

  // ---------------------------------------------------------------------------
  // 3. Execute Canonical E6 Hero Journey (₹50k Monitor Checkout Drift)
  // ---------------------------------------------------------------------------
  const handleRunHeroJourney = async () => {
    setIsRunningHero(true);
    try {
      const res = await fetch(`${apiUrl}/api/v1/hero-transaction/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scenario: "e6", simulate_mutation: true }),
      });
      if (res.ok) {
        const heroRecord = await res.json();
        await handleSelectTransaction(heroRecord.transaction_id);
        await fetchLiveTelemetry();
        setCurrentView("control_room");
      }
    } catch (err) {
      console.warn("Backend hero run offline, loading canonical E6 fixture", err);
      setSnapshot(CANONICAL_E6_SNAPSHOT);
      setCurrentView("control_room");
    } finally {
      setIsRunningHero(false);
    }
  };

  // ---------------------------------------------------------------------------
  // 4. Prove & Load Scenario
  // ---------------------------------------------------------------------------
  const handleProveScenario = async (scenarioId: string) => {
    setIsProvingScenario(true);
    setCurrentScenarioId(scenarioId);
    try {
      const res = await fetch(`${apiUrl}/api/v1/scenarios/${scenarioId}/prove`, {
        method: "POST",
      });
      if (res.ok) {
        const proof = await res.json();
        if (proof.transaction_id) {
          await handleSelectTransaction(proof.transaction_id);
        }
        await fetchLiveTelemetry();
        setCurrentView("control_room");
      }
    } catch (err) {
      console.warn("Scenario proof offline, staying on current snapshot", err);
      setCurrentView("control_room");
    } finally {
      setIsProvingScenario(false);
    }
  };

  return (
    <main className="min-h-screen bg-white font-sans text-neutral-900 selection:bg-neutral-900 selection:text-white flex flex-col">
      {/* Universal Top Header (SaaS-Kit Navigation) */}
      <Header
        currentView={currentView}
        onSwitchView={handleSwitchView}
        onOpenScenarioModal={() => setActiveDrawer("scenarios")}
        onRunHeroJourney={handleRunHeroJourney}
        isRunningHero={isRunningHero}
        apiUrl={apiUrl}
        isBackendConnected={isBackendConnected}
        executionMode={snapshot.execution_mode}
        advisoryModel={snapshot.buyer_agent.advisory_model}
        isAuthenticated={isAuthenticated}
        userRole={userRole}
        onSignOut={handleSignOut}
      />

      {/* View 1: SaaS-Kit Styled Landing Page */}
      {currentView === "landing" && (
        <LandingPage
          onEnterControlRoom={() => handleSwitchView("control_room")}
          onNavigateToOrderSimulator={() => handleSwitchView("order_simulator")}
          onNavigateToAnalytics={() => handleSwitchView("analytics")}
          onNavigateToLogin={() => setCurrentView("login")}
          onRunHeroJourney={handleRunHeroJourney}
          isRunningHero={isRunningHero}
          snapshot={snapshot}
          onOpenDrawer={setActiveDrawer}
          onSnapshotUpdated={setSnapshot}
          isBackendConnected={isBackendConnected}
        />
      )}

      {/* View 2: Live Order & Razorpay Checkout Simulator */}
      {currentView === "order_simulator" && (
        <OrderPlacementView
          onOpenDrawer={setActiveDrawer}
          onViewInControlRoom={() => setCurrentView("control_room")}
        />
      )}

      {/* View 3: Analytics, Test Cases & Agent Architecture */}
      {currentView === "analytics" && (
        <AnalyticsPage
          onOpenDrawer={setActiveDrawer}
          onLaunchOrderSimulator={() => setCurrentView("order_simulator")}
        />
      )}

      {/* View 4: Unified Transaction Control Room */}
      {currentView === "control_room" && (
        <div className="flex-1 flex flex-col bg-white">
          {/* Authority Invariant Strip */}
          <AuthorityStrip />

          {/* Transaction Header */}
          <TransactionHeader
            snapshot={snapshot}
            recentSummaries={recentSummaries}
            onSelectTransaction={handleSelectTransaction}
          />

          {/* Transaction Lifecycle Spine */}
          <TransactionSpine
            snapshot={snapshot}
            onOpenDrawer={setActiveDrawer}
            activeDrawer={activeDrawer}
          />

          {/* Authoritative Truth Status Card */}
          <TruthStatusCard
            snapshot={snapshot}
            onOpenDrawer={setActiveDrawer}
          />

          {/* Live System File & Telemetry Activity Stream */}
          <div className="py-6 px-4 sm:px-6 lg:px-8 border-t border-neutral-200/90 bg-neutral-50/30">
            <div className="mx-auto max-w-7xl">
              <LiveActivityStream />
            </div>
          </div>

          {/* Real-Time Interactive Order Studio inside Control Room */}
          <div className="py-6 px-4 sm:px-6 lg:px-8 border-t border-neutral-200/90 bg-neutral-50/50">
            <div className="mx-auto max-w-7xl">
              <RealTimeOrderStudio
                onSnapshotUpdated={setSnapshot}
                onOpenDrawer={setActiveDrawer}
                isBackendConnected={isBackendConnected}
              />
            </div>
          </div>
        </div>
      )}

      {/* View 5: SaaS-Kit Styled Authentication Screen */}
      {currentView === "login" && (
        <LoginPage
          onSuccessLogin={handleSuccessLogin}
          onNavigateHome={() => setCurrentView("landing")}
        />
      )}

      {/* --------------------------------------------------------------------- */}
      {/* DRAWERS & INSPECTION SHEETS                                           */}
      {/* --------------------------------------------------------------------- */}

      {/* 1. Agent Drawer */}
      <AgentDrawer
        isOpen={activeDrawer === "agent"}
        onClose={() => setActiveDrawer(null)}
        snapshot={snapshot}
      />

      {/* 2. Offer Drawer */}
      <OfferDrawer
        isOpen={activeDrawer === "offer"}
        onClose={() => setActiveDrawer(null)}
        snapshot={snapshot}
      />

      {/* 3. Payment Drawer */}
      <PaymentDrawer
        isOpen={activeDrawer === "payment"}
        onClose={() => setActiveDrawer(null)}
        snapshot={snapshot}
      />

      {/* 4. Integrity & MRDP Drawer */}
      <IntegrityDrawer
        isOpen={activeDrawer === "integrity" || activeDrawer === "mrdp"}
        onClose={() => setActiveDrawer(null)}
        snapshot={snapshot}
        initialTab={activeDrawer === "mrdp" ? "mrdp" : "verdict"}
      />

      {/* 5. Recovery Drawer */}
      <RecoveryDrawer
        isOpen={activeDrawer === "recovery"}
        onClose={() => setActiveDrawer(null)}
        snapshot={snapshot}
      />

      {/* 6. Evidence Drawer */}
      <EvidenceDrawer
        isOpen={activeDrawer === "evidence"}
        onClose={() => setActiveDrawer(null)}
        snapshot={snapshot}
      />

      {/* 7. Passport Drawer */}
      <PassportDrawer
        isOpen={activeDrawer === "passport"}
        onClose={() => setActiveDrawer(null)}
        snapshot={snapshot}
      />

      {/* 8. Replay Drawer */}
      <ReplayDrawer
        isOpen={activeDrawer === "replay"}
        onClose={() => setActiveDrawer(null)}
        snapshot={snapshot}
      />

      {/* 9. Security Drawer */}
      <SecurityDrawer
        isOpen={activeDrawer === "security"}
        onClose={() => setActiveDrawer(null)}
        snapshot={snapshot}
      />

      {/* 10. Scenario Lab Launcher Drawer / Modal */}
      <ScenarioModal
        isOpen={activeDrawer === "scenarios"}
        onClose={() => setActiveDrawer(null)}
        scenarios={scenarios}
        onProveScenario={handleProveScenario}
        isProving={isProvingScenario}
        currentScenarioId={currentScenarioId}
      />
    </main>
  );
}
