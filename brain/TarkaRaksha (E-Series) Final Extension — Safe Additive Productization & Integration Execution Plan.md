# TARKARAKSHA
# FINAL EXTENSION — SAFE ADDITIVE PRODUCTIZATION & INTEGRATION EXECUTION PLAN

**Document type:** Final additive execution-plan extension  
**Project:** TarkaRaksha — Agentic Transaction Integrity & Recovery Control Plane  
**Companion documents:**
- `brain/TarkaRaksha_IDEA.md`
- `brain/TarkaRaksha_Execution.md`
- `brain/TarkaRaksha_TESTING.md`
- `brain/INNOVATION_HANDOFF.md`
- `brain/STATUS.md`
- `brain/HANDOFF.md`

**Purpose:** Convert the already-implemented innovation stack into one coherent, demonstrable Track-01 agentic-commerce experience without rewriting, bypassing, or destabilizing completed work.

---

# 0. ABSOLUTE SAFETY RULE

This document is **additive only**.

It MUST NOT:

- replace `TarkaRaksha_Execution.md`
- replace `TarkaRaksha_IDEA.md`
- rewrite T01–T13
- recreate I4–I15 functionality
- introduce a second integrity engine
- introduce a second payment authority
- introduce generic fraud scoring
- introduce merchant trust/reputation scoring
- turn an LLM into a financial decision-maker
- replace Razorpay with a simulation where real Test Mode is already available
- replace TIX, replay, checkpoints, recovery, or binding with duplicate implementations
- modify working behavior merely to make the UI easier to build

The governing rule remains:

> **AI proposes. Evidence proves. Deterministic logic decides.**

---

# 1. VERIFIED STARTING POINT

The existing implementation already contains:

- Merchant Agent
- Buyer Agent
- agent/transaction/payment binding
- TIX
- bounded negotiation and replanning
- kill switch / execution safety
- evidence-aware explanation
- operational modes
- merchant capability graph
- scenario lab
- ground-truth certification
- trace/fault localization
- integrity checkpoints
- integrity SLA metrics
- Razorpay integration
- deterministic PASS / DRIFT / UNKNOWN
- recovery and UNKNOWN resolution
- deterministic replay

Therefore the final extension is a **productization and integration layer**, not a new backend rewrite.

---

# 2. FINAL PRODUCT BOUNDARY

TarkaRaksha begins where ordinary agentic commerce becomes financially consequential.

```text
USER DISCOVERY / PRODUCT SEARCH
        ↓
BUYER AGENT
        ↓
AUTHORIZED INTENT
        ↓
TARKARAKSHA INTEGRITY BOUNDARY
        ↓
MERCHANT AGENT
        ↓
OFFER / INVENTORY / FULFILLMENT
        ↓
TARKARAKSHA VERIFICATION
        ↓
RAZORPAY EXECUTION
        ↓
CHECKPOINTS / EVIDENCE
        ↓
PASS / DRIFT / UNKNOWN
        ↓
RECOVER / HOLD / ABSTAIN
        ↓
REVALIDATE
        ↓
FINAL OUTCOME
```

Product discovery may be demonstrated, but it is **not the product's differentiation**.

TarkaRaksha owns:

> **transaction integrity across execution and lifecycle, not product discovery itself.**

---

# 3. FINAL E-SERIES

```text
E0  Final Baseline & Contract Freeze
 ↓
E1  Integration Boundary
 ↓
E2  Consumer + Merchant Gate Composition
 ↓
E3  Agentic Transaction Lifecycle Orchestration
 ↓
E4  Security / Threat Guard Composition
 ↓
E5  Transaction Passport
 ↓
E6  Failure → Recovery → Revalidation Demo Loop
 ↓
E7  Real-time Control-Room Data Surface
 ↓
E8  Scenario / Proof Surface
 ↓
E9  Full End-to-End Demonstration Certification
```

These are implementation groups, not a new replacement task numbering system.

---

# 4. E0 — FINAL BASELINE & CONTRACT FREEZE

## Objective

Freeze the current green I-series state before final integration.

## Required

Record:

```text
HEAD_COMMIT
TEST_COUNT
CURRENT_STATUS
API_SURFACE
MODEL_SURFACE
Razorpay verification status
frontend build status
```

## Gate

No E-series implementation begins unless:

```text
existing regression suite = PASS
existing build = PASS
existing API smoke tests = PASS
```

## Hard rule

No existing test is deleted.

No existing passing invariant is relaxed.

---

# 5. E1 — INTEGRATION BOUNDARY

## Objective

Create one stable application-facing composition boundary around existing components.

The boundary must expose:

```text
Buyer Agent
Merchant Agent
Intent
Transaction
TIX
Integrity
Recovery
Payment
Evidence
Replay
```

without moving their authority.

## Required behavior

