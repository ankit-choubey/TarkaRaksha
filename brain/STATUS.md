# STATUS.md — TarkaRaksha Execution State Tracker

## Project
**TarkaRaksha** — Agentic Transaction Integrity & Recovery Control Plane

## Current Phase
Payment Gateway Adapter Layer

## Current Task
T09 — Razorpay Adapter

## Task Status
COMPLETE

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

## Last Verified
2026-09-05T15:47:00+05:30

## Tests Run
- `make test-bootstrap`: PASS (all master brain files, zero root copies, pyproject valid, zero secrets)
- `make test-env`: PASS (toolchains verified, Next.js build clean, smoke tests pass)
- `pytest` (142 passed, 1 skipped in 2.30s):
  - `testing/unit/test_payment_adapter.py` (12 tests): order creation in integer minor units, parse raw Razorpay order, float rejection, minimum amount guard, parse raw Razorpay payment, fetch payment/order payments in fake provider, not found handling, payment signature verification success, signature verification failure cases (wrong secret, tampered order/payment, invalid hex), webhook signature verification, RazorpayAdapter exception translation (401, 404, 429, timeout, 500), missing credentials configuration error.
  - `testing/unit/test_payment_adversarial.py` (7 tests, 6 passed, 1 skipped): signature forgery rejection, unverified webhook rejection, webhook replay and event deduplication via T06, prompt injection in payment notes treated as inert text, deterministic engine isolation (adapter makes zero integrity decisions), credential security (secrets never leaked in repr or exceptions), real Razorpay Test Mode smoke test (cleanly skipped per availability).
  - `testing/unit/test_ai_agent.py` (16 tests): valid intent parsing, empty prompt rejection, missing required fields, float amount rejection, quantity violations, budget inconsistency, bounded retries on malformed JSON, valid advisory recovery proposals, CAPTURE action rejection, refund exceeding discrepancy rejection, currency mismatch rejection, confidence informational invariant, AI provider failure matrix (timeout, rate limit, unavailable).
  - `testing/unit/test_ai_adversarial.py` (10 tests): budget increase attempt rejected with contract immutability, AI opinion cannot create PASS status, prompt injection in user intent treated as inert text, prompt injection in recovery reasoning rejected, extra unexpected fields rejected, boolean-as-integer rejected, string-as-integer rejected, nulls rejected, deterministic engine and MRDP zero AI calls verification, real Groq live smoke test verified.
  - `testing/unit/test_mrdp.py` (5 tests): valid DRIFT proof generation from IntegrityResult and EvidenceBundle, canonical fields and aliases (`expected`, `observed`, `evidence_refs`, `remediation_hint`), stable error code taxonomy (`ECONOMIC_DRIFT_CEILING_EXCEEDED`, etc.), UNKNOWN diagnostic proofs, and 100x identical deterministic digest stability.
  - `testing/unit/test_mrdp_adversarial.py` (5 tests): safety boundary blocking budget increases / verifier bypass in remediation, tamper detection catching payload field mutation via SHA-256 digest invalidation, prompt injection payloads treated strictly as inert strings, Pydantic immutability enforcement, and round-trip intent preservation (DRIFT -> MRDP -> RecoveryProposal).
  - `testing/unit/test_evidence.py` (9 tests): source taxonomy validation, explicit authority tiers and ranking, timezone-aware timestamp validation, monetary value normalization into Money, conflict resolution via authority dominance, irreconcilable tie at top tier (UNKNOWN), evidence deduplication, immutability, 100x repeated determinism
  - `testing/unit/test_evidence_adversarial.py` (6 tests): prompt injection in evidence payloads as inert data, fake claims cannot override gateway truth, extra unexpected fields rejected by strict schema, float financial injection rejected, temporal anomalies (naive/unparseable) rejected, deeply nested JSON treated as inert dict
  - `testing/unit/test_state_machine.py` (10 tests): normal lifecycle, drift recovery, unknown resolution, abstain branches, invalid transitions, intent immutability, and determinism
  - `testing/unit/test_state_machine_adversarial.py` (7 tests): prompt injection in reasons, untrusted AI triggers, lifecycle skipping, financial actions in unauthorized states, and temporal regression
  - `testing/unit/test_engine.py` (21 tests): Economic boundary (49999 PASS, 50000 PASS, 50001 DRIFT), currency mismatch, missing evidence UNKNOWN, authority conflict resolution, Semantic SKU/quantity/substitutions, Temporal duplicate/expiration/double-capture/late-success, Priority semantics (DRIFT > UNKNOWN > PASS), 100x identical determinism run, adversarial prompt injection resistance
  - `testing/unit/test_money.py` (12 tests): integer minor units, float rejection, bool rejection, currency checks
  - `testing/unit/test_models.py` (18 tests): domain contracts, serialization round-trips
  - `testing/unit/test_environment.py` (5 tests): baseline environment checks

