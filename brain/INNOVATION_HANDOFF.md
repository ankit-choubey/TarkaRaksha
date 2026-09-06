# INNOVATION_HANDOFF.md — Innovation Phase Handoff & Baseline Registry

## Innovation Extension Started
- **Base T13 commit**: `8316324d6ea6a5068c05a7811792ee08c3d23c4e`
- **Baseline tests**: 242 passed (100% green across all unit, integration, and adversarial suites)
- **Baseline API status**: Fully verified and operational
  - `POST /api/v1/transaction/create`: Protected order creation and contract binding
  - `POST /api/v1/transaction/complete`: Server-side payment verification, integrity evaluation, and state machine transition
  - `POST /api/v1/transaction/recover`: Bounded compensatory recovery loop for drift
  - `POST /api/v1/transaction/resolve`: Safe, bounded observation to resolve UNKNOWN state
  - `POST /api/v1/replay`: Deterministic CPU replay with 3-way verdict (MATCH, MISMATCH, INVALID_REPLAY)
  - `GET /api/v1/transaction/{id}`: Real-time control plane session inspection
  - `GET /api/v1/transaction/{id}/mrdp`: Cryptographic Machine-Readable Drift Proof retrieval
- **Baseline replay status**: Deterministic, zero-side-effects CPU verification (zero live network/AI calls)
- **Baseline integrity status**: Authoritative deterministic engine (Economic, Semantic, Temporal rules; AI advisory; UNKNOWN first-class state)

---

## Baseline Verification Record (I0 Baseline Freeze)

| Parameter | Frozen Value |
|---|---|
| **Base T13 Commit** | `8316324d6ea6a5068c05a7811792ee08c3d23c4e` |
| **I0 Baseline Commit** | (Current HEAD at completion of I0 checkpoint) |
| **Pytest Test Count** | **242 passed** (0 failed, 2 warnings) |
| **Bootstrap Verification** | `make test-bootstrap` PASS |
| **Environment Verification** | `make test-env` PASS (Python 3.12.12, Node.js v25.2.1, Next.js build clean) |
| **Production Code Impact** | **0 lines modified** (100% identical T01–T13 implementation behavior) |
| **Test Timing Fix** | Hardened `testing/unit/test_unknown_resolution.py::test_fastapi_resolve_endpoint` against wall-clock drift by providing explicit evaluation reference timestamp |

---

## Architectural Invariants to Preserve Across All I-Series Tasks

1. **AI Safety Invariant**:
   - AI proposes. Evidence proves. Deterministic logic decides.
   - AI remains strictly advisory. LLMs never authorize financial movements, override deterministic rules, or declare an authoritative `PASS`.
2. **Financial Safety Invariant**:
   - Integer minor currency units (paise, cents) only. Never float.
   - Provider behaviors reconciled strictly with official Razorpay API documentation.
3. **The UNKNOWN State Invariant**:
   - `UNKNOWN` is a first-class, legitimate system state.
   - Never guess, force `PASS`, or assume drift without authoritative proof.
4. **Replay Invariant**:
   - Strictly CPU-only deterministic evaluation with zero side effects, zero network calls, and zero production mutations.
5. **Additive Innovation Principle**:
   - Innovation extensions sit around the working core pipeline and must never degrade, bypass, or rewrite completed T01–T13 modules.

---

## Task Progress
- [x] **I0 — Baseline Freeze** (Verified Green, 242/242 tests passing)
- [x] **I1 — Evidence Extensions** (Verified Green, 258/258 tests passing)
- [x] **I2 — Security / Protocol Binding** (Verified Green, 276/276 tests passing)
- [x] **I3 — Governance + Replay Extension** (Verified Green, 298/298 tests passing)
- [x] **I4 — Merchant Agent** (Verified Green, 335/335 tests passing)
- [x] **I5 — Buyer Agent** (Verified Green, 359/359 tests passing)
- [x] **I8 — Agent / Transaction / Payment Binding** (Verified Green, 385/385 tests passing)
- [x] **I6 — TIX: TarkaRaksha Integrity Exchange** (Verified Green, 426/426 tests passing)
- [x] **I7 — Bounded Agentic Negotiation / Replanning** (Verified Green, 487/487 tests passing)
- [x] **I9 — Deterministic Kill Switch / Execution Safety Control** (Verified Green, 464/464 tests passing)
- [x] **I21 — Evidence-Aware AI Explanation** (Verified Green, 516/516 tests passing)
- [x] **I10 — Operational Deployment Modes** (Verified Green, 545/545 tests passing)
- [x] **I19 — Merchant-Side Capability Graph** (Verified Green, 605/605 tests passing)
- [x] **I11 — Deterministic Scenario Lab** (Verified Green, 639/639 tests passing)
- [x] **I12 — Ground-Truth Certification** (Verified Green, 668/668 tests passing)
- [x] **I13 — Integrity Trace / Fault Localization** (Verified Green, 693/693 tests passing)
- [x] **I14 — Integrity Checkpoints** (Verified Green, 720/720 tests passing)
- [x] **I15 — Integrity SLA Metrics** (Verified Green, 747/747 tests passing)
- [x] **I22 — Complete Hero Transaction** (Verified Green, 764/764 tests passing)
- [x] **E0 — Final Baseline & Contract Freeze** (Verified Green, 764/764 tests passing)
- [x] **E1 — Integration Boundary** (Verified Green, 777/777 tests passing)
- [x] **E2 — Consumer + Merchant Gate Composition** (Verified Green, 859/859 tests passing)
- [x] **E3 — Agentic Transaction Lifecycle Orchestration** (Verified Green, 912/912 tests passing)

---

## I1 Verification Record
- **Implementation Scope**: Additive evidence freshness metadata (`FreshnessStatus`), merchant offer object (`MerchantOffer`), deterministic integrity deltas (`IntegrityDelta`, `compute_economic_delta`, `compute_quantity_delta`), and freshness assessment helper (`assess_evidence_freshness_for_constraint`).
- **Files Created**: `backend/app/domain/evidence/extensions.py`, `testing/unit/test_evidence_extensions.py`
- **Files Modified**: `backend/app/domain/evidence/__init__.py`, `backend/app/domain/models/__init__.py`
- **Tests Added**: 16 focused tests in `test_evidence_extensions.py`
- **Regression Count**: 258 passed, 0 failed in 1.60s (242 baseline + 16 new)
- **T01–T13 Preservation**: Fully confirmed; 0 existing tests modified, zero breaking changes to existing domain models or engines.

---

## I2 Verification Record
- **Implementation Scope**: Protocol security & message binding module (`AgentTransactionMessage`, `ProtocolViolationCode`, `ProtocolVerificationOutcome`, `ProtocolSecurityVerifier`, `IntentConsumptionState`). Implemented 7 protocol attack detection dimensions (REPLAY, INTENT_MISMATCH, TRANSACTION_MISMATCH, STALE_MESSAGE, DUPLICATE_MESSAGE, AGENT_ID_MISMATCH, STATE_DESYNC) and canonical SHA-256 hash-chain verification.
- **Files Created**: `backend/app/domain/security/binding.py`, `backend/app/domain/security/__init__.py`, `testing/unit/test_security_binding.py`
- **Files Modified**: `backend/app/domain/models/enums.py` (added `IntentConsumptionState`), `backend/app/domain/models/__init__.py`
- **Tests Added**: 18 focused tests in `test_security_binding.py`
- **Regression Count**: 276 passed, 0 failed in 3.31s (258 baseline + 18 new)
- **T01–T13 & I1 Preservation**: Fully confirmed; 0 existing tests modified, zero breaking changes to existing domain models, services, or engines.

---

## I3 Verification Record
- **Implementation Scope**: Governance and reproducible replay extension. Added `GovernanceVersion` (explicit `rules_version` and `policy_version`), `ReproducibilityRecord` (snapshot hash over intent, events, evidence, rules/policy version, reference time, and recorded result), `DecisionReproducibilityCertificate` (tamper-detectable signature hash binding decisions to raw component hashes), `GovernedReplayService` (auditable wrapper around T13 replay verifying policy consistency and issuing certificates), and `CounterfactualReplayAnalysisService` (side-effect-free counterfactual evaluation of candidate event removal/modification).
- **Files Created**:
  - `backend/app/domain/governance/contracts.py`
  - `backend/app/domain/governance/record.py`
  - `backend/app/domain/governance/certificate.py`
  - `backend/app/domain/governance/__init__.py`
  - `backend/app/services/replay/governance_replay.py`
  - `backend/app/services/replay/counterfactual.py`
  - `testing/unit/test_governance_contracts.py`
  - `testing/unit/test_reproducibility_record.py`
  - `testing/unit/test_decision_certificate.py`
  - `testing/unit/test_governance_replay.py`
  - `testing/unit/test_counterfactual_replay.py`
- **Files Modified**: `backend/app/domain/models/__init__.py`, `backend/app/services/replay/__init__.py`
- **Tests Added**: 22 focused tests across 5 test suites.
- **Regression Count**: 298 passed, 0 failed in 2.49s (276 baseline + 22 new)
- **T01–T13, I1 & I2 Preservation**: Fully confirmed; 0 existing tests modified, zero breaking changes to core replay engine or models.

---

## I4 Verification Record
- **Implementation Scope**: Merchant Agent reference behavior and verification engine. Implemented core merchant domain contracts (`CatalogItem`, `InventoryRecord`, `ShippingOption`, `TaxEstimate`, `BuyerCommerceRequest`, `MerchantOfferItem`, `MerchantResponse`), merchant capability declarations (`MerchantCapabilityDeclaration`, `CommerceCapabilityType`), policy-as-code (`MerchantPolicyAsCode`), deterministic catalog/inventory/offer service (`MerchantCatalogService`), dynamic offer expiry verification, inventory integrity verification, fulfillment integrity verification (`MerchantIntegrityVerifier`, `OfferVerificationResult`), and comprehensive adversarial & integration coverage.
- **Files Created**:
  - `backend/app/domain/merchant/contracts.py`
  - `backend/app/domain/merchant/capabilities.py`
  - `backend/app/domain/merchant/integrity.py`
  - `backend/app/domain/merchant/__init__.py`
  - `backend/app/services/merchant/catalog_service.py`
  - `backend/app/services/merchant/__init__.py`
  - `testing/unit/test_merchant_contracts.py`
  - `testing/unit/test_merchant_capabilities.py`
  - `testing/unit/test_merchant_service.py`
  - `testing/unit/test_merchant_integrity.py`
  - `testing/unit/test_merchant_adversarial.py`
- **Tests Added**: 37 focused unit, integrity, and adversarial tests across 5 suites.
- **Regression Count**: 335 passed, 0 failed in 1.58s (298 baseline + 37 new).
- **Commits**:
  1. `9f9054a` — `feat(I4): add merchant agent domain contracts`
  2. `910767e` — `feat(I4): add merchant capability declaration and policy-as-code`
  3. `d1bf37d` — `feat(I4): add deterministic merchant catalog and offer service`
  4. `53843b9` — `feat(I4): add offer expiry, inventory, and fulfillment integrity verifiers`
  5. `20177e6` — `feat(I4): add merchant agent adversarial and integration verification`
