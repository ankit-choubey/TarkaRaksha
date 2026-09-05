# HANDOFF.md — Agent Session Handoff Document

## Handoff Metadata
- **Current Task Completed**: `T03 — Domain Contracts`
- **Current Checkpoint**: `C03 — PASS`
- **Next Task**: `T04 — Deterministic Engine`
- **Active Branch**: `main`
- **Handoff Timestamp**: 2026-09-05T14:10:00+05:30

---

## 1. What Was Done in T03
1. **Canonical Domain Contracts Implemented** (`backend/app/domain/models/`):
   - `enums.py`: `IntegrityStatus` (`PASS`, `DRIFT`, `UNKNOWN`), `DecisionAction`, `EvidenceSource`, `TransactionState`, `ActionType`.
   - `money.py`: `Money` immutable value object enforcing strict integer minor units, uppercase ISO-4217 currency, strict float/bool rejection, and exact arithmetic.
   - `intent.py`: `IntentItem` and `IntentContract` with timezone-aware timestamps, non-empty items, and immutability.
   - `authorization.py`: `Authorization` distinct from AI recommendations with explicit validity bounds.
   - `evidence.py`: `CanonicalEvent` and `Evidence` with normalized fields and deterministic authority ranking (`RAZORPAY` > `INTENT` > `MERCHANT` > `REPLAY` > `AGENT` > `SYNTHETIC`).
   - `integrity.py`: `IntegrityResult` (first-class `UNKNOWN`), `Decision`, and `MRDP` (Machine-Readable Drift Proof).
   - `recovery.py`: `RecoveryProposal` (advisory untrusted AI proposal) and `ActionRequest` (unvalidated until rule engine approval).
   - `transaction.py`: Domain-level `Transaction` model.
2. **Testing Suite Established**:
   - `testing/unit/test_money.py`: 12 tests covering integer representation, float rejection, boolean rejection, boundary values (49999, 50000, 50001, 0, huge integers), currency validation, arithmetic, and serialization.
   - `testing/unit/test_models.py`: 18 tests covering all domain models, timestamp requirements, authority ranking, first-class UNKNOWN, advisory AI proposals, and serialization round-trips.
3. **Checkpoints & Validation**:
   - `make test-bootstrap`: PASS.
   - `make test-env`: PASS.
   - `pytest`: 35 passed in 0.16s across all unit test suites.

---

## 2. Verified Invariants
- **AI Output is Untrusted**: `RecoveryProposal` is typed as an advisory proposal and cannot be executed directly; only validated `ActionRequest` can be authorized.
- **Deterministic Authority**: All contracts enforce strong types and immutable boundaries; no floating-point currency math is possible.
- **UNKNOWN is First-Class**: `IntegrityStatus.UNKNOWN` is explicitly separate from `PASS` and `DRIFT`.
- **Zero Scope Leakage**: No deterministic engine rules (`check_economic`, etc.), state machine logic, or third-party adapters implemented in T03.

---

## 3. Explicit Instructions for Next Task (`T04 — Deterministic Engine`)
When starting `T04`:
1. **Read `brain/STATUS.md` first**.
2. **Read `brain/TarkaRaksha_Execution.md` §7.17–§7.20, §8.15–§8.22 (T04)** and `brain/TarkaRaksha_TESTING.md` §9.10–§9.16.
3. **Task Objective**: Implement deterministic evaluation rules under `backend/app/domain/rules/` and `backend/app/services/evaluation.py`:
   - `check_economic(contract, evidence) -> RuleResult` (assert ₹49,999 / ₹50,000 PASS, ₹50,001 DRIFT).
   - `check_semantic(contract, evidence) -> RuleResult` (SKU mismatch, unauthorized substitutions).
   - `check_temporal(contract, evidence) -> RuleResult` (duplicate event detection, timeout, order of arrival).
   - `evaluate_integrity(contract, evidence_bundle) -> IntegrityResult`.
4. **Testing Requirement**: Implement comprehensive engine tests under `testing/unit/test_engine.py` covering all positive, drift, and unknown paths.
5. **Pass Checkpoint C04** before committing and pushing.
