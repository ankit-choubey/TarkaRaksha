# STATUS.md — TarkaRaksha Execution State Tracker

## Project
**TarkaRaksha** — Agentic Transaction Integrity & Recovery Control Plane

## Current Phase
AI Integration Layer (Intent Parser & Advisory Recovery Agent)

## Current Task
T08 — Groq AI

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

## Last Verified
2026-09-05T15:40:00+05:30

## Tests Run
- `make test-bootstrap`: PASS (all master brain files, zero root copies, pyproject valid, zero secrets)
- `make test-env`: PASS (toolchains verified, Next.js build clean, smoke tests pass)
- `pytest` (124 passed in 1.07s):
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
- **Payment Client**: `razorpay` 2.0.1 (instantiation verified)
- **Node.js**: v25.2.1, **npm**: 11.6.2
- **Frontend Stack**: Next.js 15.5.25 (App Router, Turbopack), TypeScript 5, Tailwind CSS 4, shadcn/ui

## Known Failures
None

## Blockers
None

## Important Decisions
1. **Untrusted AI Boundary**:
   - AI is advisory. All outputs from Groq or any model are treated as untrusted inputs.
   - The validation pipeline is strictly: `Natural Language -> Groq -> Structured JSON -> Pydantic Intermediate DTO -> Domain Validation -> Validated Domain Contract / RecoveryProposal`.
   - AI can never authorize payments, capture funds, increase budget, modify authorized SKU/quantity/currency, or declare PASS.
2. **Narrow Provider Abstraction**:
   - `AIProvider` ABC decouples domain services from the Groq SDK.
   - `GroqAIProvider` handles production calls with timeout/rate-limit translation.
   - `FakeAIProvider` enables deterministic, network-free local testing.
3. **Model Selection**:
   - Configured `qwen/qwen3.8-27b` as default model due to verified support on Groq for `json_object` structured output and fast inference; configurable via `GROQ_MODEL`.
4. **Bounded Retries & Safe Fallback**:
   - Bounded retry (default 2 retries) catches transient network errors and JSON formatting glitches.
   - If retries exhaust or model produces invalid schema, the system fails safely with `IntentParsingError` or safe abstain, never fabricating authorization.
5. **Deterministic Engine Independence**:
   - `evaluate_integrity()` and `build_mrdp()` make zero AI calls; deterministic verification remains 100% independent of external AI availability.

## Active Branch
`main`

## Last Verified Remote Commit
8cf3b65 (docs: synchronize persistent brain and handoff for T08 completion)
Prior Remote Commits: 326f72b, 81400cf, 793e32d, 62fe47f, ee34cc8, 3ebec10, dc4961a, ...

## Next Task
**T09 — Razorpay Adapter** (Razorpay payment gateway adapter: order creation, payment verification, webhook ingestion, test mode integration)

## Parallel Candidates
With T08 complete, the AI intent parsing and advisory recovery layer is verified. T09 builds the payment adapter, which consumes validated intent and produces evidence for the deterministic engine. Work proceeds sequentially.

## Source Documents Consulted
- `brain/TarkaRaksha_IDEA.md` (§31, §34)
- `brain/TarkaRaksha_Execution.md` (§7.27–§7.31, §8.33–§8.36)
- `brain/TarkaRaksha_TESTING.md` (§9.30–§9.36)
- `brain/CONTEXT.md`
- `brain/HANDOFF.md`

## External Sources Consulted
- Groq Cloud API documentation on chat completions, model catalog, and `response_format={'type': 'json_object'}`
- Official Groq Python SDK v1.7.0 client specification

## Open Questions
None
