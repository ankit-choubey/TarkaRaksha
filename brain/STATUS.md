# STATUS.md — TarkaRaksha Execution State Tracker

## Project
**TarkaRaksha** — Agentic Transaction Integrity & Recovery Control Plane

## Current Phase
Innovation Extension

## Current Task
I5 — Buyer Agent

## Task Status
IN PROGRESS — implementation started; verification pending

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
- [ ] **I5 — Buyer Agent** (In progress)

## Last Verified
2026-09-05T20:10:00+05:30 — I4 checkpoint

## I5 Verification Status
- Focused tests: not yet executed in this environment
- Full regression: not yet executed in this environment
- Bootstrap/environment checks: not yet executed in this environment
- Do not mark I5 COMPLETE until actual execution verification is available.

## Key Invariants Maintained
- **Deterministic Replay Guarantee**: Identical IntentContract + identical ordered evidence + same rules version + same explicit reference time MUST yield an identical deterministic replay result.
- **Zero Side Effects**: Replay engine remains CPU-only and side-effect free.
- **AI Independence**: Replay never invokes live LLMs; historical AI proposals remain advisory.
- **Authoritative Engine Reuse**: Replay directly consumes the existing deterministic engine, state machine, evidence hierarchy, and MRDP verification.
- **Three-Way Classification**: Replay outcomes remain MATCH, MISMATCH, or INVALID_REPLAY.
- **Additive Innovation**: Completed T01–T13 and I0–I4 functionality remains protected; innovation extensions are additive.
- **Evidence Freshness Invariant**: Freshness is determined from explicit timestamps, not AI confidence.
- **Protocol Binding Invariant**: intent_id, transaction_id, attempt_id, and agent identity remain explicitly bound with tamper-evident SHA-256 message chaining.
- **Governance & Replay Invariant**: Decisions remain attributable to rules_version and policy_version.
- **Merchant Agent Authority Invariant**: Merchant offers remain merchant-attested evidence and cannot declare PASS or override authoritative payment evidence.
- **Buyer Agent Authority Invariant**: Buyer-agent proposals are projections of the immutable IntentContract; the buyer agent cannot authorize payment, alter authorized constraints, declare PASS, or turn insufficient evidence into PASS.

## Next Task
I5 is the active task. Do not start I6 until I5 reaches a verified checkpoint.
