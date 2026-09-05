# HANDOFF.md — Agent Session Handoff Document

## Handoff Metadata
- **Current Task Completed**: `T11 — Recovery Loop`
- **Current Checkpoint**: `C11 — PASS`
- **Next Task**: `T12 — UNKNOWN Resolution`
- **Active Branch**: `main`
- **Handoff Timestamp**: 2026-09-05T16:32:00+05:30

---

## 1. What Was Done in T11
1. **Recovery Contracts & Models** (`backend/app/services/recovery/contracts.py`, `backend/app/domain/models/slice.py`):
   - Defined `RecoverabilityStatus` enum (`RECOVERABLE`, `NON_RECOVERABLE`, `UNKNOWN`, `ABSTAIN`).
   - Defined `RecoveryClassification` with explicit bounds, reasoning, and recommended action.
   - Defined `RecoveryExecutionResult` tracking evidence, canonical events, idempotency status, and execution details.
   - Defined `RecoverTransactionRequest` schema for API boundary.
   - Defined exception hierarchy: `RecoveryError`, `UnsafeActionRequestError`, `InvalidRecoveryStateError`, `RecoveryExhaustedError`.
2. **Deterministic Recovery Policy & Classification** (`backend/app/services/recovery/policy.py`):
   - Implemented `classify_recovery`: pure deterministic evaluation depending strictly on explicit inputs (`IntentContract`, `IntegrityResult`, `MRDP`, `current_attempt`).
   - Classifies overcharge with explicit MRDP discrepancy into `RECOVERABLE` with bounded `ActionType.REFUND`.
   - Classifies unauthorized SKU or quantity mismatch into `NON_RECOVERABLE` (escalates to `ABSTAIN`).
   - Enforces attempt limit (`MAX_RECOVERY_ATTEMPTS = 3`) and expiration guards, escalating to `ABSTAIN`.
   - Zero AI dependency in classification.
3. **Deterministic ActionRequest Safety Validation** (`backend/app/services/recovery/validator.py`):
   - Implemented `validate_action_request`: validates candidate actions against authorization bounds, state machine rules, and MRDP discrepancy facts.
   - Strictly forbids `ActionType.CAPTURE` in the recovery control plane.
   - Rejects amounts exceeding contract `max_total` or detected MRDP discrepancy.
   - Validates currency alignment, positive amounts, contract expiration, and non-empty idempotency key.
   - Rejects attempts from invalid lifecycle states (`CREATED`, `EXECUTING`).
4. **Bounded Recovery Executor with Idempotency** (`backend/app/services/recovery/executor.py`):
   - Implemented `RecoveryExecutor`: re-validates ActionRequest on dispatch (defense in depth).
   - Enforces deterministic recovery idempotency: repeated execution with identical `idempotency_key` returns cached result without repeating financial side effects.
   - Enforces attempt bounds: attempts exceeding 3 raise `RecoveryExhaustedError`.
   - Dispatches only explicitly supported actions (`REFUND`, `CANCEL`/`VOID`, `NOTIFY`/`HOLD`).
   - Emits canonical `Evidence` with `AUTHORITATIVE` authority and lifecycle `CanonicalEvent` (`payment.refunded`).
5. **Deterministic Revalidation & Economic Netting** (`backend/app/services/recovery/revalidator.py`):
   - Implemented `revalidate_recovery`: calculates net observed amount (`captured - refund_amount`) and generates authoritative net amount evidence.
   - Evaluates consolidated evidence using pure T04 `evaluate_integrity`.
   - Recovery execution alone never declares PASS; only the deterministic engine determines whether integrity is restored.
6. **Transaction Service & State Machine Integration** (`backend/app/services/transaction_service.py`):
   - Implemented `recover_transaction`: orchestrates the closed recovery loop:
     `DRIFT → Prove → Recovery Proposal → Deterministic Safety Validation → Bounded Recovery Action → Observe → Deterministic Revalidation → PASS / DRIFT / UNKNOWN / ABSTAIN`.
   - Follows strict state machine progression: `DRIFT → RECOVERING → REVALIDATING → PASS` (or `ABSTAIN`).
7. **FastAPI REST Endpoint & Frontend Dashboard** (`backend/app/main.py`, `frontend/app/page.tsx`):
   - Added `POST /api/v1/transaction/recover` endpoint to FastAPI control plane.
   - Added interactive "Execute Bounded Recovery Action" button to Next.js frontend for DRIFT transactions, demonstrating the complete live loop.
8. **Comprehensive Unit & Adversarial Test Suites**:
   - `testing/unit/test_recovery.py`: 18 tests covering policy, classification, validation, executor idempotency, attempt bounds, deterministic revalidation, and end-to-end service and API recovery flows.
   - `testing/unit/test_recovery_adversarial.py`: 11 tests covering prompt injection in MRDP remediation, AI proposal requesting CAPTURE, AI manipulated high-confidence score, currency mismatch, intent ID mismatch, post-expiration compensatory actions, duplicate replay defense, invalid state transitions, and advisory evidence override resistance.
   - Full repository test suite: 189 tests passing in 2.96s.

---

## 2. Verified Invariants
- **Original Intent is Immutable**: Recovery can never expand the original authorization envelope (no budget increase, no SKU/quantity substitution, no silent expiration extension).
- **AI is Strictly Advisory**: AI cannot authorize recovery actions, cannot declare PASS, and cannot override deterministic rejection.
- **Financial Actions Require Deterministic Authorization**: `ActionType.CAPTURE` is strictly forbidden in recovery.
- **Recovery Action Alone Never Declares PASS**: Only the deterministic integrity engine (`evaluate_integrity`) evaluates whether integrity has been restored.
- **Deterministic Policy**: Recovery classification is a pure function of explicit inputs.
- **Recovery Idempotency**: Duplicate recovery requests with identical idempotency keys return cached results without repeating side effects.
- **Bounded Attempts**: Maximum recovery attempts bounded at 3 (`MAX_RECOVERY_ATTEMPTS = 3`). Attempt 4 forces `ABSTAIN`.
- **First-Class UNKNOWN Preserved**: UNKNOWN remains UNKNOWN unless recovery obtains new authoritative evidence.

---

## 3. Explicit Instructions for Next Task (`T12 — UNKNOWN Resolution`)
When starting `T12`:
1. **Read `brain/STATUS.md` first**.
2. **Read `brain/TarkaRaksha_Execution.md` §7.35, §8.40 (T12)** and `brain/TarkaRaksha_TESTING.md` §9.52–§9.56.
3. **Task Objective**: Implement the formal **UNKNOWN Resolution** flow:
   - When evidence is missing, ambiguous, or delayed, system enters `UNKNOWN`.
   - Move state: `UNKNOWN → RESOLVING → REVALIDATING → PASS / DRIFT / UNKNOWN / ABSTAIN`.
   - Re-query authoritative provider state with bounded retry / backoff.
   - Normalize newly ingested evidence through T06 conflict resolution.
   - If authoritative evidence confirms valid execution → `PASS`.
   - If authoritative evidence reveals violation → `DRIFT` (triggers T11 recovery).
   - If still unresolved within resolution budget → escalate to `ABSTAIN`.
   - NEVER guess or convert `UNKNOWN` directly into `PASS`.
4. **Pass Checkpoint C12** before committing and pushing.
