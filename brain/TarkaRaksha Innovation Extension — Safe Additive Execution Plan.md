# TARKARAKSHA
# INNOVATION EXTENSION — SAFE ADDITIVE EXECUTION PLAN

**Document type:** Execution-plan extension  
**Project:** TarkaRaksha — Agentic Transaction Integrity Engine  
**Primary integration point:** `TarkaRaksha_Execution.md`  
**Current baseline:** T01–T13 complete  
**Current next planned task:** T14 — Control Room UI  
**Purpose:** Add the approved innovation and agentic-commerce extensions without disturbing completed functionality.

---

# 0. DOCUMENT STATUS

## 0.1 Purpose

This document is an **extension layer** to the existing TarkaRaksha execution plan.

It does NOT replace:

- `TarkaRaksha_Execution.md`
- `TarkaRaksha_IDEA.md`
- `brain/CONTEXT.md`
- `brain/STATUS.md`
- `brain/HANDOFF.md`
- existing T01–T13 implementation
- existing tests
- existing APIs
- existing deterministic integrity engine
- existing replay engine
- existing Razorpay adapter
- existing Groq adapter

It exists to define **additional capabilities that can be added around the already-working system**.

---

# 0.2 Non-Disturbance Principle

The highest-priority rule of this extension is:

> **Existing working functionality must remain functionally unchanged unless an additive extension requires an explicitly tested integration point.**

No innovation is worth breaking:

```text
T01
 ↓
T02
 ↓
T03
 ↓
...
 ↓
T13
```

The extension therefore follows:

```text
EXISTING SYSTEM
      │
      ├──────────────► EXISTING BEHAVIOUR
      │                       │
      │                       ▼
      │                    PRESERVE
      │
      └──────────────► EXTENSION LAYER
                              │
                              ▼
                        ADDITIVE FEATURES
```

---

# 0.3 Current Verified Baseline

At the time this extension is defined:

```text
T01–T13 = COMPLETE
T13 Replay = COMPLETE
T14 = NOT STARTED
```

The existing project state records:

- 242 tests passing
- Python 3.12.12
- FastAPI 0.141.1
- Uvicorn 0.52.4
- Pydantic 2.13.5
- HTTPX 0.28.1
- Pytest 9.1.1
- Groq adapter with verified live smoke test
- Razorpay test-mode order creation and signature verification
- deterministic replay
- zero-live-network replay invariant



Therefore this extension starts from a **working baseline**, not a blank repository.

---

# 1. RELATIONSHIP TO THE EXISTING EXECUTION PLAN

The existing execution architecture already establishes:

```text
USER INTENT
     ↓
AI INTENT PARSER
     ↓
VALIDATED INTENT
     ↓
AGENT EXECUTION
     ↓
RAZORPAY TEST PAYMENT
     ↓
AUTHORITATIVE PAYMENT STATE
     ↓
EVIDENCE NORMALIZATION
     ↓
DETERMINISTIC INTEGRITY
     ↓
PASS / DRIFT / UNKNOWN
     ↓
MRDP / RECOVERY / RESOLVE
     ↓
REVALIDATE
     ↓
PASS
```



The innovation extension must sit **around this chain**, not replace it.

---

# 2. FINAL ARCHITECTURAL RULE

The following remains immutable:

# AI proposes. Evidence proves. Deterministic logic decides.

Therefore:

### LLM may

- interpret intent
- interpret merchant context
- generate an offer proposal
- generate a remediation proposal
- negotiate within explicit constraints
- explain deterministic results
- produce machine-readable requests

### LLM may NOT

- independently authorize money
- override deterministic rules
- declare PASS
- convert UNKNOWN to PASS
- fabricate evidence
- declare payment success without authoritative evidence
- modify an intent contract after authorization
- bypass retry limits
- bypass policy limits
- approve its own remediation

---

# 3. INNOVATION EXTENSION STACK

The extensions are divided into six layers.

```text
LAYER A
Evidence & Integrity Extensions

LAYER B
Security & Protocol Extensions

LAYER C
Governance & Replay Extensions

LAYER D
Agentic Commerce Extensions

LAYER E
Merchant-Agent Extensions

LAYER F
Evaluation & Demonstration Extensions
```

These layers must be implemented in dependency order.

---

# 4. IMPLEMENTATION ORDER

The safe order is:

```text
T13 COMPLETE
     ↓
I0 BASELINE FREEZE
     ↓
I1 EVIDENCE EXTENSIONS
     ↓
I2 SECURITY / BINDING EXTENSIONS
     ↓
I3 GOVERNANCE / REPLAY EXTENSIONS
     ↓
I4 MERCHANT AGENT
     ↓
I5 BUYER AGENT
     ↓
I6 TIX EXCHANGE
     ↓
I7 BOUNDED NEGOTIATION
     ↓
I8 RECOVERY + REVALIDATION LOOP
     ↓
I9 SCENARIO / CERTIFICATION LAB
     ↓
I10 FULL REGRESSION
     ↓
BACKEND FREEZE
     ↓
T14 CONTROL ROOM UI
     ↓
T15 SECURITY HARDENING
     ↓
T16 INTEGRATION
     ↓
T17 DEPLOYMENT
     ↓
T18 VALIDATION
```

The existing execution plan already defines the broader T13 → T14 → T15 → T16 → T17 → T18 progression. 

---

# 5. I0 — BASELINE FREEZE

## Timing

Immediately after T13.

## Objective

Create a safety boundary before any innovation work begins.

## Required actions

Record:

```text
BASELINE_COMMIT
BASELINE_TEST_COUNT
BASELINE_API_BEHAVIOUR
BASELINE_REPLAY_BEHAVIOUR
BASELINE_INTEGRITY_BEHAVIOUR
```

Create:

```text
brain/INNOVATION_HANDOFF.md
```

if it does not already exist.

The file must contain:

```text
Innovation Extension Started
Base T13 commit:
Baseline tests:
Baseline API status:
Baseline replay status:
Baseline integrity status:
```

## Rule

No innovation task starts until the baseline passes.

---

# 6. FILE OWNERSHIP MODEL

