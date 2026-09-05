# AGENTS.md — Persistent Execution Rules for TarkaRaksha Agents

> **Role**: Primary operating instruction for all AI coding agents working on the TarkaRaksha codebase.
> **Human Owner**: Final decision-maker.

---

## 1. Master Agent Loop

At the start of **EVERY** task:
1. **Read `brain/STATUS.md` first**: Identify `CURRENT TASK`, `STATUS`, and dependencies.
2. **Consult Master Documents**:
   - `brain/TarkaRaksha_IDEA.md`: Product definition, boundaries, and conceptual invariants.
   - `brain/TarkaRaksha_Execution.md`: Architecture, file paths, and exact task sequence (`T01`–`T18`).
   - `brain/TarkaRaksha_TESTING.md`: Relevant testing sections and continuous verification requirements.
   - `brain/TarkaRaksha_PreFinal.md`: Downstream context only (DO NOT prematurely implement).
3. **Inspect Repository Reality**: Check Git status, existing files, and active branch (`main`). Never assume a file is missing or present without checking.
4. **Work One Approved Task at a Time**: Never skip ahead or batch future tasks unless explicitly instructed.
5. **Implement Safely**: Minimal infrastructure, maximum verifiable engineering.
6. **Test Continuously**: Run the relevant tests before running checkpoints.
7. **Run Step 8 Checkpoint (`C01`–`C18`)**: Verify all checklist items pass.
8. **Update `brain/STATUS.md`**: Record verified state, tests run, and decisions.
9. **Review Diff & Commit**: Create clean, meaningful commits matching the task description.
10. **Push**: Only when aligned with user instructions and repository workflow.

---

## 2. Core Invariants & Safety Principles

### AI Safety Rule
- **AI is advisory. Deterministic verification is authoritative.**
- LLM outputs (intent parsing, recovery proposals, explanations) are untrusted inputs.
- LLMs must **NEVER**:
  - Authorize money transfers or payments.
  - Override user limits or policies.
  - Declare an authoritative `PASS`.
  - Convert `UNKNOWN` into `PASS`.
  - Override deterministic rules or alter trusted evidence.

### Financial Safety Rule
- Money must be represented in integer minor units (e.g., paise, cents) with explicit currency codes.
- **Never** use floating-point arithmetic for currency calculations.
- Never invent payment statuses, capture behaviors, or refund semantics.
- Reconcile provider behaviors with official Razorpay API documentation.

### The UNKNOWN State Rule
- `UNKNOWN` is a first-class, legitimate system state.
- When authoritative evidence is missing, delayed, or conflicting:
  - Do **NOT** guess or force `PASS`.
  - Do **NOT** assume `DRIFT` without proof.
  - Trigger the resolution flow: `UNKNOWN` → `RESOLUTION` → `REVERIFY` → `ABSTAIN / ESCALATE`.

### Anti-Hallucination Rule
- Never invent API endpoints, request schemas, or response fields.
- Never claim a test passed without running it.
- Never claim an API works without verified execution or documented evidence.
- When uncertain: **STOP**, consult official docs, verify, then implement.

### Safe Parallelism Rule
- Parallel work is allowed only when tasks operate on separate files, isolated responsibilities, and have no shared mutable state or unresolved dependencies.
- Never parallelize merely for speed; prefer sequential verifiable execution.

### Stop Conditions & Uncertainty Rule
- When an API endpoint, third-party provider behavior (Razorpay, Groq), financial rule, schema, or security boundary is ambiguous or uncertain:
  - **STOP** immediately.
  - Check official documentation and primary technical sources.
  - Report the ambiguity clearly with facts; do not improvise or invent an answer.

---

## 3. Implementation Rules

- **No Overbuilding**: No unnecessary microservices, message queues (Kafka), Redis, Kubernetes, or massive agent frameworks unless explicitly called for by an approved milestone.
- **Single Canonical Brain**: All authoritative master documents reside exclusively in `brain/`.
- **Change Management**: If user requirements change, analyze impacts across completed and future tasks, adapt `STATUS.md`, and proceed cleanly.

