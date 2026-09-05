# CONTEXT.md — Persistent Operational Context & Architecture Snapshot

## Executive Summary
**TarkaRaksha** (तर्क रक्षा — *Reasoned Defense / Logical Protection*) is an agentic transaction integrity & recovery control plane.
- **Core Principle**: AI is advisory. Deterministic verification is authoritative.
- **Core Loop**: Authorized Intent → Agent Execution → Observe → Deterministic Integrity Verification (Pass/Drift/Unknown) → Prove (MRDP) → Safe Recovery → Revalidate.

---

## Canonical Document Hierarchy (under `brain/`)
1. **`brain/TarkaRaksha_IDEA.md`**: Product definition, core conceptual boundaries, invariant definitions, and problem space.
2. **`brain/TarkaRaksha_Execution.md`**: Authoritative technical architecture, sequential build sequence (`T01`–`T18`), checkpoints (`C01`–`C18`), and repository specifications.
3. **`brain/TarkaRaksha_TESTING.md`**: Continuous test mappings (Step 8 → Step 9) and adversarial hardening specifications.
4. **`brain/TarkaRaksha_PreFinal.md`**: Downstream deliverables and final-phase reference (do not prematurely implement).
5. **`brain/STATUS.md`**: Authoritative, real-time execution state tracking.

---

## Architectural & Safety Invariants
1. **Deterministic Authority**: The rule engine is the sole source of truth on transaction integrity. LLMs cannot authorize money, override user policy, or declare `PASS`.
2. **Untrusted AI Outputs**: Natural language inputs and agent recovery suggestions are untrusted inputs requiring deterministic parsing, bounded limits, and verification.
3. **Financial Safety**: Monetary amounts must strictly be represented in integer minor units (paise, cents). Floating-point currency math is strictly forbidden.
4. **First-Class UNKNOWN**: When gateway evidence is ambiguous or delayed, state transitions to `UNKNOWN` and enters a dedicated resolution/re-verification flow rather than guessing.
5. **Zero Premature Code**: Minimal infrastructure, maximum verifiable engineering. No Kafka, Redis, or microservice overbuilding.

---

## Repository State (End of T01)
- **Current Phase**: Repository Bootstrap (`T01`)
- **Active Branch**: `main`
- **Governance Established**: `AGENTS.md`, `.agents/rules/tarkaraksha.md`, `SECURITY.md`, `README.md`, `Makefile`, `pyproject.toml`, `.gitignore`, `.env.example`.
- **Planned Modules**: `backend/`, `frontend/`, `testing/`, `scripts/` to be introduced starting in `T02`.