The extension uses the following ownership model.

| Area | Primary files | Rule |
|---|---|---|
| Domain contracts | existing domain/model files | Extend only |
| Integrity engine | existing integrity services | Do not rewrite |
| Replay | existing replay package | Extend through versioned inputs |
| Evidence | existing evidence package | Additive |
| Recovery | existing recovery package | Additive |
| Agent adapters | new `backend/app/agents/` | New boundary |
| Merchant simulation | new `backend/app/merchant/` | New boundary |
| TIX | new `backend/app/tix/` | New boundary |
| Protocol security | new security helpers | Additive |
| Scenario lab | new scenario package | Reuse existing engine |
| Tests | new test modules | Never delete existing tests |
| UI | T14-owned frontend | Do not touch during innovation backend phase |
| Documentation | `brain/` + extension document | Update after checkpoints |

---

# 7. IMPORTANT FILE PROTECTION RULES

The following existing areas are treated as protected.

## Protected category A

Existing T01–T13 domain behaviour.

Do not rewrite working business rules merely to introduce new abstractions.

---

## Protected category B

Existing deterministic PASS / DRIFT / UNKNOWN decision logic.

New features must feed the existing authority model.

They must not create a second competing integrity engine.

---

## Protected category C

Existing replay engine.

T13 already establishes deterministic replay.

The innovation layer may add:

```text
rules_version
policy_version
contract_version
snapshot_hash
extension_metadata
```

but must continue using the authoritative replay mechanism.

---

## Protected category D

Existing Razorpay integration.

Do not replace verified Razorpay integration with simulated payment logic.

Simulation may exist alongside it.

---

## Protected category E

Existing tests.

No test should be deleted simply because an extension changes architecture.

If a test becomes invalid because a contract intentionally changes, document why and replace it with an equivalent invariant test.

---

# 8. I1 — EVIDENCE EXTENSION LAYER

## Objective

Strengthen the existing evidence model without changing its authority hierarchy.

Existing evidence authority remains authoritative.

The extension adds:

```text
freshness
provenance
binding
sequence
integrity metadata
```

---

# 8.1 Evidence Freshness

Add optional evidence metadata:

```text
observed_at
valid_until
source_timestamp
freshness_status
```

Possible status:

```text
FRESH
STALE
EXPIRED
UNKNOWN
```

Do not make freshness itself override authoritative evidence.

Instead:

```text
authoritative + stale
```

may become:

```text
UNKNOWN
```

if the contract explicitly requires fresh state.

---

# 8.2 Merchant Offer Evidence

Introduce a structured merchant offer object.

Suggested fields:

```text
offer_id
merchant_id
sku
quantity
unit_price
discount
shipping
tax
total
currency
inventory_status
delivery_estimate
offer_created_at
offer_expires_at
merchant_policy_version
evidence_refs
```

The offer becomes evidence input.

The merchant agent does not become the final authority.

---

# 8.3 Integrity Delta

Add a deterministic difference representation:

```text
baseline
observed
delta
violated_constraint
```

Example:

```text
AUTHORIZED_TOTAL = ₹50,000
OBSERVED_TOTAL   = ₹54,000

DELTA = +₹4,000

RULE = MAX_TOTAL

RESULT = DRIFT
```

This should be generated by deterministic code.

---

# 8.4 Checkpoint

Required tests:

- fresh evidence accepted
- expired evidence handled correctly
- stale evidence cannot silently become PASS
- economic delta deterministic
- evidence provenance preserved
- existing evidence tests still pass

Commit:

```text
feat: add evidence freshness and integrity deltas
```

---

# 9. I2 — SECURITY / PROTOCOL BINDING

## Objective

Protect the transaction from:

- replay
- intent substitution
- cross-transaction message reuse
- stale agent responses
- state desynchronization
- unauthorized agent action

---

# 9.1 Intent Binding

Every agent transaction message should reference:

```text
intent_id
transaction_id
attempt_id
```

A message for one transaction must not be accepted for another.

---

# 9.2 Freshness

Messages should include:

```text
timestamp
expiry
```

The deterministic verifier checks:

```text
now <= expiry
```

where appropriate.

---

# 9.3 Intent Consumption

Add:

```text
intent_consumption_state
```

Possible values:

```text
ACTIVE
CONSUMED
EXPIRED
REVOKED
```

The purpose is to prevent the same authorization context from silently being reused for a second logical transaction.

---

# 9.4 Message Chain

TIX messages should support:

```text
previous_message_hash
current_message_hash
```

Conceptually:

```text
MESSAGE 1
   ↓ hash
MESSAGE 2
   ↓ hash
MESSAGE 3
   ↓ hash
MESSAGE 4
```

Any mutation changes the chain.

This is an extension of the existing MRDP/evidence philosophy, not a replacement for it.

---

# 9.5 Protocol Attack Detection

Detect bounded patterns:

```text
REPLAY
INTENT_MISMATCH
TRANSACTION_MISMATCH
STALE_MESSAGE
DUPLICATE_MESSAGE
AGENT_ID_MISMATCH
STATE_DESYNC
```

Do not build a generic intrusion-detection platform.

Only implement transaction-integrity-relevant patterns.

---

# 9.6 Checkpoint

Tests must prove:

```text
valid message → accepted

wrong intent → rejected

wrong transaction → rejected

expired message → rejected/UNKNOWN according to contract

replayed consumed intent → rejected

tampered chain → invalid
```

Commit:

```text
feat: add transaction and agent message binding
```

---

# 10. I3 — GOVERNANCE + REPLAY EXTENSION

T13 already provides deterministic replay.

The innovation is to make replay more reproducible and governance-aware.

---

# 10.1 Policy Version

Every deterministic decision should be attributable to:

```text
policy_version
rules_version
```

Example:

```text
rules_version = integrity-1.0
policy_version = merchant-policy-3
```

---

# 10.2 Reproducibility Record

A replay snapshot should be able to identify:

```text
intent
events
evidence
rules_version
policy_version
reference_time
input_snapshot_hash
recorded_result
```

The goal is:

```text
same inputs
+
same rules
+
same policy
=
same decision
```