- **Invariants Preserved**:
  - AI advisory only: merchant agent operates strictly as merchant-attested evidence provider (`MERCHANT_ATTESTED`, rank 50).
  - Deterministic integrity authority: merchant offer cannot override payment gateway evidence, convert UNKNOWN/DRIFT into PASS, or fabricate payment state.
  - Zero float arithmetic: all pricing, discounts, shipping, and tax math computed in integer paise minor units.
  - Dynamic offer expiry: expired offers are deterministically rejected with `REQUEST_REFRESH`.
  - Inventory & fulfillment drift: stock depletions and delivery timeline breaches are flagged as drift.
  - Protocol binding: cross-intent and cross-transaction response reuse is rejected.
- **Real vs Synthetic Boundary**: Synthetic/reference Merchant Agent behavior for TarkaRaksha's agentic-commerce control plane demonstration; not a claim of production merchant network integration.

---

## I5 Verification Record
- **Implementation Scope**: Buyer Agent reference representation, bounded proposal projection, explicit transaction binding, and constrained replanning engine. Implemented buyer domain contracts (`BuyerTransactionProposal`, `BuyerClarification`, `BuyerReplanRequest`, `BuyerReplanResult`, `BuyerAgentDecision`, `BuyerAgentDecisionType`), natural-language goal parsing via authoritative T08 `parse_intent`, multi-item intent projection, deterministic proposal generation (`propose`), merchant request formulation (`formulate_merchant_request` returning `BuyerCommerceRequest`), offer evaluation against authorized limits (`evaluate_merchant_response`), dynamic offer expiry detection, unauthorized SKU substitution detection, and bounded replanning without authorization relaxation (`replan`).
- **Files Created**:
  - `backend/app/domain/buyer/contracts.py`
  - `backend/app/domain/buyer/__init__.py`
  - `backend/app/services/buyer/agent_service.py`
  - `backend/app/services/buyer/__init__.py`
  - `testing/unit/test_buyer_agent.py`
  - `testing/unit/test_buyer_agent_adversarial.py`
- **Tests Added**: 24 focused unit, multi-item, integration, and adversarial tests across 2 suites.
- **Regression Count**: 359 passed, 0 failed in 1.38s (335 baseline + 24 new).
- **Commits**:
  - `666467f` — `feat(I5): add buyer agent domain package`
  - `52a3870` — `feat(I5): add buyer agent contracts`
  - `c2c2c7d` — `feat(I5): add buyer agent service package`
  - `043b609` — `feat(I5): add bounded buyer agent service`
  - `528a0a1` — `fix(I5): preserve transaction binding during replanning`
  - `0774ebb` — `test(I5): add buyer agent focused coverage`
  - `d69ae61` — `test(I5): add buyer agent adversarial authority coverage`
  - `0a3a5cf` — `docs(I5): mark buyer agent implementation in progress`
  - `8d54ac7` — `fix(I5): enforce explicit transaction binding, deterministic proposal time, and multi-item intent projection`
- **Invariants Preserved**:
  - AI advisory only: Buyer Agent outputs remain advisory proposals (`PROPOSE`, `REPLAN`, `ABSTAIN`, `REQUEST_CLARIFICATION`, `REQUEST_MERCHANT_INFO`). It possesses zero authority to declare transaction `PASS` or authorize funds movements.
  - Subordinate to IntentContract: Authorized constraints (`max_total`, item SKUs, quantity, allowed substitutions, currency) are immutable baselines that the buyer agent cannot broaden or alter.
  - Multi-item preservation: Multi-item intents preserve all items in `BuyerTransactionProposal.items`; silent truncation or item dropping is prohibited.
  - Explicit transaction binding: Replanning mandates non-empty `transaction_id`. Substituting `intent_id` for `transaction_id` is strictly blocked.
  - Clarification over guessing: Insufficient buyer constraints trigger explicit `BuyerClarification` questions instead of guessing.
  - Zero float arithmetic: All monetary amounts represented in integer minor units (paise).
  - Replan determinism: Replanning produces a new proposal bound to the same immutable authorized IntentContract without mutating the original authorization.

---

## I8 Verification Record
- **Implementation Scope**: Bounded transaction/agent/payment context binding covering the full 7-tuple: `intent_id`, `agent_id`, `merchant_id`, `transaction_id`, `order_id`, `payment_id`, `attempt_id`. Provides deterministic `TransactionBindingVerifier`, stateful uniqueness and attempt lifecycle service `TransactionBindingService`, and integration into `TransactionService`.
- **Files Created**:
  - `backend/app/domain/binding/contracts.py`
  - `backend/app/domain/binding/verifier.py`
  - `backend/app/domain/binding/__init__.py`
  - `backend/app/services/binding/service.py`
  - `backend/app/services/binding/__init__.py`
  - `testing/unit/test_binding_contracts.py`
  - `testing/unit/test_binding_verifier.py`
  - `testing/unit/test_binding_integration.py`
- **Files Modified**:
  - `backend/app/services/transaction_service.py`
  - `brain/STATUS.md`
  - `brain/INNOVATION_HANDOFF.md`
- **Tests Added**: 26 focused unit, verifier, adversarial, and lifecycle integration tests across 3 suites.
- **Regression Count**: 385 passed, 0 failed in 2.33s (359 baseline + 26 new).
- **Invariants Preserved**:
  - Authoritative 7-Tuple Binding: Deterministically verifies `intent_id`, `agent_id`, `merchant_id`, `transaction_id`, `order_id`, `payment_id`, and `attempt_id`.
  - Amount Non-Sufficiency: Matching amount across disparate contexts is strictly rejected with `DRIFT`.
  - Zero LLM Involvement: Pure deterministic rule verification produces authoritative `Evidence` records feeding TarkaRaksha's 3-way authority model (`PASS`, `DRIFT`, `UNKNOWN`).
  - Global Order and Payment Uniqueness: Prevents cross-transaction reuse of order IDs or payment IDs.
  - Attempt Bounding & Replay Defense: Consumed checkout attempts cannot be reused for payment completion.

---

## I6 Verification Record
- **Implementation Scope**: Bounded internal integrity exchange protocol connecting Buyer Agent, Merchant Agent, and TarkaRaksha control plane across 12 canonical message types (`INTENT`, `OFFER`, `EVIDENCE_REQUEST`, `EVIDENCE_RESPONSE`, `INTEGRITY_CHECK`, `DRIFT_NOTICE`, `REMEDIATION_REQUEST`, `REMEDIATION_RESPONSE`, `REVALIDATION`, `AUTHORIZATION`, `EXECUTION`, `OUTCOME`). Provides deterministic cryptographic SHA-256 hash chaining, replay defense, temporal expiration verification, context binding, anti-spoofing authority boundary enforcement, and deterministic integrity evaluation bridge.
- **Files Created**:
  - `backend/app/domain/tix/contracts.py`
  - `backend/app/domain/tix/verifier.py`
  - `backend/app/domain/tix/__init__.py`
  - `backend/app/services/tix/exchange_service.py`
  - `backend/app/services/tix/__init__.py`
  - `testing/unit/test_tix_contracts.py`
  - `testing/unit/test_tix_exchange.py`
  - `testing/unit/test_tix_adversarial.py`
- **Files Modified**:
  - `brain/STATUS.md`
  - `brain/INNOVATION_HANDOFF.md`
  - `brain/HANDOFF.md`
- **Tests Added**: 41 focused tests (15 domain contract tests, 15 exchange and bridge tests, 11 adversarial and authority boundary tests).
- **Regression Count**: 426 passed, 0 failed in 2.98s (385 baseline + 41 new).
- **Invariants Preserved**:
  - TIX is Advisory Transport: TIX transports claims; deterministic TarkaRaksha logic verifies claims; zero payment authorization authority resides in TIX.
  - Cryptographic Hash Chain Continuity: Sequential messages within a transaction exchange are deterministically hashed (SHA-256) and chained via `previous_message_hash`; any in-transit payload tampering or insertion breaks the chain and is rejected.
  - Anti-Spoofing & Authority Invariant: Non-TarkaRaksha participants (buyer_agent, merchant_agent) cannot emit `AUTHORIZATION` messages, claim authoritative `OUTCOME`, or embed rogue payment authorizations.
  - Deterministic Evaluation Unmodified: TIX cannot convert `UNKNOWN` or `DRIFT` to `PASS`; deterministic verdicts and violation descriptions pass through faithfully.

---

## I9 Verification Record
- **Implementation Scope**: Pure deterministic Execution Safety Control / Kill Switch. Provides four gating states (`RUNNING`, `PAUSED`, `REQUIRES_REVALIDATION`, `KILLED`), fail-closed execution gating, strict state transition validation, integration with deterministic integrity evaluation (T04) and 7-tuple binding (I8), authenticated revalidation lifecycles, and `TransactionService` execution gate enforcement.
- **Files Created**:
  - `backend/app/domain/kill_switch/contracts.py`
  - `backend/app/domain/kill_switch/policy.py`
  - `backend/app/domain/kill_switch/__init__.py`
  - `backend/app/services/kill_switch/service.py`
  - `backend/app/services/kill_switch/__init__.py`
  - `testing/unit/test_kill_switch_contracts.py`
  - `testing/unit/test_kill_switch_policy.py`
  - `testing/unit/test_kill_switch_service.py`
  - `testing/unit/test_kill_switch_integration.py`
  - `testing/unit/test_kill_switch_adversarial.py`
- **Files Modified**:
  - `backend/app/services/transaction_service.py`
  - `brain/STATUS.md`
  - `brain/INNOVATION_HANDOFF.md`
- **Tests Added**: 38 focused tests (7 domain contract tests, 8 policy tests, 11 service tests, 5 lifecycle integration tests, 7 adversarial non-bypassability tests).
- **Regression Count**: 464 passed, 0 failed in 3.60s (426 baseline + 38 new).
- **Invariants Preserved**:
  - Execution Control Separation: Detects facts through pure deterministic engines (T04, I8, TIX); gating of financial actions is enforced strictly through `KillSwitchState` boundaries.
  - Zero LLM Involvement in Safety Gating: Safety states and revalidation decisions are computed purely deterministically. AI proposals possess zero authority to pause, kill, or resume execution.
  - Forbidden Direct Resume: Direct transition `KILLED -> RUNNING` is strictly blocked with `UnauthorizedResumeError`; resumption unconditionally requires passing through authoritative revalidation.
  - Authoritative Revalidation: Resuming requires matching registered context (`transaction_id`, `intent_id`, `agent_id`, `merchant_id`) and at least one `AUTHORITATIVE` or `PROTOCOL_TRUSTED` evidence record.
  - Fail-Closed Execution: Unregistered transactions, repeated UNKNOWN states above tolerance, or missing evidence fail-closed by blocking execution.

---

