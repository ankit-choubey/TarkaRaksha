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



