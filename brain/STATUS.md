# STATUS.md — TarkaRaksha Execution State Tracker

## Project
**TarkaRaksha** — Agentic Transaction Integrity & Recovery Control Plane

## Current Phase
Evidence Normalization Layer

## Current Task
T06 — Evidence

## Task Status
COMPLETE

## Completed Tasks
- [x] **T01 — Repository Bootstrap** (Completed 2026-09-05)
- [x] **T02 — Environment** (Completed 2026-09-05)
- [x] **T03 — Domain Contracts** (Completed 2026-09-05)
- [x] **T04 — Deterministic Engine** (Completed 2026-09-05)
- [x] **T05 — State Machine** (Completed 2026-09-05)
- [x] **T06 — Evidence** (Completed 2026-09-05)

## Last Verified
2026-09-05T14:46:00+05:30

## Tests Run
- `make test-bootstrap`: PASS (all master brain files, zero root copies, pyproject valid, zero secrets)
- `make test-env`: PASS (toolchains verified, Next.js build clean, smoke tests pass)
- `pytest` (88 passed in 0.19s):
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
- **AI Client**: `groq` 1.7.0 (instantiation verified)
- **Payment Client**: `razorpay` 2.0.1 (instantiation verified)
- **Node.js**: v25.2.1, **npm**: 11.6.2
- **Frontend Stack**: Next.js 15.5.25 (App Router, Turbopack), TypeScript 5, Tailwind CSS 4, shadcn/ui

## Known Failures
None

## Blockers
None

## Important Decisions
1. **Source vs Authority Decoupling**:
   - `EvidenceSource` represents the origin channel (`INTENT`, `USER_INTENT`, `AGENT`, `MERCHANT`, `RAZORPAY`, `SYSTEM`, `REPLAY`, `SYNTHETIC`).
   - `EvidenceAuthority` represents the authoritative weighting tier (`AUTHORITATIVE`: 100 > `PROTOCOL_TRUSTED`: 90 > `MERCHANT_ATTESTED`: 70 > `REPLAY_OBSERVED`: 60 > `SYSTEM_DERIVED`: 50 > `ADVISORY`: 20).
   - Reconciled terminology: `USER_INTENT` is supported as canonical alias for `INTENT`; `SYSTEM` represents control plane/internal observations, distinct from `SYNTHETIC` mock data.
2. **Provider-Neutral Normalization**: The normalization layer converts observed payloads into canonical `Evidence` items without leaking gateway-specific schema dependencies into generic domain logic.
3. **Deterministic Conflict Resolution**:
   - Conflicts between differing authority tiers are resolved strictly in favor of the higher tier (e.g. `RAZORPAY` overrides `AGENT`), while preserving the lower tier in `conflicting_records` for provenance.
   - Contradictions at the identical top authority tier remain unresolved (`is_resolved = False`), preserving ambiguity to feed `UNKNOWN` into downstream engines.
4. **Idempotent Deduplication**: Duplicate deliveries sharing exact IDs or semantic content keys are deterministically deduplicated while maintaining relative order.
5. **Inert Data Guarantee**: All payload contents and strings are treated strictly as inert data; prompt injection instructions are never executed.

## Active Branch
`main`

## Last Verified Remote Commit
5ea1c53 (docs: synchronize persistent brain and handoff for T06 completion)
Prior Remote Commits: 3c93250, 898edc3, 3da5b7f, 855af66, de72092, 4ac842d, 38e0658, cd6af7c, ...

## Next Task
**T07 — MRDP** (Machine-Readable Drift Proof: generate cryptographic/tamper-evident drift proofs containing contract baseline, observed evidence, rule results, and explanations)

## Parallel Candidates
With T06 complete, the evidence normalization pipeline is verified. T07 (MRDP) consumes the verified `IntegrityResult` (T04) and `EvidenceBundle` (T06) to generate machine-readable proofs, so work proceeds sequentially.

## Source Documents Consulted
- `brain/TarkaRaksha_IDEA.md` (§31, §34)
- `brain/TarkaRaksha_Execution.md` (§7.23–§7.24, §8.26–§8.27)
- `brain/TarkaRaksha_TESTING.md` (§9.22–§9.24)
- `brain/CONTEXT.md`
- `brain/HANDOFF.md`

## External Sources Consulted
- Pydantic v2 documentation on `ConfigDict(frozen=True, extra='forbid', strict=True)`
- ISO-8601 datetime specification for timezone offset representation

## Open Questions
None