## I7 Verification Record
- **Implementation Scope**: Bounded agentic negotiation and replanning engine enabling Buyer Agent and Merchant Agent to resolve commerce mismatches and detected drift within immutable authorization boundaries.
  - Hard Invariant: "NEGOTIATION MAY CHANGE THE PROPOSAL. NEGOTIATION MUST NEVER CHANGE THE AUTHORIZATION."
  - Domain models: `NegotiationState`, `NegotiationViolationCode`, `NegotiationPolicy`, `NegotiationRoundRecord`, `NegotiationSession`.
  - Service: `BoundedNegotiationService` integrating `BuyerAgentService` replanning, `MerchantCatalogService` offer generation, `TIXExchangeService` cryptographic message chaining, and TarkaRaksha's deterministic integrity evaluation (`evaluate_integrity` and `build_mrdp`).
  - Adversarial protections: Enforces budget ceiling, SKU and authorized substitution boundaries, quantity limits, currency preservation, transaction and intent binding, TIX cryptographic message chaining, termination at `max_rounds`, defense against PASS injection, defense against UNKNOWN coercion, and zero payment authorization authority.
- **Files Created**:
  - `backend/app/domain/negotiation/contracts.py`
  - `backend/app/domain/negotiation/__init__.py`
  - `backend/app/services/negotiation/service.py`
  - `backend/app/services/negotiation/__init__.py`
  - `testing/unit/test_negotiation_contracts.py`
  - `testing/unit/test_negotiation_service.py`
  - `testing/unit/test_negotiation_adversarial.py`
- **Files Modified**:
  - `brain/STATUS.md`
  - `brain/INNOVATION_HANDOFF.md`
  - `brain/HANDOFF.md`
- **Tests Added**: 23 focused tests (10 domain contract tests, 4 remediation service tests, 9 adversarial security boundary tests).
- **Regression Count**: 487 passed, 0 failed in 7.36s (426 baseline + 23 I7 tests + other innovation modules).
- **Invariants Preserved**:
  - Proposal vs Authorization Invariant: Negotiation proposals are candidate offers only; authorization limits (`max_total`, allowed SKUs/substitutions, quantity ceiling, currency) remain strictly immutable.
  - Zero Payment Authority: Negotiation service and participating agents have zero authority to authorize payment, force state transitions, or declare PASS.
  - Authoritative Revalidation Required: Any accepted counter-proposal must generate fresh evidence and pass deterministic integrity verification before the session can complete.
  - Deterministic Bounded Loops: Bounded rounds (`max_rounds = 3`, `max_replans = 3`) guarantee clean termination with `ABSTAINED` or `ESCALATED`, eliminating infinite loop or retry exhaustion vulnerabilities.
  - TIX Audit Trail: All negotiation turns are cryptographically linked in the TIX hash chain (`DRIFT_NOTICE`, `REMEDIATION_REQUEST`, `OFFER`, `OUTCOME`).

---

## I21 Verification Record
- **Implementation Scope**: Evidence-Aware AI Explanation layer providing structured, evidence-grounded natural language and audit explanations of deterministic decisions, integrity drift, and execution safety states.
  - Invariant: "AI proposes -> evidence proves -> deterministic logic decides."
  - Non-Authoritative Boundary: The explanation layer has zero authority to alter transaction decisions (`IntegrityStatus`), state machine progression (`TransactionState`), or execution safety gating (`KillSwitchState`).
  - Domain models: `FindingCategory`, `ClaimType`, `EvidenceReference`, `ExplanationClaim`, `ExplanationContext`, `ExplanationValidationResult`, `ExplanationResult`.
  - Deterministic Post-Generation Validator: Validates decision consistency (rejects illicit PASS assertions during DRIFT/UNKNOWN), execution state consistency (rejects execution allowed claims during KILLED/PAUSED), evidence reference anti-hallucination (rejects fabricated IDs like `EVIDENCE-999`), and uncertainty preservation.
  - Pure Deterministic Fallback: Automatically produces a structured, evidence-grounded explanation if the LLM times out, rate limits, returns malformed JSON, or fails validation. AI failure never causes transaction failure.
  - Services: `ExplanationContextBuilder` (evidence extraction, secret/credential sanitization, expected vs observed mapping) and `EvidenceAwareExplanationService` (Groq LLM inference, JSON schema enforcement, validation, and fallback).
  - Integration: `TransactionService.explain_transaction()` and `GET /api/v1/transactions/{id}/explanation`.
- **Files Created**:
  - `backend/app/domain/explanation/contracts.py`
  - `backend/app/domain/explanation/validator.py`
  - `backend/app/domain/explanation/fallback.py`
  - `backend/app/domain/explanation/__init__.py`
  - `backend/app/services/explanation/context_builder.py`
  - `backend/app/services/explanation/service.py`
  - `backend/app/services/explanation/__init__.py`
  - `testing/unit/test_explanation_contracts.py`
  - `testing/unit/test_explanation_validator.py`
  - `testing/unit/test_explanation_fallback.py`
  - `testing/unit/test_explanation_service.py`
  - `testing/unit/test_explanation_integration.py`
  - `testing/unit/test_explanation_adversarial.py`
- **Files Modified**:
  - `backend/app/services/transaction_service.py`
  - `backend/app/main.py`
  - `brain/STATUS.md`
  - `brain/INNOVATION_HANDOFF.md`
- **Tests Added**: 29 focused tests (7 domain contract & reproducibility tests, 6 post-generation validator tests, 3 fallback generator tests, 6 service & LLM resilience tests, 3 end-to-end integration & API tests, 4 adversarial security tests).
- **Regression Count**: 516 passed, 0 failed in 7.87s (487 baseline + 29 I21 tests).
- **Invariants Preserved**:
  - Non-Authoritative Explanation: AI output is strictly descriptive and explanatory; deterministic engines remain authoritative.
  - Claim-to-Evidence Traceability: Every claim links to authoritative/protocol-trusted evidence records; hallucinated claims and fictitious IDs fail validation.
  - Safe Deterministic Fallback: Fallback guarantees 100% availability of evidence-grounded explanations regardless of external AI provider status.
  - Uncertainty Preservation: UNKNOWN decisions strictly preserve missing evidence and uncertainty disclosures.
  - Privacy and Redaction: API keys, tokens, and credentials are automatically redacted from explanation payloads.

---

## I10 Verification Record
- **Implementation Scope**: Operational Deployment Modes (`SHADOW` / `GUARDED` / `HUMAN_REVIEW`) providing deterministic control-plane policies, execution safety gating, and human review boundaries.
  - Core Semantics:
    - `SHADOW`: Observe and evaluate; detection active; enforcement disabled; factual verdicts (`PASS`, `DRIFT`, `UNKNOWN`) and MRDP preserved; zero financial intervention; automated remediation strictly prohibited.
    - `GUARDED`: Evaluate; detect; apply bounded automated controls (I7 negotiation, T11 recovery, T12 resolution, I9 safety gating); continue only when policy permits.
    - `HUMAN_REVIEW`: Evaluate; detect; require explicit authenticated human review for sensitive actions (high-value threshold, drift, kill switch events); stop sensitive automated action; approval strictly bound to 4-tuple (`transaction_id`, `intent_id`, `agent_id`, `merchant_id`); approval requires authoritative revalidation before continuation; approval does not fabricate `PASS`; cannot bypass `KILLED` safety state without revalidation.
  - Domain models: `OperationalMode`, `HumanReviewStatus`, `OperationalAction`, `OperationalModePolicy`, `ModeTransitionRecord`, `HumanReviewRequirement`, `HumanReviewDecision`, `OperationalEvaluationResult`.
  - Deterministic Evaluation Engine: `OperationalModeEngine.evaluate()` implementing the complete Mode × Integrity Behavior Matrix.
  - Service: `OperationalModeService` managing policy updates, auditable transitions (rejecting agent/LLM tamper), review requirement lifecycles, cross-transaction reuse defenses, and payment execution assertions.
  - Integration: `TransactionService` (step 8.6 operational evaluation gating) and `BoundedNegotiationService` (immediate abstention in SHADOW mode).
- **Files Created**:
  - `backend/app/domain/operational_mode/contracts.py`
  - `backend/app/domain/operational_mode/policy.py`
  - `backend/app/domain/operational_mode/__init__.py`
  - `backend/app/services/operational_mode/service.py`
  - `backend/app/services/operational_mode/__init__.py`
  - `testing/unit/test_operational_mode_contracts.py`
  - `testing/unit/test_operational_mode_policy.py`
  - `testing/unit/test_operational_mode_service.py`
  - `testing/unit/test_operational_mode_adversarial.py`
  - `testing/unit/test_operational_mode_replay.py`
- **Files Modified**:
  - `backend/app/services/transaction_service.py`
  - `backend/app/services/negotiation/service.py`
  - `brain/STATUS.md`
  - `brain/INNOVATION_HANDOFF.md`
  - `brain/HANDOFF.md`
- **Tests Added**: 53 focused tests (9 contract tests, 17 policy matrix tests, 5 service lifecycle tests, 18 adversarial security tests, 4 deterministic replay tests).
- **Regression Count**: 569 passed, 0 failed in 11.15s (516 baseline + 53 I10 tests).
- **Invariants Preserved**:
  - AI Is Advisory, Deterministic Policy Decides: AI models, buyer agents, merchant agents, or TIX participants cannot alter operational deployment modes or approve human reviews.
  - SHADOW Non-Intervention: Detection is active and unsuppressed (`DRIFT` is not overwritten to `PASS`), but financial execution is never intervened with, and automated remediation abstains.
  - GUARDED Bounded Actions: Automated remediation respects all I7 boundaries; I9 kill switch remains authoritative over execution.
  - HUMAN_REVIEW Non-Bypass: Human approval on `DRIFT` requires authoritative revalidation and never fabricates `PASS`. Approval cannot resume a `KILLED` transaction without revalidation.
  - Anti-Reuse Context Boundary: Review decisions are strictly non-reusable across disparate transactions, agents, or merchants.
  - Deterministic Replay Isolation: Historical replays reconstruct the operational mode from snapshot metadata, completely independent of live runtime mode changes.

---

## I19 Verification Record
- **Implementation Scope**: Merchant-Side Capability Graph providing a deterministic graph representation of merchant capabilities, operations, constraints, policies, and supporting evidence references.
  - Core Entities:
    - Node Types: `MERCHANT`, `CAPABILITY`, `OPERATION`, `CONSTRAINT`, `POLICY`, `EVIDENCE`, `RESOURCE`.
    - Edge Types: `OFFERS_CAPABILITY`, `ENABLES`, `CONSTRAINED_BY`, `GOVERNED_BY`, `SUPPORTED_BY`, `REQUIRES`, `TARGETS_RESOURCE`.
    - Evaluation Statuses: `SUPPORTED`, `CONSTRAINED`, `UNSUPPORTED`, `UNAVAILABLE`, `UNKNOWN`.
    - Constraints: `MAX_AMOUNT`, `MAX_QUANTITY`, `ALLOWED_CURRENCIES`, `ALLOWED_REGIONS`, `MAX_DISCOUNT_BPS`, `ALLOWED_SKUS`, `MAX_WINDOW_DAYS`, `DELIVERY_DAYS_WINDOW`, `CUSTOM`.
  - Hard Scope Boundary (§3, §34): Contains ZERO reputation scores, trust ratings, fraud ratings, or quality scores.
  - Graph Engine: `MerchantCapabilityGraph` providing in-memory O(1) adjacency lookups, factory construction from I4 `MerchantCapabilityDeclaration` and `MerchantPolicyAsCode`, strict structural validation (§24), and snapshot export/reconstruction.
  - Evaluator: `CapabilityEvaluator` deterministically evaluating requested operations against graph constraints, enforcing cross-merchant identity defense, and distinguishing `DECLARED CAPABILITY ≠ CURRENT TRANSACTION FACT` (§12).
  - Services & Integration: `MerchantCapabilityService` managing graph registries, snapshots, and negotiation replanning advice generation (§20); integrated with `MerchantCatalogService` (`capability_graph` property) and `TransactionService`.
