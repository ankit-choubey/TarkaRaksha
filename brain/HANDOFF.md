# HANDOFF.md — Agent Session Handoff Document

## Handoff Metadata
- **Current Task Completed**: `T12 — UNKNOWN Resolution`
- **Current Checkpoint**: `C12 — PASS`
- **Next Task**: `T13 — Replay Engine`
- **Active Branch**: `main`
- **Handoff Timestamp**: 2026-09-05T16:50:00+05:30

---

## 1. What Was Done in T12
1. **UNKNOWN Resolution Contracts & Error Hierarchy** (`backend/app/services/resolution/contracts.py`, `backend/app/domain/models/slice.py`):
   - Defined `ResolutionCategory` (`RESOLVABLE`, `REMAINS_UNKNOWN`, `ABSTAIN`).
   - Defined `ResolutionStrategy` (`FETCH_PAYMENT`, `FETCH_ORDER_PAYMENTS`, `RECONCILE_EVIDENCE`, `HOLD_OBSERVATION`).
   - Defined `ResolutionDiagnosis` and `ResolutionResult` models.
   - Defined `ResolveTransactionRequest` schema for API boundary.
   - Defined exception hierarchy: `ResolutionError`, `InvalidResolutionStateError`, `ResolutionExhaustedError`, `ResolutionConflictError`.
2. **Deterministic Resolution Policy & Diagnosis** (`backend/app/services/resolution/policy.py`):
   - Implemented `diagnose_unknown`: pure deterministic function of explicit inputs (`contract`, `integrity_result`, `evidence_bundle`, `current_attempt`, `reference_time`).
   - Classifies missing provider confirmation as `RESOLVABLE` with recommended observation strategy.
   - Escalates contradictory top-tier evidence, expired contracts, and attempt budget exhaustion to `ABSTAIN`.
   - Zero AI dependencies.
3. **Safe Provider Observation Engine with Bounded Idempotency** (`backend/app/services/resolution/observer.py`):
   - Implemented `UnknownObserver`: queries provider truth strictly without side effects or moving money (`fetch_payment`, `fetch_order_payments`).
   - Normalizes newly ingested records into canonical T06 `Evidence` and `CanonicalEvent`.
   - Re-evaluates integrity using pure T04 `evaluate_integrity`.
   - Enforces attempt budget (`MAX_RESOLUTION_ATTEMPTS = 3`).
   - Enforces idempotency via `_idempotency_records` cache.
4. **State Machine & Transaction Service Integration** (`backend/app/services/transaction_service.py`):
   - Implemented `resolve_transaction`: orchestrates the UNKNOWN resolution flow:
     `UNKNOWN → Diagnose → Safe Observation → Evidence Normalization → Conflict Resolution → Deterministic Verification → PASS / DRIFT / UNKNOWN / ABSTAIN`.
   - Follows strict state machine progression: `UNKNOWN → RESOLVING → REVALIDATING → PASS / DRIFT / UNKNOWN / ABSTAIN`.
   - If DRIFT is established, T12 does NOT execute financial recovery; hands over cleanly to the established T11 recovery subsystem.
5. **FastAPI REST Endpoint & Frontend Dashboard** (`backend/app/main.py`, `frontend/app/page.tsx`):
   - Added `POST /api/v1/transaction/resolve` endpoint to FastAPI control plane.
   - Added interactive "Execute Safe UNKNOWN Resolution" button to Next.js frontend when status is `UNKNOWN`, enabling live operator inspection.
6. **Comprehensive Unit & Adversarial Test Suites**:
   - `testing/unit/test_unknown_resolution.py`: 15 tests covering diagnosis, observation, insufficient evidence, provider timeout/500 errors, merchant vs provider conflict, advisory AI rejection, bounded attempts, idempotency, expired contracts, and end-to-end service/API resolution flows.
   - `testing/unit/test_unknown_adversarial.py`: 11 tests covering untrusted AI confidence (1.0) and prompt injection, fake merchant claims, direct illegal transition from UNKNOWN to PASS, illegal state rejection (CREATED, EXECUTING, PASS, ABSTAIN), read-only invariant (zero calls to `refund_payment`), and intent immutability under observation.
   - Full repository regression suite: 215 tests passing in 1.49s.

---

## 2. Verified Invariants
- **UNKNOWN is Authoritative**: Never guessed away, never assumed PASS, never timed out to PASS, never resolved by AI confidence.
- **Strictly Non-Side-Effecting**: UNKNOWN resolution queries provider truth without moving money.
- **Separation of Concerns**: T12 answers "What actually happened?", while T11 repairs confirmed DRIFT. T12 does not execute financial recovery actions.
- **Deterministic Resolution**: Identical inputs yield identical diagnosis and evaluation results.
- **Bounded Observation**: Maximum 3 observation attempts before escalating to ABSTAIN.
- **Original Intent Immutability**: Intent contract is immutable throughout resolution.

---

## 3. What Needs to Be Done Next (T13 — Replay Engine)
1. Implement the deterministic **Replay Engine** (`backend/app/services/replay/`).
2. Consume canonical audit log of `CanonicalEvent` and `Evidence` records.
3. Re-execute verification against historical states using `REPLAY_OBSERVED` authority tier.
4. Verify idempotency, temporal rewind, divergence detection, and tamper resistance.
5. Add unit and adversarial test suites for replay.
6. Verify C13 checkpoint and synchronize brain documentation.