---

# 10.3 Decision Certificate

Add an optional deterministic certificate:

```text
decision
intent_hash
evidence_hash
event_chain_hash
rules_version
policy_version
decision_timestamp
```

This is not a legal certificate.

Call it:

> **Decision Reproducibility Certificate**

unless later research establishes a better formal term.

---

# 10.4 Counterfactual Verification — OPTIONAL

Do not introduce "causal inference."

The precise implementation term is:

> **Counterfactual replay analysis**

For a detected violation:

```text
ORIGINAL TRACE
     ↓
DRIFT
```

then:

```text
REMOVE / MODIFY candidate event
     ↓
REPLAY
     ↓
COMPARE RESULT
```

Example:

```text
WITH RETRY:
duplicate capture → DRIFT

WITHOUT RETRY:
single capture → PASS
```

Output:

```text
candidate contributing event:
RETRY-02

counterfactual result:
DRIFT disappears
```

This is an experimental replay feature, not a claim of formal causal inference.

---

# 10.5 Checkpoint

Tests:

- same snapshot gives same decision
- different rules version is distinguishable
- different policy version is distinguishable
- certificate detects snapshot mutation
- counterfactual replay has zero external side effects

Commit:

```text
feat: add reproducible policy-aware replay
```

---

# 11. I4 — MERCHANT AGENT

## Objective

Introduce genuine agentic-commerce behaviour on the merchant side.

This is important because TarkaRaksha should not merely demonstrate:

```text
BUYER → PAYMENT
```

It should demonstrate:

```text
BUYER AGENT
     ↕
MERCHANT AGENT
     ↕
TARKARAKSHA
     ↕
RAZORPAY
```

---

# 11.1 Important Boundary

The merchant agent is a:

> **synthetic/reference merchant agent for the prototype**

unless an actual external merchant-agent integration is implemented and verified.

Do not claim real merchants are connected.

---

# 11.2 Merchant Agent Responsibilities

The merchant agent may:

- expose catalog
- expose inventory
- return prices
- calculate offers
- provide shipping options
- provide tax information
- propose alternatives
- explain merchant policy
- propose remediation-compatible offers
- respond to buyer-agent requests

It may NOT:

- override TarkaRaksha
- declare integrity PASS
- fabricate payment state
- authorize arbitrary refunds
- change buyer constraints
- use its own proposal as proof

---

# 11.3 Merchant Capability Declaration

Merchant agent advertises:

```text
catalog
inventory
pricing
shipping
tax
alternative_offer
refund
fulfillment
```

Each capability has:

```text
available
version
scope
constraints
```

This lets TarkaRaksha reason about what the merchant agent can actually do.

---

# 11.4 Merchant Policy-as-Code

Create a small deterministic policy representation.

Example:

```text
MAX_ORDER_VALUE
MAX_DISCOUNT
ALLOWED_SUBSTITUTIONS
MAX_NEGOTIATION_ROUNDS
OFFER_TTL
REFUND_LIMIT
```

The policy is data, not LLM instructions.

---

# 11.5 Dynamic Offer Expiry

Offers contain:

```text
offer_expires_at
```

If expired:

```text
DO NOT ACCEPT OLD OFFER
```

Instead:

```text
REQUEST REFRESH
```

---

# 11.6 Inventory Integrity

Merchant offer may state:

```text
inventory_status = AVAILABLE
```

Later:

```text
inventory_status = SOLD_OUT
```

TarkaRaksha detects the state change.

Possible result:

```text
DRIFT
```

or:

```text
UNKNOWN
```

depending on available authoritative evidence.

---

# 11.7 Fulfillment Integrity

Intent:

```text
DELIVER_WITHIN = 2 DAYS
```

Observed:

```text
DELIVERY = 5 DAYS
```

Result:

```text
TEMPORAL / FULFILLMENT DRIFT
```

This extends the transaction contract beyond price alone.

---

# 11.8 Checkpoint

Merchant agent tests must prove:

- catalog response structured correctly
- inventory response structured correctly
- offer generation deterministic where required
- merchant cannot override integrity
- expired offer rejected
- invalid capability rejected
- policy boundaries respected

Commit:

```text
feat: add bounded merchant agent
```

---

# 12. I5 — BUYER AGENT

## Objective

Provide an agentic buyer representation that converts natural-language goals into a structured transaction contract.

---

# 12.1 Buyer Agent Responsibilities

Buyer agent may:

- interpret natural language
- extract constraints
- ask clarifying questions
- request merchant information
- propose transaction configuration
- receive integrity feedback
- replan
- submit a new proposal

---

# 12.2 Deterministic Boundary

The buyer agent's output must pass:

```text
LLM
 ↓
structured proposal
 ↓
schema validation
 ↓
intent validation
 ↓
deterministic engine
```

The LLM never directly controls payment.

---

# 12.3 Example

User:

```text
Buy SERVER-256,
one unit,
under ₹50,000,
delivery within two days,
no substitution.
```

Buyer Agent produces:

```text
SKU = SERVER-256
QTY = 1
MAX_TOTAL = 50000 INR
MAX_DELIVERY_DAYS = 2
SUBSTITUTION = FALSE
```

This becomes the transaction contract.

---

# 12.4 Checkpoint

Test:

```text
natural language
 ↓
structured intent
 ↓
schema validation
 ↓
same deterministic contract
```

Also test adversarial input.

Commit:

```text
feat: add bounded buyer agent
```

---

# 13. I6 — TIX: TARKARAKSHA INTEGRITY EXCHANGE

## Status

Proposed prototype protocol.

It is NOT:

- AP2
- ACP
- UCP
- UAP
- a replacement for any standard
- a public industry standard

---

# 13.1 Purpose

TIX is a lightweight internal exchange format allowing:

```text
BUYER AGENT
      ↕
TARKARAKSHA
      ↕
MERCHANT AGENT
```

to exchange transaction-integrity information.

---

# 13.2 Message Types

Initial bounded set:

```text
INTENT
OFFER
EVIDENCE_REQUEST
EVIDENCE_RESPONSE
INTEGRITY_CHECK
DRIFT_NOTICE
REMEDIATION_REQUEST
REMEDIATION_RESPONSE
REVALIDATION
AUTHORIZATION
EXECUTION
OUTCOME
```

Do not implement unnecessary protocol complexity.

---

# 13.3 Common Message Envelope

Suggested fields:

```text
message_id
transaction_id
intent_id
sender
receiver
timestamp
expires_at
message_type
payload
evidence_refs
previous_message_hash
```

Optional:

```text
capability_refs
policy_version
rules_version
```

---

# 13.4 TIX Rule

TIX transports claims.

TarkaRaksha verifies claims.

Therefore:

```text
TIX message
    ↓
TarkaRaksha
    ↓
authoritative evidence
    ↓
deterministic verification
```

not:

```text
TIX message
    ↓
TRUST
```

---

# 13.5 Checkpoint

Test:

- message schema
- transaction binding
- intent binding
- expiry
- replay protection
- message hash
- unknown message handling
- malformed message handling

Commit:

```text
feat: add TIX integrity exchange
```

---

# 14. I7 — BOUNDED AGENTIC NEGOTIATION

Use the term carefully.

This is not unrestricted financial negotiation.

It is:

> **bounded agentic replanning under an existing authorization contract.**

---

# 14.1 Main Loop

```text
BUYER AGENT
    ↓
MERCHANT AGENT
    ↓
TARKARAKSHA
    ↓
DRIFT
    ↓
DRIFT NOTICE
    ↓
BUYER AGENT
    ↓
NEW PROPOSAL
    ↓
MERCHANT AGENT
    ↓
TARKARAKSHA
    ↓
PASS / DRIFT / UNKNOWN
```

---

# 14.2 Example

Buyer:

```text
SERVER-256
≤ ₹50,000
2 days
no substitution
```

Merchant:

```text
₹54,000
```

TarkaRaksha:

```text
DRIFT
MAX_TOTAL_EXCEEDED
DELTA = +₹4,000
```

Buyer Agent asks for a compliant configuration.

Merchant:

```text
₹49,000
delivery 2 days
```

TarkaRaksha:

```text
PASS
```

---

# 14.3 Negotiation Limits

Hard limits:

```text
MAX_REPLANS = 3
MAX_ROUNDS = 3
MAX_FINANCIAL_DELTA = policy-defined
MAX_EXECUTION_TIME = policy-defined
```

After the limit:

```text
ABSTAIN
```

or:

```text
ESCALATE
```

Never:

```text
continue forever
```

---

# 14.4 Checkpoint

Demonstrate:

```text
DRIFT
 ↓
PROOF
 ↓
REPLAN
 ↓
REVALIDATE
 ↓
PASS
```

This is the primary agentic innovation demonstration.

Commit:

```text
feat: add bounded agentic remediation loop
```

---

# 15. I8 — AGENT / TRANSACTION / PAYMENT BINDING

The final transaction should explicitly connect:

```text
intent_id
agent_id
merchant_id
order_id
payment_id
attempt_id
```

Conceptually:

```text
AUTHORIZED INTENT
      │
      ├── intent_id
      │
      ▼
BUYER AGENT
      │
      ├── agent_id
      │
      ▼
MERCHANT AGENT
      │
      ├── merchant_id
      │
      ▼
RAZORPAY ORDER
      │
      ├── order_id
      │
      ▼
PAYMENT
      │
      ├── payment_id
      │
      ▼
TARKARAKSHA
```

---

# 15.1 Important Razorpay Rule

Do not invent a universal payment cancellation or authorization-void API.

Where provider capabilities are unavailable:

```text
PREVENT CAPTURE
```

should be used only where the integration actually permits it.

Otherwise:

```text
SAFE PROVIDER-SUPPORTED REMEDIATION
```

or:

```text
SIMULATED / DOCUMENTED CONTROL
```

must be clearly labelled.

---

# 15.2 Checkpoint

Tests:

```text
correct binding → PASS

wrong order → reject

wrong payment → reject

wrong merchant → reject

wrong intent → reject

duplicate attempt → controlled handling
```

Commit:

```text
feat: bind agents intents orders and payments
```

---

# 16. I9 — AGENT KILL SWITCH

Introduce a deterministic execution control:

```text
RUNNING
PAUSED
REQUIRES_REVALIDATION
TERMINATED
```

The kill switch is activated by conditions such as:

```text
critical drift
repeated UNKNOWN
replan limit reached
policy violation
agent capability violation
expired intent
```

After a kill:

```text
NO CONTINUATION
```

until the system explicitly authorizes resumption.

---

# 16.1 Checkpoint

Prove:

```text
critical violation
 ↓
pause
 ↓
no further financial action
 ↓
revalidation required
```

Commit:

```text
feat: add agent execution kill switch
```

---

# 17. I10 — SHADOW / GUARDED / REVIEW MODES

Add merchant operational modes:

```text
SHADOW
GUARDED
HUMAN_REVIEW
```

### SHADOW

Observe and evaluate.

Do not intervene.

### GUARDED

Allow bounded automated actions.

### HUMAN_REVIEW

Require approval for sensitive actions.

These modes must be policy-controlled.

---

# 18. I11 — SCENARIO LAB

Create deterministic scenario definitions.

Do not build a separate business logic engine.

The scenario lab must feed the same engine used by production-shaped execution.

---

# 18.1 Required Scenarios

Minimum:

```text
01 HAPPY_PATH

02 PRICE_DRIFT

03 WRONG_SKU

04 INVENTORY_DISAPPEARS

05 DELIVERY_DRIFT

06 DUPLICATE_PAYMENT

07 DELAYED_WEBHOOK

08 REPLAY_ATTACK

09 PROMPT_INJECTION_IN_EVIDENCE

10 MERCHANT_AGENT_COMPROMISED

11 BUYER_AGENT_REUSE

12 UNKNOWN_PROVIDER_STATE
```

---

# 18.2 Scenario Structure

Each scenario contains:

```text
scenario_id
intent
events
evidence
expected_result
expected_policy_action
fault_injection
```

The expected result must be independent of the runtime LLM.

---

