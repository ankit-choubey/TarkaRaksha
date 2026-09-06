# HANDOFF.md — Agent Session Handoff Document

## Handoff Metadata
- **Current Task Completed**: `E8 — Scenario / Proof Surface`
- **Current Checkpoint**: `C_E8 — PASS`
- **Baseline SHA**: `5c59a7dde7ef741078a785077677dd67070226f2`
- **Next Task**: `E9 — Final End-to-End Demonstration Certification`
- **Active Branch**: `main`
- **Handoff Timestamp**: 2026-09-06T15:54:00+05:30

---

## 1. What Was Done in E8

1. **Scenario & Proof Domain Contracts (`backend/app/domain/scenario/contracts.py`)**:
   - `ScenarioProof`: Read-only, deterministic proof projection aggregating factual evidence, comparison table, 5-Question narrative, 6-stage proof chain, security findings, recovery summary, and tamper-evident SHA-256 proof digest.
   - `ScenarioProofComparisonItem`: Parameter-level Expected vs Observed ledger row (`is_match`, notes, values).
   - `ScenarioProofChainStage`: Structured stage in the canonical verification chain (`AUTHORIZED STATE` → `OBSERVED EVENT` → `DETERMINISTIC VERIFICATION` → `EVIDENCE / MRDP` → `SECURITY & RECOVERY` → `FINAL OUTCOME`).
   - `ScenarioNarrative`: The canonical 5-Question proof narrative (`what_was_authorized`, `what_happened`, `did_it_match`, `why`, `what_happened_next`).
   - Backwards-compatible expansion of `ScenarioDefinition` with structured specification fields (`initial_conditions`, `mutation_input`, `expected_behavior`, `expected_proof`, `provider_mode`, `related_capability`).

2. **Canonical 12-Scenario Catalog (`backend/app/domain/scenario/catalog.py`)**:
   - Complete specification and enrichment of all 12 canonical scenarios:
     1. `HAPPY_PATH`: Authorized valid offer -> PASS -> Completed payment.
     2. `PRICE_DRIFT`: Authorized ₹5,000 vs Observed ₹6,000 -> DRIFT -> Cryptographic MRDP -> Bounded replan within ceiling.
     3. `WRONG_SKU`: Authorized `SKU-BOOK-001` vs Observed unauthorized gadget -> Unauthorized SKU rejection -> DRIFT.
     4. `INVENTORY_DISAPPEARS`: Stockout during checkout -> Missing authorized item -> DRIFT.
     5. `DELIVERY_DRIFT`: Breach of fulfillment deadline after contract expiry -> DRIFT.
     6. `DUPLICATE_PAYMENT`: Multiple capture attempts against single authorization -> Double execution risk -> DRIFT.
     7. `DELAYED_WEBHOOK`: Provider webhook arriving after contract expiration -> Expired execution -> DRIFT.
     8. `REPLAY_ATTACK`: Tampered historical state replayed against CPU-only engine -> MISMATCH detected with zero side effects.
     9. `PROMPT_INJECTION_IN_EVIDENCE`: Malicious text embedded in evidence -> AI remains strictly advisory -> UNKNOWN / No forced PASS.
     10. `MERCHANT_AGENT_COMPROMISED`: Merchant attested claim contradicts authoritative gateway evidence -> UNKNOWN -> Payment blocked.
     11. `BUYER_AGENT_REUSE`: Cross-transaction reuse attempt of buyer credentials -> I8 7-tuple binding mismatch -> REJECTED.
     12. `UNKNOWN_PROVIDER_STATE`: Ambiguous provider state -> UNKNOWN preserved -> Resolution flow triggered -> Never coerced to PASS.