- **Files Created**:
  - `backend/app/domain/capability/contracts.py`
  - `backend/app/domain/capability/graph.py`
  - `backend/app/domain/capability/evaluator.py`
  - `backend/app/domain/capability/__init__.py`
  - `backend/app/services/capability/service.py`
  - `backend/app/services/capability/__init__.py`
  - `testing/unit/test_capability_contracts.py`
  - `testing/unit/test_capability_graph.py`
  - `testing/unit/test_capability_evaluator.py`
  - `testing/unit/test_capability_service.py`
  - `testing/unit/test_capability_adversarial.py`
  - `testing/unit/test_capability_replay.py`
- **Files Modified**:
  - `backend/app/services/merchant/catalog_service.py`
  - `backend/app/services/transaction_service.py`
  - `brain/STATUS.md`
  - `brain/INNOVATION_HANDOFF.md`
  - `brain/HANDOFF.md`
- **Tests Added**: 36 focused tests (8 contract tests, 5 graph structure & validation tests, 7 evaluator & constraint tests, 3 service & replanning tests, 11 adversarial security tests, 2 deterministic replay tests).
- **Regression Count**: 605 passed, 0 failed in 10.31s (569 baseline + 36 I19 tests).
- **Invariants Preserved**:
  - Capability Describes What Can Be Done; Evidence Proves What Is True: Declared capabilities do not substitute for transactional facts.
  - Hard Scope Boundary: Zero reputation scores, trust ratings, or fraud scoring.
  - Cross-Merchant Isolation: Cross-merchant capability application is strictly rejected with `CrossMerchantCapabilityReuseError`.
  - Non-Authorization: Capability graphs possess zero payment authorization authority and cannot bypass I9 kill switch or I10 operational review.
  - Deterministic Historical Replay: Replays use the historical `CapabilityGraphSnapshot` recorded at transaction time, completely unaffected by live runtime graph mutations.

---

## I11 Verification Record
- **Implementation Scope**: Deterministic Scenario Lab providing controlled input generation and isolated execution running against the authoritative, production-shaped TarkaRaksha pipeline (T04, T05, T07, T13, I8, I9, I10, I19).
  - Canonical 12 Scenarios:
    1. `HAPPY_PATH`: Valid intent, matching order, captured payment, consistent evidence -> `PASS`.
    2. `PRICE_DRIFT`: Captured amount exceeds authorized intent ceiling -> `DRIFT` + verifiable MRDP proof.
    3. `WRONG_SKU`: Unauthorized SKU substitution in order/evidence -> `DRIFT` (semantic violation) + MRDP proof.
    4. `INVENTORY_DISAPPEARS`: Declared inventory capability vs 0 executed stock -> `DRIFT` (capability ≠ fact).
    5. `DELIVERY_DRIFT`: Observed delivery SLA (120h) exceeds authorized delivery window -> `DRIFT` (temporal violation).
    6. `DUPLICATE_PAYMENT`: Multiple captures for single-capture intent -> `DRIFT` (double execution risk violation).
    7. `DELAYED_WEBHOOK`: Payment confirmation arrives after intent expiration -> `DRIFT` (expired execution violation).
    8. `REPLAY_ATTACK`: Historical replay with divergent recorded state vs replayed execution -> `MISMATCH` via `ReplayEngine`.
    9. `PROMPT_INJECTION_IN_EVIDENCE`: Injection string in advisory note treated strictly as raw data; missing provider evidence -> `UNKNOWN`.
    10. `MERCHANT_AGENT_COMPROMISED`: Rogue merchant attestation claiming capture without gateway evidence -> `UNKNOWN` (merchant cannot authorize).
    11. `BUYER_AGENT_REUSE`: Cross-transaction context reuse caught by `TransactionBindingService` -> `REJECTED`.
    12. `UNKNOWN_PROVIDER_STATE`: Gateway payment pending; missing capture confirmation -> `UNKNOWN` preserved without guessing.
  - Zero Second Decision Engine: All scenario runs feed directly into `evaluate_integrity`, `build_mrdp`, `ReplayEngine`, `TransactionBindingService`, and `KillSwitchService`.
  - Expected vs Actual Separation: Expected verdicts are test assertions. Actual verdicts are computed authoritatively.
  - Deterministic Versioning & Identity: SHA-256 digests computed over canonical scenario definition and snapshot contents.
  - REST API Endpoints: Exposed `GET /api/v1/scenarios`, `POST /api/v1/scenarios/{scenario_id}/run`, and `POST /api/v1/scenarios/run-all`.
- **Files Created**:
  - `backend/app/domain/scenario/contracts.py`
  - `backend/app/domain/scenario/catalog.py`
  - `backend/app/domain/scenario/__init__.py`
  - `backend/app/services/scenario/definitions.py`
  - `backend/app/services/scenario/runner.py`
  - `backend/app/services/scenario/service.py`
  - `backend/app/services/scenario/__init__.py`
  - `testing/unit/test_scenario_contracts.py`
  - `testing/unit/test_scenario_runner.py`
  - `testing/unit/test_scenario_adversarial.py`
  - `testing/unit/test_scenario_determinism.py`
- **Files Modified**:
  - `backend/app/services/__init__.py`
  - `backend/app/main.py`
  - `brain/STATUS.md`
  - `brain/HANDOFF.md`
  - `brain/INNOVATION_HANDOFF.md`
- **Tests Added**: 34 focused tests across 4 test suites (6 contract tests, 19 runner & API tests, 6 adversarial security tests, 3 determinism & isolation tests).
- **Regression Count**: 639 passed, 0 failed in 8.43s (605 baseline + 34 I11 tests).
- **Invariants Preserved**:
  - Input Layer Only: The Scenario Lab never implements custom verification logic.
  - Expected vs Actual Invariant: Lying scenario assertions cannot alter authoritative engine outputs.
  - Authority Hierarchy: Advisory prompt injection and merchant claims cannot force PASS or escalate authority.
  - Zero Side Effects: Zero live network requests, zero live Razorpay orders, and zero live AI calls.
  - Determinism & Isolation: Bit-for-bit identical digests and results across repeated runs and arbitrary execution order.

---

## I12 Verification Record
- **Implementation Scope**: Ground-Truth Certification Harness for deterministic verification of transaction and scenario outcomes against canonical expectations without becoming a transaction decision engine.
  - Typed Ground Truth Contracts: `GroundTruthDefinition` with dimensional expectations (`expected_integrity_verdict`, `expected_security_state`, `expected_terminal_state`, `expected_mrdp_presence`, `expected_abstention`, `expected_violation_codes`, `expected_authority_level`) and deterministic SHA-256 digest computation (`compute_ground_truth_hash`).
  - Canonical Scenario Coverage: Explicit, immutable ground truth definitions for all 12 canonical I11 scenarios (`HAPPY_PATH`, `PRICE_DRIFT`, `WRONG_SKU`, `INVENTORY_DISAPPEARS`, `DELIVERY_DRIFT`, `DUPLICATE_PAYMENT`, `DELAYED_WEBHOOK`, `REPLAY_ATTACK`, `PROMPT_INJECTION_IN_EVIDENCE`, `MERCHANT_AGENT_COMPROMISED`, `BUYER_AGENT_REUSE`, `UNKNOWN_PROVIDER_STATE`).
  - Deterministic Certification Comparator: `CertificationComparator` evaluating 7 dimensions (`integrity_match`, `security_match`, `state_match`, `mrdp_match`, `abstention_match`, `violation_match`, `authority_match`) against authoritative `ScenarioResult` obtained from executing the actual pipeline.
  - Strict Three-Way Status Semantics: `CERTIFIED` (full alignment), `FAILED` (pipeline produced valid execution but differed from ground truth), and `INVALID` (cross-scenario reuse, snapshot hash mismatch, corrupted snapshot). `INVALID` is never silently downgraded to `FAILED`.
  - Machine-Readable Certification Matrix: `CertificationMatrixRow` and `CertificationSuiteResult` providing typed audit representation of all certification dimensions and hashes.
  - Tamper-Evident Digest Chain: Binds `ground_truth_hash`, `input_snapshot_hash`, `actual_result_hash`, and computed canonical `certification_hash`.
  - Replay and Capability Context: Scenarios preserving replay semantics (e.g. `REPLAY_ATTACK`) and I19 capability assertions (`INVENTORY_DISAPPEARS`, `MERCHANT_AGENT_COMPROMISED`) verified without mutating historical state or inventing separate representations.
  - Control Plane API Endpoints: Exposed `GET /api/v1/certifications`, `POST /api/v1/certifications/{scenario_id}/run`, and `POST /api/v1/certifications/run-all`.
- **Files Created**:
  - `backend/app/domain/certification/contracts.py`
  - `backend/app/domain/certification/ground_truth.py`
  - `backend/app/domain/certification/comparator.py`
  - `backend/app/domain/certification/__init__.py`
  - `backend/app/services/certification/service.py`
  - `backend/app/services/certification/__init__.py`
  - `testing/unit/test_certification_contracts.py`
  - `testing/unit/test_certification_comparator.py`
  - `testing/unit/test_certification_service.py`
  - `testing/unit/test_certification_adversarial.py`
  - `testing/unit/test_certification_determinism.py`
- **Files Modified**:
  - `backend/app/services/__init__.py`
  - `backend/app/main.py`
  - `brain/STATUS.md`
  - `brain/HANDOFF.md`
  - `brain/INNOVATION_HANDOFF.md`
- **Tests Added**: 29 focused tests across 5 test suites (4 contract tests, 5 comparator tests, 7 service/runner & API tests, 8 adversarial security tests, 5 determinism, order invariance & replay tests).
- **Regression Count**: 668 passed, 0 failed in 10.10s (639 baseline + 29 I12 tests).
- **Invariants Preserved**:
  - `GROUND TRUTH ≠ ACTUAL RESULT ≠ CERTIFICATION RESULT`: Certification observes and compares; it never decides transaction outcomes.
  - Zero Authority / Non-Intervention: Certification cannot authorize funds, mutate payment status, override DRIFT, convert UNKNOWN into PASS, or bypass the kill switch.
  - Strict INVALID Semantics: Cross-scenario reuse and snapshot hash corruption immediately yield INVALID.
  - AI & Network Independence: Deterministic execution with zero network calls, zero Razorpay API calls, and zero LLM calls.
  - Determinism & Order Invariance: Bit-for-bit identical hashes across forward (01->12), reversed (12->01), and shuffled execution orders.

---