# 18.3 Scenario Lab Rule

The scenario lab is:

```text
TEST / DEMONSTRATION INPUT
```

not:

```text
PRODUCTION INFRASTRUCTURE
```

Fault injection remains data-driven.

Do not introduce unnecessary Kafka/Redis/event-bus infrastructure.

---

# 19. I12 — GROUND-TRUTH CERTIFICATION

The evaluation system should distinguish:

```text
MODEL OUTPUT
```

from:

```text
GROUND TRUTH
```

---

# 19.1 Dual Oracle

For each scenario:

```text
Scenario Generator
      ↓
Ground Truth
      ↓
TarkaRaksha
      ↓
Decision
      ↓
Compare
```

Where possible, use construction-based labels.

Example:

```text
scenario generated with
total = ₹55,000
max = ₹50,000

ground truth = DRIFT
```

---

# 19.2 Mutation Testing

Start with valid traces.

Apply controlled mutations:

```text
amount mutation
SKU mutation
quantity mutation
timestamp mutation
payment duplication
message replay
agent identity mutation
inventory mutation
delivery mutation
```

Then verify the engine catches the intended violation.

---

# 19.3 Required Metrics

Record actual values, not targets:

```text
PASS accuracy
DRIFT detection rate
UNKNOWN precision
false-positive rate
unsafe escape rate
recovery success rate
replay agreement
mutation detection rate
```

Never claim:

```text
0% unsafe escape
```

without specifying:

```text
test-set size
scenario classes
held-out status
evaluation method
```

---

# 20. I13 — INTEGRITY TRACE / FAULT LOCALIZATION

T13 already reconstructs event sequences.

The extension may add a deterministic trace view:

```text
EVENT 1
 ↓
EVENT 2
 ↓
EVENT 3
 ↓
EVENT 4 ← candidate violating event
 ↓
EVENT 5
```

Output:

```text
FIRST DETECTABLE VIOLATION
```

Do not call this:

> causal inference

unless a genuine causal methodology is implemented.

Preferred term:

> **Deterministic fault localization**

or:

> **Event-sequence fault localization**

---

# 21. I14 — INTEGRITY CHECKPOINTS

Introduce checkpoints such as:

```text
INTENT_LOCKED
OFFER_VERIFIED
ORDER_CREATED
PAYMENT_AUTHORIZED
PAYMENT_CAPTURED
OUTCOME_VERIFIED
```

At each checkpoint:

```text
contract
+
evidence
+
state
```

can be verified.

This allows:

```text
continuous integrity
```

rather than a single final check.

---

# 22. I15 — INTEGRITY SLA METRICS

Record:

```text
time_to_detect
time_to_prove
time_to_intervene
time_to_revalidate
time_to_final_decision
```

These are product metrics.

Do not fabricate benchmark values.

Measure them during T18 validation.

---

# 23. I16 — VALUE-AT-RISK INTERVENTION RANKING

Optional extension if implementation remains stable.

When multiple safe remediation options exist:

```text
OPTION A
₹2,000 loss prevented

OPTION B
₹8,000 loss prevented

OPTION C
requires human review
```

The system can rank candidate interventions using deterministic policy inputs.

Do not allow the LLM to decide the financial ranking independently.

---

# 24. I17 — TRUST-CONTEXT ADAPTER

Do not implement complete AP2, ACP, UCP, FACT, Visa TAP, or another ecosystem protocol.

Instead create a conceptual adapter boundary:

```text
External Trust / Authorization Context
              ↓
       Trust Context Adapter
              ↓
       TarkaRaksha Contract
```

This preserves future interoperability without creating a multi-protocol implementation project.

---

# 25. I18 — PROTOCOL COMPATIBILITY POSITION

The documentation must explicitly state:

```text
AP2 / Verifiable Intent
        ↓
authorization / intent context

Agent identity / trust systems
        ↓
identity / trust context

Commerce protocols
        ↓
commerce execution

TARKARAKSHA
        ↓
transaction execution integrity
```

This is a compatibility architecture.

It is not a claim that TarkaRaksha replaces these systems.

---

# 26. I19 — MERCHANT-SIDE CAPABILITY GRAPH

The merchant agent can expose:

```text
MERCHANT
 ├── CATALOG
 ├── INVENTORY
 ├── PRICING
 ├── SHIPPING
 ├── TAX
 ├── OFFERS
 ├── FULFILLMENT
 └── REFUND
```

TarkaRaksha can verify whether an action is within declared capability.

Example:

```text
Merchant Agent:
CAPABILITY = refund

SCOPE:
≤ ₹10,000

Requested:
₹25,000 refund

RESULT:
CAPABILITY VIOLATION
```

This is more useful than a generic agent "trust score."

---

# 27. I20 — NO AGENT REPUTATION SCORE

Do not build:

```text
Agent Trust Score = 87
```

This would introduce unsupported complexity.

Instead use observable controls:

```text
IDENTITY
CAPABILITY
AUTHORIZATION
FRESHNESS
BINDING
EVIDENCE
POLICY
HISTORY
```

This is explainable and deterministic.

---

# 28. I21 — EVIDENCE-AWARE AI EXPLANATION

LLM may receive:

```text
deterministic decision
+
MRDP
+
evidence
+
event trace
```

and generate:

```text
human explanation
```

Example:

> Transaction blocked because the verified total exceeded the authorized maximum by ₹4,000.

The LLM must not invent a reason.

The deterministic MRDP remains authoritative.

---

# 29. I22 — COMPLETE HERO TRANSACTION

The implementation must eventually support this end-to-end demonstration.

## Step 1

Buyer:

```text
Buy SERVER-256,
one unit,
under ₹50,000,
deliver within 2 days,
no substitution.
```

---

## Step 2

Buyer Agent:

```text
SKU = SERVER-256
QTY = 1
MAX = ₹50,000
DELIVERY <= 2 days
SUBSTITUTION = false
```

---

## Step 3

Merchant Agent:

```text
PRODUCT = SERVER-256
PRICE = ₹47,000
SHIPPING = ₹2,000
TAX = ₹1,000
TOTAL = ₹50,000
DELIVERY = 2 days
```

