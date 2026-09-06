# CONTEXT.md — Persistent Operational Context & Architecture Snapshot

## Executive Summary
**TarkaRaksha** (तर्क रक्षा — *Reasoned Defense / Logical Protection*) is an agentic transaction integrity & recovery control plane.
- **Core Principle**: AI is advisory. Deterministic verification is authoritative.
- **Core Loop**: Authorized Intent → Agent Execution → Observe → Deterministic Integrity Verification (Pass/Drift/Unknown) → Prove (MRDP) → Safe Recovery → Revalidate.
- **Audit Capability**: Historical transactions and evidence bundles can be replayed deterministically to verify past decisions and detect post-facto tampering.

---

## Canonical Document Hierarchy (under `brain/`)
1. **`brain/TarkaRaksha_IDEA.md`**: Product definition, core conceptual boundaries, invariant definitions, and problem space.
2. **`brain/TarkaRaksha_Execution.md`**: Authoritative technical architecture, sequential build sequence (`T01`–`T18`), checkpoints (`C01`–`C18`), and repository specifications.
3. **`brain/TarkaRaksha_TESTING.md`**: Continuous test mappings (Step 8 → Step 9) and adversarial hardening specifications.
4. **`brain/TarkaRaksha_PreFinal.md`**: Downstream deliverables and final-phase reference (do not prematurely implement).
5. **`brain/STATUS.md`**: Authoritative, real-time execution state tracking.

---

## Architectural & Safety Invariants
1. **Deterministic Authority**: The rule engine is the sole source of truth on transaction integrity. LLMs cannot authorize money, override user policy, or declare `PASS`.
2. **Untrusted AI Outputs**: Natural language inputs and agent recovery suggestions are untrusted inputs requiring deterministic parsing, bounded limits, and verification.
3. **Financial Safety**: Monetary amounts must strictly be represented in integer minor units (paise, cents). Floating-point currency math is strictly forbidden.
4. **First-Class UNKNOWN**: UNKNOWN is a legitimate transaction state, not a failure to be guessed away. It may leave UNKNOWN only when sufficient authoritative evidence is acquired and deterministically verified.
5. **Observation vs Recovery**: UNKNOWN resolution (T12) performs strictly non-side-effecting observation without moving money. If DRIFT is established, it hands off to the established T11 recovery loop.
6. **Replay Determinism & Isolation (T13)**: The replay engine is a pure verification and audit capability. Zero live network calls, zero live AI queries, zero Razorpay API mutations, and zero production database state alterations.
7. **Zero Premature Code**: Minimal infrastructure, maximum verifiable engineering. No Kafka, Redis, or microservice overbuilding.
8. **TIX Advisory Transport (I6)**: TIX transports claims across participants; deterministic TarkaRaksha logic verifies claims; zero payment authorization authority resides in TIX. Sequential messages within a transaction exchange are cryptographically chained (SHA-256).

---

## Implemented Domain & Integrity Foundations (T01–T13)
1. **Domain Contracts (`backend/app/domain/models/`)**:
   - `Money`: Immutable integer minor unit representation (paise, cents) with ISO 4217 validation, rejecting float/bool.
   - Enums: `IntegrityStatus` (PASS, DRIFT, UNKNOWN), `DriftDomain`, `EvidenceSource`, `EvidenceAuthority`, `TransactionState`, `MRDPErrorCode`, `ActionType`.
   - Frozen immutable Pydantic v2 models: `IntentContract`, `IntentItem`, `Authorization`, `CanonicalEvent`, `Evidence`, `EvidenceBundle`, `IntegrityResult`, `RuleResult`, `RecoveryProposal`, `ActionRequest`, `MRDP`, `ProviderOrder`, `ProviderPayment`, `ProviderWebhookEvent`, `CreateTransactionRequest`, `CreateTransactionResponse`, `CompleteTransactionRequest`, `CompleteTransactionResponse`, `RecoverTransactionRequest`, `ResolveTransactionRequest`.

