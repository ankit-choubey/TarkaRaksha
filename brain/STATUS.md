# STATUS.md — TarkaRaksha Execution State Tracker

## Project
**TarkaRaksha** — Agentic Transaction Integrity & Recovery Control Plane

## Current Phase
Deterministic Integrity Engine

## Current Task
T04 — Deterministic Engine

## Task Status
COMPLETE

## Completed Tasks
- [x] **T01 — Repository Bootstrap** (Completed 2026-09-05)
- [x] **T02 — Environment** (Completed 2026-09-05)
- [x] **T03 — Domain Contracts** (Completed 2026-09-05)
- [x] **T04 — Deterministic Engine** (Completed 2026-09-05)

## Last Verified
2026-09-05T14:24:00+05:30

## Tests Run
- `make test-bootstrap`: PASS (all master brain files, zero root copies, pyproject valid, zero secrets)
- `make test-env`: PASS (toolchains verified, Next.js build clean, smoke tests pass)
- `pytest` (56 passed in 0.21s):
  - `testing/unit/test_engine.py` (21 tests): Economic boundary (49999 PASS, 50000 PASS, 50001 DRIFT), currency mismatch, missing evidence UNKNOWN, authority conflict resolution, Semantic SKU/quantity/substitutions, Temporal duplicate/expiration/double-capture/late-success, Priority semantics (DRIFT > UNKNOWN > PASS), 100x identical determinism run, adversarial prompt injection resistance
  - `testing/unit/test_money.py` (12 tests): integer minor units, float rejection, bool rejection, currency checks
  - `testing/unit/test_models.py` (18 tests): domain contracts, serialization round-trips
  - `testing/unit/test_environment.py` (5 tests): baseline environment checks

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
1. **Three Orthogonal Drift Domains**: Modularized checks into `check_economic`, `check_semantic`, and `check_temporal` in `backend/app/domain/rules/`.
2. **Deterministic Priority Semantics**:
   - If any sub-check produces `DRIFT` -> overall `DRIFT` (violations aggregated).
   - If no `DRIFT`, but any sub-check produces `UNKNOWN` -> overall `UNKNOWN` (safety invariant: missing evidence never defaults to `PASS`).
   - Only when all sub-checks produce `PASS` -> overall `PASS`.
3. **No External or Network Dependencies**: Integrity evaluation is strictly offline and pure; zero LLM calls, zero database calls, zero current-time dependencies (`reference_time` explicitly passed).
4. **Authority-Based Conflict Resolution**: Conflicting evidence resolved via `authority_rank` (`RAZORPAY` > `INTENT` > `MERCHANT` > `REPLAY` > `AGENT` > `SYNTHETIC`). Unresolvable ties at highest tier yield `UNKNOWN`.

## Active Branch
`main`

## Last Verified Remote Commit
6ea3c9c (feat: implement deterministic integrity engine)
Prior Remote Commits: 84c7142, f9fa88c, 17e99c9, 1a740b0, beca9e8, 020cf38

## Next Task
**T05 — State Machine** (Implement lifecycle states: CREATED, EXECUTING, OBSERVING, VERIFYING, PASS, DRIFT, UNKNOWN, RESOLVING, ABSTAIN, RECOVERING, REVALIDATING)

## Parallel Candidates
With T04 complete, the deterministic engine core is verified. T05 (State Machine) depends on the `IntegrityResult` output of T04 to orchestrate state transitions, so T05 proceeds sequentially.

## Source Documents Consulted
- `brain/TarkaRaksha_IDEA.md`
- `brain/TarkaRaksha_Execution.md` (§7.17–§7.20, §8.15–§8.22)
- `brain/TarkaRaksha_TESTING.md` (§9.10–§9.16)
- `brain/CONTEXT.md`
- `brain/HANDOFF.md`

## External Sources Consulted
- Pydantic v2 documentation on `ConfigDict(frozen=True, extra='forbid', strict=True)` and `@field_validator(..., mode='before')`
- ISO 4217 Currency Code specifications (3-letter alpha representation)
- Razorpay Payment API documentation (verified currency minor subunits representation for amounts)

## Open Questions
None
