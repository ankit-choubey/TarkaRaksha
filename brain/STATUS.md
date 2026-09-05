# STATUS.md — TarkaRaksha Execution State Tracker

## Project
**TarkaRaksha** — Agentic Transaction Integrity & Recovery Control Plane

## Current Phase
Replay Engine

## Current Task
T13 — Replay Engine

## Task Status
COMPLETE (C13 PASS)

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
- [x] **T13 — Replay Engine** (Completed 2026-09-05)

## Last Verified
2026-09-05T17:08:00+05:30

## Tests Run
- `make test-bootstrap`: PASS (all master brain files, zero root copies, pyproject valid, zero secrets)
- `make test-env`: PASS (toolchains verified, Next.js build clean, smoke tests pass)
- `pytest` (242 passed in 1.33s):
  - `testing/unit/test_replay.py` (17 tests): determinism across identical inputs, repeated replay stability (50x iterations), explicit reference time reproducibility, chronological event ordering, deterministic timestamp tie-breaking, ambiguous ordering rejection, illegal state transitions detection, skipped transitions detection, UNKNOWN resolution lifecycle replay, historical PASS verification match, tampered evidence amount mismatch detection, tampered intent limit mismatch detection, MRDP proof matching, tampered MRDP digest detection, pure CPU execution without AI, advisory AI claims unable to override authoritative provider drift, and FastAPI REST endpoint verification (`POST /api/v1/replay`).
  - `testing/unit/test_replay_adversarial.py` (10 tests): attacker modifies authorized intent amount post-facto (MISMATCH), attacker substitutes unauthorized SKU (MISMATCH), attacker inflates item quantity (MISMATCH), attacker injects future-dated events after contract expiration (MISMATCH), attacker injects duplicate capture events (MISMATCH), attacker forges MRDP proof payload without matching digest (is_mrdp_valid=False, MISMATCH), attacker inserts fake PASS transition from UNKNOWN (INVALID_REPLAY), zero side-effects verification ensuring no live network or HTTP requests occur during replay, attacker embeds prompt injection inside evidence notes/provenance without altering deterministic evaluation, and conflicting event IDs with divergent types/timestamps safely flagged as ambiguity (INVALID_REPLAY).
  - `testing/unit/test_unknown_resolution.py` (15 tests): full T12 test suite.
  - `testing/unit/test_unknown_adversarial.py` (11 tests): full T12 adversarial suite.
  - `testing/unit/test_recovery.py` (18 tests): full T11 test suite.
  - `testing/unit/test_recovery_adversarial.py` (11 tests): full T11 adversarial suite.
  - `testing/unit/test_transaction_slice.py` (7 tests): full T10 test suite.
  - `testing/unit/test_transaction_adversarial.py` (10 tests): full T10 adversarial suite.
  - `testing/unit/test_payment_adapter.py` (12 tests): full T09 test suite.
  - `testing/unit/test_payment_adversarial.py` (7 tests): full T09 adversarial suite.
  - `testing/unit/test_ai_agent.py` (16 tests): full T08 test suite.
  - `testing/unit/test_ai_adversarial.py` (10 tests): full T08 adversarial suite.
  - `testing/unit/test_mrdp.py` (5 tests) & `test_mrdp_adversarial.py` (5 tests): full T07 test suite.
  - `testing/unit/test_evidence.py` (9 tests) & `test_evidence_adversarial.py` (6 tests): full T06 test suite.
  - `testing/unit/test_state_machine.py` (10 tests) & `test_state_machine_adversarial.py` (7 tests): full T05 test suite.
  - `testing/unit/test_engine.py` (21 tests): full T04 test suite.
  - `testing/unit/test_money.py` (12 tests): full T03 money test suite.
  - `testing/unit/test_models.py` (18 tests): full T03 models test suite.
  - `testing/unit/test_environment.py` (5 tests): full baseline environment suite.

## Environment & Toolchains Verified
- **Python**: 3.12.12 (via project-local `.venv`)
- **FastAPI**: 0.141.1, **Uvicorn**: 0.52.4, **Pydantic**: 2.13.5, **HTTPX**: 0.28.1, **Pytest**: 9.1.1
- **AI Client**: `groq` 1.7.0 (instantiation and live smoke test verified with `qwen/qwen3.8-27b`)
- **Payment Client**: `razorpay` 2.0.1 (live Test Mode order creation and HMAC-SHA256 signature verification verified)
- **Node.js**: v25.2.1, **npm**: 11.6.2
- **Frontend Stack**: Next.js 15.5.25 (App Router, Turbopack), TypeScript 5, Tailwind CSS 4, Lucide icons

## Key Invariants Maintained
- **Deterministic Replay Guarantee**: Identical IntentContract + identical ordered evidence + same rules version + same explicit reference time MUST yield an identical deterministic replay result.
- **Zero Side Effects**: Replay engine performs strictly CPU-based deterministic computation. Zero live HTTP calls, zero live AI calls, zero live Razorpay queries, and zero production state mutations.
- **AI Independence**: Replay never invokes live LLMs; historical AI proposals are evaluated purely as untrusted, static advisory records.
- **Authoritative Engine Reuse**: Replay directly consumes T04 `evaluate_integrity`, T05 `TransactionStateMachine`, T06 authority hierarchy, and T07 `verify_mrdp_integrity` without duplicating business logic.
- **Three-Way Classification**: Categorizes replay outcomes into `MATCH` (agreement), `MISMATCH` (drift or tampering detected), or `INVALID_REPLAY` (illegal lifecycle transition or ambiguous event ordering).

## Next Task
**T14 — Control Room UI** (STOP — await explicit user instruction before starting T14)
