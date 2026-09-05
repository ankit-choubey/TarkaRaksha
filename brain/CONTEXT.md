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

## Implemented Domain & Integrity Foundations (T01–T04)
1. **Domain Contracts (`backend/app/domain/models.py`)**:
   - `Money`: Immutable integer minor unit representation (paise, cents) with ISO 4217 validation, rejecting float/bool.
   - Enums: `IntegrityStatus` (PASS, DRIFT, UNKNOWN), `DriftDomain` (ECONOMIC, SEMANTIC, TEMPORAL), `EvidenceAuthority` (RAZORPAY, INTENT, MERCHANT, REPLAY, AGENT, SYNTHETIC), `TransactionStatus`.
   - Frozen immutable Pydantic v2 models: `IntentContract`, `ItemSpec`, `AllowedSubstitution`, `EvidenceBundle`, `IntegrityResult`, `RuleResult`, `RecoveryPlan`, `EvidenceRecord`.
2. **Deterministic Integrity Engine (`backend/app/domain/rules/` & `backend/app/services/evaluation.py`)**:
   - **Economic Rule (`check_economic`)**: Verifies authorized amount bounds (e.g. ₹50,000 threshold: 49999 PASS, 50000 PASS, 50001 DRIFT), currency match, missing/malformed amounts (`UNKNOWN`), and authority-tier conflict resolution.
   - **Semantic Rule (`check_semantic`)**: Checks SKU matching, quantity bounds, explicitly authorized substitutions (`AllowedSubstitution`), and missing attribute (`UNKNOWN`).
   - **Temporal Rule (`check_temporal`)**: Validates contract validity window (`not_before`/`expires_at`), detects duplicate event IDs, multi-capture double execution risk, and timeout with late success conflict.
   - **Overall Evaluation (`evaluate_integrity`)**: Pure deterministic evaluation with explicit `reference_time`. Priority semantics: DRIFT dominates (confirmed violation), followed by UNKNOWN (missing or ambiguous evidence cannot PASS), and PASS only when all sub-checks pass cleanly.

---

## Repository State (End of T04)
- **Current Phase**: Deterministic Integrity Engine (`T04`)
- **Active Branch**: `main`
- **Core Modules**:
  - `backend/app/domain/`: Immutable contracts, financial math, and deterministic rule engines.
  - `backend/app/services/evaluation.py`: Deterministic integrity orchestration.
  - `testing/unit/`: Test suites covering environment, domain models, money constraints, and rule engine.
  - `frontend/`: Next.js 15 App Router scaffold verified and build-ready.