2. **Deterministic Integrity Engine (`backend/app/domain/rules/` & `backend/app/services/evaluation.py`)**:
   - **Economic Rule (`check_economic`)**: Verifies authorized amount bounds (e.g. ₹50,000 threshold), currency match, missing/malformed amounts (`UNKNOWN`), and authority-tier conflict resolution.
   - **Semantic Rule (`check_semantic`)**: Checks SKU matching, quantity bounds, explicitly authorized substitutions, and missing attribute (`UNKNOWN`).
   - **Temporal Rule (`check_temporal`)**: Validates contract validity window (`issued_at`/`expires_at`), detects duplicate event IDs, multi-capture double execution risk, and timeout with late success conflict.
   - **Overall Evaluation (`evaluate_integrity`)**: Pure deterministic evaluation with priority semantics: DRIFT dominates, followed by UNKNOWN, and PASS only when all pass cleanly.

3. **Lifecycle State Machine (`backend/app/domain/states/`)**:
   - **11 Lifecycle States**: `CREATED`, `EXECUTING`, `OBSERVING`, `VERIFYING`, `PASS`, `DRIFT`, `UNKNOWN`, `RESOLVING`, `ABSTAIN`, `RECOVERING`, `REVALIDATING`.
   - **UNKNOWN Resolution Progression**: Permitted transitions: `UNKNOWN → RESOLVING → REVALIDATING → PASS / DRIFT / UNKNOWN / ABSTAIN`. Direct jumps from `UNKNOWN → PASS` are strictly forbidden.

4. **Evidence Normalization Layer (`backend/app/domain/evidence/`)**:
   - Authority Hierarchy: `AUTHORITATIVE` (100) > `PROTOCOL_TRUSTED` (90) > `MERCHANT_ATTESTED` (70) > `REPLAY_OBSERVED` (60) > `SYSTEM_DERIVED` (50) > `ADVISORY` (20).
   - Conflict resolution engine resolves contradictions in favor of higher authority; contradictory top-tier evidence is left unresolved to preserve UNKNOWN/ABSTAIN ambiguity.

5. **Machine-Readable Drift Proof Layer (`backend/app/services/mrdp.py`)**:
   - Constructs immutable `MRDP` proof answering "what drifted?", with traceable baseline, observed evidence, rule results, and cryptographic SHA-256 tamper-evident digest.

6. **Closed Recovery Loop (`backend/app/services/recovery/`) (T11)**:
   - Evaluates recoverability, deterministically validates candidate compensatory actions, executes bounded refunds with idempotency caching, and revalidates via pure deterministic engine.

7. **UNKNOWN Resolution Subsystem (`backend/app/services/resolution/`) (T12)**:
   - **Diagnostic Policy (`diagnose_unknown`)**: Pure deterministic function evaluating explicit inputs, classifying into `RESOLVABLE`, `REMAINS_UNKNOWN`, and `ABSTAIN`.
   - **Safe Observation Engine (`UnknownObserver`)**: Non-side-effecting observation querying provider truth (`fetch_payment`, `fetch_order_payments`), normalizing evidence, and re-evaluating through `evaluate_integrity`.
   - **Bounded Attempts & Idempotency**: Bounded at 3 attempts; attempt 4 forces `ABSTAIN`. Idempotency table caches results by `idempotency_key`.

8. **Deterministic Replay Engine (`backend/app/services/replay/`) (T13)**:
   - **Replay Snapshot (`ReplaySnapshot`)**: Immutable audit input encapsulating `contract`, `events`, `evidence`, `state_transitions`, `recorded_integrity_result`, `recorded_final_state`, `recorded_mrdp`, explicit `reference_time`, and `rules_version`.
   - **Deterministic Ordering (`ordering.py`)**: Strict canonical ordering using chronological timestamps, sequence numbers, and deterministic string ID tie-breakers. Conflicting duplicate events/evidence trigger `ReplayAmbiguityError`.
   - **State Machine Reconstruction (`reconstructor.py`)**: Replays recorded transitions using authoritative T05 `TransactionStateMachine`, detecting illegal jumps (e.g. UNKNOWN to PASS) and skipped states.
   - **Deterministic Verification & Comparison (`engine.py`)**: Re-runs T04 `evaluate_integrity`, verifies cryptographic MRDP digests via `verify_mrdp_integrity`, and compares outcomes.
   - **Verdict Classification**: Yields `MATCH` (perfect agreement), `MISMATCH` (drift/tamper detected with exact discrepancies), or `INVALID_REPLAY` (illegal transition or ambiguous ordering).
   - **REST API Endpoint (`main.py`)**: `POST /api/v1/replay` accepts replay snapshot and returns diagnostic comparison.

