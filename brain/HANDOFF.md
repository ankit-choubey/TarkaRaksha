# HANDOFF.md — Agent Session Handoff Document

## Handoff Metadata
- **Current Task Completed**: `E6 — Failure → Recovery → Revalidation Hero Loop`
- **Current Checkpoint**: `C_E6 — PASS`
- **Baseline SHA**: `f208436`
- **Next Task**: `E7 — Real-time Control-Room Data Surface` (Await human owner approval)
- **Active Branch**: `main`
- **Handoff Timestamp**: 2026-09-06T15:20:00+05:30

---

## 1. What Was Done in E6 & Fix-Only Cleanup

1. **Canonical E6 Failure → Recovery → Revalidation Hero Loop**:
   - High-value commercial transaction proving the closed-loop thesis:
     - **Canonical Authorization**: Ceiling ₹50,000 (5,000,000 paise), SKU `SKU-4K-MONITOR-01`, Qty 1, Shipping ceiling ₹3,000, Currency INR.
     - **Initial Valid Offer**: ₹47,000 product + ₹3,000 shipping = ₹50,000 total. Deterministic evaluation: `PASS`.
     - **Controlled Mutation**: Mutated total ₹55,000 (price drift). Deterministic evaluation: `DRIFT`.
     - **Cryptographic Proof**: Generated Machine-Readable Drift Proof (`MRDP`) with SHA-256 digest capturing expected ₹50,000 vs observed ₹55,000.
     - **Bounded Remediation**: Buyer replan within original immutable authorization (₹50,000 max). Merchant counter-offer restores ₹47,000 product + ₹3,000 shipping = ₹50,000 total.
     - **Deterministic Revalidation**: Remediated offer independently re-evaluated; yields `PASS`.
     - **Payment Gating & Execution**: Payment is strictly blocked while in DRIFT or UNKNOWN; execution unlocks only upon revalidation PASS.
     - **Authoritative Restored Outcome**: System authoritatively emits `TRANSACTION RESTORED`.
   - **Provider Execution Distinction**:
     - When valid Razorpay sandbox credentials (`RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`) are configured, real Razorpay Test Mode order creation and HMAC-SHA256 signature capture are verified.
     - When sandbox credentials are not present or placeholders, synthetic offline payment simulation is executed. Gateway success is never falsely claimed.
   - **AI Advisory vs Deterministic Logic**:
     - Deterministic backend logic authoritatively decides all integrity verdicts (`PASS`, `DRIFT`, `UNKNOWN`).
     - Advisory AI explanation (via default `openai/gpt-oss-20b`) is strictly descriptive, with structured deterministic fallback.

2. **Fix-Only Cleanup Completed**:
   - **Model Decision**: Kept `openai/gpt-oss-20b` as default `GROQ_MODEL` in `backend/app/core/config.py`.
   - **Restored Intent Parser**: Restored `backend/app/services/ai/intent_parser.py` byte-for-byte to pre-E6 baseline `f208436`.
   - **Explicit Scenario Selection**: Refactored `execute_hero_journey` and API endpoint `POST /api/v1/hero-transaction/run` to explicitly accept `scenario: Optional[str] = "default"`. Passing `scenario="e6"` deterministically selects E6 canonical flow without guessing from monetary amounts.
   - **I22 Backward Compatibility**: 100% preserved. All 17 existing I22 hero tests pass green.
   - **E6 Focused Tests**: 14 tests pass green in `testing/unit/test_e6_failure_recovery_revalidation.py`.
   - **Total Hero Tests**: 31 tests (14 E6 + 17 I22) pass green.
   - **Full Regression**: 992 tests pass green.

---

## 2. Core Invariants Maintained
- **Principle**: "AI proposes. Evidence proves. Deterministic logic decides."
- **Immutable Authorization**: Recovery and replanning may alter proposed prices, but never change the `IntentContract` ceiling (₹50,000) or authorization constraints.
- **Deterministic Revalidation Gate**: Payment is strictly prohibited while a transaction is in DRIFT or UNKNOWN; execution unlocks only after fresh deterministic revalidation yields PASS.
- **Authoritative Outcome Emitted**: Final restored message ("TRANSACTION RESTORED") reflects verified state, never synthesized independently.
- **Provider Accuracy**: Strictly distinguishes real Razorpay Test Mode execution from synthetic offline payment execution.
- **Financial Minor Units**: All monetary values strictly use integer minor units (paise/cents). Zero floats.

---

## 3. What Needs to Be Done Next
1. Execute **E7 — Real-time Control-Room Data Surface**.
2. Await human owner instruction / approval before beginning E7.
