# HANDOFF.md — Agent Session Handoff Document

## Handoff Metadata
- **Current Task Completed**: `T08 — Groq AI`
- **Current Checkpoint**: `C08 — PASS`
- **Next Task**: `T09 — Razorpay Adapter`
- **Active Branch**: `main`
- **Handoff Timestamp**: 2026-09-05T15:40:00+05:30

---

## 1. What Was Done in T08
1. **AI Provider Abstraction & Settings** (`backend/app/core/config.py`, `backend/app/services/ai/provider.py`):
   - Created runtime `Settings` reading `GROQ_API_KEY`, `GROQ_MODEL`, `GROQ_TIMEOUT_SECONDS`, `GROQ_MAX_RETRIES` without secret leakage.
   - Defined `AIProvider` ABC with `generate()`.
   - Implemented `GroqAIProvider` backed by Groq SDK v1.7.0, translating exceptions into `AITimeoutError`, `AIRateLimitError`, `AIUnavailableError`, `AIProviderError`.
   - Implemented deterministic `FakeAIProvider` for isolated, repeatable testing without external network calls.
2. **AI Intermediate DTOs & Error Hierarchy** (`backend/app/services/ai/contracts.py`):
   - `AIIntentExtraction`: Pydantic frozen model for JSON-extracted product specifications, positive integer quantities, integer minor units for financial amounts.
   - `AIRecoverySuggestion`: Pydantic model for proposed corrective action (`ActionType`), advisory compensation amount, reasoning, confidence.
   - Exception hierarchy: `AIError`, `AIProviderError`, `AITimeoutError`, `AIRateLimitError`, `AIUnavailableError`, `StructuredOutputError`, `IntentParsingError`, `UnsafeRecoveryProposalError`.
3. **Intent Parser Service** (`backend/app/services/ai/intent_parser.py`):
   - `parse_intent()`: Pure service function extracting natural language into `AIIntentExtraction`, then validating into authoritative immutable `IntentContract`.
   - Bounded retries on malformed JSON or transient provider errors.
   - Treats natural language prompt injections as inert text data; strictly validates item pricing and budget consistency.
4. **Advisory Recovery Agent Service** (`backend/app/services/ai/recovery_agent.py`):
   - `propose_recovery()`: Analyzes MRDP and IntentContract to propose advisory `RecoveryProposal`.
   - `validate_recovery_proposal_safety()`: Deterministic safety guardrail rejecting any attempt to propose `CAPTURE`, exceed authorized budget `max_total`, exceed detected MRDP discrepancy amounts, mismatch currencies, or use verifier bypass phrases.
   - Invariant: Model confidence (even 99.9%) is purely informational, never financial authorization.
5. **Comprehensive Test Suites**:
   - `testing/unit/test_ai_agent.py`: 16 unit tests covering valid parsing, empty prompt rejection, missing fields, float amount rejection, non-positive quantity rejection, budget inconsistency, bounded retries on malformed JSON, valid recovery proposal, CAPTURE rejection, refund exceeding discrepancy rejection, currency mismatch rejection, confidence informational invariant, AI provider failure matrix.
   - `testing/unit/test_ai_adversarial.py`: 10 tests covering budget increase attempt rejection with contract immutability, AI opinion cannot create PASS status, prompt injection in user intent treated as inert, prompt injection in recovery reasoning rejected, extra unexpected fields rejected, boolean-as-integer rejected, string-as-integer rejected, nulls rejected, deterministic engine and MRDP zero AI calls verification, real Groq live smoke test verified.
   - Full repository test suite: 124/124 passing tests.
6. **Checkpoints & Validation**:
   - `make test-bootstrap`: PASS.
   - `make test-env`: PASS.
   - `pytest`: 124 passed in 1.07s.

---

## 2. Verified Invariants
- **AI Is Strictly Advisory**: LLMs are untrusted inputs. AI cannot authorize payments, capture money, modify budget limits, alter authorized SKUs, or declare PASS.
- **Pydantic & Domain Validation Are Authoritative**: AI structured output is always independently validated by intermediate schemas and domain models.
- **Bounded Retry & Safe Fallback**: Bounded retry catches transient glitches; failure safely triggers `IntentParsingError` or safe abstain, never fabricating authorization.
- **Confidence != Authorization**: Model confidence (even 99.9%) has zero authoritative power over state or financial movement.
- **Deterministic Core Independence**: `evaluate_integrity()` and `build_mrdp()` make zero AI calls and operate completely independently of AI availability.
- **Zero Leaked Secrets**: No API keys are logged or printed.

---

## 3. Explicit Instructions for Next Task (`T09 — Razorpay Adapter`)
When starting `T09`:
1. **Read `brain/STATUS.md` first**.
2. **Read `brain/TarkaRaksha_Execution.md` §7.32, §8.37 (T09)** and `brain/TarkaRaksha_TESTING.md` §9.37–§9.41.
3. **Task Objective**: Implement Razorpay Gateway Adapter:
   - Order creation with integer minor units (paise).
   - Payment fetch / verification.
   - Webhook signature verification (`X-Razorpay-Signature` with HMAC SHA-256).
   - Test mode integration with `FakeRazorpayProvider` for unit tests and real Test Mode client viability.
   - Ingest observed events into `Evidence` / `EvidenceBundle` (T06) for deterministic verification (T04).
4. **Pass Checkpoint C09** before committing and pushing.
