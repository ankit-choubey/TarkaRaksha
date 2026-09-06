// TarkaRaksha Frontend Domain Types (E7 / E8 / T14)

export type IntegrityStatusType = "PASS" | "DRIFT" | "UNKNOWN" | "ABSTAIN";

export interface MoneyValue {
  amount: number; // in minor units (paise)
  currency: string;
}

export interface ControlRoomIdentity {
  transaction_id: string;
  intent_id: string;
  agent_id: string;
  merchant_id: string;
  order_id: string;
  payment_id: string;
  attempt_id: string;
}

export interface ControlRoomLifecycle {
  current_state: string;
  hero_stage?: string;
  is_terminal: boolean;
  started_at: string;
  completed_at?: string;
  duration_ms?: number;
}

export interface ControlRoomAuthorization {
  max_total: MoneyValue;
  currency: string;
  allowed_skus: string[];
  allowed_substitutions: string[];
  issued_at: string;
  expires_at?: string;
}

export interface ControlRoomBuyerAgent {
  agent_id: string;
  intent_id: string;
  proposed_sku?: string;
  proposed_quantity?: number;
  proposed_unit_price?: MoneyValue;
  proposal_rationale?: string;
  advisory_model: string;
  gate_status?: string;
  replanning_status?: string;
}

export interface ControlRoomMerchantAgent {
  merchant_id: string;
  offer_id?: string;
  sku?: string;
  quantity?: number;
  unit_price?: MoneyValue;
  shipping?: MoneyValue;
  discount?: MoneyValue;
  tax?: MoneyValue;
  total?: MoneyValue;
  inventory_status?: string;
  delivery_estimate?: string;
  capabilities: string[];
  gate_status?: string;
}

export interface ControlRoomIntegrity {
  status: IntegrityStatusType;
  expected_total?: MoneyValue;
  observed_total?: MoneyValue;
  discrepancy_amount?: MoneyValue;
  economic_verdict?: boolean;
  semantic_verdict?: boolean;
  temporal_verdict?: boolean;
  violations: string[];
  authoritative_engine: string;
}

export interface ControlRoomDriftProof {
  mrdp_id: string;
  error_code: string;
  drift_source: string;
  expected_value?: any;
  observed_value?: any;
  remediation?: string;
  proof_digest: string;
}

export interface ControlRoomRecovery {
  recovery_invoked: boolean;
  action_type?: string;
  action_amount?: MoneyValue;
  recovery_status?: string;
  replan_rounds: number;
  revalidation_verdict?: IntegrityStatusType;
  revalidated_pass: boolean;
  attempts_count: number;
  max_attempts: number;
}

export interface ControlRoomPayment {
  provider: string;
  order_id: string;
  payment_id: string;
  payment_status: string;
  amount: MoneyValue;
  payment_captured: boolean;
  integrity_vs_payment_distinction: string;
}

export interface ControlRoomSecurity {
  binding_verified: boolean;
  kill_switch_state: string; // RUNNING | PAUSED | KILLED | REQUIRES_REVALIDATION
  threat_status: string; // CLEAN | THREAT_DETECTED | BLOCKED
  threats_detected: string[];
  prompt_injection_detected: boolean;
  tampering_detected: boolean;
}

export interface ControlRoomEvidenceItem {
  evidence_id: string;
  field_name: string;
  field_value_repr: string;
  source: string;
  authority: string; // AUTHORITATIVE | MERCHANT_ATTESTED | ADVISORY | PROVIDER
  recorded_at: string;
  is_synthetic: boolean;
}

export interface ControlRoomReplay {
  replay_available: boolean;
  replay_verdict?: string; // MATCH | MISMATCH | INVALID_REPLAY
  is_cpu_only: boolean;
  discrepancy_count: number;
}

export interface ControlRoomObservability {
  checkpoints_count: number;
  checkpoints_timeline_valid: boolean;
  last_valid_checkpoint?: string;
  trace_divergence_stage?: string;
  time_to_detect_ms?: number;
  time_to_prove_ms?: number;
  time_to_revalidate_ms?: number;
}

export interface ControlRoomTimelineStage {
  stage_id: string;
  stage_name: string;
  timestamp: string;
  status: string;
  description: string;
}

export interface ControlRoomSnapshot {
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

export interface ControlRoomSummary {
  transaction_id: string;
  intent_id: string;
  current_state: string;
  integrity_status: IntegrityStatusType;
  payment_status: string;
  payment_captured: boolean;
  max_authorized: MoneyValue;
  observed_total?: MoneyValue;
  execution_mode: string;
  started_at: string;
}

export interface ScenarioDefinition {
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

export interface ScenarioProof {
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
  comparison: Array<{
    parameter: string;
    expected_value: string;
    observed_value: string;
    is_match: boolean;
    notes?: string;
  }>;
  narrative: {
    what_was_authorized: string;
    what_happened: string;
    did_it_match: string;
    why: string;
    what_happened_next: string;
  };
  proof_chain: Array<{
    stage_name: string;
    status: string;
    description: string;
    evidence_ref?: string;
    timestamp?: string;
  }>;
  proof_digest: string;
  created_at: string;
}

export type DrawerType =
  | "agent"
  | "offer"
  | "payment"
  | "integrity"
  | "mrdp"
  | "recovery"
  | "evidence"
  | "passport"
  | "replay"
  | "security"
  | "scenarios";
