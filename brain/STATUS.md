# STATUS.md — TarkaRaksha Execution State Tracker

## Project
**TarkaRaksha** — Agentic Transaction Integrity & Recovery Control Plane

## Current Phase
Innovation Extension

## Current Task
I4 — Merchant Agent

## Task Status
COMPLETE (C_I4 PASS)

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
- [x] **I0 — Baseline Freeze** (Completed 2026-09-05)
- [x] **I1 — Evidence Extensions** (Completed 2026-09-05)
- [x] **I2 — Security / Protocol Binding** (Completed 2026-09-05)
- [x] **I3 — Governance + Replay Extension** (Completed 2026-09-05)
- [x] **I4 — Merchant Agent** (Completed 2026-09-05)

## Last Verified
2026-09-05T20:10:00+05:30

## Tests Run
- `make test-bootstrap`: PASS (all master brain files, zero root copies, pyproject valid, zero secrets)
- `make test-env`: PASS (toolchains verified, Next.js build clean, smoke tests pass)
- `pytest` (335 passed in 1.58s across all unit, integration, and adversarial suites)


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
- **Additive Innovation**: Completed T01–T13 and I1–I2 functionality frozen; innovation extensions added strictly additively.
- **Evidence Freshness Invariant**: Freshness determined from explicit reference timestamps, not AI confidence. Stale or expired evidence cannot silently produce PASS.
- **Protocol Binding Invariant**: Explicit binding of intent_id, transaction_id, attempt_id, and agent identity. Tamper-evident message chaining via SHA-256 canonical hashing. Replayed consumed intents strictly blocked.
- **Governance & Replay Invariant**: Explicit attribution of every decision to rules_version and policy_version. Same inputs + same rules + same policy = same decision. Cryptographically verifiable Decision Reproducibility Certificate and side-effect-free counterfactual replay analysis.
- **Merchant Agent Authority Invariant**: Merchant proposals and offers are merchant-attested evidence (`MERCHANT_ATTESTED`, rank 50). The merchant agent cannot declare transaction PASS, override authoritative gateway evidence, convert UNKNOWN into PASS, or bypass deterministic rules.
- **Dynamic Offer Expiry Invariant**: Offers contain explicit `offer_expires_at` timestamps. Expired offers are rejected deterministically and prompt a refresh request.
- **Inventory & Fulfillment Integrity Invariant**: State transitions (e.g. stock depletion) trigger inventory drift detection. Deliveries breaching buyer deadlines trigger temporal fulfillment drift.

## Next Task
**I5 — Buyer Agent** (STOP — await explicit user prompt before starting I5)