One orchestrated transaction context must preserve:

```text
intent_id
agent_id
merchant_id
transaction_id
order_id
payment_id
attempt_id
```

using the existing I8 binding service.

## Do not

- duplicate I8
- bypass TIX
- bypass deterministic integrity
- call Razorpay directly from the frontend
- allow agents to directly authorize payment

---

# 6. E2 — CONSUMER + MERCHANT GATE COMPOSITION

## Objective

Expose the two agent-facing sides as **integration boundaries**, not new payment gateways.

### Consumer side

```text
Buyer Agent
     ↓
Consumer Integrity Gate
     ↓
Intent / Authorization
```

### Merchant side

```text
Merchant Agent
     ↓
Merchant Integrity Gate
     ↓
Offer / Capability / Evidence
```

Both feed the existing deterministic core.

## Consumer gate validates

- intent binding
- authorization constraints
- agent identity
- transaction context
- proposal validity

## Merchant gate validates

- merchant identity
- capability
- SKU
- inventory
- price
- shipping
- fulfillment
- offer expiry
- merchant policy

## Output

The gate must produce structured facts.

It must never emit an authoritative financial PASS.

---

# 7. E3 — AGENTIC TRANSACTION LIFECYCLE ORCHESTRATION

## Objective

Connect already-built Buyer Agent, Merchant Agent, TIX, negotiation and integrity components into one bounded transaction loop.

## Canonical path

```text
BUYER AGENT
    ↓
MERCHANT AGENT
    ↓
OFFER
    ↓
TIX
    ↓
TARKARAKSHA
    ↓
PASS
    ↓
RAZORPAY
```

Failure path:

```text
DRIFT
  ↓
MRDP / EXPLANATION
  ↓
BOUNDED REPLAN
  ↓
MERCHANT COUNTER-OFFER
  ↓
REVALIDATE
  ↓
PASS
```

Unknown path:

```text
UNKNOWN
  ↓
AUTHORITATIVE RESOLUTION
  ↓
PASS / DRIFT / UNKNOWN
  ↓
ABSTAIN WHEN REQUIRED
```

## Hard bounds

Reuse existing I7 limits.

Do not introduce an open-ended agent loop.

---

# 8. E4 — SECURITY / THREAT GUARD COMPOSITION

## Objective

Expose existing security primitives as one coherent transaction threat boundary.

This is NOT a new cybersecurity engine.

## Threat classes to demonstrate

### A. Prompt injection

Untrusted agent/evidence content attempts to change authorized financial behavior.

Expected:

```text
AI output = advisory
deterministic policy = authoritative
```

### B. Agent capability abuse

Agent attempts an operation outside declared capability.

Expected:

```text
AUTHORITY DRIFT
→ BLOCK / PAUSE
```

### C. Replay

Previously consumed transaction/message is reused.

Expected:

```text
REPLAY
→ REJECT
```

### D. Tampered evidence

Evidence content/hash no longer verifies.

Expected:

```text
UNKNOWN / INVALID
→ HOLD
```

### E. Provider-state ambiguity

Conflicting or missing state exists.

Expected:

```text
UNKNOWN
→ no duplicate payment
→ bounded resolution
```

## Reuse

Use existing:

- I2 security binding
- I8 transaction/payment binding
- I9 kill switch
- I11 scenarios
- I12 certification
- I14 checkpoint chain
- I13 trace
- T13 replay

No duplicate decision logic.

---

# 9. E5 — TRANSACTION PASSPORT

## Objective

Create a single human-readable representation of the transaction's verified lifecycle.

The passport must compose existing records.

## Passport contents

```text
Transaction ID
Intent ID
Buyer Agent
Merchant Agent
Merchant ID
Order ID
Payment ID
Authorization
Policy Version
Rules Version

Integrity Status
Drift Domains
Checkpoint Status
Evidence References
MRDP
Trace
Recovery Attempts
Revalidation
SLA Metrics
Replay Reference
Final Outcome
```

## Example

```text
TRANSACTION PASSPORT

Intent         VERIFIED
Buyer Agent    VERIFIED
Merchant       VERIFIED
Offer          VERIFIED
Authorization  VERIFIED
Payment        VERIFIED
Fulfillment    DRIFT
Recovery       COMPLETED
Revalidation   PASS
Final          PASS
```

## Safety

Passport is observational.

It cannot alter any transaction decision.

---

# 10. E6 — FAILURE → RECOVERY → REVALIDATION HERO LOOP

## Objective

Create one deterministic, repeatable hero journey for judging.

## Required scenario

Use:

```text
Authorized:
₹50,000 maximum
SKU fixed
Quantity fixed
Delivery constrained
```

### Step 1

Valid offer:

```text
₹47,000 product
₹3,000 shipping
₹50,000 total
```

→ PASS

### Step 2