---

## Step 4

TarkaRaksha:

```text
PASS
```

---

## Step 5 — Inject Drift

Merchant state changes:

```text
PRICE = ₹51,000
SHIPPING = ₹2,000
TAX = ₹1,000
```

Total:

```text
₹54,000
```

---

## Step 6

TarkaRaksha:

```text
DRIFT
```

MRDP:

```text
AUTHORIZED = ₹50,000
OBSERVED = ₹54,000
DELTA = +₹4,000
RULE = MAX_TOTAL
```

---

## Step 7

Buyer Agent receives:

```text
DRIFT_NOTICE
```

---

## Step 8

Buyer Agent requests a compliant alternative.

---

## Step 9

Merchant Agent proposes:

```text
PRICE = ₹49,000
SHIPPING = ₹1,000
TAX = included
DELIVERY = 2 days
```

---

## Step 10

TarkaRaksha:

```text
REVALIDATION
 ↓
PASS
```

---

## Step 11

Razorpay test-mode payment execution.

---

## Step 12

Final verification:

```text
INTENT
ORDER
PAYMENT
EVIDENCE
INTEGRITY
```

all bound.

Final:

```text
TRANSACTION INTEGRITY VERIFIED
```

---

# 30. REQUIRED CLOSED-LOOP DEMONSTRATION

The strongest demo sequence is:

```text
BUYER AGENT
     ↓
MERCHANT AGENT
     ↓
OFFER
     ↓
TARKARAKSHA
     ↓
PASS
     ↓
PRICE MUTATION
     ↓
DRIFT
     ↓
MRDP
     ↓
DRIFT NOTICE
     ↓
BUYER AGENT REPLAN
     ↓
MERCHANT AGENT
     ↓
NEW OFFER
     ↓
REVALIDATION
     ↓
PASS
     ↓
RAZORPAY
     ↓
OUTCOME
```

This demonstrates:

> **Detect → Prove → Repair → Revalidate**

rather than simply:

> Detect → Block.

---

# 31. DOCUMENTATION FILE PLAN

The following files should be maintained.

---

## 31.1 Existing

### `TarkaRaksha_IDEA.md`

Purpose:

```text
WHAT the product is
WHY it exists
INNOVATION thesis
```

Do not turn it into a task tracker.

Only update it after innovation architecture is actually implemented.

---

## 31.2 Existing

### `TarkaRaksha_Execution.md`

Purpose:

```text
HOW the project is built
```

Do not rewrite T01–T13.

The innovation extension should initially remain in this separate document.

After implementation stabilizes, add a short integration section to the execution plan:

```text
8.x — Innovation Extension
```

containing only:

```text
I0 → I22
```

and links/references to this document.

Do not duplicate the entire innovation document inside Execution.md.

---

## 31.3 New

### `TarkaRaksha_Innovation_Extension.md`

Purpose:

```text
Detailed additive innovation implementation plan
```

This is the primary source document for the extension.

---

## 31.4 New / existing brain file

### `brain/INNOVATION_HANDOFF.md`

Purpose:

```text
Current innovation checkpoint
Completed extensions
Pending extensions
Files changed
Tests
Commit
Known risks
Next safe task
```

This is the primary handoff file for another coding agent.

---

## 31.5 Existing

### `brain/STATUS.md`

Only add concise state:

```text
T13 COMPLETE
Innovation Extension:
I0 COMPLETE
I1 COMPLETE
...
```

Do not turn STATUS.md into a detailed technical document.

---

## 31.6 Existing

### `brain/CONTEXT.md`

Only add architectural invariants that become permanently true.

For example:

```text
TIX is advisory transport.
Deterministic engine remains authoritative.
Merchant agent cannot self-authorize.
Buyer agent cannot authorize payment.
Innovation extensions are additive.
```

Do not copy the entire extension plan here.

---

## 31.7 Existing

### `brain/HANDOFF.md`

Use after each major checkpoint.

It should state:

```text
LAST VERIFIED TASK
CURRENT COMMIT
TEST RESULT
FILES CHANGED
NEXT TASK
DO NOT TOUCH
KNOWN ISSUES
```

---

# 32. FILE CHANGE MATRIX

| Stage | New files | Existing files allowed to change | Protected |
|---|---|---|---|
| I0 | `brain/INNOVATION_HANDOFF.md` | STATUS/HANDOFF | all T01–T13 logic |
| I1 | evidence extension + tests | existing evidence models/services | replay core |
| I2 | security/binding + tests | contract models if additive | decision semantics |
| I3 | governance/replay extensions | replay contracts | replay determinism |
| I4 | merchant agent package + tests | integration contracts only | Razorpay adapter |
| I5 | buyer agent package + tests | intent adapter only | deterministic rules |
| I6 | TIX package + tests | message/domain models only | payment authority |
| I7 | negotiation/replan service + tests | recovery interfaces | core recovery invariants |
| I8 | binding integration + tests | transaction integration | provider assumptions |
| I9 | scenario package + tests | evaluation integration | production engine |
| I10 | certification outputs | STATUS/CONTEXT/HANDOFF | existing behaviour |
| T14 | frontend | frontend only initially | frozen backend |
| T15 | security hardening | security/config | product semantics |
| T16 | integration | integration boundaries | core invariants |
| T17 | deployment | deployment/config | domain logic |
| T18 | validation docs | STATUS/HANDOFF/validation | tested implementation |

---

# 33. STRICT CHANGE RULE

Before editing an existing file:

1. Read it.
2. Identify its current responsibility.
3. Identify whether an extension can live in a new file instead.
4. Prefer the new file.
5. If existing modification is necessary, make the smallest additive change.
6. Run the relevant old tests.
7. Run new tests.
8. Run full regression.
9. Commit only after verification.

---

# 34. NO-COLLATERAL-DAMAGE RULE

Never perform these operations during the extension:

```text
rewrite the whole domain model
rewrite the integrity engine
rewrite replay
replace FastAPI
replace Pydantic
replace Razorpay adapter
replace Groq adapter
introduce Kafka
introduce Redis
introduce Kubernetes
introduce microservices
replace synchronous flow with distributed infrastructure
rewrite all tests
replace the existing API
```

