# TarkaRaksha Engineering Rules

These rules apply to all coding agents operating in the TarkaRaksha repository.

## Core Architectural Invariants
1. **Deterministic Authority**: The deterministic rule engine (`evaluation.py`) is the sole authority on transaction integrity. AI/LLM components are strictly advisory.
2. **Untrusted AI Output**: All AI output (parsed intent, recovery proposals) must undergo strict deterministic validation before acceptance.
3. **Integer Money Representation**: Currency amounts must strictly be represented as integers in minor units (e.g., 50000 paise = ₹500.00). No floats.
4. **Legitimate UNKNOWN**: When evidence is indeterminate, transition to `UNKNOWN` and run the resolution loop; do not default to `PASS` or `DRIFT`.
5. **Canonical Memory**: All master documents reside in `brain/`. Track execution progress in `brain/STATUS.md`.

## Task Execution Discipline
1. Read `brain/STATUS.md` before doing any work.
2. Execute strictly one approved task at a time (from `T01` to `T18`).
3. Continuous verification: Consult relevant test mappings in `brain/TarkaRaksha_TESTING.md` for each task.
4. Verify checkpoints (`C01`–`C18`) defined in `brain/TarkaRaksha_Execution.md` before committing.
5. Never invent or mock third-party API behavior (Razorpay, Groq) without verifying against official documentation.