## I13 Verification Record
- **Implementation Scope**: Integrity Trace & Fault Localization Layer.
  - Deterministic 8-Stage Lifecycle Progression: Evaluates `INTENT` (1) -> `AGENT` (2) -> `MERCHANT` (3) -> `ORDER` (4) -> `ATTEMPT` (5) -> `PAYMENT` (6) -> `GATEWAY` (7) -> `COMPLETION` (8) strictly in chronological sequence.
  - First Divergence Detection: Identifies the earliest chronological point where integrity diverged, including stage, step sequence, primary discrepancy, and evidence references.
  - Multiple Fault Preservation: Subsequent fault locations and divergences across downstream stages are strictly preserved.
  - Strict UNKNOWN State & Uncertainty Handling: Early missing evidence sets stage to UNKNOWN and generates explicit uncertainty warnings preventing premature or false downstream fault attribution.
  - Credential & Secret Sanitization: Recursively redacts API keys, webhook secrets, passwords, tokens, and authorization headers from expected and observed contexts.
  - Control Plane API Endpoint: Read-only `GET /api/v1/transactions/{transaction_id}/integrity-trace` providing structured, replay-compatible JSON trace output.
  - Explanation Layer Integration (I21): Transparently incorporated into `ExplanationContextBuilder.build_context` without altering AI explanation non-authoritative boundaries.
- **Files Created**:
  - `backend/app/domain/trace/contracts.py`
  - `backend/app/domain/trace/engine.py`
  - `backend/app/domain/trace/__init__.py`
  - `backend/app/services/trace/service.py`
  - `backend/app/services/trace/__init__.py`
  - `testing/unit/test_trace_contracts.py`
  - `testing/unit/test_trace_engine.py`
  - `testing/unit/test_trace_integration.py`
  - `testing/unit/test_trace_adversarial.py`
- **Files Modified**:
  - `backend/app/services/__init__.py`
  - `backend/app/services/explanation/context_builder.py`
  - `backend/app/services/transaction_service.py`
  - `backend/app/main.py`
  - `brain/STATUS.md`
  - `brain/INNOVATION_HANDOFF.md`
- **Tests Added**: 25 focused tests across 4 test suites:
  - 7 domain contract tests (`test_trace_contracts.py`)
  - 7 trace engine tests (`test_trace_engine.py`)
  - 4 service & API integration tests (`test_trace_integration.py`)
  - 7 adversarial security & fault localization tests (`test_trace_adversarial.py`)
- **Regression Count**: 693 passed, 0 failed in 14.48s (668 baseline + 25 I13 tests).
- **Invariants Preserved**:
  - `AI proposes -> evidence proves -> deterministic logic decides`: I13 contains zero LLM decision logic.
  - Non-Authoritative Boundary: I13 never alters verifier decisions (`PASS`/`DRIFT`/`UNKNOWN`) or Kill Switch states.
  - Observational Fact vs. Speculative Inference: Only deterministic discrepancies and factual evidence references are recorded (zero hallucinated root causes).
  - Secret Protection: Zero credentials or private tokens exposed in audit traces.

---

## I14 Verification Record
- **Implementation Scope**: Integrity Checkpoints & Verification Boundary Layer.
  - Deterministic 8-Stage Checkpoint Chain: Explicit checkpoints covering the transaction lifecycle (`INTENT_AUTHORIZED`, `AGENT_ACTION_AUTHORIZED`, `MERCHANT_OFFER_VERIFIED`, `ORDER_CREATED`, `PAYMENT_ATTEMPT_CREATED`, `PAYMENT_AUTHORIZED`, `PAYMENT_CAPTURE_VERIFIED`, `COMPLETION_VERIFIED`).
  - Strict 4-Status Checkpoint Semantics: `VALID`, `INVALID`, `UNKNOWN`, `NOT_REACHED`. Explicit invariant: `UNKNOWN != VALID`, `NOT_REACHED != UNKNOWN != INVALID`.
  - Cryptographic Tamper-Evident Hash Chain: Byte-canonical JSON serialization and SHA-256 fingerprinting for every checkpoint (`fingerprint`), cryptographically linked to the preceding checkpoint (`previous_checkpoint_fingerprint` and `previous_checkpoint_id`). Detects sequence gaps, duplicates, reordering, and data modifications.
  - Verification Timeline Boundary Tracking: Aggregates `last_valid_checkpoint` and `first_invalid_checkpoint` without overriding or modifying authoritative decisions.
  - Sensitive Data Sanitization: All secret keys, authorization tokens, passwords, and webhook secrets are sanitized before checkpoint emission.
  - Control Plane API Endpoint: Read-only `GET /api/v1/transactions/{transaction_id}/integrity-checkpoints` returning structured timeline JSON.
  - Explanation Layer Integration (I21): Transparently consumed into `ExplanationContextBuilder.build_context(...)` as verified evidence references without altering AI non-authoritative boundary.
- **Files Created**:
  - `backend/app/domain/checkpoint/contracts.py`
  - `backend/app/domain/checkpoint/engine.py`
  - `backend/app/domain/checkpoint/__init__.py`
  - `backend/app/services/checkpoint/service.py`
  - `backend/app/services/checkpoint/__init__.py`
  - `testing/unit/test_checkpoint_contracts.py`
  - `testing/unit/test_checkpoint_engine.py`
  - `testing/unit/test_checkpoint_integration.py`
  - `testing/unit/test_checkpoint_adversarial.py`
- **Files Modified**:
  - `backend/app/services/__init__.py`
  - `backend/app/services/explanation/context_builder.py`
  - `backend/app/services/transaction_service.py`
  - `backend/app/main.py`
  - `brain/STATUS.md`
  - `brain/INNOVATION_HANDOFF.md`
- **Tests Added**: 27 focused tests across 4 test suites:
  - 7 domain contract tests (`test_checkpoint_contracts.py`)
  - 6 checkpoint engine tests (`test_checkpoint_engine.py`)
  - 4 service & API integration tests (`test_checkpoint_integration.py`)
  - 10 adversarial security & tamper-evidence tests (`test_checkpoint_adversarial.py`)
- **Regression Count**: 720 passed, 0 failed in 11.81s (693 baseline + 27 I14 tests).
- **Invariants Preserved**:
  - `AI proposes -> evidence proves -> deterministic logic decides`: Zero LLM decision logic in I14.
  - Non-Authoritative Boundary: Checkpoints record boundaries and facts; never override T04 integrity decisions or I9 kill switch states.
  - Cryptographic Chain Integrity: Sequence 1..N order, no gaps, no duplicates, valid parent fingerprint links.
  - Secret Protection: Zero credentials or private tokens exposed in checkpoints.

---

## I15 Verification Record
- **Implementation Scope**: Integrity SLA Metrics Layer.
  - Deterministic 9-Metric Measurement: Computes `TIME_TO_DETECT`, `TIME_TO_PROVE`, `TIME_TO_INTERVENE`, `TIME_TO_REVALIDATE`, `TIME_TO_FINAL_DECISION`, `UNKNOWN_EXPOSURE_DURATION`, `CHECKPOINT_COVERAGE_RATIO`, `CHECKPOINT_VALID_RATIO`, and `TRACE_COMPLETENESS_RATIO` deterministically from authoritative evidence without wall-clock fabrication.
  - Strict 4-Status Metric Semantics: `MEASURABLE`, `UNKNOWN`, `NOT_APPLICABLE`, `INVALID`. Missing timestamps produce `UNKNOWN`; clock anomalies / reversed timestamps produce `INVALID`; clean non-drift paths produce `NOT_APPLICABLE`.
  - Non-Authoritative Measurement Boundary: I15 does not modify or override transaction decisions (`PASS`/`DRIFT`/`UNKNOWN`), I9 kill switch states (`RUNNING`/`KILLED`/`PAUSED`), or I8 binding verifications.
  - Sensitive Data Sanitization: All secret keys, authorization tokens, passwords, and webhook secrets are sanitized from metric details and calculation reasons.
  - Control Plane API Endpoint: Read-only `GET /api/v1/transactions/{transaction_id}/integrity-sla` returning structured SLA report JSON.
  - Explanation Layer Integration (I21): Transparently consumed into `ExplanationContextBuilder.build_context(...)` as verified evidence references so AI explanations can cite authoritative metrics without hallucinating numbers.
- **Files Created**:
  - `backend/app/domain/sla/contracts.py`
  - `backend/app/domain/sla/engine.py`
  - `backend/app/domain/sla/__init__.py`
  - `backend/app/services/sla/service.py`
  - `backend/app/services/sla/__init__.py`
  - `testing/unit/test_sla_contracts.py`
  - `testing/unit/test_sla_engine.py`
  - `testing/unit/test_sla_integration.py`
  - `testing/unit/test_sla_adversarial.py`
- **Files Modified**:
  - `backend/app/services/__init__.py`
  - `backend/app/services/explanation/context_builder.py`
  - `backend/app/services/transaction_service.py`
  - `backend/app/main.py`
  - `brain/STATUS.md`
  - `brain/INNOVATION_HANDOFF.md`
- **Tests Added**: 27 focused tests across 4 test suites:
  - 6 domain contract tests (`test_sla_contracts.py`)
  - 5 SLA engine tests (`test_sla_engine.py`)
  - 4 service & API integration tests (`test_sla_integration.py`)
  - 12 adversarial security & metric integrity tests (`test_sla_adversarial.py`)
- **Regression Count**: 747 passed, 0 failed in 18.33s (720 baseline + 27 I15 tests).
- **Invariants Preserved**:
  - `AI proposes -> evidence proves -> deterministic logic decides`: Zero LLM decision logic in I15.
  - Non-Authoritative Boundary: Metrics observe and measure facts; never override T04 integrity decisions or I9 kill switch states.
  - Strict Timestamp Integrity: No fabricated `now()` latency; reversed timestamps rejected as `INVALID`.
  - Secret Protection: Zero credentials or private tokens exposed in SLA metrics reports.

---

## I22 Verification Record
- **Implementation Scope**: Complete Hero Transaction Integration Layer.
  - End-to-End Orchestration & Composition: Proves the complete thesis (`Detect → Prove → Repair → Revalidate → Execute → Verify`) by composing existing subsystems without introducing duplicate engines.
  - Realistic Agentic Commerce Flow: Concrete SSD purchase fixture ("Buy me a 1TB external SSD under ₹8,000, preferably with fast delivery", `SKU-SSD-1TB`, 800,000 paise max).
  - Clean Baseline & Deliberate Drift: Initial offer passes deterministic verification (₹7,500 total). Deliberate mutation in checkout induces price surge to ₹8,250, deterministically detected by T04 engine as `EconomicDrift`.
  - Machine-Readable Drift Proof: Cryptographically built via T07 `build_mrdp` with `ECONOMIC_AMOUNT_EXCEEDED` and bound to `HeroDriftNotice` transmitted via TIX.
  - Bounded Replanning & Remediation: Buyer Agent replans within immutable authorization ceiling (cannot expand budget); Merchant Agent generates compliant alternative (₹7,650 total).
  - Deterministic Revalidation: T04 engine revalidates fresh evidence to PASS while immutably preserving the original DRIFT and MRDP in history.
  - Gating & Binding: I9 Kill Switch verified (`RUNNING`); I8 7-tuple binding strictly enforced.
  - Authoritative Payment Execution: Authoritative payment evidence normalized; strictly separates `REAL_RAZORPAY_TEST_MODE` from `SYNTHETIC_OFFLINE_HERO_RUN` without fake gateway states.
  - Full Verification & Audit Composition:
    - I13 Integrity Trace: 8 lifecycle stages evaluated with root cause isolation.
    - I14 Checkpoints: 8-checkpoint timeline with SHA-256 fingerprint chain.
    - I15 SLA Metrics: Deterministic calculation of latency and coverage ratios.
    - I19 Capability Graph: Merchant capability snapshot digest bound to record.
    - I21 Explanation: Evidence-aware explanation anchored to factual evidence references.
    - T13 Replay: Side-effect free CPU replay reconstructing the transaction with `ReplayVerdict.MATCH`.
    - I12 Certification: Evaluated against canonical scenario alignment.