unless a later verified requirement proves one is necessary.

At present, none is required.

---

# 35. TESTING RULE

Every innovation task has two test obligations.

## New-feature test

```text
new feature works
```

AND:

## Regression test

```text
old feature still works
```

Therefore:

```text
NEW TESTS
+
EXISTING TESTS
=
CHECKPOINT
```

---

# 36. TEST GATE

A task cannot be marked complete if:

```text
new tests pass
```

but:

```text
old tests fail
```

The task remains incomplete.

---

# 37. ROLLBACK RULE

If an innovation breaks an existing T01–T13 invariant:

```text
STOP
 ↓
identify regression
 ↓
revert innovation change
 ↓
restore baseline
 ↓
run full tests
 ↓
redesign extension boundary
```

Do not "patch around" a broken core with increasingly complex compatibility code.

---

# 38. FEATURE FLAG RULE

Where useful, innovation functionality may initially be behind:

```text
innovation_enabled
```

or feature-specific configuration.

This permits:

```text
BASELINE MODE
```

and:

```text
EXTENDED MODE
```

to coexist during testing.

The baseline path must remain operational.

---

# 39. AI FAILURE RULE

If Groq is unavailable:

```text
system must not fabricate an AI response
```

Possible result:

```text
UNKNOWN
```

or:

```text
controlled failure
```

depending on the specific operation.

Deterministic integrity checks must remain usable where their required evidence exists.

---

# 40. PROVIDER FAILURE RULE

If Razorpay state cannot be authoritatively confirmed:

```text
UNKNOWN
```

must remain possible.

Do not convert:

```text
timeout
```

into:

```text
success
```

or:

```text
failure
```

without evidence.

This preserves the existing UNKNOWN-first-class principle.

---

# 41. MERCHANT AGENT FAILURE RULE

If merchant agent returns:

```text
invalid offer
```

or:

```text
missing evidence
```

TarkaRaksha must not trust it simply because it is the merchant agent.

Possible result:

```text
UNKNOWN
```

or:

```text
DRIFT
```

depending on the deterministic condition.

---

# 42. SECURITY RULE

Never allow:

```text
agent-generated text
```

to become:

```text
authoritative evidence
```

unless the evidence source itself is independently authoritative.

This is especially important for:

- prompt injection
- malicious merchant responses
- forged evidence notes
- agent-generated explanations

---

# 43. SCOPE RULE

The innovation package is intentionally broad at the conceptual level but must remain narrow at implementation level.

Priority order:

## Tier 1 — Must implement

```text
Evidence freshness
Integrity delta
Agent/transaction binding
Merchant Agent
Buyer Agent
TIX
Bounded remediation loop
Merchant capability declaration
Offer expiry
Scenario Lab
Certification tests
```

## Tier 2 — Strongly recommended

```text
Policy versioning
Decision reproducibility
Intent consumption
Event hash chain
Integrity checkpoints
Kill switch
Shadow/Guarded/Review modes
```

## Tier 3 — Only if stable

```text
Counterfactual replay
Value-at-risk intervention ranking
External trust-context adapters
Additional protocol attack patterns
advanced capability graphs
```

Tier 3 must never delay or destabilize Tier 1.

---

# 44. WHAT MUST NOT BE CLAIMED

The project documentation must not claim:

```text
"TarkaRaksha invented verifiable intent."

"TarkaRaksha replaces AP2."

"TarkaRaksha replaces ACP/UCP."

"TarkaRaksha is the industry's first trust layer."

"TarkaRaksha provides formal causal inference."

"TarkaRaksha provides universal payment cancellation."

"TarkaRaksha guarantees zero fraud."

"TarkaRaksha guarantees zero unsafe transactions."

"Merchant agents are already deployed everywhere."

"Razorpay lacks agent guardrails."

"Razorpay cannot handle this problem."

```

Instead use precise language:

```text
"runtime transaction-integrity layer"

"execution-integrity specialization"

"complementary to existing agentic commerce protocols"

"deterministic event-sequence verification"

"bounded remediation"

"prototype merchant agent"

"Razorpay-integrated test-mode execution"
```

---

# 45. RAZORPAY POSITIONING

The final architecture should be:

```text
BUYER AGENT
      ↓
MERCHANT AGENT
      ↓
TARKARAKSHA
      ↓
RAZORPAY
      ↓
PAYMENT RAILS
```

TarkaRaksha's purpose is not to replace Razorpay.

It provides an additional transaction-integrity control point around agentic execution.

Razorpay's existing Agent Studio already provides agent permissions, validation, review controls and audit trails, so those should not be presented as TarkaRaksha's unique innovation.

The differentiation is:

```text
specific transaction
        ↓
authorized contract
        ↓
execution evidence
        ↓
continuous integrity
        ↓
deterministic proof
        ↓
bounded remediation
        ↓
revalidation
```

---

# 46. FINAL ARCHITECTURE AFTER EXTENSION

```text
                         USER
                           │
                           ▼
                    BUYER AGENT
                           │
                           │ TIX
                           ▼
                   MERCHANT AGENT
                           │
                           │
                    OFFER / CONTEXT
                           │
                           ▼
                  TARKARAKSHA CORE
                           │
             ┌─────────────┼──────────────┐
             │             │              │
             ▼             ▼              ▼
          EVIDENCE       POLICY         SECURITY
             │             │              │
             └─────────────┼──────────────┘
                           ▼
                 DETERMINISTIC ENGINE
                           │
                ┌──────────┼──────────┐
                ▼          ▼          ▼
              PASS       DRIFT      UNKNOWN
                │          │          │
                │          ▼          ▼
                │         MRDP      RESOLUTION
                │          │          │
                │          ▼          ▼
                │      REPLAN       ABSTAIN
                │          │
                │          ▼
                │    MERCHANT AGENT
                │          │
                │          ▼
                │      REVALIDATE
                │          │
                └──────────┘
                           │
                           ▼
                    RAZORPAY TEST MODE
                           │
                           ▼
                    PAYMENT EVIDENCE
                           │
                           ▼
                    FINAL INTEGRITY
                           │
                           ▼
                    REPLAY / AUDIT
```