9. **Application Layer & Control Plane UI (`backend/app/main.py`, `frontend/app/page.tsx`)**:
   - Complete slice operational: Protected Order Creation (`POST /api/v1/transaction/create`), Completion & Verification (`POST /api/v1/transaction/complete`), Webhook Ingestion (`POST /api/v1/webhook/razorpay`), Recovery (`POST /api/v1/transaction/recover`), UNKNOWN Resolution (`POST /api/v1/transaction/resolve`), and Replay (`POST /api/v1/replay`).

---

## E-Series Productization & Certification (E0–E9)
1. **E0 — Baseline Freeze**: Frozen baseline contracts and ensured backward compatibility across all T01–T13 and I0–I22 layers.
2. **E1 — Integration Boundary (`IntegrationService`)**: Unified application orchestrator binding Buyer Agent, Merchant Agent, TIX, Intent, Transaction, Payment, Integrity, Recovery, and Replay under strict 7-tuple context isolation (`intent_id`, `agent_id`, `merchant_id`, `transaction_id`, `order_id`, `payment_id`, `attempt_id`).
3. **E2 — Consumer + Merchant Gate Composition (`ConsumerGate`, `MerchantGate`)**: Pre-execution gates enforcing temporal validity, budget ceilings, SKU constraints, prompt injection interception, and merchant capability alignment.
4. **E3 — Agentic Lifecycle Orchestration (`AgenticLifecycleOrchestrator`)**: Full transactional lifecycle coordinating proposal, gate checks, TIX messaging, T04 deterministic evaluation, bounded replanning, and revalidation.
5. **E4 — Security & Threat Guard Composition (`ThreatGuardService`)**: Defenses against prompt injection, credential swapping, replay attacks, duplicate captures, and signature forgery.
6. **E5 — Transaction Passport (`TransactionPassportService`)**: Read-only, tamper-evident observational audit passport composing 7-tuple binding, gate verdicts, TIX hashes, MRDP digests, and SLA metrics.
7. **E6 — Failure → Recovery → Revalidation Hero Loop (`HeroTransactionService`)**: Closed-loop high-value commerce verification (₹50,000 ceiling, ₹47,000 product + ₹3,000 shipping = ₹50,000 PASS -> ₹55,000 controlled drift -> MRDP -> bounded replanning -> merchant alternative -> deterministic revalidation -> payment capture -> "TRANSACTION RESTORED").
8. **E7 — Real-Time Control-Room Data Surface (`ControlRoomService`, `frontend/app/page.tsx`)**: High-density telemetry dashboard providing live triad status, timeline, economic delta, and 5 deep-dive tabs. UI possesses zero authority.
9. **E8 — Scenario / Proof Surface (`ScenarioProofService`, `frontend/app/page.tsx`)**: 12 canonical scenario catalog with interactive 5-Question proof narrative, parameter comparison ledger, 6-stage proof chain, and Control Room deep linking.
10. **E9 — Final End-to-End Demonstration Certification (`EndToEndCertificationService`)**: Complete 12-item certification matrix verifying the unified system across live Razorpay order/signature verification (`LIVE_VERIFIED`), synthetic offline fixtures (`SYNTHETIC_OFFLINE_FIXTURE`), CAPTURED != PASS, UNKNOWN non-coercion, and AI advisory demarcation (`openai/gpt-oss-20b`). REST API: `GET /api/v1/certification/e9`.
