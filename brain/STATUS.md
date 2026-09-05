# STATUS.md — TarkaRaksha Execution State Tracker

## Project
**TarkaRaksha** — Agentic Transaction Integrity & Recovery Control Plane

## Current Phase
Innovation Extension

## Current Task
I19 — Merchant-Side Capability Graph

## Task Status
COMPLETE (C_I19 PASS)

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
- [x] **I5 — Buyer Agent** (Completed 2026-09-05)
- [x] **I8 — Agent / Transaction / Payment Binding** (Completed 2026-09-05)
- [x] **I6 — TIX: TarkaRaksha Integrity Exchange** (Completed 2026-09-05)
- [x] **I7 — Bounded Agentic Negotiation / Replanning** (Completed 2026-09-05)
- [x] **I9 — Deterministic Kill Switch / Execution Safety Control** (Completed 2026-09-05)
- [x] **I21 — Evidence-Aware AI Explanation** (Completed 2026-09-05)
- [x] **I10 — Operational Deployment Modes** (Completed 2026-09-05)
- [x] **I19 — Merchant-Side Capability Graph** (Completed 2026-09-05)

## Last Verified
2026-09-05T23:55:00+05:30 — I19 checkpoint

## Tests Run
- `make test-bootstrap`: PASS (all master brain files, zero root copies, pyproject valid, zero secrets)
- `make test-env`: PASS (toolchains verified, Next.js build clean, smoke tests pass)
- `pytest` (605 passed in 10.31s across all unit, integration, and adversarial suites: 569 baseline + 36 I19 tests)