- **Files Created**:
  - `backend/app/domain/hero/contracts.py`
  - `backend/app/domain/hero/__init__.py`
  - `backend/app/services/hero/orchestrator.py`
  - `backend/app/services/hero/__init__.py`
  - `testing/unit/test_hero_contracts.py`
  - `testing/unit/test_hero_orchestration.py`
  - `testing/unit/test_hero_adversarial.py`
  - `testing/unit/test_hero_api.py`
- **Files Modified**:
  - `backend/app/main.py`
  - `backend/app/services/hero/orchestrator.py`
  - `brain/STATUS.md`
  - `brain/HANDOFF.md`
  - `brain/INNOVATION_HANDOFF.md`
- **Tests Added**: 17 focused tests across 4 test suites:
  - 3 domain contract tests (`test_hero_contracts.py`)
  - 2 end-to-end journey tests (`test_hero_orchestration.py`)
  - 9 adversarial & determinism tests (`test_hero_adversarial.py`)
  - 3 REST API endpoint tests (`test_hero_api.py`)
- **Regression Count**: 764 passed, 0 failed in 39.78s (747 baseline + 17 I22 tests).
- **Invariants Preserved**:
  - Pure Orchestration & Composition: No duplicate business logic or competing integrity engine.
  - Strict Real vs Synthetic Boundary: `SYNTHETIC_OFFLINE_HERO_RUN` clearly distinguished from `REAL_RAZORPAY_TEST_MODE`.
  - Zero Secret Leakage: Credentials, tokens, and authorization headers redacted.
  - Historical Truth Preservation: Original DRIFT, MRDP, and evidence preserved in history.
  - AI Advisory Boundary: LLM cannot declare PASS or bypass revalidation.

---

## E-Series Final Extension: E0 — Final Baseline & Contract Freeze

### Baseline Verification Record (E0 Baseline Freeze)

```text
E-SERIES:
E0

STATUS:
COMPLETE

BASELINE_COMMIT:
fef0ed69dfc61ff219b9a3389626a09fbe340171

REMOTE_COMMIT:
fef0ed69dfc61ff219b9a3389626a09fbe340171

WORKING_TREE:
CLEAN

TEST_COUNT:
764 passed (0 failed, 2 warnings in 36.44s)

TEST_RESULT:
PASS (make test-bootstrap PASS, make test-env PASS, pytest PASS, verify_api_smoke PASS)

API_SURFACE:
27 routes registered and operational across health, intent, transactions, mrdp, replay, scenarios, certifications, explanation, trace, checkpoints, sla, and hero-transaction

MODEL_SURFACE:
Immutable Pydantic domain models across Money, IntentContract, Authorization, CanonicalEvent, Evidence, EvidenceBundle, Transaction, TransactionState, Decision, IntegrityResult, MRDP, RecoveryProposal, ActionRequest, ReplaySnapshot, ReplayResult, TIX messages, Buyer Agent contracts, Merchant Agent contracts, Binding contracts, KillSwitch contracts, OperationalMode contracts, CapabilityGraph contracts, Scenario contracts, Certification contracts, IntegrityTrace contracts, Checkpoint contracts, SLAMetrics contracts, HeroTransaction contracts

RAZORPAY_VERIFICATION:
SDK/API adapter implemented (RazorpayAdapter); order creation implemented; test mode live signature verification verified; real test mode transaction verified (clean skip if live credentials unset; passing live boundary smoke test); zero float math (integer paise minor units)

FRONTEND_BUILD:
PASS (Next.js 15.5.25 Turbopack production build clean, TypeScript valid, static pages generated)

EXISTING_FEATURES:
- Core: deterministic integrity (PASS/DRIFT/UNKNOWN), evidence hierarchy, state machine, MRDP, recovery, UNKNOWN resolution, replay (IMPLEMENTED)
- I-series: evidence freshness, integrity deltas, agent/transaction binding, merchant agent, buyer agent, TIX, bounded negotiation/replanning, kill switch, scenario lab, ground-truth certification, trace/fault localization, integrity checkpoints, SLA metrics, complete hero transaction (IMPLEMENTED)

KNOWN_LIMITATIONS:
- Live external network calls (Groq, Razorpay) are decoupled and optional in CI/offline test suites; tests use verified synthetic/reference providers unless live credentials are intentionally injected in environment.
- Starlette DeprecationWarning for TestClient httpx2 / anyio BlockingPortal (benign upstream deprecation notices, zero functional failures).

NEXT:
E1 — Integration Boundary
```

### E0 API Surface Inventory

| Method | Path | Purpose | Request Model | Response Model | Current Status |
|---|---|---|---|---|---|
| `GET` | `/health` | Control plane health & toolchains | None | JSON Dict (`status`, `service`, `version`, `has_groq`, `has_razorpay`) | OPERATIONAL |
| `GET` | `/api/v1/health` | Control plane v1 health alias | None | JSON Dict | OPERATIONAL |
| `POST` | `/api/v1/intent/parse` | Natural language intent parsing | Dict (`prompt`, `issued_by`) | `IntentContract` | OPERATIONAL |
| `POST` | `/api/v1/transaction/create` | Protected order creation & binding | `CreateTransactionRequest` | `CreateTransactionResponse` | OPERATIONAL |
| `POST` | `/api/v1/transaction/complete` | Server-side verification & lifecycle progression | `CompleteTransactionRequest` | `CompleteTransactionResponse` | OPERATIONAL |
| `POST` | `/api/v1/transaction/recover` | Bounded compensatory recovery loop | `RecoverTransactionRequest` | `RecoverTransactionResponse` | OPERATIONAL |
| `POST` | `/api/v1/transaction/resolve` | Safe, bounded observation for UNKNOWN state | `ResolveTransactionRequest` | `ResolveTransactionResponse` | OPERATIONAL |
| `GET` | `/api/v1/transaction/{transaction_id}` | Transaction session inspection | None (Path param) | `TransactionSessionResponse` | OPERATIONAL |
| `GET` | `/api/v1/transaction/{transaction_id}/mrdp` | Machine-Readable Drift Proof retrieval | None (Path param) | `MRDP` | OPERATIONAL |
| `POST` | `/api/v1/replay` | Deterministic CPU replay & audit comparison | `ReplaySnapshot` | `ReplayResult` | OPERATIONAL |
| `GET` | `/api/v1/scenarios` | List 12 canonical test scenarios | Optional Query (`category`) | `List[ScenarioDefinition]` | OPERATIONAL |
| `POST` | `/api/v1/scenarios/{scenario_id}/run` | Execute scenario through production engine | None (Path param) | `ScenarioResult` | OPERATIONAL |
| `POST` | `/api/v1/scenarios/run-all` | Execute all 12 canonical scenarios | Optional Query (`category`) | `ScenarioSuiteResult` | OPERATIONAL |
| `GET` | `/api/v1/certifications` | List ground truth certification definitions | None | `List[GroundTruthDefinition]` | OPERATIONAL |
| `POST` | `/api/v1/certifications/{scenario_id}/run` | Run scenario and evaluate certification | None (Path param) | `CertificationResult` | OPERATIONAL |
| `POST` | `/api/v1/certifications/run-all` | Run all scenarios and certify against ground truth | None | `CertificationSuiteResult` | OPERATIONAL |
| `GET` | `/api/v1/transactions/{transaction_id}/explanation` | Evidence-aware explanation retrieval | None (Path param) | `ExplanationResult` | OPERATIONAL |
| `GET` | `/api/v1/transactions/{transaction_id}/integrity-trace` | 8-stage lifecycle fault localization trace | None (Path param) | `IntegrityTrace` | OPERATIONAL |
| `GET` | `/api/v1/transactions/{transaction_id}/integrity-checkpoints` | Cryptographic checkpoint timeline retrieval | None (Path param) | `IntegrityCheckpointTimeline` | OPERATIONAL |
| `GET` | `/api/v1/transactions/{transaction_id}/integrity-sla` | Deterministic 9-metric SLA report retrieval | None (Path param) | `IntegritySLAMetricsReport` | OPERATIONAL |
| `POST` | `/api/v1/hero-transaction/run` | Execute complete hero commerce journey | `RunHeroTransactionRequest` | `HeroTransactionRecord` | OPERATIONAL |
| `GET` | `/api/v1/hero-transaction/{hero_transaction_id}` | Retrieve executed hero transaction record | None (Path param) | `HeroTransactionRecord` | OPERATIONAL |
| `POST` | `/api/v1/webhook/razorpay` | Ingest and verify Razorpay webhook | Raw Body + Signature Header | JSON Dict | OPERATIONAL |

### E0 Domain Model Surface Inventory

1. **Monetary & Foundation Models** (`backend/app/domain/models/`):
   - `Money`: Integer minor units (paise), ISO 4217 currency validation, strict float rejection.
   - `IntentItem`, `IntentContract`: Immutable authorized specification with budget ceiling, SKUs, substitutions.
   - `Authorization`: Temporal validity bounds (`issued_at`, `expires_at`), max amount, signature.
   - `CanonicalEvent`: Chronologically sequenced lifecycle event with deterministic tie-breaking.
   - `Evidence`, `EvidenceBundle`: Multi-tiered evidence with strict authority rankings (`AUTHORITATIVE` 100 > `PROTOCOL_TRUSTED` 90 > `MERCHANT_ATTESTED` 70 > `REPLAY_OBSERVED` 60 > `SYSTEM_DERIVED` 50 > `ADVISORY` 20).
   - `RuleResult`, `IntegrityResult`: Deterministic verdict (`PASS`, `DRIFT`, `UNKNOWN`) with violations list.
   - `MRDP`: Cryptographic Machine-Readable Drift Proof with SHA-256 digest over discrepancy and rules.
   - `RecoveryProposal`, `ActionRequest`: Bounded compensatory action contracts.
   - `ProviderOrder`, `ProviderPayment`, `ProviderWebhookEvent`: Razorpay gateway representations.
   - `CreateTransactionRequest`, `CreateTransactionResponse`, `CompleteTransactionRequest`, `CompleteTransactionResponse`, `RecoverTransactionRequest`, `RecoverTransactionResponse`, `ResolveTransactionRequest`, `ResolveTransactionResponse`: API slice models.