3. **Scenario Proof Engine & APIs (`backend/app/services/scenario/proof.py`, `backend/app/main.py`)**:
   - `ScenarioProofService`: Pure observational projection engine running scenarios through authoritative pipelines (`ScenarioRunner`, `evaluate_integrity`, `build_mrdp`, `TransactionBindingService`, `ReplayEngine`).
   - REST Endpoints registered:
     - `GET /api/v1/scenarios/{scenario_id}/proof`: Fetch or generate authoritative scenario proof.
     - `POST /api/v1/scenarios/{scenario_id}/prove`: Execute scenario, generate proof, and sync snapshot with Control Room.
     - `GET /api/v1/scenarios/proofs`: Retrieve all generated scenario proofs in session.
   - Seamless E7 Control Room synchronization via `ControlRoomService.compose_from_scenario_proof` and `register_scenario_snapshot`.

4. **Production Scenario Lab & Proof Surface UI (`frontend/app/page.tsx`)**:
   - Integrated dual-mode navigation header: `Control Room (E7)` | `Scenario & Proof Lab (E8)`.
   - **Scenario Catalog Matrix**: 12 scenario cards with category filters (`ALL`, `INTEGRITY`, `SECURITY`, `PAYMENT`, `LIFECYCLE`, `RESOLUTION`), active badges, and execution mode tags (`SYNTHETIC_OFFLINE_FIXTURE_RUN`).
   - **Scenario Inspector Card**: Detailed initial conditions, adversarial mutation inputs, and expected authoritative behaviors.
   - **Run & Generate Proof**: One-click execution invoking `/api/v1/scenarios/{id}/prove` and rendering live proof.
   - **5-Question Narrative Card**: Human-readable and judge-auditable answers to the 5 canonical proof questions.
   - **Expected vs Observed Comparison Table**: Cell-by-cell discrepancy breakdown with match status indicators.
   - **6-Stage Proof Chain Stepper**: Interactive progression from authorized state through final outcome.
   - **Tamper-Evident SHA-256 Proof Digest**: Cryptographic proof fingerprint with one-click copy.
   - **Inspect in Control Room**: Deep-link button that switches views and loads the scenario transaction directly into E7's live telemetry and 5 deep-dive tabs.

5. **Exhaustive Testing & Verification**:
   - 30 comprehensive unit and adversarial tests in `testing/unit/test_scenario_proof_surface.py`.
   - Covers all 12 canonical scenarios, discoverability, stable IDs, unsupported scenario rejection (404), narrative completeness, comparison accuracy, proof chain stages, proof digest determinism, Control Room sync, CAPTURED != PASS invariant, UNKNOWN non-coercion, authorization ceiling preservation, adversarial injection containment, synthetic mode labeling, CPU-only replay side-effect freedom, and AI advisory demarcation.
   - Regression: 56/56 passing tests in `test_control_room_surface.py`, `test_hero_*.py`, `test_e6_failure_recovery_revalidation.py`.
   - Full regression suite: 1047 passed (0 failures).
   - Clean Next.js Turbopack production build (`npm run build`).

---

## 2. Core Invariants Maintained
- **Principle**: "AI proposes. Evidence proves. Deterministic logic decides."
- **Scenario Lab Non-Authority**: The Scenario Lab is an observation and demonstration surface; it never decides PASS/DRIFT/UNKNOWN or authorizes money.
- **UNKNOWN-First Safety**: Missing or ambiguous provider telemetry renders as UNKNOWN; never coerced into PASS.
- **Payment Separation**: `CAPTURED != PASS`. Captured gateway state is never portrayed as an integrity clearance.
- **Ceiling Invariance**: Scenarios cannot escalate or mutate the original authorized budget ceiling.
- **Default AI Model**: Kept `openai/gpt-oss-20b` as default `GROQ_MODEL` with strictly advisory status.
- **Provider Accuracy**: Strictly distinguishes real Razorpay Test Mode from synthetic offline simulation (`SYNTHETIC_OFFLINE_FIXTURE_RUN`).

---

## 3. What Needs to Be Done Next
1. Execute **E9 — Final End-to-End Demonstration Certification**.
2. Never automatically begin E9 without explicit instruction.