## Environment & Toolchains Verified
- **Python**: 3.12.12 (via project-local `.venv`)
- **FastAPI**: 0.141.1, **Uvicorn**: 0.52.4, **Pydantic**: 2.13.5, **HTTPX**: 0.28.1, **Pytest**: 9.1.1
- **AI Client**: `groq` 1.7.0 (instantiation and live smoke test verified with `qwen/qwen3.8-27b`)
- **Payment Client**: `razorpay` 2.0.1 (instantiation and SDK signatures verified)
- **Node.js**: v25.2.1, **npm**: 11.6.2
- **Frontend Stack**: Next.js 15.5.25 (App Router, Turbopack), TypeScript 5, Tailwind CSS 4, shadcn/ui

## Known Failures
None

## Blockers
None

## Important Decisions
1. **Narrow Payment Provider Interface**:
   - `PaymentProvider` ABC cleanly shields the deterministic domain from gateway-specific schema shapes.
   - Provider-neutral models: `ProviderOrder`, `ProviderPayment`, `ProviderWebhookEvent` ensure amounts remain in integer minor units (`Money`).
2. **Cryptographic Signature Verification**:
   - Payment checkout signature verified using HMAC-SHA256 over `order_id|payment_id`.
   - Webhook signature verified using HMAC-SHA256 over raw request body.
   - Constant-time comparison (`hmac.compare_digest`) prevents timing attacks.
   - Unverified signatures raise `PaymentSignatureError` and cannot produce authoritative evidence.
3. **Canonical Evidence Translation (T06 Integration)**:
   - Gateway state is normalized into `Evidence` items with `EvidenceSource.RAZORPAY` and `EvidenceAuthority.AUTHORITATIVE`.
   - Webhooks produce `CanonicalEvent` and evidence items; duplicate deliveries are deduplicated via `deduplicate_events()`.
4. **Zero Business Logic in Adapter**:
   - RazorpayAdapter never makes integrity decisions (never evaluates `amount <= max_total` or declares PASS/DRIFT/UNKNOWN).
   - Gateway state is purely evidence for the deterministic integrity engine.
5. **Credential Security**:
   - Secret keys (`RAZORPAY_KEY_SECRET`) are never logged, printed, or included in string representations.
   - Real Razorpay Test Mode smoke test safely skipped when credentials are not configured in environment.

## Active Branch
`main`

## Last Verified Remote Commit
b22200f (test: add adversarial, signature forgery, webhook replay, and credential security tests)

## Next Task
**T10 — First Complete Real Transaction Slice** (Vertical slice: Natural Language Intent -> IntentContract -> Razorpay Order -> Checkout -> Payment -> Verification -> Evidence -> Integrity Engine)

## Parallel Candidates
With T09 complete, the payment provider adapter is verified. T10 assembles the first vertical end-to-end transaction slice, consuming T03, T04, T05, T06, T07, T08, and T09 sequentially.

## Source Documents Consulted
- `brain/TarkaRaksha_IDEA.md` (§31, §34)
- `brain/TarkaRaksha_Execution.md` (§7.32, §8.37)
- `brain/TarkaRaksha_TESTING.md` (§9.37–§9.41)
- `brain/CONTEXT.md`
- `brain/HANDOFF.md`

## External Sources Consulted
- Razorpay Payments API Documentation: Order creation, payment retrieval, and fetch order payments
- Razorpay Webhook Documentation: Signature verification with HMAC-SHA256 and event payloads
- Razorpay Python SDK v2.0.1 implementation and error hierarchy

## Open Questions
None