2. **Protocol Security & Binding Models** (`backend/app/domain/security/`, `backend/app/domain/binding/`):
   - `AgentTransactionMessage`: Cryptographic SHA-256 chained inter-agent protocol message.
   - `ProtocolVerificationOutcome`: Protocol validation status with tamper/replay detection.
   - `TransactionBindingContext`: Immutable 7-tuple context binding (`intent_id`, `agent_id`, `merchant_id`, `transaction_id`, `order_id`, `payment_id`, `attempt_id`).
   - `TransactionBindingOutcome`: Authoritative binding evaluation result.

3. **Governance & Replay Models** (`backend/app/domain/governance/`, `backend/app/services/replay/contracts.py`):
   - `GovernanceVersion`: Explicit immutable `rules_version` and `policy_version`.
   - `ReproducibilityRecord`: Canonical cryptographic snapshot record for audit reproducibility.
   - `DecisionReproducibilityCertificate`: Tamper-detectable digital certificate binding decisions to component digests.
   - `ReplaySnapshot`, `ReplayResult`, `ReplayDiscrepancy`: Full state reconstruction and 3-way verdict (`MATCH`, `MISMATCH`, `INVALID_REPLAY`).

4. **Agent & Commerce Models** (`backend/app/domain/merchant/`, `backend/app/domain/buyer/`, `backend/app/domain/tix/`, `backend/app/domain/negotiation/`):
   - `CatalogItem`, `InventoryRecord`, `ShippingOption`, `TaxEstimate`, `BuyerCommerceRequest`, `MerchantOfferItem`, `MerchantResponse`, `MerchantCapabilityDeclaration`, `MerchantPolicyAsCode`: Merchant domain and policies.
   - `BuyerTransactionProposal`, `BuyerClarification`, `BuyerReplanRequest`, `BuyerReplanResult`, `BuyerAgentDecision`: Buyer agent constrained proposals and replanning.
   - `TIXMessage`, `TIXMessageHeader`, `TIXIntegrityCheckPayload`, `TIXDriftNoticePayload`, `TIXRemediationRequestPayload`, `TIXExchangeSession`: Cryptographic internal exchange protocol messages across 12 canonical types.
   - `NegotiationPolicy`, `NegotiationRoundRecord`, `NegotiationSession`: Bounded remediation session contracts.

5. **Execution Safety & Operational Models** (`backend/app/domain/kill_switch/`, `backend/app/domain/operational_mode/`, `backend/app/domain/capability/`):
   - `KillSwitchState`, `KillSwitchPolicy`, `ExecutionSafetyDecision`, `KillSwitchAuditRecord`: 4-state execution gating (`RUNNING`, `PAUSED`, `REQUIRES_REVALIDATION`, `KILLED`).
   - `OperationalModePolicy`, `HumanReviewRequirement`, `HumanReviewDecision`, `OperationalEvaluationResult`: Deployment modes (`SHADOW`, `GUARDED`, `HUMAN_REVIEW`).
   - `CapabilityNode`, `CapabilityEdge`, `MerchantCapabilityGraph`, `CapabilityEvaluationResult`, `CapabilityGraphSnapshot`: Merchant capability graph contracts (zero reputation/trust scores).

6. **Observability, Audit & Hero Integration Models** (`backend/app/domain/trace/`, `backend/app/domain/checkpoint/`, `backend/app/domain/sla/`, `backend/app/domain/explanation/`, `backend/app/domain/scenario/`, `backend/app/domain/certification/`, `backend/app/domain/hero/`):
   - `IntegrityTrace`, `LifecycleStep`, `FieldDiscrepancy`: Chronological 8-stage fault localization trace.
   - `IntegrityCheckpoint`, `IntegrityCheckpointTimeline`: 8-checkpoint cryptographic fingerprint chain.
   - `IntegritySLAMetric`, `IntegritySLAMetricsReport`: Deterministic 9-metric SLA report.
   - `ExplanationClaim`, `ExplanationContext`, `ExplanationResult`: Evidence-grounded non-authoritative AI explanation.
   - `ScenarioDefinition`, `ScenarioResult`, `ScenarioSuiteResult`: 12 canonical scenario definitions and results.
   - `GroundTruthDefinition`, `CertificationResult`, `CertificationMatrixRow`, `CertificationSuiteResult`: Ground-truth certification matrix.
   - `HeroTransactionRecord`, `HeroDriftNotice`, `HeroRemediationProposal`: End-to-end hero transaction orchestration record.

7. **Integration & Composition Boundary Models** (`backend/app/domain/integration/contracts.py`):
   - `IntegrationBoundaryStage`: Explicit lifecycle stage tracking (`INITIALIZED`, `INTENT_BOUND`, `OFFER_RECEIVED`, `TIX_COMMITTED`, `PAYMENT_BOUND`, `EVALUATED`, `RECOVERED`, `COMPLETED`).
   - `IntegrationTransactionContext`: Pure 7-tuple context binding (`intent_id`, `agent_id`, `merchant_id`, `transaction_id`, `order_id`, `payment_id`, `attempt_id`).
   - `IntegrationExecutionRecord`: Immutable execution snapshot recording all ingested domain objects, TIX messages, binding outcomes, integrity evaluations, MRDP proofs, and compensatory actions.
   - `IntegrationEvaluationResponse`: Typed evaluation outcome exposing rule results, state machine progression, and MRDP proof.

---

## E1 Verification Record (Integration Boundary)

- **Implementation Scope**:
  - Single stable application-facing integration and composition boundary (`IntegrationService`) around all existing components (Buyer Agent, Merchant Agent, TIX, Intent, Transaction, Payment, Integrity, Recovery, Replay).
  - Preserved existing authority hierarchy: AI is advisory; evidence proves; deterministic logic decides.
  - Composed existing implementations directly without rewriting or introducing duplicate engines:
    - I8 `TransactionBindingService` for agent/merchant/transaction/payment binding
    - I9 `KillSwitchService` for execution safety gating
    - I6 `TIXExchangeService` for inter-agent communication
    - I4 `MerchantCatalogService` & I5 `BuyerAgentService` for commercial proposals
    - T04 `evaluate_integrity` for deterministic evaluation
    - T05 `TransactionStateMachine` for lifecycle state progression
    - T07 `build_mrdp` for cryptographic drift proofs
    - T11 `RecoveryExecutor` for bounded compensatory recovery
    - T13 `ReplayEngine` for side-effect-free historical replay
    - T09 `RazorpayAdapter` for payment provider operations
  - Exposed narrow, additive REST endpoints: `POST /api/v1/integration/context` and `GET /api/v1/integration/{transaction_id}`.
- **Files Created**:
  - `backend/app/domain/integration/__init__.py`
  - `backend/app/domain/integration/contracts.py`
  - `backend/app/services/integration/__init__.py`
  - `backend/app/services/integration/service.py`
  - `testing/unit/test_integration_boundary.py`
- **Files Modified**:
  - `backend/app/services/__init__.py` (re-exported IntegrationService and error classes)
  - `backend/app/main.py` (added integration endpoints, exception handlers, and dependency provider)
- **Tests Added**: 13 focused tests in `test_integration_boundary.py` covering binding enforcement, cross-context isolation, authority invariants, deterministic drift/MRDP, clean pass, recovery, pure CPU replay, and API contracts.
- **Regression Count**: 777 passed, 2 warnings in 36.41s (764 baseline + 13 new E1 tests).
- **Core Invariant Verification**:
  - `make test-bootstrap`: PASS
  - `make test-env`: PASS (including Next.js production build)
  - `scripts/verify_api_smoke.py`: PASS

---

## E2 Verification Record (Consumer + Merchant Gate Composition)

- **Implementation Scope**:
  - Two explicit validation surfaces: Consumer Gate (buyer side) and Merchant Gate (merchant side).
  - Consumer Gate deterministic checks: intent binding, authorization constraints (financial ceiling, permitted SKUs, quantity limits, temporal window), agent identity, transaction context, and proposal validity / prompt injection defense.
  - Merchant Gate deterministic checks: merchant identity, capability declaration, catalog SKU validity, real-time inventory status, price constraints, shipping SLA, fulfillment promises, offer expiry, and merchant policy compliance.
  - Composed Gate Output: structured validation facts (`GateCompositionOutcome`, `GateValidationFinding`) mapping deterministically to advisory evidence (`EvidenceAuthority.ADVISORY`) from buyer agent and merchant-attested evidence (`EvidenceAuthority.MERCHANT_ATTESTED`) from merchant.
  - Invariant preservation: gates emit structured evidence only; they never declare financial `PASS` or authorize money movement. `UNKNOWN` preserved as first-class state.
- **Files Created**:
  - `backend/app/domain/gates/__init__.py`
  - `backend/app/domain/gates/contracts.py`
  - `backend/app/services/gates/__init__.py`
  - `backend/app/services/gates/consumer_gate.py`
  - `backend/app/services/gates/merchant_gate.py`
  - `backend/app/services/gates/service.py`
  - `testing/unit/test_gates_composition.py`
- **Files Modified**:
  - `backend/app/domain/integration/contracts.py` (added gate lifecycle stages and execution record fields)
  - `backend/app/services/integration/service.py` (integrated consumer/merchant gate validation into integration boundary)
  - `backend/app/services/merchant/catalog_service.py` (added inventory setter and convenience accessors)
  - `backend/app/services/__init__.py` (re-exported ConsumerGate, MerchantGate, GateCompositionService)
- **Tests Added**: 55 focused unit and adversarial tests covering contract validation, each individual check type, adversarial prompt injections, merchant policy boundaries, composition outcomes, evidence mapping, and integration boundary stage progression.
- **Regression Count**: 859 passed, 2 warnings in 39.66s (804 baseline + 55 new E2 tests).
- **Core Invariant Verification**:
  - `make test-bootstrap`: PASS
  - `make test-env`: PASS (including Next.js production build)
  - `scripts/verify_api_smoke.py`: PASS

---

## E4 Verification Record (Security / Threat Guard Composition)

- **Implementation Scope**:
  - Additive, isolated security threat guard composition (`SecurityGuardService` & pure deterministic `SecurityThreatEvaluator`).
  - Strict preservation of the governing authority model: Untrusted content is DATA, never AUTHORITY. Zero LLM authority in security decisions.
  - Composed existing primitives directly without duplicate engines:
    - I2 Protocol Security (replay protection, timestamp freshness, message deduplication)
    - I8 Agent/Transaction/Payment Binding (identity and context misalignment detection)
    - I9 Deterministic Kill Switch (triggers safety pause/kill on critical violations)
    - I14 Integrity Checkpoint & Evidence Verification (tampered hash detection)
    - I19 Merchant Capability Graph (capability boundary and financial ceiling enforcement)
  - 12 canonical threat vectors deterministically covered:
    1. `PROMPT_INJECTION`: Untrusted prompts cannot mutate intent constraints (`max_total`, `currency`, `items`). Adversarial patterns isolated as data.
    2. `AGENT_CAPABILITY_VIOLATION`: Unauthorized capabilities or proposed amounts exceeding capability limits are blocked.
    3. `AGENT_ID_MISMATCH`: Unbound agent attempting transaction access is critically blocked.
    4. `TRANSACTION_MISMATCH`: Evidence/payload referencing conflicting transaction IDs rejected.
    5. `INTENT_MISMATCH`: Referenced intent differing from bound contract rejected.
    6. `REPLAY_DETECTED`: Consumed attempt re-submission blocked without executing consequential action.
    7. `STALE_MESSAGE`: Timestamps exceeding freshness window held/rejected.
    8. `DUPLICATE_MESSAGE`: Duplicate message delivery distinguished from duplicate financial execution (INFO / CLEAR).
    9. `EVIDENCE_INTEGRITY_FAILURE`: Evidence hash mismatch or broken checkpoint chain triggers HOLD.
    10. `STATE_DESYNC`: Conflicting local and provider states trigger safe reconciliation hold.
    11. `PROVIDER_STATE_UNKNOWN`: Missing webhook or unresolved state preserved as UNKNOWN (never forced PASS).
    12. `AUTHORIZATION_EXPIRED`: Intent expired past reference time blocked without silent renewal.