## Environment & Toolchains Verified
- **Python**: 3.12.12 (via project-local `.venv`)
- **FastAPI**: 0.141.1, **Uvicorn**: 0.52.4, **Pydantic**: 2.13.5, **HTTPX**: 0.28.1, **Pytest**: 9.1.1
- **AI Client**: `groq` 1.7.0 (instantiation and live smoke test verified with `qwen/qwen3.8-27b`)
- **Payment Client**: `razorpay` 2.0.1 (live Test Mode order creation and HMAC-SHA256 signature verification verified)
- **Node.js**: v25.2.1, **npm**: 11.6.2
- **Frontend Stack**: Next.js 15.5.25 (App Router, Turbopack), TypeScript 5, Tailwind CSS 4, Lucide icons

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
- **Explicit Transaction Binding Invariant**: Replanning requires explicit, non-empty transaction_id. The system strictly forbids and rejects substituting intent_id for transaction_id.
- **Multi-Item Intent Projection Invariant**: Multi-item intents preserve all items in transaction proposals; no silent truncation or item dropping is permitted.
- **Clarification Over Guessing**: Insufficient constraints trigger explicit BuyerClarification requests instead of AI guessing.
- **Agent / Transaction / Payment Binding Invariant**: intent_id, agent_id, merchant_id, transaction_id, order_id, payment_id, and attempt_id are deterministically bound and strictly verified; matching amount alone is never sufficient to establish validity.
- **Global Order and Payment Uniqueness Invariant**: Order ID and Payment ID reuse across different transactions is strictly rejected with DRIFT / DUPLICATE errors.
- **Attempt Bounding & Replay Defense Invariant**: Consumed attempts cannot be reused for payment completion.
- **TIX Advisory Transport Invariant**: TIX transports claims across buyer, merchant, and control plane; TarkaRaksha deterministic logic verifies claims; zero payment authorization authority resides in TIX.
- **TIX Cryptographic Chain Continuity**: Sequential messages within a transaction exchange are deterministically hashed (SHA-256) and chained via previous_message_hash; any in-transit payload tampering or insertion is deterministically detected and rejected.
- **TIX Anti-Spoofing & Authority Invariant**: Non-TarkaRaksha participants (buyer_agent, merchant_agent) cannot emit AUTHORIZATION messages, claim authoritative OUTCOME, or embed rogue payment authorizations.
- **Kill Switch Execution Gating Invariant**: Safety states (RUNNING, PAUSED, REQUIRES_REVALIDATION, KILLED) deterministically gate financial actions; execution control is strictly separated from fact detection.
- **Forbidden Direct Resume Invariant**: Direct transition from KILLED to RUNNING is strictly prohibited; resuming a killed transaction unconditionally requires passing through authoritative revalidation.
- **Authoritative Revalidation Invariant**: Revalidation requires verified registered context matching (transaction_id, intent_id, agent_id, merchant_id) and at least one AUTHORITATIVE or PROTOCOL_TRUSTED evidence record; advisory LLM/agent claims are rejected.
- **Fail-Closed Execution Gate Invariant**: Unknown transactions, missing evidence, uninitialized context, or repeated UNKNOWNs above tolerance fail-closed by blocking execution.
-**Negotiation Proposal vs Authorization Invariant**: Negotiation may change the proposal, but negotiation must never change the authorization. The immutable IntentContract remains the authoritative, tamper-proof ceiling (`max_total`, allowed SKUs/substitutions, quantity ceiling, currency). Bounded remediation strictly enforces `max_rounds`, zero payment authorization authority, and mandatory deterministic revalidation.
- **Deterministic Bounded Loop Invariant**: Negotiation terminates deterministically within configured limits (`max_rounds = 3`, `max_replans = 3`), defaulting to `ABSTAINED` or `ESCALATED` rather than looping indefinitely or exhausting retries.
- **Evidence-Aware AI Explanation Invariant**: AI explanation is strictly descriptive and non-authoritative (`AI proposes -> evidence proves -> deterministic logic decides`). The explanation layer has zero authority to alter transaction decisions (`IntegrityStatus`), state machine progression (`TransactionState`), or execution safety gates (`KillSwitchState`).
- **Claim-to-Evidence Traceability Invariant**: Every substantive explanation claim must be anchored to verified `EvidenceReference` records with explicit authority rankings; hallucinated evidence IDs (e.g. `EVIDENCE-999`) or unsupported assertions fail post-generation validation.
- **Deterministic Fallback Guarantee**: If the AI model fails, times out, rate limits, returns malformed JSON, contradicts deterministic state, or attempts prompt injection, a structured deterministic fallback explanation is automatically produced. AI failure never causes transaction failure.
- **Uncertainty Preservation Invariant**: When deterministic status is `UNKNOWN`, explanations cannot manufacture certainty or claim transaction validity; missing evidence and uncertainties must be explicitly articulated.
- **Operational Mode Determinism & Separation Invariant**: Operational deployment modes (`SHADOW`, `GUARDED`, `HUMAN_REVIEW`) are deterministic control-plane policies. Detection remains active across all modes.
- **SHADOW Financial Non-Intervention Invariant**: In `SHADOW` mode, facts (`PASS`, `DRIFT`, `UNKNOWN`) and MRDP records are faithfully computed and recorded, but payment execution is never intervened with, and automated remediation is strictly prohibited.
- **GUARDED Bounded Control Invariant**: In `GUARDED` mode, automated remediation operates strictly within bounded policy limits (I7 negotiation); I9 safety gating (`KILLED`, `PAUSED`, `REQUIRES_REVALIDATION`) remains authoritative.
- **HUMAN_REVIEW Decision Boundary Invariant**: Human review is an explicit deterministic decision boundary requiring authenticated human operator review. AI models and autonomous agents are strictly forbidden from acting as reviewers.
- **Review Non-Bypass & Revalidation Invariant**: Human approval for a `DRIFT` transaction cannot fabricate `PASS` and unconditionally requires authoritative revalidation before payment execution can proceed. Human approval on a `KILLED` transaction cannot bypass execution safety revalidation.
- **Anti-Reuse Context Invariant**: Human review approvals and decisions are cryptographically bound to the 4-tuple (`transaction_id`, `intent_id`, `agent_id`, `merchant_id`) and can never be reused across disparate transactions, agents, or merchants.
- **Historical Replay Mode Isolation**: Historical replays strictly reconstruct transactions under their recorded operational mode from snapshot metadata, completely isolated from runtime deployment mode changes.
- **Merchant Capability Graph Representation Invariant**: The capability graph deterministically represents what a merchant can do, under what conditions (constraints), governed by which policy, and supported by which evidence.
- **Hard Scope Boundary — Zero Reputation / Trust Score Invariant**: TarkaRaksha strictly forbids and rejects merchant trust scores, agent reputation ratings, fraud ratings, or quality scores (§3, §34). Capability evaluation answers what is possible and permitted, not how trustworthy a merchant is.
- **Declared Capability ≠ Current Transaction Fact Invariant**: Declaring a capability (e.g. `INVENTORY` or `EXPRESS_SHIPPING`) does not establish current transaction truth. Capability evaluation verifies boundary conformance; authoritative evidence establishes transaction facts.
- **Cross-Merchant Capability Reuse Rejection Invariant**: Capabilities belonging to merchant A can never be evaluated, substituted, or applied to merchant B; evaluations are strictly bound to `merchant_id`.
- **Capability Graph Non-Authorization Invariant**: Capability graphs possess zero payment authorization authority and cannot bypass deterministic integrity (T04), I9 kill switch states (`KILLED`), or I10 operational review gates (`HUMAN_REVIEW`).
- **Negotiation Constraint Replanning Invariant**: Capability constraint failures produce structured replanning advice for Buyer Agent and I7 negotiation without altering immutable intent authorization bounds.
- **Historical Capability Graph Replay Invariant**: Replay strictly utilizes the historical `CapabilityGraphSnapshot` and version recorded at transaction time, guaranteeing that runtime merchant graph updates do not alter historical verification.

## Next Task
Await user instruction for next innovation extension milestone.



