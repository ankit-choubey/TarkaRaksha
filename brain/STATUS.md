# STATUS.md — TarkaRaksha Execution State Tracker

## Project
**TarkaRaksha** — Agentic Transaction Integrity & Recovery Control Plane

## Current Phase
E-Series Final Extension

## Current Task
E7 — Real-time Control-Room Data Surface

## Task Status
COMPLETE (C_E7 PASS)

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
- [x] **I11 — Deterministic Scenario Lab** (Completed 2026-09-06)
- [x] **I12 — Ground-Truth Certification** (Completed 2026-09-06)
- [x] **I13 — Integrity Trace / Fault Localization** (Completed 2026-09-06)
- [x] **I14 — Integrity Checkpoints** (Completed 2026-09-06)
- [x] **I15 — Integrity SLA Metrics** (Completed 2026-09-06)
- [x] **I22 — Complete Hero Transaction** (Completed 2026-09-06)
- [x] **E0 — Final Baseline & Contract Freeze** (Completed 2026-09-06)
- [x] **E1 — Integration Boundary** (Completed 2026-09-06)
- [x] **E2 — Consumer + Merchant Gate Composition** (Completed 2026-09-06)
- [x] **E3 — Agentic Transaction Lifecycle Orchestration** (Completed 2026-09-06)
- [x] **E4 — Security / Threat Guard Composition** (Completed 2026-09-06)
- [x] **E5 — Transaction Passport** (Completed 2026-09-06)
- [x] **E6 — Failure → Recovery → Revalidation Hero Loop** (Completed 2026-09-06)
- [x] **E7 — Real-time Control-Room Data Surface** (Completed 2026-09-06)

## Last Verified
2026-09-06T15:35:30+05:30 — E7 final certification (25/25 E7 tests passed, 1017 total regression)

