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

## Implemented Domain & Integrity Foundations (T01–T09)
1. **Domain Contracts (`backend/app/domain/models/`)**:
   - `Money`: Immutable integer minor unit representation (paise, cents) with ISO 4217 validation, rejecting float/bool.
   - Enums: `IntegrityStatus` (PASS, DRIFT, UNKNOWN), `DriftDomain` (ECONOMIC, SEMANTIC, TEMPORAL), `EvidenceSource`, `EvidenceAuthority`, `TransactionStatus`, `MRDPErrorCode`, `ActionType`.
   - Frozen immutable Pydantic v2 models: `IntentContract`, `ItemSpec`, `AllowedSubstitution`, `Evidence`, `EvidenceBundle`, `IntegrityResult`, `RuleResult`, `RecoveryProposal`, `MRDP`, `ProviderOrder`, `ProviderPayment`, `ProviderWebhookEvent`.
2. **Deterministic Integrity Engine (`backend/app/domain/rules/` & `backend/app/services/evaluation.py`)**:
   - **Economic Rule (`check_economic`)**: Verifies authorized amount bounds (e.g. ₹50,000 threshold: 49999 PASS, 50000 PASS, 50001 DRIFT), currency match, missing/malformed amounts (`UNKNOWN`), and authority-tier conflict resolution.
   - **Semantic Rule (`check_semantic`)**: Checks SKU matching, quantity bounds, explicitly authorized substitutions (`AllowedSubstitution`), and missing attribute (`UNKNOWN`).
   - **Temporal Rule (`check_temporal`)**: Validates contract validity window (`not_before`/`expires_at`), detects duplicate event IDs, multi-capture double execution risk, and timeout with late success conflict.
   - **Overall Evaluation (`evaluate_integrity`)**: Pure deterministic evaluation with explicit `reference_time`. Priority semantics: DRIFT dominates (confirmed violation), followed by UNKNOWN (missing or ambiguous evidence cannot PASS), and PASS only when all sub-checks pass cleanly. Zero AI dependencies.

3. **Lifecycle State Machine (`backend/app/domain/states/`)**:
   - **11 Lifecycle States**: `CREATED`, `EXECUTING`, `OBSERVING`, `VERIFYING`, `PASS`, `DRIFT`, `UNKNOWN`, `RESOLVING`, `ABSTAIN`, `RECOVERING`, `REVALIDATING`.
   - **Transition Enforcement**: Authoritative transition graph (`PERMITTED_TRANSITIONS`). Self-transitions, skipped states, and illegal pathways (e.g. `PASS -> EXECUTING`, `ABSTAIN -> CAPTURE`) are rejected with `InvalidStateTransitionError`.
   - **Financial Safety Guards**: `request_action` permanently blocks financial capture in `UNKNOWN`, `DRIFT`, `ABSTAIN`, and non-verified states. Enforces amount and currency alignment against `IntentContract.max_total`.
   - **Advisory AI Boundary**: Untrusted agent/AI triggers cannot force state transitions without deterministic verification (`is_verified=True`).
   - **Deterministic Consumption**: `apply_integrity_result` consumes T04 `IntegrityResult` to drive transitions from `VERIFYING` or `REVALIDATING` to `PASS`, `DRIFT`, or `UNKNOWN`.

4. **Evidence Normalization Layer (`backend/app/domain/evidence/` & `backend/app/domain/models/evidence.py`)**:
   - **Source vs Authority Decoupling**: Origin channel (`EvidenceSource`) is explicitly distinct from authoritative weighting tier (`EvidenceAuthority`).
   - **Authority Hierarchy**: `AUTHORITATIVE` (100) > `PROTOCOL_TRUSTED` (90) > `MERCHANT_ATTESTED` (70) > `REPLAY_OBSERVED` (60) > `SYSTEM_DERIVED` (50) > `ADVISORY` (20).
   - **Canonical EvidenceBundle**: Immutable container grouping evidence items and canonical lifecycle events with query, conflict detection, and completeness utilities.
   - **Conflict Resolution Engine**: Deterministically resolves contradictions across authority tiers in favor of higher rank; leaves contradictory top-tier evidence unresolved to preserve `UNKNOWN` ambiguity.
   - **Deterministic Normalization & Deduplication**: Provider-neutral normalizer converting monetary fields to integer-minor-unit `Money` value objects, validating timezone-aware timestamps, and deduplicating deliveries idempotently.

