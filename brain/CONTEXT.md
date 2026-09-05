# CONTEXT.md — Persistent Operational Context & Architecture Snapshot

## Executive Summary
**TarkaRaksha** (तर्क रक्षा — *Reasoned Defense / Logical Protection*) is an agentic transaction integrity & recovery control plane.
- **Core Principle**: AI is advisory. Deterministic verification is authoritative.
- **Core Loop**: Authorized Intent → Agent Execution → Observe → Deterministic Integrity Verification (Pass/Drift/Unknown) → Prove (MRDP) → Safe Recovery → Revalidate.

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
4. **First-Class UNKNOWN**: When gateway evidence is ambiguous or delayed, state transitions to `UNKNOWN` and enters a dedicated resolution/re-verification flow rather than guessing.
5. **Zero Premature Code**: Minimal infrastructure, maximum verifiable engineering. No Kafka, Redis, or microservice overbuilding.

---

## Implemented Domain & Integrity Foundations (T01–T11)
1. **Domain Contracts (`backend/app/domain/models/`)**:
   - `Money`: Immutable integer minor unit representation (paise, cents) with ISO 4217 validation, rejecting float/bool.
   - Enums: `IntegrityStatus` (PASS, DRIFT, UNKNOWN), `DriftDomain` (ECONOMIC, SEMANTIC, TEMPORAL), `EvidenceSource`, `EvidenceAuthority`, `TransactionState`, `MRDPErrorCode`, `ActionType`.
   - Frozen immutable Pydantic v2 models: `IntentContract`, `IntentItem`, `Authorization`, `CanonicalEvent`, `Evidence`, `EvidenceBundle`, `IntegrityResult`, `RuleResult`, `RecoveryProposal`, `ActionRequest`, `MRDP`, `ProviderOrder`, `ProviderPayment`, `ProviderWebhookEvent`, `CreateTransactionRequest`, `CreateTransactionResponse`, `CompleteTransactionRequest`, `CompleteTransactionResponse`, `RecoverTransactionRequest`.

2. **Deterministic Integrity Engine (`backend/app/domain/rules/` & `backend/app/services/evaluation.py`)**:
   - **Economic Rule (`check_economic`)**: Verifies authorized amount bounds (e.g. ₹50,000 threshold: 49999 PASS, 50000 PASS, 50001 DRIFT), currency match, missing/malformed amounts (`UNKNOWN`), and authority-tier conflict resolution.
   - **Semantic Rule (`check_semantic`)**: Checks SKU matching, quantity bounds, explicitly authorized substitutions, and missing attribute (`UNKNOWN`).
   - **Temporal Rule (`check_temporal`)**: Validates contract validity window (`issued_at`/`expires_at`), detects duplicate event IDs, multi-capture double execution risk, and timeout with late success conflict.
   - **Overall Evaluation (`evaluate_integrity`)**: Pure deterministic evaluation with explicit `reference_time`. Priority semantics: DRIFT dominates (confirmed violation), followed by UNKNOWN (missing or ambiguous evidence cannot PASS), and PASS only when all sub-checks pass cleanly. Zero AI dependencies.

3. **Lifecycle State Machine (`backend/app/domain/states/`)**:
   - **11 Lifecycle States**: `CREATED`, `EXECUTING`, `OBSERVING`, `VERIFYING`, `PASS`, `DRIFT`, `UNKNOWN`, `RESOLVING`, `ABSTAIN`, `RECOVERING`, `REVALIDATING`.
   - **Transition Enforcement**: Authoritative transition graph (`PERMITTED_TRANSITIONS`). Self-transitions, skipped states, and illegal pathways are rejected with `InvalidStateTransitionError`.
   - **Financial Safety Guards**: `request_action` permanently blocks financial capture in `UNKNOWN`, `DRIFT`, `ABSTAIN`, and non-verified states. Enforces amount and currency alignment against `IntentContract.max_total`.
   - **Advisory AI Boundary**: Untrusted agent/AI triggers cannot force state transitions without deterministic verification (`is_verified=True`).
   - **Deterministic Consumption**: `apply_integrity_result` consumes T04 `IntegrityResult` to drive transitions from `VERIFYING` or `REVALIDATING` to `PASS`, `DRIFT`, or `UNKNOWN`.

