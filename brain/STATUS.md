# STATUS.md — TarkaRaksha Execution State Tracker

## Project
**TarkaRaksha** — Agentic Transaction Integrity & Recovery Control Plane

## Current Phase
Domain Contracts

## Current Task
T03 — Domain Contracts

## Task Status
COMPLETE

## Completed Tasks
- [x] **T01 — Repository Bootstrap** (Completed 2026-09-05)
- [x] **T02 — Environment** (Completed 2026-09-05)
- [x] **T03 — Domain Contracts** (Completed 2026-09-05)

## Last Verified
2026-09-05T14:10:00+05:30

## Tests Run
- `make test-bootstrap`: PASS (canonical docs in brain/, zero root copies, pyproject valid, zero secrets)
- `make test-env`: PASS (Python 3.12, Node.js 25.2, npm 11.6, Git 2.50, backend packages, AI/payment client imports, Next.js 15 build, pytest smoke)
- `pytest` (35 passed in 0.16s):
  - `testing/unit/test_money.py` (12 tests): strict integer minor units, float rejection, bool rejection, currency ISO-4217, immutability, exact arithmetic, comparisons, serialization round-trip
  - `testing/unit/test_models.py` (18 tests): IntentItem, IntentContract, Authorization, CanonicalEvent, Evidence, IntegrityResult, Decision, MRDP, RecoveryProposal, ActionRequest, Transaction, round-trip serialization for all models
  - `testing/unit/test_environment.py` (5 tests): baseline runtime smoke tests

## Environment & Toolchains Verified
- **Python**: 3.12.12 (via project-local `.venv`)
- **FastAPI**: 0.141.1, **Uvicorn**: 0.52.4, **Pydantic**: 2.13.5, **HTTPX**: 0.28.1, **Pytest**: 9.1.1
- **AI Client**: `groq` 1.7.0 (instantiation verified)
- **Payment Client**: `razorpay` 2.0.1 (instantiation verified)
- **Node.js**: v25.2.1, **npm**: 11.6.2
- **Frontend Stack**: Next.js 15.5.25 (App Router, Turbopack), TypeScript 5, Tailwind CSS 4, shadcn/ui

## Known Failures
None

## Blockers
None

## Important Decisions
1. **Pydantic v2 Idiomatic Typing**: Enforced `frozen=True`, `extra='forbid'`, and `strict=True` across domain contracts.
2. **Strict Integer Minor Units**: `Money` strictly rejects `float` and `bool` (subclass of int in Python) via custom `@field_validator(..., mode='before')` returning clear validation errors.
3. **First-Class UNKNOWN**: `IntegrityStatus.UNKNOWN` is explicitly distinct from `PASS` and `DRIFT`.
4. **Untrusted AI Invariant**: `RecoveryProposal` is typed as an advisory proposal and cannot be executed directly; only validated `ActionRequest` can be authorized.
5. **Evidence Authority Hierarchy**: Implemented deterministic `authority_rank` on `Evidence` (`RAZORPAY` > `INTENT` > `MERCHANT` > `REPLAY` > `AGENT` > `SYNTHETIC`).

## Active Branch
`main`

## Last Verified Remote Commit
f9fa88c (chore: configure development environment)
Prior Remote Commits: 17e99c9, 1a740b0, beca9e8, 020cf38

## Next Task
**T04 — Deterministic Engine** (Implement core verification functions: economic_check, semantic_check, temporal_check, evaluate_integrity)

## Parallel Candidates
With T03 complete, the domain boundary is established. However, T04 directly depends on T03 contracts to build the deterministic rule evaluation logic, so T04 should proceed sequentially.

## Source Documents Consulted
- `brain/TarkaRaksha_IDEA.md`
- `brain/TarkaRaksha_Execution.md` (§7.15–§7.21, §8.10–§8.14)
- `brain/TarkaRaksha_TESTING.md` (§9.5–§9.9)
- `brain/CONTEXT.md`
- `brain/HANDOFF.md`

## External Sources Consulted
- Pydantic v2 documentation on `ConfigDict(frozen=True, extra='forbid', strict=True)` and `@field_validator(..., mode='before')`
- ISO 4217 Currency Code specifications (3-letter alpha representation)
- Razorpay Payment API documentation (verified currency minor subunits representation for amounts)

## Open Questions
None
