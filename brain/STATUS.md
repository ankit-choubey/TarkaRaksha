# STATUS.md — TarkaRaksha Execution State Tracker

## Project
**TarkaRaksha** — Agentic Transaction Integrity & Recovery Control Plane

## Current Phase
Recovery Loop

## Current Task
T11 — Recovery Loop

## Task Status
COMPLETE (C11 PASS)

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

## Last Verified
2026-09-05T16:32:00+05:30

## Tests Run
- `make test-bootstrap`: PASS (all master brain files, zero root copies, pyproject valid, zero secrets)
- `make test-env`: PASS (toolchains verified, Next.js build clean, smoke tests pass)
- `pytest` (189 passed in 2.96s):
  - `testing/unit/test_recovery.py` (18 tests): recoverable economic drift classification (overcharge with discrepancy), non-recoverable semantic drift (unauthorized SKU/quantity mismatch), UNKNOWN state classification for missing evidence, attempt budget exhaustion escalation to ABSTAIN, expired intent classification escalation to ABSTAIN, valid ActionRequest validation, strict rejection of forbidden CAPTURE action in recovery, rejection of amount exceeding authorized max_total, rejection of amount exceeding MRDP discrepancy, rejection of illegal lifecycle states (CREATED/EXECUTING), recovery executor refund execution producing authoritative evidence and canonical lifecycle event, recovery idempotency returning cached result on duplicate key, attempt budget enforcement (3 allowed, 4th raises `RecoveryExhaustedError`), deterministic revalidation restoring PASS on compensatory refund, deterministic revalidation leaving DRIFT on insufficient refund, full transaction service recovery lifecycle (DRIFT -> RECOVERING -> REVALIDATING -> PASS), non-recoverable drift transition to ABSTAIN, and FastAPI REST endpoint (`/api/v1/transaction/recover`).
  - `testing/unit/test_recovery_adversarial.py` (11 tests): prompt injection in MRDP remediation text inert to policy, AI proposal requesting CAPTURE rejected, AI manipulated high-confidence score cannot bypass deterministic boundaries, currency mismatch attack rejected, intent ID mismatch rejected, post-expiration compensatory action rejected, duplicate ActionRequest replay defense, recovery attempt from CREATED state rejected, direct skip from DRIFT to PASS rejected, revalidation invocation from CREATED rejected, and advisory AI evidence cannot override authoritative Razorpay evidence.
  - `testing/unit/test_transaction_slice.py` (7 tests): complete transaction slice happy path, intent-to-order binding and constraint preservation, server-side HMAC-SHA256 signature verification, state machine lifecycle progression (CREATED -> EXECUTING -> OBSERVING -> VERIFYING -> PASS), bounded polling fallback to UNKNOWN with MRDP generation, FastAPI REST endpoints (`/api/v1/transaction/create`, `/api/v1/transaction/complete`, `/api/v1/transaction/{id}`, `/api/v1/transaction/{id}/mrdp`).
  - `testing/unit/test_transaction_adversarial.py` (10 tests): cryptographic signature forgery rejection, wrong order/payment association rejection, economic DRIFT overcharge producing MRDP with exact discrepancy, semantic DRIFT unauthorized SKU detection, temporal DRIFT expired intent detection, duplicate completion idempotency without state corruption, intent contract immutability enforcement, adapter cannot independently declare PASS, secret leakage prevention across models and logs, live Razorpay Test Mode smoke test.
  - `testing/unit/test_payment_adapter.py` (12 tests): order creation, raw order parsing, float rejection, minimum amount guard, raw payment parsing, fake provider retrieval, signature verification, webhook verification, exception translation, missing credentials error.
  - `testing/unit/test_payment_adversarial.py` (7 tests): signature forgery, unverified webhook rejection, replay deduplication via T06, prompt injection in notes as inert text, deterministic engine isolation, credential security, real Test Mode smoke test.
  - `testing/unit/test_ai_agent.py` (16 tests): valid intent parsing, empty prompt rejection, missing required fields, float amount rejection, quantity violations, budget inconsistency, bounded retries on malformed JSON, valid advisory recovery proposals, CAPTURE action rejection, refund exceeding discrepancy rejection, currency mismatch rejection, confidence informational invariant, AI provider failure matrix.
  - `testing/unit/test_ai_adversarial.py` (10 tests): budget increase attempt rejected, AI opinion cannot create PASS status, prompt injection in user intent treated as inert text, prompt injection in recovery reasoning rejected, extra unexpected fields rejected, boolean-as-integer rejected, string-as-integer rejected, nulls rejected, deterministic engine and MRDP zero AI calls verification, real Groq live smoke test verified.
  - `testing/unit/test_mrdp.py` (5 tests): valid DRIFT proof generation from IntegrityResult and EvidenceBundle, canonical fields and aliases, stable error code taxonomy, UNKNOWN diagnostic proofs, and 100x identical deterministic digest stability.
  - `testing/unit/test_mrdp_adversarial.py` (5 tests): safety boundary blocking budget increases / verifier bypass in remediation, tamper detection catching payload field mutation via SHA-256 digest invalidation, prompt injection payloads treated strictly as inert strings, Pydantic immutability enforcement, and round-trip intent preservation.
  - `testing/unit/test_evidence.py` (9 tests): source taxonomy validation, explicit authority tiers and ranking, timezone-aware timestamp validation, monetary value normalization into Money, conflict resolution via authority dominance, irreconcilable tie at top tier (UNKNOWN), evidence deduplication, immutability, 100x repeated determinism.
  - `testing/unit/test_evidence_adversarial.py` (6 tests): prompt injection in evidence payloads as inert data, fake claims cannot override gateway truth, extra unexpected fields rejected by strict schema, float financial injection rejected, temporal anomalies rejected, deeply nested JSON treated as inert dict.
  - `testing/unit/test_state_machine.py` (10 tests): normal lifecycle, drift recovery, unknown resolution, abstain branches, invalid transitions, intent immutability, and determinism.
  - `testing/unit/test_state_machine_adversarial.py` (7 tests): prompt injection in reasons, untrusted AI triggers, lifecycle skipping, financial actions in unauthorized states, and temporal regression.
  - `testing/unit/test_engine.py` (21 tests): Economic boundary (49999 PASS, 50000 PASS, 50001 DRIFT), currency mismatch, missing evidence UNKNOWN, authority conflict resolution, Semantic SKU/quantity/substitutions, Temporal duplicate/expiration/double-capture/late-success, Priority semantics (DRIFT > UNKNOWN > PASS), 100x identical determinism run, adversarial prompt injection resistance.
  - `testing/unit/test_money.py` (12 tests): integer minor units, float rejection, bool rejection, currency checks.
  - `testing/unit/test_models.py` (18 tests): domain contracts, serialization round-trips.
  - `testing/unit/test_environment.py` (5 tests): baseline environment checks.