5. **Machine-Readable Drift Proof Layer (`backend/app/domain/models/integrity.py`, `backend/app/services/mrdp.py`, `backend/app/services/canonicalization.py`)**:
   - **Protocol Designation**: MRDP is strictly TarkaRaksha's proposed "Machine-Readable Drift Proof", NOT an industry standard, NOT a payment standard, and NOT an official Razorpay protocol.
   - **Deterministic Consumption & Chain**: Consumes `IntentContract` + `IntegrityResult` + `EvidenceBundle` to produce an immutable `MRDP` proof answering "what drifted?", with traceable baseline, observed evidence, rule results, and permissible advisory remediation. Zero AI dependencies.
   - **Canonicalization & SHA-256 Digest**: Stable JSON canonicalization with sorted keys, compact separators, normalized Money integers, and ISO-8601 datetimes. Hashed via SHA-256 (`proof_digest`). Proves tamper-evident integrity of the proof representation.
   - **Tamper Verification**: `verify_mrdp_integrity()` verifies whether any serialized or model field was tampered with post-creation.

6. **AI Integration Layer (`backend/app/services/ai/`, `backend/app/core/config.py`)**:
   - **Two Logical AI Roles**:
     1. `Intent Parser`: Extracts structured constraints from user natural language into intermediate `AIIntentExtraction`, validated into authoritative immutable `IntentContract`.
     2. `Advisory Recovery Agent`: Analyzes MRDP and IntentContract to propose advisory `RecoveryProposal`.
   - **AI Trust Boundary**: AI outputs are strictly untrusted inputs. AI cannot authorize payments, increase budget, modify authorized SKU/quantity/currency, or declare PASS.
   - **Provider Abstraction**: Narrow `AIProvider` ABC implemented by `GroqAIProvider` (production) and `FakeAIProvider` (deterministic local tests without network calls).
   - **Deterministic Safety Validator**: `validate_recovery_proposal_safety()` enforces that AI suggestions cannot propose CAPTURE, exceed budget, exceed MRDP discrepancy amounts, or introduce bypass instructions.
   - **Bounded Retries & Safe Fallback**: Bounded retries on malformed JSON or transient provider errors, falling back safely to `IntentParsingError` or safe abstain without crashing.

7. **Payment Gateway Adapter Layer (T09) (`backend/app/services/payment/`)**:
   - **Narrow Provider Interface (`PaymentProvider`)**: Decouples domain services from Razorpay SDK specifics (`create_order`, `fetch_payment`, `fetch_order_payments`, `verify_payment_signature`, `verify_webhook_signature`, `parse_webhook_payload`).
   - **Provider-Neutral Models**: `ProviderOrder`, `ProviderPayment`, and `ProviderWebhookEvent` ensure amounts remain strictly in integer minor units (`Money`).
   - **Cryptographic Signatures**: Constant-time HMAC-SHA256 signature verification for checkout completion and webhook deliveries. Invalid signatures reject unverified data before normalization.
   - **Canonical Evidence Normalization**: Translates provider observations into `Evidence` (`EvidenceSource.RAZORPAY`, `EvidenceAuthority.AUTHORITATIVE`) and `CanonicalEvent`. Integrates with T06 deduplication for replayed webhooks.
   - **Zero Business Logic in Adapter**: RazorpayAdapter never evaluates budget rules or declares PASS/DRIFT/UNKNOWN.

---

## Repository State (End of T09)
- **Current Phase**: Payment Gateway Adapter Layer (`T09`)
- **Active Branch**: `main`
- **Core Modules**:
  - `backend/app/core/`: Runtime settings and environment configuration.
  - `backend/app/domain/models/`: Immutable contracts, financial math, enums, evidence models, MRDP model, recovery model, payment models, bundle.
  - `backend/app/domain/rules/`: Deterministic economic, semantic, and temporal rule engines.
  - `backend/app/domain/states/`: Lifecycle state machine, transitions, invariants, and audit history.
  - `backend/app/domain/evidence/`: Provider-neutral evidence normalizers, conflict resolution, deduplication.
  - `backend/app/services/canonicalization.py`: Deterministic canonical serialization and SHA-256 digest computation.
  - `backend/app/services/mrdp.py`: Pure deterministic MRDP builder and tamper-evident verification.
  - `backend/app/services/evaluation.py`: Deterministic integrity orchestration.
  - `backend/app/services/ai/`: AIProvider interface, GroqAIProvider, FakeAIProvider, Intent Parser, and Advisory Recovery Agent.
  - `backend/app/services/payment/`: PaymentProvider interface, RazorpayAdapter, FakePaymentProvider, signature verification, and normalization.
  - `testing/unit/`: Comprehensive test suites covering environment, models, money, engine, state machine, evidence normalization, MRDP, AI integration, and payment adapter (142 passing tests, 1 skipped).
  - `frontend/`: Next.js 15 App Router scaffold verified and build-ready.