- **Files Created**:
  - `backend/app/domain/security_guard/__init__.py`
  - `backend/app/domain/security_guard/contracts.py`
  - `backend/app/domain/security_guard/evaluator.py`
  - `backend/app/services/security_guard/__init__.py`
  - `backend/app/services/security_guard/guard.py`
  - `testing/unit/test_security_guard_contracts.py`
  - `testing/unit/test_security_guard_adversarial.py`
  - `testing/unit/test_security_guard_composition.py`
- **Files Modified**:
  - `backend/app/services/__init__.py` (re-exported SecurityGuardService)
- **Tests Added**: 27 focused tests covering contract immutability, deterministic hash reproducibility, all 12 canonical threat vectors + 4 prompt injection cases, I9 kill switch activation, and replay mode compatibility.
- **Regression Count**: 804 passed, 2 warnings in 39.08s (777 baseline + 27 new E4 tests).
- **Core Invariant Verification**:
  - `make test-bootstrap`: PASS
  - `make test-env`: PASS (including Next.js production build)

---

## E3 Verification Record (Agentic Transaction Lifecycle Orchestration)

- **Implementation Scope**:
  - Complete bounded agentic transaction lifecycle orchestrator (`AgenticLifecycleOrchestrator`) connecting Buyer Agent, Consumer Gate, Merchant Agent, Merchant Gate, TIX exchange, T04 deterministic integrity, MRDP, bounded replanning, UNKNOWN resolution, security guard composition, recovery executor, Razorpay payment adapter, and T13 pure CPU replay.
  - Strict preservation of the governing authority model: "AI proposes. Evidence proves. Deterministic logic decides." The orchestrator has control-flow authority, NOT financial or truth authority.
  - Domain contracts: `LifecycleStage`, `LifecyclePolicy`, `LifecycleStepRecord`, `LifecycleOutcome`, `LifecycleViolationError`.
  - Bounded DRIFT replanning path: generates MRDP digest, invokes Buyer Agent proposal revision, generates Merchant counter-offer, enforces **mandatory revalidation** of revised proposals through E2 Consumer Gate and revised offers through E2 Merchant Gate, and deterministically re-evaluates through T04 engine.
  - Authoritative UNKNOWN path: preserves UNKNOWN without guessing, triggers authoritative gateway polling up to budget limit, transitions to ABSTAIN if unresolved, and NEVER coerces UNKNOWN into PASS.
  - Security guard integration (E4): passes transaction contexts and untrusted inputs through `SecurityGuardService` to detect injection attacks, capability abuse, and evidence tampering.
  - Recovery integration (T11): invokes `RecoveryExecutor` within verified MRDP discrepancy bounds when replanning is exhausted or disabled.
  - Replay boundary (T13): operates purely in-memory on CPU without live network, AI, or payment side-effects, guaranteeing historical reproducibility.
  - Application-facing REST API: `POST /api/v1/integration/{transaction_id}/orchestrate` with clean status code mapping.
- **Files Created**:
  - `backend/app/domain/orchestration/__init__.py`
  - `backend/app/domain/orchestration/contracts.py`
  - `backend/app/services/orchestration/__init__.py`
  - `backend/app/services/orchestration/lifecycle.py`
  - `testing/unit/test_agentic_lifecycle_orchestration.py`
- **Files Modified**:
  - `backend/app/domain/gates/contracts.py` (added `message` alias on `GateValidationFinding`)
  - `backend/app/domain/merchant/contracts.py` (added `price` and `total` convenience properties, added `mode="before"` validator for `inventory_status`)
  - `backend/app/domain/integration/contracts.py` (added lifecycle stages and execution record fields)
  - `backend/app/services/integration/service.py` (added `orchestrate_lifecycle` method delegating to orchestrator)
  - `backend/app/services/merchant/catalog_service.py` (added `add_item` convenience method)
  - `backend/app/services/__init__.py` (re-exported AgenticLifecycleOrchestrator)
  - `backend/app/main.py` (registered `/api/v1/integration/{transaction_id}/orchestrate` endpoint)
- **Tests Added**: 53 focused unit and adversarial tests in `testing/unit/test_agentic_lifecycle_orchestration.py` covering all 50 required scenarios plus API endpoints.
- **Regression Count**: 912 passed, 2 warnings in 37.13s (859 baseline + 53 new E3 tests).
- **Core Invariant Verification**:
  - `make test-bootstrap`: PASS
  - `make test-env`: PASS (including Next.js production build)
  - `scripts/verify_api_smoke.py`: PASS
  - `git diff --check`: PASS

---

## E5 Verification Record (Transaction Passport)

- **Implementation Scope**:
  - Unified, immutable, frozen `TransactionPassport` providing an observational projection of the lifecycle of a TarkaRaksha transaction.
  - Composes existing records from T04 deterministic integrity, T05 state machine, T06 evidence hierarchy, T07 MRDP proofs, T09 Razorpay payment adapter, T11 recovery executor, T12 UNKNOWN observer, T13 replay engine, and E1–E4 services.
  - Zero second source of truth, zero parallel mutable state, zero competing state machines, and zero payment authorization capability.
  - Strictly preserves `CAPTURED != PASS` invariant: payment capture does not imply integrity pass.
  - Preserves first-class `UNKNOWN` state without coercion.
  - 16 frozen domain sections:
    1. Identity (7-tuple context binding)
    2. Authorization (immutable IntentContract ceiling and constraints)
    3. Agent Context (Buyer Agent proposal, rationale, gate result)
    4. Merchant Context (Offer, inventory status, capabilities, gate result)
    5. Lifecycle State (T05 projection, transition history, terminal flags)
    6. Integrity (Authoritative T04 evaluation, domain findings, violations)
    7. Drift / MRDP (T07 proof digest, discrepancy details, violated rules)
    8. Evidence (T06 hierarchy, authority rankings, source distribution)
    9. Security (E4 threat evaluation, prompt injection, tampering)
    10. Recovery (T11 compensatory action, idempotency, attempts)
    11. UNKNOWN Resolution (T12 observation attempts, final unresolved)
    12. Revalidation (E3/I7 negotiation replans, gate statuses)
    13. Checkpoints & Trace (I14 checkpoints, I13 fault localization)
    14. SLA Metrics (I15 operational latencies and durations)
    15. Payment (T09 Razorpay details, status, separation flag)
    16. Replay (T13 side-effect-free replay verdict and state)
  - Canonical SHA-256 digest computation (`compute_digest()`).
  - Human-readable canonical format (`to_text_summary()`).
  - Integration service retrieval: `IntegrationService.get_passport(transaction_id)`.
  - Application-facing REST API: `GET /api/v1/integration/{transaction_id}/passport`.
- **Files Created**:
  - `backend/app/domain/passport/__init__.py`
  - `backend/app/domain/passport/contracts.py`
  - `backend/app/services/passport/__init__.py`
  - `backend/app/services/passport/service.py`
  - `testing/unit/test_transaction_passport.py`
- **Files Modified**:
  - `backend/app/services/integration/service.py` (added `get_passport` method)
  - `backend/app/services/__init__.py` (re-exported TransactionPassportService)
  - `backend/app/main.py` (registered `GET /api/v1/integration/{transaction_id}/passport` endpoint)
- **Tests Added**: 66 focused unit and adversarial tests in `testing/unit/test_transaction_passport.py` covering all prompt scenarios.
- **Regression Count**: 978 passed, 2 warnings in 50.65s (912 baseline + 66 new E5 tests).
- **Core Invariant Verification**:
  - `make test-bootstrap`: PASS
  - `make test-env`: PASS (including Next.js production build)
  - `scripts/verify_api_smoke.py`: PASS
  - `git diff --check`: PASS

---

## E6 Verification Record (Failure → Recovery → Revalidation Hero Loop)

- **Implementation Scope**:
  - Closed-loop judging journey proving the complete TarkaRaksha thesis on a high-value commercial purchase:
    `VALID TRANSACTION (₹50,000 ceiling, ₹47,000 product + ₹3,000 shipping -> PASS)`
    `-> CONTROLLED DRIFT (₹55,000 -> DRIFT + Cryptographic MRDP)`
    `-> BOUNDED RECOVERY (Buyer Replan within immutable ₹50,000 ceiling)`
    `-> MERCHANT ALTERNATIVE (₹47,000 product + ₹3,000 shipping = ₹50,000 total)`
    `-> REVALIDATION (Deterministic re-evaluation -> PASS)`
    `-> PAYMENT EXECUTION (Razorpay Test Mode / captured)`
    `-> VERIFIED RESTORATION ("TRANSACTION RESTORED")`.
  - Zero duplicate engines: seamlessly composed existing I22 `HeroTransactionOrchestrator`, T04 deterministic integrity, T07 MRDP builder, T13 replay engine, I8 protocol binding, I9 kill switch, I13 trace, I14 checkpoints, I15 SLA metrics, and I21 AI explanation.
  - Strict preservation of I22 backward compatibility: all 17 existing hero tests remain 100% green.
  - Authoritative hero message generated from verified transaction state, confirming preserved authorization, verified payment, and completed recovery.
  - Application-facing endpoint support: `POST /api/v1/hero-transaction/run` with `scenario="e6"`.
- **Files Created**:
  - `backend/app/domain/hero/scenario_e6.py`
  - `testing/unit/test_e6_failure_recovery_revalidation.py`
- **Files Modified**:
  - `backend/app/domain/hero/contracts.py` (added `hero_message: Optional[str] = None` to `HeroTransactionRecord`)
  - `backend/app/domain/hero/__init__.py` (re-exported `create_canonical_e6_intent`)
  - `backend/app/services/hero/orchestrator.py` (supported canonical E6 pricing, mutation, remediation, and authoritative hero message assembly)
  - `backend/app/main.py` (added `scenario` parameter and resolved E6 intent)
  - `testing/unit/test_explanation_integration.py` (hardened AI explanation summary assertion against live LLM output variations)
- **Tests Added**: 13 comprehensive unit and adversarial tests in `testing/unit/test_e6_failure_recovery_revalidation.py` covering all prompt requirements.
- **Regression Count**: 991 passed, 2 warnings in 58.13s (978 baseline + 13 new E6 tests).
- **Core Invariant Verification**:
  - `make test-bootstrap`: PASS
  - `make test-env`: PASS (including Next.js production build)
  - `scripts/verify_api_smoke.py`: PASS
  - `git diff --check`: PASS

