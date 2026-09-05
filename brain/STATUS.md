# STATUS.md — TarkaRaksha Execution State Tracker

## Project
**TarkaRaksha** — Agentic Transaction Integrity & Recovery Control Plane

## Current Phase
Lifecycle State Machine

## Current Task
T05 — State Machine

## Task Status
COMPLETE

## Completed Tasks
- [x] **T01 — Repository Bootstrap** (Completed 2026-09-05)
- [x] **T02 — Environment** (Completed 2026-09-05)
- [x] **T03 — Domain Contracts** (Completed 2026-09-05)
- [x] **T04 — Deterministic Engine** (Completed 2026-09-05)
- [x] **T05 — State Machine** (Completed 2026-09-05)

## Last Verified
2026-09-05T14:35:00+05:30

## Tests Run
- `make test-bootstrap`: PASS (all master brain files, zero root copies, pyproject valid, zero secrets)
- `make test-env`: PASS (toolchains verified, Next.js build clean, smoke tests pass)
- `pytest` (73 passed in 0.17s):
  - `testing/unit/test_state_machine.py` (10 tests): normal lifecycle (CREATED->EXECUTING->OBSERVING->VERIFYING->PASS), DRIFT recovery/revalidation flow, UNKNOWN resolution/revalidation/abstain flow, forbidden transitions (PASS->EXECUTING, ABSTAIN->CAPTURE, CREATED->PASS), atomic state immutability on failure, intent immutability preservation, excessive financial action guards, apply_integrity_result verification, 50x repeated determinism
  - `testing/unit/test_state_machine_adversarial.py` (7 tests): prompt injection resistance in transition reason, untrusted AI trigger rejection, lifecycle skipping attacks, financial capture in unauthorized states, intent mutation attack detection, temporal regression and naive timestamp rejection, direct revalidation rejection without drift/unknown
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
1. **Explicit Lifecycle Graph**: Mapped all 11 lifecycle states in `PERMITTED_TRANSITIONS`. Self-transitions and skipping intermediate stages are strictly forbidden.
2. **Deterministic Consumption of T04 Results**: `apply_integrity_result` directly translates `IntegrityResult` outcomes to matching destination states (`PASS`, `DRIFT`, `UNKNOWN`) exclusively from `VERIFYING` or `REVALIDATING`. Zero rule logic duplication.
3. **Hard Financial & Safety Invariants**:
   - `UNKNOWN` permanently blocks financial actions until resolution.
   - `DRIFT` strictly prohibits financial capture without successful revalidation.
   - `ABSTAIN` is terminal and blocks all financial execution.
   - `Recovery` strictly preserves original `IntentContract` limits and specifications.
   - AI and agent triggers are strictly advisory and require deterministic verification.
4. **Pure & Explicit Time**: State transitions accept explicit timezone-aware `datetime` objects; backward timestamp movement is rejected.

## Active Branch
`main`

## Last Verified Remote Commit
812a1c4 (test: add adversarial tests and security invariant hardening)
Prior Remote Commits: d271fec, 5be768a, 02f5789, 5f41a3c, c898ad8, 3d07dd1, 6ea3c9c, 84c7142, f9fa88c, 17e99c9, 1a740b0, beca9e8, 020cf38

## Next Task
**T06 — Evidence** (Evidence normalization: USER_INTENT, AGENT, MERCHANT, RAZORPAY, SYSTEM, REPLAY into single canonical evidence bundle with authority tiers)

## Parallel Candidates
With T05 complete, the transaction state machine is verified. T06 (Evidence Normalization) provides the structured evidence pipeline feeding the deterministic engine and state machine, so work proceeds sequentially.

## Source Documents Consulted
- `brain/TarkaRaksha_IDEA.md` (§87–§90)
- `brain/TarkaRaksha_Execution.md` (§7.21–§7.22, §8.23–§8.25)
- `brain/TarkaRaksha_TESTING.md` (§9.17–§9.21)
- `brain/CONTEXT.md`
- `brain/HANDOFF.md`

## External Sources Consulted
- Pydantic v2 documentation on `ConfigDict(frozen=True, extra='forbid', strict=True)`
- Python datetime library standards regarding timezone awareness and comparison

## Open Questions
None