Introduce controlled drift:

```text
Final total = ₹55,000
```

→ DRIFT

### Step 3

Show:

```text
MRDP
Why blocked
Evidence
First invalid checkpoint
```

### Step 4

Buyer Agent receives bounded remediation information.

### Step 5

Merchant Agent proposes a valid alternative.

### Step 6

TarkaRaksha revalidates.

### Step 7

PASS.

### Step 8

Execute Razorpay Test Mode.

## Final visible message

```text
TRANSACTION RESTORED

Original authorization preserved
Payment verified
Recovery completed
Evidence recorded
```

---

# 11. E7 — REAL-TIME CONTROL-ROOM DATA SURFACE

## Objective

Make the existing backend observable through a production-quality frontend.

The UI must be a consumer of actual API responses.

It must not manufacture transaction states.

## Required primary surfaces

### A. Buyer Agent

Show:

```text
User request
Intent extraction
Constraints
Agent proposal
Clarification if needed
```

### B. Merchant Agent

Show:

```text
Catalog
Offer
Inventory
Shipping
Capabilities
Policy
```

### C. Live Transaction

Show:

```text
Intent
Offer
Authorization
Order
Payment
Checkpoints
Current integrity state
```

### D. Integrity

Show:

```text
Economic
Semantic
Temporal
Authority
PASS / DRIFT / UNKNOWN
```

### E. Recovery

Show:

```text
Drift
Reason
MRDP
Recovery candidates
Selected candidate
Revalidation
Result
```

### F. Evidence

Show:

```text
Evidence
Authority
Timestamp
Source
Digest
```

### G. Replay

Show:

```text
Historical state
Recorded result
Replayed result
MATCH / MISMATCH / INVALID_REPLAY
```

### H. Security

Show:

```text
Threat
Evidence
Agent
Rule
Action
Result
```

### I. Scenario Lab

Show:

```text
Scenario
Expected
Actual
Certification
Evidence
```

---

# 12. E8 — SCENARIO / PROOF SURFACE

## Objective

Turn already-built testing/certification into judge-visible product proof.

The frontend must surface the canonical scenarios already implemented.

At minimum:

```text
HAPPY_PATH
PRICE_DRIFT
WRONG_SKU
INVENTORY_DISAPPEARS
DELIVERY_DRIFT
DUPLICATE_PAYMENT
DELAYED_WEBHOOK
REPLAY_ATTACK
PROMPT_INJECTION_IN_EVIDENCE
MERCHANT_AGENT_COMPROMISED
BUYER_AGENT_REUSE
UNKNOWN_PROVIDER_STATE
```

## For every scenario show

```text
Input
Expected
Actual
Integrity
Security
Recovery
Certification
```

## Rule

Scenario Lab remains a test/input-generation surface.

It does not become a second decision engine.

---

# 13. E9 — FINAL END-TO-END DEMONSTRATION CERTIFICATION

## Objective

Certify that the final product presentation uses the real system rather than disconnected mock components.

## Required complete path

```text
User
 ↓
Buyer Agent
 ↓
Intent
 ↓
Merchant Agent
 ↓
Offer
 ↓
TIX
 ↓
TarkaRaksha
 ↓
PASS / DRIFT / UNKNOWN
 ↓
Recovery where required
 ↓
Revalidation
 ↓
Razorpay Test Mode
 ↓
Evidence
 ↓
Checkpoint
 ↓
Passport
 ↓
Replay
```

## Required proof cases

### Case 1 — Happy path

Expected:

```text
PASS
```

### Case 2 — Economic drift

Expected:

```text
DRIFT
BLOCK
RECOVER
PASS
```

### Case 3 — Merchant-agent abuse

Expected:

```text
AUTHORITY VIOLATION
PAUSE / BLOCK
```

### Case 4 — Unknown provider state

Expected:

```text
UNKNOWN
HOLD
RESOLVE
```

### Case 5 — Replay/tamper

Expected:

```text
INVALID_REPLAY / MISMATCH
```

## Final gate

Everything must run using the same authoritative backend components.

---

# 14. FRONTEND NON-DUPLICATION RULE

Frontend must never reimplement:

```text
integrity rules
recovery rules
binding
authorization
checkpoint validation
Razorpay verification
replay logic
security verdicts
```

Frontend is:

```text
presentation
inspection
interaction
```

Backend remains:

```text
authority
```

---

# 15. REAL VS SYNTHETIC BOUNDARY

The application must visibly distinguish:

### Real

- Razorpay Test Mode payment lifecycle where verified
- deterministic TarkaRaksha decisions
- replay
- evidence
- checkpoints
- existing implemented services

### Synthetic / reference

- Merchant Agent environment
- synthetic merchant catalog
- synthetic external commerce data where used
- controlled adversarial scenario fixtures
- demonstration negotiation data