4. **Evidence Normalization Layer (`backend/app/domain/evidence/` & `backend/app/domain/models/evidence.py`)**:
   - **Source vs Authority Decoupling**: Origin channel (`EvidenceSource`) is explicitly distinct from authoritative weighting tier (`EvidenceAuthority`).
   - **Authority Hierarchy**: `AUTHORITATIVE` (100) > `PROTOCOL_TRUSTED` (90) > `MERCHANT_ATTESTED` (70) > `REPLAY_OBSERVED` (60) > `SYSTEM_DERIVED` (50) > `ADVISORY` (20).
   - **Canonical EvidenceBundle**: Immutable container grouping evidence items and canonical lifecycle events with query, conflict detection, and completeness utilities.
   - **Conflict Resolution Engine**: Deterministically resolves contradictions across authority tiers in favor of higher rank; leaves contradictory top-tier evidence unresolved to preserve `UNKNOWN` ambiguity.

5. **Machine-Readable Drift Proof Layer (`backend/app/domain/models/integrity.py`, `backend/app/services/mrdp.py`, `backend/app/services/canonicalization.py`)**:
   - **Protocol Designation**: MRDP is strictly TarkaRaksha's proposed "Machine-Readable Drift Proof", NOT an industry standard, NOT a payment standard, and NOT an official Razorpay protocol.
   - **Deterministic Consumption & Chain**: Consumes `IntentContract` + `IntegrityResult` + `EvidenceBundle` to produce an immutable `MRDP` proof answering "what drifted?", with traceable baseline, observed evidence, rule results, and permissible advisory remediation. Zero AI dependencies.
   - **Canonicalization & SHA-256 Digest**: Stable JSON canonicalization with sorted keys, compact separators, normalized Money integers, and ISO-8601 datetimes. Hashed via SHA-256 (`proof_digest`).
   - **Tamper Verification**: `verify_mrdp_integrity()` verifies whether any serialized or model field was tampered with post-creation.

6. **AI Integration Layer (`backend/app/services/ai/`, `backend/app/core/config.py`)**:
   - **Two Logical AI Roles**:
     1. `Intent Parser`: Extracts structured constraints from user natural language into intermediate `AIIntentExtraction`, validated into authoritative immutable `IntentContract`.
     2. `Advisory Recovery Agent`: Analyzes MRDP and IntentContract to propose advisory `RecoveryProposal`.
   - **AI Trust Boundary**: AI outputs are strictly untrusted inputs. AI cannot authorize payments, increase budget, modify authorized SKU/quantity/currency, or declare PASS.
   - **Provider Abstraction**: Narrow `AIProvider` ABC implemented by `GroqAIProvider` (production) and `FakeAIProvider` (deterministic local tests without network calls).

7. **Payment Gateway Adapter Layer (`backend/app/services/payment/`)**:
   - **Narrow Provider Interface (`PaymentProvider`)**: Decouples domain services from Razorpay SDK specifics (`create_order`, `fetch_payment`, `fetch_order_payments`, `verify_payment_signature`, `verify_webhook_signature`, `parse_webhook_payload`).
   - **Provider-Neutral Models**: `ProviderOrder`, `ProviderPayment`, and `ProviderWebhookEvent` ensure amounts remain strictly in integer minor units (`Money`).
   - **Cryptographic Signatures**: Constant-time HMAC-SHA256 signature verification for checkout completion and webhook deliveries. Invalid signatures reject unverified data before normalization.

8. **First Complete Real Transaction Slice (T10) (`backend/app/services/transaction_service.py`, `backend/app/main.py`, `frontend/app/page.tsx`)**:
   - **End-to-End Orchestration (`TransactionService`)**: Implements the full protected transaction loop:
     `Authorized Intent → Create Gateway Order → Checkout Completion → Server Signature Verification → Gateway State Polling → Normalized Evidence → Deterministic Verification → PASS / DRIFT / UNKNOWN`.
   - **FastAPI REST Control Plane**:
     - `POST /api/v1/transaction/create`: Binds intent to provider order, returns checkout params.
     - `POST /api/v1/transaction/complete`: Validates signature, ingests evidence, evaluates integrity.
     - `GET /api/v1/transaction/{id}`: Returns audit history, state transitions, and evaluation results.
     - `GET /api/v1/transaction/{id}/mrdp`: Serves cryptographic MRDP proof for DRIFT or UNKNOWN.
     - `POST /api/v1/webhook/razorpay`: Ingests asynchronous signed webhook notifications.
   - **Interactive Frontend Control Plane**: Clean Next.js dashboard providing interactive intent configuration, real-time checkout simulation with preset attack scenarios (overcharge drift, signature forgery), live state machine inspection, and MRDP visualization.