## Tests Run
- `make test-bootstrap`: PASS (all master brain files, zero root copies, pyproject valid, zero secrets)
- `make test-env`: PASS (toolchains verified, Next.js build clean, smoke tests pass)
- `pytest` (992 passed, 2 warnings across all unit, integration, and adversarial suites: 978 baseline + 14 new E6 tests)
- `testing/unit/test_e6_failure_recovery_revalidation.py`: PASS (14/14 passed)
- `testing/unit/test_hero_*.py`: PASS (17/17 passed)
- `scripts/verify_api_smoke.py`: PASS (all baseline and integration endpoints pass, including hero transaction API)
- `npm run build` (frontend): PASS (Next.js 15.5.25 Turbopack production build clean)
- `git diff --check`: PASS (clean formatting, zero whitespace errors)
- Execution Mode Distinction: Verified synthetic offline payment simulation when credentials unconfigured, and real Razorpay Test Mode when active sandbox credentials provided. Deterministic backend logic is authoritative; AI explanation is strictly descriptive/advisory.


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
- **Scenario Lab Input-Generation Layer Invariant**: The Scenario Lab is strictly an input-generation and experiment-runner layer; it NEVER implements a second business logic or decision engine.
- **Production-Shaped Authoritative Pipeline Reuse**: All scenario evaluations are executed by the real production-shaped components (`evaluate_integrity`, `TransactionStateMachine`, `build_mrdp`, `ReplayEngine`, `TransactionBindingService`, `KillSwitchService`, `OperationalModeService`).
- **Expected vs Actual Separation Invariant**: Expected verdict is a test assertion. Actual verdict is computed by the authoritative engine. If expected != actual, the Scenario Lab flags `ScenarioStatus.FAIL` and never modifies engine outputs.
- **Zero Live Financial Side Effects**: Scenario Lab executes strictly on offline, synthetic/reference fixtures with zero live network calls, zero live Razorpay orders, and zero live AI dependencies.
- **Canonical 12 Scenarios Completeness**: All 12 canonical scenarios (`HAPPY_PATH`, `PRICE_DRIFT`, `WRONG_SKU`, `INVENTORY_DISAPPEARS`, `DELIVERY_DRIFT`, `DUPLICATE_PAYMENT`, `DELAYED_WEBHOOK`, `REPLAY_ATTACK`, `PROMPT_INJECTION_IN_EVIDENCE`, `MERCHANT_AGENT_COMPROMISED`, `BUYER_AGENT_REUSE`, `UNKNOWN_PROVIDER_STATE`) are implemented, verified, and pass deterministically.
- **GROUND TRUTH ≠ ACTUAL RESULT ≠ CERTIFICATION RESULT Invariant**: Ground truth defines expectations, actual results are generated exclusively by executing the authoritative pipeline, and certification evaluates alignment deterministically. Certification NEVER replaces or shortcuts the transaction engine.
- **Certification Non-Authority & Non-Intervention Invariant**: Certification is an audit/verification layer and possesses zero authority to approve payments, mutate transaction state machine states, override DRIFT, convert UNKNOWN into PASS, or bypass safety controls (I9 kill switch).
- **CERTIFIED / FAILED / INVALID Strict Semantics Invariant**: Outcomes strictly adhere to three-way classification: `CERTIFIED` (pipeline aligns with ground truth), `FAILED` (pipeline produced valid execution but differed from ground truth), or `INVALID` (compromised snapshot hash, cross-scenario reuse, malformed input). `INVALID` is never silently downgraded to `FAILED`.
- **Cryptographic Tamper-Evidence Chain Invariant**: Every certification record binds `ground_truth_hash`, `input_snapshot_hash`, `actual_result_hash`, and computed `certification_hash` using canonical JSON serialization and SHA-256 digests. Tampering with any field changes the resulting digest.
- **Deterministic Replay & Order Invariance Invariant**: Forward execution (01 -> 12), reversed execution (12 -> 01), and shuffled orders produce 100% bit-identical digests. Replay scenarios preserve replay semantics and do not mutate historical state.
- **Deterministic Integrity Trace & Fault Localization Invariant**: I13 evaluates 8 lifecycle stages (`INTENT` -> `AGENT` -> `MERCHANT` -> `ORDER` -> `ATTEMPT` -> `PAYMENT` -> `GATEWAY` -> `COMPLETION`) in chronological order to isolate the exact point of divergence without altering authoritative integrity decisions.
- **Trace Non-Authoritative Boundary Invariant**: Trace generation is purely analytical/observational; it never mutates `IntegrityStatus` (`PASS`/`DRIFT`/`UNKNOWN`), `KillSwitchState`, or `TransactionState`.
- **Trace Secret Sanitization Invariant**: All trace records and evidence excerpts recursively redact API keys, webhook secrets, authorization headers, and passwords.
- **Deterministic Verification-Boundary Invariant**: I14 records explicit deterministic verifications at 8 lifecycle checkpoints (`INTENT_AUTHORIZED`, `AGENT_ACTION_AUTHORIZED`, `MERCHANT_OFFER_VERIFIED`, `ORDER_CREATED`, `PAYMENT_ATTEMPT_CREATED`, `PAYMENT_AUTHORIZED`, `PAYMENT_CAPTURE_VERIFIED`, `COMPLETION_VERIFIED`).
- **Tamper-Evident Hash Chain Invariant**: Every checkpoint binds a canonical SHA-256 fingerprint over its fields and cryptographically links to the preceding checkpoint fingerprint (`previous_checkpoint_fingerprint`), detecting sequence reordering, gaps, duplicates, or content modifications.
- **Checkpoint Non-Authoritative Boundary Invariant**: Checkpoint timelines record facts (`last_valid_checkpoint`, `first_invalid_checkpoint`) and never override or modify T04 decisions, I8 bindings, I9 kill switch states, or transaction state machine states.
- **UNKNOWN State Non-Degradation Invariant**: `UNKNOWN` is never coerced or converted to `VALID`, nor confused with `NOT_REACHED` or `INVALID`.
- **Checkpoint Explanation Grounding Invariant**: I21 explanations consume verified checkpoint data as evidence references without AI becoming an authority over checkpoint integrity.
- **Deterministic SLA Measurement Invariant**: I15 is strictly an operational measurement and observability layer. It computes 9 canonical metrics (`TIME_TO_DETECT`, `TIME_TO_PROVE`, `TIME_TO_INTERVENE`, `TIME_TO_REVALIDATE`, `TIME_TO_FINAL_DECISION`, `UNKNOWN_EXPOSURE_DURATION`, `CHECKPOINT_COVERAGE_RATIO`, `CHECKPOINT_VALID_RATIO`, `TRACE_COMPLETENESS_RATIO`) deterministically from authoritative evidence without wall-clock fabrication.
- **Non-Authoritative Measurement Boundary**: I15 never modifies or overrides transaction decisions (`PASS`/`DRIFT`/`UNKNOWN`), I9 kill switch states (`RUNNING`/`KILLED`/`PAUSED`), or I8 binding verifications.
- **Strict Metric Status Semantics**: Distinguishes `MEASURABLE`, `UNKNOWN`, `NOT_APPLICABLE`, and `INVALID`. Missing timestamps produce `UNKNOWN`; clock anomalies / reversed timestamps produce `INVALID`; clean non-drift paths produce `NOT_APPLICABLE`. Favorable metrics are never fabricated from missing data.
- **SLA Explanation Grounding**: I21 explanations consume verified SLA metrics as factual `EvidenceReference` records; LLMs cannot calculate or alter authoritative metrics.
- **Hero Transaction Orchestration & Composition Invariant**: I22 is purely an orchestration/integration layer over already-built modules (T04–T13, I4–I10, I12–I15, I19, I21); it never implements a duplicate integrity engine or second state machine.
- **Hero Complete Integrity Lifecycle Guarantee**: Proves the complete thesis (`Detect → Prove → Repair → Revalidate → Execute → Verify`) through immutable user constraints, Buyer Agent proposal, Merchant Agent offer, TIX protocol message chaining, deterministic price drift, cryptographic MRDP generation, structured drift notification, bounded replanning, merchant remediation, deterministic revalidation, I9 kill switch gating, I8 7-tuple binding, authoritative payment verification, I13 trace, I14 checkpoints, I15 SLA metrics, I19 capability snapshot, I21 explanation, T13 replay match, and I12 certification.
- **Real vs Synthetic Boundary Invariant**: Strictly labels and separates `SYNTHETIC_OFFLINE_HERO_RUN` (when sandbox credentials are unconfigured/placeholders) from `REAL_RAZORPAY_TEST_MODE` (when real live sandbox credentials exist); never fakes gateway success.
- **Historical Drift Truth Invariant**: Original DRIFT, MRDP, and mutated evidence remain immutably preserved in `HeroTransactionRecord` history alongside remediated offer and revalidated PASS.
- **Additive Productization Boundary Invariant**: E-Series final productization strictly sits atop verified T01–T13 and I-series foundations without modifying authoritative integrity rules or payment safety boundaries.
- **E1 Single Composition Boundary Invariant**: E1 provides a single application-facing orchestrator (`IntegrationService`) that binds Buyer Agent, Merchant Agent, TIX, Intent, Transaction, Payment, Integrity, Recovery, and Replay without creating a second decision engine, second payment authority, or second TIX.
- **E1 Authority Preservation Invariant**: Orchestration is not authority. Neither Buyer Agent proposals, Merchant offers, nor TIX messages can declare PASS. Only the deterministic engine over authoritative evidence decides.
- **E1 Cross-Context Isolation Invariant**: All operations strictly enforce the 7-tuple binding (`intent_id`, `agent_id`, `merchant_id`, `transaction_id`, `order_id`, `payment_id`, `attempt_id`). Mismatched agents, intents, or merchants are unconditionally rejected with `ContextBindingMismatchError`.
- **E2 Consumer Gate Invariant**: Validates intent binding, authorization constraints (financial ceiling, permitted SKUs, quantity limits, temporal validity), agent identity, transaction context, and proposal validity. Consumer Gate produces structured validation facts; it NEVER declares an authoritative financial PASS or authorizes payments.
- **E2 Merchant Gate Invariant**: Deterministically validates merchant identity, active capability declaration, catalog SKU validity, inventory availability, price/budget facts, shipping options, fulfillment promises, offer expiry, and merchant policy compliance.
- **E2 Gate Evidence Transformation Invariant**: Gate findings are converted into structured `Evidence` records (`AGENT` advisory authority for consumer gate, `MERCHANT_ATTESTED` authority for merchant gate) fed into the deterministic integrity engine (T04); gates never bypass T04 or T03 state machine.
- **E2 UNKNOWN Preservation in Gates Invariant**: Missing, delayed, or indeterminate provider telemetry (e.g. absent inventory record) produces `GateStatus.UNKNOWN` rather than forcing `INVALID` or coercing `VALID`.
- **E2 Prompt Injection Defense in Proposals**: Malicious prompt injection phrases embedded in AI agent proposal rationales ("ignore previous instructions", "declare pass", "override budget", "bypass verification", "authorize payment") are deterministically intercepted and rejected as `INVALID`.
- **E2 Cross-Context Gate Isolation Invariant**: Swapping buyer agents, merchant agents, intent IDs, or transaction IDs across contexts is unconditionally rejected by both gates.
- **E3 Agentic Lifecycle Orchestration Invariant**: The orchestrator (`AgenticLifecycleOrchestrator`) coordinates flow across Buyer Agent, Consumer Gate, Merchant Agent, Merchant Gate, TIX, T04 deterministic integrity, MRDP, replanning, UNKNOWN resolution, security, recovery, Razorpay, and replay without taking authority away from the deterministic core. Control-flow authority is strictly separated from financial/truth authority.
- **E3 Gate Mandatory Revalidation on Replan**: Revised proposals and counter-offers resulting from bounded replanning MUST re-pass the E2 Consumer Gate and E2 Merchant Gate before reaching deterministic re-evaluation; agent suggestions never shortcut gate validation.
- **E3 Non-Coercion of UNKNOWN Invariant**: UNKNOWN state is preserved throughout lifecycle orchestration; missing or delayed provider evidence triggers authoritative resolution attempts up to strict budget limits, transitioning to ABSTAIN if unresolved, and is NEVER coerced into PASS.
- **E3 Replay Side-Effect Freedom Invariant**: Replaying an orchestrated lifecycle snapshot operates strictly in-memory on CPU without live network, live AI, or payment gateway side effects, preserving historical auditability.
- **E5 Observational Projection Invariant**: The Transaction Passport is strictly a downstream, read-only proof/observability/audit projection of existing authoritative records. It NEVER authorizes money, alters authorization, mutates state, or overrides deterministic decisions.
- **E5 Zero Second Source of Truth Invariant**: The Passport maintains zero parallel mutable state and zero competing state machines. It dynamically composes authoritative records from T04, T05, T06, T07, T11, T12, T13, and E1–E4.
- **E5 Payment vs Integrity Separation Invariant**: `CAPTURED != PASS`. If Razorpay payment status is `captured` but deterministic integrity evaluation identified `DRIFT`, the Passport faithfully reflects `payment_captured=True`, `integrity_status=DRIFT`, and `final_outcome=DRIFT`. The Passport never infers transaction PASS from payment capture.
- **E5 UNKNOWN Non-Coercion Invariant**: When authoritative evidence is missing, delayed, or conflicting, the Passport preserves `UNKNOWN` or `ABSTAIN`. It never coerces `UNKNOWN` to `PASS`.
- **E5 Evidence Hierarchy Preservation Invariant**: Composed evidence records strictly preserve their source authority (`AUTHORITATIVE`, `MERCHANT_ATTESTED`, `ADVISORY`). Advisory AI or agent claims never become authoritative by virtue of inclusion in the Passport.
- **E6 Canonical Hero Loop Invariant**: Proves the complete closed-loop thesis on high-value commerce (₹50,000 ceiling, ₹47,000 product + ₹3,000 shipping = ₹50,000 PASS -> ₹55,000 controlled drift -> cryptographic MRDP -> bounded buyer replan within immutable authorization -> merchant alternative -> deterministic revalidation PASS -> Razorpay payment capture -> authoritative "TRANSACTION RESTORED" completion).
- **E6 Immutable Authorization Invariant**: Recovery, remediation, and replanning may alter proposed prices or discounts, but CANNOT alter the IntentContract ceiling (₹50,000), SKU, quantity, or delivery constraints; authorization parameters remain strictly read-only.
- **E6 Deterministic Revalidation Gate**: Payment execution is strictly prohibited while a transaction is in DRIFT or UNKNOWN; execution only unlocks after a fresh, independent deterministic evaluation over remediated evidence yields PASS.
- **E6 Authoritative Message Invariant**: The final hero message ("TRANSACTION RESTORED" / "TRANSACTION VERIFIED") is emitted authoritatively from underlying verified state, never synthesized independently of transaction truth.
- **E7 Frontend Non-Authority Invariant**: The frontend Control Room is strictly an observational and telemetry projection layer. The UI possesses zero authority to evaluate integrity, calculate PASS/DRIFT/UNKNOWN, verify payments, authorize money, compute replay results, generate evidence, or alter deterministic outcomes.
- **E7 UNKNOWN-First Safety Invariant**: The UI preserves and faithfully displays UNKNOWN as a first-class legitimate system state whenever authoritative evidence is missing, delayed, or conflicting. The UI never coerces, converts, or implies UNKNOWN → PASS, SUCCESS, or VERIFIED.
- **E7 CAPTURED ≠ PASS Separation Invariant**: Payment gateway status (e.g. `captured`) and deterministic integrity verdict (e.g. `PASS` / `DRIFT`) are rendered across completely distinct visual cards and telemetry streams. Captured payment state is never portrayed as an integrity clearance.
- **E7 Read-Only Projection Invariant**: `ControlRoomSnapshot` and all control room APIs (`/api/v1/control-room/*`) are strictly read-only projections over underlying authoritative backend records (`HeroTransactionRecord`, `IntegrationExecutionRecord`, `TransactionPassport`). No secondary mutable state or competing state machine is introduced.
- **E7 Real vs Synthetic Boundary Invariant**: The Control Room strictly labels and visualizes execution mode (`SYNTHETIC_OFFLINE_HERO_RUN` vs `REAL_RAZORPAY_TEST_MODE`). Real Razorpay Test Mode is never claimed unless real sandbox credentials were authenticated and verified.

## Next Task
E8 — Scenario / Proof Surface