## Environment & Toolchains Verified
- **Python**: 3.12.12 (via project-local `.venv`)
- **FastAPI**: 0.141.1, **Uvicorn**: 0.52.4, **Pydantic**: 2.13.5, **HTTPX**: 0.28.1, **Pytest**: 9.1.1
- **AI Client**: `groq` 1.7.0 (instantiation and live smoke test verified with `qwen/qwen3.8-27b`)
- **Payment Client**: `razorpay` 2.0.1 (live Test Mode order creation and HMAC-SHA256 signature verification verified)
- **Node.js**: v25.2.1, **npm**: 11.6.2
- **Frontend Stack**: Next.js 15.5.25 (App Router, Turbopack), TypeScript 5, Tailwind CSS 4, Lucide icons

## Real Razorpay Test Mode Status
- **PASS**: Live credentials in `.env` verified against Razorpay API. Real Test Mode order created successfully (`order_TYKIyG8zBaphGY`), returned order ID bound to intent, integer minor units verified, and constant-time HMAC-SHA256 verification confirmed.

## Known Failures
None

## Blockers
None

## Important Decisions
1. **The Closed Recovery Loop**:
   - Implemented the central differentiator of TarkaRaksha:
     `DRIFT / RECOVERABLE UNKNOWN → MRDP / Evidence → Recovery Proposal → Deterministic Safety Validation → Bounded Recovery Action → Observe → Deterministic Revalidation → PASS / DRIFT / UNKNOWN / ABSTAIN`.
2. **Absolute Safety & Intent Envelope Invariance**:
   - The original authorized intent is strictly immutable. Recovery can repair discrepancy but can NEVER expand original authority (no amount increase, no SKU/quantity substitution, no silent expiration extension).
3. **Financial Action Boundaries**:
   - `ActionType.CAPTURE` is strictly forbidden in the recovery control plane.
   - Financial actions require deterministic authorization; AI cannot authorize actions or declare PASS.
4. **Deterministic Recovery Policy & Classification**:
   - Pure function of explicit inputs (`contract`, `integrity_result`, `mrdp`, `current_attempt`).
   - Explicitly classifies into `RECOVERABLE`, `NON_RECOVERABLE`, `UNKNOWN`, and `ABSTAIN`.
   - Identical inputs produce identical classification. Zero AI dependence.
5. **Bounded Execution & Recovery Idempotency**:
   - Maximum recovery attempts bounded at 3 (`MAX_RECOVERY_ATTEMPTS = 3`). Attempt 4 forces terminal `ABSTAIN`.
   - Idempotency table caches `RecoveryExecutionResult` by `idempotency_key`, preventing duplicate financial execution.
6. **Deterministic Revalidation & Economic Netting**:
   - Recovery execution alone NEVER declares `PASS`.
   - Compensatory refund evidence is netted against original captured amount to derive authoritative net total evidence, which is re-evaluated by the pure T04 deterministic engine. Only the deterministic engine determines the revalidation verdict.
7. **Frontend Control Plane Recovery Trigger**:
   - Added interactive "Execute Bounded Recovery Action" trigger to `frontend/app/page.tsx` for DRIFT transactions, demonstrating the full live loop.

## Active Branch
`main`

## Last Verified Remote Commit
902355a (docs: finalize verified remote commit reference in STATUS.md)

## Next Task
**T12 — UNKNOWN Resolution** (Consuming T05 `RESOLVING` state + T06 conflict resolution + T07 MRDP + automated gateway polling & evidence collection)

## Source Documents Consulted
- `brain/TarkaRaksha_IDEA.md` (§31, §34, §35, §37)
- `brain/TarkaRaksha_Execution.md` (§7.34, §8.39)
- `brain/TarkaRaksha_TESTING.md` (§9.47–§9.51)
- `brain/CONTEXT.md`
- `brain/HANDOFF.md`