Never imply a production merchant network connection where none exists.

---

# 16. ACCEPTANCE CRITERIA

The final extension is complete only when:

```text
[ ] Existing regression tests remain green
[ ] No T01–T13 behavior is broken
[ ] Existing I-series invariants remain green
[ ] Buyer Agent participates in a complete flow
[ ] Merchant Agent participates in a complete flow
[ ] TIX participates in a complete flow
[ ] Existing binding remains authoritative
[ ] Existing integrity engine remains authoritative
[ ] Existing recovery remains authoritative
[ ] Existing kill switch remains authoritative
[ ] Razorpay Test Mode remains the payment reference
[ ] At least one drift is detected
[ ] At least one drift is recovered
[ ] Revalidation passes
[ ] At least one attack is visibly blocked
[ ] UNKNOWN remains UNKNOWN when evidence is insufficient
[ ] Evidence is inspectable
[ ] Checkpoints are inspectable
[ ] Passport is inspectable
[ ] Replay is inspectable
[ ] Scenario certification is inspectable
[ ] Frontend consumes real API results
[ ] No frontend-only fake verdicts exist
```

---

# 17. IMPLEMENTATION RULE

Every E-series step follows:

```text
READ CURRENT STATE
 ↓
INSPECT EXISTING IMPLEMENTATION
 ↓
IDENTIFY REUSABLE SERVICE
 ↓
ADD ONLY MISSING COMPOSITION
 ↓
WRITE FOCUSED TESTS
 ↓
RUN FULL REGRESSION
 ↓
FIX
 ↓
CHECKPOINT
 ↓
COMMIT
 ↓
PUSH
 ↓
UPDATE STATUS / HANDOFF
```

Do not refactor unrelated code.

Do not rename working public contracts without necessity.

Do not optimize before correctness.

---

# 18. FILE OWNERSHIP

## New files preferred

Use new files wherever possible for orchestration/composition.

Examples:

```text
backend/app/services/final_flow/
backend/app/services/integration/
backend/app/domain/passport/
backend/app/domain/threat/
testing/unit/test_final_flow_*.py
testing/unit/test_passport_*.py
```

Exact paths must be determined from the current repository structure before implementation.

## Existing files

Modify existing files only when:

```text
a real integration hook is required
```

and keep the change minimal.

---

# 19. FRONTEND ENTRY AFTER E-SERIES

Once E0–E9 backend/product composition is green:

```text
E-SERIES COMPLETE
      ↓
BACKEND CONTRACT FREEZE
      ↓
T14 CONTROL ROOM UI
```

The UI should then be implemented as a visual projection of the verified system.

Primary navigation:

```text
Overview
Transactions
Agents
Integrity
Recovery
Evidence
Replay
Security
Scenarios
```

A single transaction should be inspectable from:

```text
Intent
→ Agent
→ Offer
→ Authorization
→ Payment
→ Integrity
→ Drift
→ Recovery
→ Revalidation
→ Evidence
→ Replay
```

---

# 20. FINAL DEMONSTRATION PRINCIPLE

The product must not try to impress by displaying the largest number of features.

It must demonstrate one coherent truth:

> **An AI agent can execute commerce, but the transaction does not get to redefine the user's authorization while it is executing.**

Therefore the hero demonstration is:

```text
DISCOVER
 ↓
AUTHORIZE
 ↓
EXECUTE
 ↓
DRIFT
 ↓
PROVE
 ↓
RECOVER
 ↓
REVALIDATE
 ↓
PAY
 ↓
AUDIT
 ↓
REPLAY
```

The visual product should make every one of those stages observable.

---

# 21. FINAL PRODUCT POSITION

TarkaRaksha is not:

```text
another shopping assistant
another checkout
another payment gateway
another fraud detector
another generic trust platform
```

It is:

> **A transaction-integrity and recovery control plane that can sit around agentic commerce and payment execution, keeping the executed transaction bound to authorized user intent and providing evidence-backed intervention when reality diverges.**

The reference payment implementation is Razorpay.

The Buyer Agent and Merchant Agent provide the agentic-commerce demonstration.

The deterministic TarkaRaksha core provides the integrity authority.

The Control Room makes the complete lifecycle visible.

The Scenario Lab and Replay Engine provide proof.

---

# 22. SUCCESS CONDITION

When the user finishes the build, a judge must be able to understand TarkaRaksha without reading the source code:

```text
"What did the user authorize?"
          ↓
"What did the agents propose?"
          ↓
"What did the merchant actually offer?"
          ↓
"What did Razorpay actually report?"
          ↓
"Did the transaction remain within authorization?"
          ↓
"If not, why?"
          ↓
"Was it safely blocked or recovered?"
          ↓
"Can you prove it?"
```

If the UI can answer those questions directly from the real system, the extension is successful.