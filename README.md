# TarkaRaksha — Agentic Transaction Integrity & Recovery Control Plane

> **"AI is advisory. Deterministic verification is authoritative."**

TarkaRaksha (तर्क रक्षा — *Reasoned Defense / Logical Protection*) is an enterprise-grade control plane that detects, proves, repairs, and revalidates agentic financial transactions against authorized user intent.

---

## The Problem

Autonomous AI agents operating financial actions (such as Razorpay checkouts, subscription adjustments, or multi-item purchases) can suffer from:
- **Semantic drift**: Misinterpreting user instructions (e.g., ordering wrong items, quantity mismatch).
- **Economic drift**: Incorrect amounts, unexpected currency conversions, or surcharges.
- **State divergence**: Disconnect between agent belief and authoritative payment gateway state.
- **Hallucinated authorizations**: Agents assuming execution succeeded or claiming recovery without deterministic proof.

---

## Core Product Loop

```text
AUTHORIZED INTENT
       │
       ▼
AGENT EXECUTION
       │
       ▼
    OBSERVE
       │
       ▼
DETERMINISTIC INTEGRITY VERIFICATION
       │
       ├──────────────┬───────────────┐
       ▼              ▼               ▼
     PASS           DRIFT          UNKNOWN
                      │               │
                      ▼               ▼
                    PROVE         RESOLUTION
                      │               │
                      ▼               ▼
               SAFE RECOVERY       ABSTAIN
                      │
                      ▼
                 REVALIDATE
                      │
                      ▼
             PASS / DRIFT / ABSTAIN
```

---

## Core Innovation: Detect → Prove → Repair → Revalidate

1. **Detect**: Compare immutable authorized intent against normalized gateway evidence.
2. **Prove**: Generate a cryptographically verifiable Machine-Readable Dispute Packet (MRDP) proving exact divergence.
3. **Repair**: Autonomous recovery agent proposes safe, bounded compensatory actions (e.g., partial refund, void).
4. **Revalidate**: Deterministic re-verification confirms system integrity before declaring resolution.

---

## Architecture & Repository Layout

```text
tarkaraksha/
├── README.md                 # Project overview and orientation
├── AGENTS.md                 # Persistent execution rules for coding agents
├── SECURITY.md               # Security and financial safety policy
├── LICENSE                   # MIT License
├── Makefile                  # Build and repository automation
├── pyproject.toml            # Python packaging and dependency specs
├── .gitignore                # Git ignore patterns
├── .env.example              # Environment variables template
├── brain/                    # Persistent project memory & master documents
│   ├── STATUS.md             # Authoritative execution state tracker
│   ├── CONTEXT.md            # Persistent architecture snapshot & invariants
│   ├── HANDOFF.md            # Task-to-task transition log & instructions
│   ├── TarkaRaksha_IDEA.md   # Product definition, boundaries, innovation
│   ├── TarkaRaksha_Execution.md # Technical architecture, task sequence (T01-T18)
│   ├── TarkaRaksha_PreFinal.md  # Downstream compatibility & deliverables
│   └── TarkaRaksha_TESTING.md   # Continuous verification & test map
├── .agents/                  # Workspace agent configuration & rules
│   └── rules/
│       └── tarkaraksha.md    # Workspace guidance & safety principles
```

### Module Implementation Status
- **Current State (T01)**: Repository Bootstrap verified. Only foundational governance, persistent brain, and configuration files are present.
- **Planned Modules (T02–T18)**: `backend/`, `frontend/`, `testing/`, `scripts/` will be established as their respective sequential milestones are reached. No premature or placeholder code is present.

---

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+ / npm
- Git

### Verification

```bash
# Verify repository bootstrap integrity
make test-bootstrap

# View current project execution status
make status
```

---

## Documentation

Master project documents are maintained in the [`brain/`](brain/) directory:
- [TarkaRaksha_IDEA.md](brain/TarkaRaksha_IDEA.md) — Product definition and conceptual boundaries
- [TarkaRaksha_Execution.md](brain/TarkaRaksha_Execution.md) — Technical architecture and build sequence
- [TarkaRaksha_TESTING.md](brain/TarkaRaksha_TESTING.md) — Continuous testing methodology
- [TarkaRaksha_PreFinal.md](brain/TarkaRaksha_PreFinal.md) — Final deliverables and architectural context
- [STATUS.md](brain/STATUS.md) — Real-time execution tracking
