# STATUS.md — TarkaRaksha Execution State Tracker

## Project
**TarkaRaksha** — Agentic Transaction Integrity & Recovery Control Plane

## Current Phase
UNKNOWN Resolution

## Current Task
T12 — UNKNOWN Resolution

## Task Status
COMPLETE (C12 PASS)

## Completed Tasks
- [x] **T01 — Repository Bootstrap** (Completed 2026-09-05)
- [x] **T02 — Environment** (Completed 2026-09-05)
- [x] **T03 — Domain Contracts** (Completed 2026-09-05)
- [x] **T04 — Deterministic Engine** (Completed 2026-09-05)
- [x] **T05 — State Machine** (Completed 2026-09-05)
- [x] **T06 — Evidence** (Completed 2026-09-05)
- [x] **T07 — MRDP** (Completed 2026-09-05)
- [x] **T08 — Groq AI** (Completed 2026-09-05)
- [x] **T09 — Razorpay Adapter** (Completed 2026-09-05)
- [x] **T10 — First Complete Real Transaction Slice** (Completed 2026-09-05)
- [x] **T11 — Recovery Loop** (Completed 2026-09-05)
- [x] **T12 — UNKNOWN Resolution** (Completed 2026-09-05)

## Last Verified
2026-09-05T16:50:00+05:30

## Tests Run
- `make test-bootstrap`: PASS (all master brain files, zero root copies, pyproject valid, zero secrets)
- `make test-env`: PASS (toolchains verified, Next.js build clean, smoke tests pass)
- `pytest` (215 passed in 1.49s):
  - `testing/unit/test_unknown_resolution.py` (15 tests): diagnosis of missing provider evidence as RESOLVABLE by observation, insufficient evidence remaining UNKNOWN when gateway has no payments, provider observation resolving UNKNOWN -> PASS with authoritative payment, provider observation resolving UNKNOWN -> DRIFT without performing recovery, merchant attested claims cannot override authoritative Razorpay evidence, lower-authority advisory/AI claims cannot resolve UNKNOWN, conflicting authoritative provider evidence escalates to ABSTAIN, provider timeout handled gracefully remaining UNKNOWN, provider 500 error handled gracefully remaining UNKNOWN, bounded resolution attempts (3 allowed, 4th raises `ResolutionExhaustedError` and transitions to ABSTAIN), duplicate resolution request idempotency returning cached result without repeat provider queries, late payment after intent expiry evaluated safely as ABSTAIN, intent immutability preserved under observation, full transaction service resolution lifecycle (`UNKNOWN -> RESOLVING -> REVALIDATING -> PASS`), and FastAPI REST endpoint (`/api/v1/transaction/resolve`).
  - `testing/unit/test_unknown_adversarial.py` (11 tests): untrusted AI confidence (1.0) and prompt injection cannot resolve UNKNOWN, fake merchant claims cannot override provider truth when gateway reports drift, direct illegal transition from UNKNOWN to PASS rejected by state machine, resolution attempted from illegal lifecycle states (CREATED, EXECUTING, PASS, ABSTAIN) rejected with `InvalidResolutionStateError`, TransactionService rejects resolution from PASS, UNKNOWN resolution never calls `refund_payment` (strictly read-only observation), frozen intent contract cannot be mutated during resolution (amount/expiry modifications fail), and post-expiration observation attempts rejected as ABSTAIN.
  - `testing/unit/test_recovery.py` (18 tests): closed recovery loop, drift classification, action request validation, executor idempotency, bounded attempt budget, deterministic revalidation, state machine transitions.
  - `testing/unit/test_recovery_adversarial.py` (11 tests): prompt injection resistance, capture forbidden, high-confidence AI rejection, replay defense.
  - `testing/unit/test_transaction_slice.py` (7 tests): real slice happy path, HMAC-SHA256 signature verification, state machine lifecycle, bounded polling.
  - `testing/unit/test_transaction_adversarial.py` (10 tests): signature forgery rejection, economic/semantic/temporal drift, intent immutability.
  - `testing/unit/test_payment_adapter.py` (12 tests): order creation, parsing, float rejection, fake provider retrieval.
  - `testing/unit/test_payment_adversarial.py` (7 tests): signature forgery, unverified webhook rejection, replay deduplication.
  - `testing/unit/test_ai_agent.py` (16 tests): intent parsing, recovery proposals, bounded retries.
  - `testing/unit/test_ai_adversarial.py` (10 tests): prompt injection resistance, zero AI calls in verifier.
  - `testing/unit/test_mrdp.py` (5 tests) & `test_mrdp_adversarial.py` (5 tests): tamper detection, SHA-256 digests.
  - `testing/unit/test_evidence.py` (9 tests) & `test_evidence_adversarial.py` (6 tests): authority hierarchy, deduplication, conflict resolution.
  - `testing/unit/test_state_machine.py` (10 tests) & `test_state_machine_adversarial.py` (7 tests): transition enforcement, safety invariants.
  - `testing/unit/test_engine.py` (21 tests): economic boundary (49999 PASS, 50000 PASS, 50001 DRIFT), semantic checks, temporal validity.
  - `testing/unit/test_money.py` (12 tests): integer minor units, float rejection.
  - `testing/unit/test_models.py` (18 tests): domain contracts.
  - `testing/unit/test_environment.py` (5 tests): baseline environment checks.