9. **Recovery Loop Control Plane (T11) (`backend/app/services/recovery/`)**:
   - **Closed Control Loop**:
     `DRIFT / RECOVERABLE UNKNOWN → MRDP / Evidence → Recovery Proposal → Deterministic Safety Validation → Bounded Recovery Action → Observe → Deterministic Revalidation → PASS / DRIFT / UNKNOWN / ABSTAIN`.
   - **Deterministic Policy (`classify_recovery`)**:
     - Evaluates recoverability purely from explicit inputs (`IntentContract`, `IntegrityResult`, `MRDP`, `attempt_count`).
     - Classifies outcomes:
       - `RECOVERABLE`: Overcharge with explicit MRDP discrepancy -> bounded `ActionType.REFUND`.
       - `NON_RECOVERABLE`: Unauthorized SKU or quantity mismatch outside authorization envelope -> escalates to `ABSTAIN`.
       - `UNKNOWN`: Missing/delayed evidence -> safe observation query (`ActionType.NOTIFY`).
       - `ABSTAIN`: Contradictory evidence, expired intent, temporal multi-capture risk, or attempts exhausted.
   - **ActionRequest Safety Validator (`validate_action_request`)**:
     - Validates candidate action requests against contract bounds, state machine rules, and MRDP discrepancy facts.
     - `ActionType.CAPTURE` is strictly forbidden in recovery.
     - Requested amounts must be positive, match contract currency, not exceed authorized `max_total`, and not exceed MRDP discrepancy.
     - Rejects expired intents, mismatched intent IDs, and illegal lifecycle states (`CREATED`, `EXECUTING`).
   - **Bounded Recovery Executor (`RecoveryExecutor`)**:
     - Re-validates ActionRequest (defense in depth).
     - Enforces recovery attempt budget (`MAX_RECOVERY_ATTEMPTS = 3`). Attempt 4 raises `RecoveryExhaustedError`.
     - Enforces deterministic recovery idempotency: repeated executions with identical `idempotency_key` return cached results without repeating side effects.
     - Emits authoritative `Evidence` and `CanonicalEvent` (`payment.refunded`, `order.cancelled`, etc.).
   - **Deterministic Revalidation (`revalidate_recovery`)**:
     - Consolidates compensatory evidence (e.g. refund netting against original overcharge) into authoritative net amount evidence.
     - Submits canonical evidence to pure T04 `evaluate_integrity`. Recovery action execution alone never declares PASS; only the deterministic engine determines whether integrity has been restored.
   - **State Machine Integration**:
     - Follows strict legal progression: `DRIFT → RECOVERING → REVALIDATING → PASS` (or `DRIFT`, `UNKNOWN`, `ABSTAIN`).
     - State machine `apply_integrity_result` consumes the revalidation outcome.
   - **FastAPI Endpoint & Frontend Integration**:
     - Exposes `POST /api/v1/transaction/recover` on the control plane.
     - Interactive recovery button in `frontend/app/page.tsx` executes the compensatory loop and displays revalidated PASS state.

---

## Repository State (End of T11)
- **Current Phase**: Recovery Loop (`T11`)
- **Active Branch**: `main`
- **Core Modules**:
  - `backend/app/core/`: Runtime settings and environment configuration.
  - `backend/app/domain/models/`: Immutable contracts, financial math, enums, evidence models, MRDP model, recovery model, payment models, slice schemas.
  - `backend/app/domain/rules/`: Deterministic economic, semantic, and temporal rule engines.
  - `backend/app/domain/states/`: Lifecycle state machine, transitions, invariants, and audit history.
  - `backend/app/domain/evidence/`: Provider-neutral evidence normalizers, conflict resolution, deduplication.
  - `backend/app/services/canonicalization.py`: Deterministic canonical serialization and SHA-256 digest computation.
  - `backend/app/services/mrdp.py`: Pure deterministic MRDP builder and tamper-evident verification.
  - `backend/app/services/evaluation.py`: Deterministic integrity orchestration.
  - `backend/app/services/ai/`: AIProvider interface, GroqAIProvider, FakeAIProvider, Intent Parser, and Advisory Recovery Agent.
  - `backend/app/services/payment/`: PaymentProvider interface, RazorpayAdapter, FakePaymentProvider, signature verification, and normalization.
  - `backend/app/services/transaction_service.py`: Control plane transaction orchestrator with complete slice and recovery loop.
  - `backend/app/services/recovery/`: Recovery contracts, deterministic policy, safety validator, bounded executor, deterministic revalidator.
  - `backend/app/main.py`: FastAPI application endpoints (create, complete, recover, status, mrdp, webhook).
  - `frontend/`: Next.js 15 App Router interactive control plane dashboard with slice checkout and autonomous recovery controls.
  - `testing/unit/`: Comprehensive test suites covering all modules (189 passing tests).
