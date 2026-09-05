# STATUS.md — TarkaRaksha Execution State Tracker

## Project
**TarkaRaksha** — Agentic Transaction Integrity & Recovery Control Plane

## Current Phase
Machine-Readable Drift Proof Layer

## Current Task
T07 — MRDP

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

## Last Verified
2026-09-05T14:55:00+05:30

## Tests Run
- `make test-bootstrap`: PASS (all master brain files, zero root copies, pyproject valid, zero secrets)
- `make test-env`: PASS (toolchains verified, Next.js build clean, smoke tests pass)
- `pytest` (98 passed in 0.18s):
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
- **AI Client**: `groq` 1.7.0 (instantiation verified)
- **Payment Client**: `razorpay` 2.0.1 (instantiation verified)
- **Node.js**: v25.2.1, **npm**: 11.6.2
- **Frontend Stack**: Next.js 15.5.25 (App Router, Turbopack), TypeScript 5, Tailwind CSS 4, shadcn/ui

## Known Failures
None

## Blockers
None

## Important Decisions
1. **MRDP Protocol Status**:
   - Machine-Readable Drift Proof (MRDP) is strictly **TarkaRaksha's proposed protocol/artifact**, NOT an industry standard, NOT a payment standard, and NOT an official Razorpay or universal specification.
2. **Deterministic & Downstream of Verifier**:
   - The architecture remains `Evidence -> Deterministic Engine -> IntegrityResult -> MRDP -> Recovery Agent`.
   - AI is strictly advisory and is not introduced into proof generation.
   - Given identical inputs (`IntentContract`, `IntegrityResult`, `EvidenceBundle`), `build_mrdp()` produces bit-for-bit identical proofs and canonical digests across 100x runs.
3. **Cryptographic / Tamper-Evidence Specification**:
   - Defined deterministic canonical JSON serialization (`canonicalize_mrdp_payload`) with sorted keys, compact separators, explicit ISO-8601 strings, and integer minor units.
   - Hashed using standard SHA-256 (`proof_digest`).
   - `verify_mrdp_integrity()` detects any post-creation mutation or tampering.
   - Explicitly documented that this proves **tamper-evident integrity of the canonicalized proof representation** under SHA-256, and does NOT claim digital signatures, author authenticity, or non-repudiation without PKI/asymmetric signing keys.
4. **Safety Boundaries & Inert Data**:
   - Remediation hints are strictly advisory guidance for downstream recovery; `validate_remediation_safety()` blocks any attempt to instruct budget increases, constraint bypasses, or authorization changes.
   - Malicious prompt injections inside violation strings, evidence payloads, or remediation text are treated strictly as inert data.
5. **Canonical Aliases and Backward Compatibility**:
   - Preserved canonical aliases (`expected` -> `expected_value`, `observed` -> `observed_value`, `evidence_refs` -> `evidence_references`, `remediation_hint` -> `remediation`) in `MRDP` to guarantee complete compatibility across T03 models and T07 execution specifications.

## Active Branch
`main`

## Last Verified Remote Commit
2d59ea8 (test: add adversarial, safety boundary, prompt injection, and round-trip tests for MRDP)

## Next Task
**T08 — Groq AI** (Intent Parser & Advisory Recovery Agent: untrusted natural-language parsing, bounded recovery suggestions, strictly downstream of verifier)

## Parallel Candidates
With T07 complete, the MRDP proof generation layer is verified. T08 (Groq AI) consumes intent specs and MRDP proofs to propose recovery actions, operating strictly within advisory bounds.

## Source Documents Consulted
- `brain/TarkaRaksha_IDEA.md` (§31, §34)
- `brain/TarkaRaksha_Execution.md` (§7.25, §8.28)
- `brain/TarkaRaksha_TESTING.md` (§9.25–§9.29)
- `brain/CONTEXT.md`
- `brain/HANDOFF.md`

## External Sources Consulted
- hashlib (Python standard library SHA-256 implementation)
- RFC 8785 (JSON Canonicalization Scheme reference principles)

## Open Questions
None