## Environment & Toolchains Verified
- **Python**: 3.12.12 (via project-local `.venv`)
- **FastAPI**: 0.141.1, **Uvicorn**: 0.52.4, **Pydantic**: 2.13.5, **HTTPX**: 0.28.1, **Pytest**: 9.1.1
- **AI Client**: `groq` 1.7.0 (instantiation and live smoke test verified with `qwen/qwen3.8-27b`)
- **Payment Client**: `razorpay` 2.0.1 (live Test Mode order creation and HMAC-SHA256 signature verification verified)
- **Node.js**: v25.2.1, **npm**: 11.6.2
- **Frontend Stack**: Next.js 15.5.25 (App Router, Turbopack), TypeScript 5, Tailwind CSS 4, Lucide icons

## Real Razorpay Test Mode Status
- **PASS**: Live credentials in `.env` verified against Razorpay API. Real Test Mode order creation, integer minor units, and constant-time HMAC-SHA256 verification confirmed.

## Known Failures
None

## Blockers
None

## Important Decisions
1. **UNKNOWN as a First-Class State**:
   - UNKNOWN is a legitimate transaction state, never guessed away, never timed out to PASS, and never resolved by AI confidence or merchant assertion.
   - Intended flow strictly enforced:
     `UNKNOWN → Diagnose missing/conflicting evidence → Resolution Strategy → Safe Observation / Evidence Acquisition → Evidence Normalization → Conflict Resolution → Deterministic Integrity Verification → PASS / DRIFT / UNKNOWN / ABSTAIN`.
2. **Strictly Non-Side-Effecting Observation**:
   - T12 resolution performs only read-only queries against provider truth (`fetch_payment`, `fetch_order_payments`, reconciling evidence).
   - Zero financial recovery inside T12. If resolution discovers overcharge or discrepancy, it convicts with `DRIFT` and hands over cleanly to T11 rather than attempting refunds.
3. **Resolution Categories**:
   - `RESOLVABLE`: Resolvable by additional authoritative provider observation or hierarchy reconciliation.
   - `REMAINS_UNKNOWN`: Required evidence missing or gateway unreachable.
   - `ABSTAIN`: Unsafe conditions (expired contract, irreconcilable top-tier conflict, attempt budget exhausted).
4. **Bounded Observation & Idempotency**:
   - Observation attempts bounded at 3 (`MAX_RESOLUTION_ATTEMPTS = 3`). Attempt 4 deterministically escalates to `ABSTAIN`.
   - Idempotency table caches `ResolutionResult` by `idempotency_key`, preventing duplicate network polling.
5. **State Machine Lifecycle Progression**:
   - Enforces transition graph: `UNKNOWN → RESOLVING → REVALIDATING → PASS / DRIFT / UNKNOWN / ABSTAIN`. Direct jumps from `UNKNOWN → PASS` are strictly forbidden.
6. **Frontend Control Plane UNKNOWN Resolution Trigger**:
   - Added interactive "Execute Safe UNKNOWN Resolution" trigger to `frontend/app/page.tsx` when status is `UNKNOWN`, enabling operator inspection.

## Active Branch
`main`

## Last Verified Remote Commit
acba399 (docs: synchronize persistent brain and handoff for T12 completion)

## Next Task
**T13 — Replay Engine** (Consuming T05 `REPLAY_OBSERVED` authority + canonical event journal + deterministic verification replay)

## Source Documents Consulted
- `brain/TarkaRaksha_IDEA.md` (§31, §34, §35, §37)
- `brain/TarkaRaksha_Execution.md` (§7.36, §8.40)
- `brain/TarkaRaksha_TESTING.md` (§9.52–§9.56)
- `brain/CONTEXT.md`
- `brain/HANDOFF.md`