---

# 47. T14 BOUNDARY

Only after:

```text
I0–I10
```

are stable and the backend is regression-clean should T14 begin.

T14 should consume the new backend capabilities.

The UI must NOT become the place where integrity logic is implemented.

Frontend:

```text
DISPLAY
```

Backend:

```text
DECIDE
```

---

# 48. T14 UI DATA CONTRACT

The Control Room should eventually consume:

```text
intent
agent
merchant
offer
order
payment
event stream
evidence
integrity result
MRDP
drift delta
policy
recovery
revalidation
replay
```

The UI should therefore be built **after the backend event/data contract stabilizes**.

---

# 49. T15 SECURITY HARDENING

T15 should harden:

```text
TIX
agent binding
message validation
replay protection
secrets
webhooks
authentication
authorization
rate limits
input validation
prompt-injection boundaries
```

Do not move these concerns into arbitrary agent prompts.

---

# 50. T16 INTEGRATION

T16 verifies:

```text
Buyer Agent
     ↓
Merchant Agent
     ↓
TIX
     ↓
TarkaRaksha
     ↓
Razorpay
     ↓
Evidence
     ↓
Integrity
     ↓
Recovery
     ↓
Revalidation
```

The real Razorpay path must remain distinguishable from simulated merchant-agent behaviour.

---

# 51. T17 DEPLOYMENT

Deployment must preserve:

```text
deterministic behaviour
configuration
secrets
webhook security
agent boundaries
replay reproducibility
```

No deployment optimization should alter decision semantics.

---

# 52. T18 FINAL VALIDATION

Final validation must test three categories.

## A. Functional

```text
happy path
price drift
semantic drift
temporal drift
inventory drift
delivery drift
duplicate payment
UNKNOWN
recovery
revalidation
```

## B. Security

```text
replay
tampering
wrong intent
wrong transaction
wrong agent
expired message
prompt injection
state desynchronization
```

## C. Reproducibility

```text
live-shaped execution
        vs
replay
```

must produce equivalent deterministic decisions for equivalent evidence.

---

# 53. FINAL HANDOFF FORMAT

After every major extension checkpoint, update:

```text
brain/STATUS.md
brain/HANDOFF.md
brain/INNOVATION_HANDOFF.md
```

Use:

```text
LAST COMPLETED:
CURRENT COMMIT:
TEST COUNT:
NEW TESTS:
FILES ADDED:
FILES MODIFIED:
FILES PROTECTED:
KNOWN LIMITATIONS:
NEXT TASK:
ROLLBACK POINT:
```

---

# 54. CONTEXT-HANDOFF RULE

A future coding agent must be able to understand the current state without reading the entire conversation.

Therefore the handoff must explicitly say:

```text
BASELINE:
T13 complete

EXTENSION STATUS:
I0 complete
I1 complete
I2 pending
...

CURRENT ARCHITECTURE:
...

CURRENT TEST COUNT:
...

CURRENT COMMIT:
...

DO NOT TOUCH:
...

NEXT TASK:
...

KNOWN UNKNOWN:
...
```

No implicit conversational context may be required.

---

# 55. COMMIT STRATEGY

One meaningful checkpoint = one meaningful commit.

Preferred:

```text
feat: add evidence freshness and integrity deltas
feat: add transaction and agent binding
feat: add reproducible policy-aware replay
feat: add bounded merchant agent
feat: add bounded buyer agent
feat: add TIX integrity exchange
feat: add bounded agentic remediation
feat: add scenario certification
```

Avoid:

```text
update stuff
fix things
more changes
final final
```

---

# 56. FINAL EXTENSION CHECKLIST

Before T14:

```text
[ ] T13 baseline remains green
[ ] I0 baseline freeze complete
[ ] I1 evidence extensions complete
[ ] I2 security binding complete
[ ] I3 replay/governance complete
[ ] I4 merchant agent complete
[ ] I5 buyer agent complete
[ ] I6 TIX complete
[ ] I7 bounded remediation complete
[ ] I8 payment/intent binding complete
[ ] I9 scenario lab complete
[ ] I10 certification complete
[ ] full regression passes
[ ] no existing T01–T13 behaviour changed unintentionally
[ ] Razorpay test-mode path still works
[ ] replay remains zero-side-effect
[ ] UNKNOWN remains first-class
[ ] AI remains advisory
[ ] deterministic engine remains authoritative
[ ] backend frozen
```

Only then:

```text
BEGIN T14
```

---

# 57. DEFINITION OF DONE

The innovation extension is complete only when:

```text
Existing T01–T13
        +
Innovation Layer
        +
Agentic Commerce Loop
        +
Merchant Agent
        +
Buyer Agent
        +
TIX
        +
Deterministic Integrity
        +
Recovery
        +
Replay
        +
Certification
```

operate together without breaking the original system.

The final system must demonstrate:

# **AI proposes → Merchant responds → Evidence arrives → Deterministic integrity verifies → Drift is proved → Agent replans within bounds → Transaction is revalidated → Razorpay executes → Outcome is independently verified → Entire execution can be replayed.**

---

# 58. FINAL GOVERNING PRINCIPLE

This extension does not change what TarkaRaksha fundamentally is.

It makes the existing idea deeper.

The project remains:

> **A Transaction Integrity Control Plane for Agentic Commerce.**

The innovation is the closed-loop execution model:

```text
AUTHORIZED INTENT
       ↓
AGENTIC EXECUTION
       ↓
CONTINUOUS EVIDENCE
       ↓
DETERMINISTIC INTEGRITY
       ↓
PASS / DRIFT / UNKNOWN
       ↓
PROOF
       ↓
BOUNDED REMEDIATION
       ↓
AGENT REPLAN
       ↓
REVALIDATION
       ↓
PAYMENT
       ↓
OUTCOME VERIFICATION
       ↓
REPLAYABLE AUDIT
```

And the permanent engineering invariant remains:

# **AI proposes. Evidence proves. Deterministic logic decides.**