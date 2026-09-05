"""
FastAPI Application and API Endpoints for TarkaRaksha (T10).
Exposes the first complete real transaction slice:
- Protected Order Creation
- Server-Side Payment Verification & Integrity Evaluation
- Webhook Ingestion
- Real-Time Control Plane State Inspection
"""
from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, Depends, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.app.core.config import settings
from backend.app.domain.hero import HeroTransactionRecord, HeroStage
from backend.app.domain.models import (
    CreateTransactionRequest,
    CreateTransactionResponse,
    CompleteTransactionRequest,
    CompleteTransactionResponse,
    RecoverTransactionRequest,
    ResolveTransactionRequest,
    IntentContract,
    IntentItem,
    Money,
    TransactionState,
)
from backend.app.domain.explanation import ExplanationResult
from backend.app.domain.trace import IntegrityTrace
from backend.app.domain.checkpoint import IntegrityCheckpointTimeline
from backend.app.domain.sla import IntegritySLAMetricsReport
from backend.app.services.hero import HeroTransactionOrchestrator
from backend.app.services.recovery import (
    InvalidRecoveryStateError,
    RecoveryExhaustedError,
    UnsafeActionRequestError,
)
from backend.app.services.resolution import (
    InvalidResolutionStateError,
    ResolutionConflictError,
    ResolutionExhaustedError,
)
from backend.app.services.replay import (
    ReplayEngine,
    ReplaySnapshot,
    ReplayResult,
    ReplayError,
    InvalidReplayInputError,
    ReplayAmbiguityError,
)
from backend.app.domain.scenario import (
    ScenarioDefinition,
    ScenarioResult,
    ScenarioSuiteResult,
    ScenarioId,
    ScenarioCategory,
)
from backend.app.services.scenario import ScenarioLabService
from backend.app.domain.certification import (
    CertificationMatrixRow,
    CertificationResult,
    CertificationSuiteResult,
    GroundTruthDefinition,
)
from backend.app.services.certification import GroundTruthCertificationService
from backend.app.services import TransactionService
from backend.app.services.ai import parse_intent, IntentParsingError
from backend.app.services.payment import (
    PaymentAuthenticationError,
    PaymentConfigurationError,
    PaymentNotFoundError,
    PaymentProvider,
    PaymentSignatureError,
    PaymentTimeoutError,
    PaymentProviderError,
    RazorpayAdapter,
    WebhookValidationError,
)

logger = logging.getLogger(__name__)

# Singleton transaction service for control plane runtime
_global_transaction_service = TransactionService()


def get_payment_provider() -> PaymentProvider:
    """Dependency provider for PaymentProvider. Can be overridden in tests."""
    return RazorpayAdapter()


def get_transaction_service() -> TransactionService:
    """Dependency provider for TransactionService. Can be overridden in tests."""
    return _global_transaction_service


_global_scenario_service = ScenarioLabService()


def get_scenario_service() -> ScenarioLabService:
    """Dependency provider for ScenarioLabService. Can be overridden in tests."""
    return _global_scenario_service


_global_certification_service = GroundTruthCertificationService()


def get_certification_service() -> GroundTruthCertificationService:
    """Dependency provider for GroundTruthCertificationService. Can be overridden in tests."""
    return _global_certification_service


_global_hero_orchestrator = HeroTransactionOrchestrator()


def get_hero_orchestrator() -> HeroTransactionOrchestrator:
    """Dependency provider for HeroTransactionOrchestrator (I22). Can be overridden in tests."""
    return _global_hero_orchestrator



app = FastAPI(
    title="TarkaRaksha Control Plane",
    description="Agentic Transaction Integrity & Recovery Control Plane",
    version="1.0.0",
)

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Custom Exception Handlers ---

@app.exception_handler(PaymentSignatureError)
async def signature_error_handler(request: Request, exc: PaymentSignatureError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc), "error_type": "SIGNATURE_VERIFICATION_FAILED"},
    )


@app.exception_handler(PaymentNotFoundError)
async def not_found_error_handler(request: Request, exc: PaymentNotFoundError):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(exc), "error_type": "RESOURCE_NOT_FOUND"},
    )


@app.exception_handler(PaymentTimeoutError)
async def timeout_error_handler(request: Request, exc: PaymentTimeoutError):
    return JSONResponse(
        status_code=status.HTTP_504_GATEWAY_TIMEOUT,
        content={"detail": str(exc), "error_type": "GATEWAY_TIMEOUT"},
    )


@app.exception_handler(IntentParsingError)
async def intent_parsing_error_handler(request: Request, exc: IntentParsingError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": str(exc), "error_type": "INTENT_PARSING_FAILED"},
    )


@app.exception_handler(ReplayError)
async def replay_error_handler(request: Request, exc: ReplayError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": str(exc), "error_type": type(exc).__name__},
    )


# --- API Endpoints ---

@app.get("/api/v1/health")
@app.get("/health")
def health_check():
    """Health check verifying control plane readiness and toolchains."""
    return {
        "status": "ok",
        "service": "tarkaraksha-control-plane",
        "version": "1.0.0",
        "has_groq": settings.has_groq_credentials,
        "has_razorpay": bool(settings.razorpay_key_id and settings.razorpay_key_secret),
    }


@app.post("/api/v1/intent/parse")
def parse_natural_language_intent(
    payload: Dict[str, Any],
):
    """
    Parses natural language user intent into an authoritative IntentContract using T08.
    """
    prompt = payload.get("prompt")
    if not prompt or not str(prompt).strip():
        raise HTTPException(status_code=400, detail="prompt cannot be empty")

    issued_by = payload.get("issued_by", "user_default")
    try:
        contract = parse_intent(user_prompt=str(prompt), issued_by=issued_by)
        return contract
    except IntentParsingError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.post("/api/v1/transaction/create", response_model=CreateTransactionResponse)
def create_transaction_slice(
    request: CreateTransactionRequest,
    service: TransactionService = Depends(get_transaction_service),
    provider: PaymentProvider = Depends(get_payment_provider),
):
    """
    Initiates a protected transaction slice: binds intent to a gateway order.
    Returns checkout parameters for the frontend.
    """
    try:
        response = service.create_transaction(request=request, provider=provider)
        return response
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except PaymentConfigurationError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except PaymentProviderError as exc:
        raise HTTPException(status_code=502, detail=f"Gateway failure: {exc}")


@app.post("/api/v1/transaction/complete", response_model=CompleteTransactionResponse)
def complete_transaction_slice(
    request: CompleteTransactionRequest,
    service: TransactionService = Depends(get_transaction_service),
    provider: PaymentProvider = Depends(get_payment_provider),
):
    """
    Verifies payment signature, polls gateway for authoritative state,
    normalizes evidence, and executes deterministic verification.
    """
    try:
        response = service.complete_transaction(request=request, provider=provider)
        return response
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except PaymentSignatureError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid signature: {exc}")
    except PaymentProviderError as exc:
        raise HTTPException(status_code=502, detail=f"Gateway error: {exc}")


@app.post("/api/v1/transaction/recover", response_model=CompleteTransactionResponse)
def recover_transaction_slice(
    request: RecoverTransactionRequest,
    service: TransactionService = Depends(get_transaction_service),
    provider: PaymentProvider = Depends(get_payment_provider),
):
    """
    Executes the T11 Recovery Loop:
    Classifies drift/unknown, deterministically validates recovery action,
    executes compensatory bounded action, and deterministically revalidates integrity.
    """
    try:
        response = service.recover_transaction(request=request, provider=provider)
        return response
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except InvalidRecoveryStateError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except (UnsafeActionRequestError, RecoveryExhaustedError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except PaymentProviderError as exc:
        raise HTTPException(status_code=502, detail=f"Gateway error during recovery: {exc}")


@app.post("/api/v1/transaction/resolve", response_model=CompleteTransactionResponse)
def resolve_transaction_slice(
    request: ResolveTransactionRequest,
    service: TransactionService = Depends(get_transaction_service),
    provider: PaymentProvider = Depends(get_payment_provider),
):
    """
    Executes the T12 UNKNOWN Resolution subsystem:
    Safe, bounded, non-side-effecting observation to establish ground truth
    for an ambiguous UNKNOWN transaction and deterministically re-evaluates integrity.
    """
    try:
        response = service.resolve_transaction(request=request, provider_override=provider)
        return response
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except InvalidResolutionStateError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except (ResolutionExhaustedError, ResolutionConflictError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except PaymentProviderError as exc:
        raise HTTPException(status_code=502, detail=f"Gateway error during resolution: {exc}")


@app.get("/api/v1/transaction/{transaction_id}")

def get_transaction_status(
    transaction_id: str,
    service: TransactionService = Depends(get_transaction_service),
):
    """
    Returns current control plane status and history of an active transaction.
    """
    session = service.get_session(transaction_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Transaction '{transaction_id}' not found")

    return {
        "transaction_id": session.transaction_id,
        "intent_id": session.intent.intent_id,
        "order_id": session.order.order_id,
        "state": session.state_machine.current_state.value,
        "updated_at": session.state_machine.updated_at.isoformat(),
        "history_count": len(session.state_machine.history),
        "history": [
            {
                "from_state": r.from_state.value,
                "to_state": r.to_state.value,
                "reason": r.reason,
                "timestamp": r.timestamp.isoformat(),
                "triggered_by": r.triggered_by,
                "is_verified": r.is_verified,
            }
            for r in session.state_machine.history
        ],
        "completed_result": session.completed_response.model_dump() if session.completed_response else None,
    }


@app.get("/api/v1/transaction/{transaction_id}/mrdp")
def get_transaction_mrdp(
    transaction_id: str,
    service: TransactionService = Depends(get_transaction_service),
):
    """
    Returns the Machine-Readable Drift Proof (MRDP) if DRIFT or UNKNOWN occurred.
    Returns 404 if transaction is PASS (no drift proof generated).
    """
    session = service.get_session(transaction_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Transaction '{transaction_id}' not found")

    if not session.completed_response:
        raise HTTPException(status_code=400, detail="Transaction has not yet been verified")

    if session.completed_response.state == TransactionState.PASS:
        raise HTTPException(status_code=404, detail="No MRDP generated for PASS transaction")

    if session.completed_response.mrdp:
        return session.completed_response.mrdp

    raise HTTPException(status_code=404, detail="No MRDP found for this transaction")


@app.get("/api/v1/transactions/{transaction_id}/explanation", response_model=ExplanationResult)
async def get_transaction_explanation(
    transaction_id: str,
    service: TransactionService = Depends(get_transaction_service),
) -> ExplanationResult:
    """
    Evidence-Aware AI Explanation endpoint (I21).
    Produces an evidence-grounded explanation of deterministic decisions and execution states.
    Non-authoritative: strictly explanatory.
    """
    try:
        return service.explain_transaction(transaction_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Transaction '{transaction_id}' not found")


@app.get("/api/v1/transactions/{transaction_id}/integrity-trace", response_model=IntegrityTrace)
async def get_transaction_integrity_trace(
    transaction_id: str,
    service: TransactionService = Depends(get_transaction_service),
) -> IntegrityTrace:
    """
    Integrity Trace & Fault Localization endpoint (I13).
    Deterministic 8-stage lifecycle evaluation, first-divergence detection,
    and structured fault localization.
    """
    try:
        return service.get_integrity_trace(transaction_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Transaction '{transaction_id}' not found")


@app.get("/api/v1/transactions/{transaction_id}/integrity-checkpoints", response_model=IntegrityCheckpointTimeline)
async def get_transaction_integrity_checkpoints(
    transaction_id: str,
    service: TransactionService = Depends(get_transaction_service),
) -> IntegrityCheckpointTimeline:
    """
    Integrity Checkpoints endpoint (I14).
    Deterministic 8-boundary lifecycle verification, last-valid boundary,
    first-invalid boundary, and cryptographic hash chain integrity.
    """
    try:
        return service.get_integrity_checkpoints(transaction_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Transaction '{transaction_id}' not found")


@app.get("/api/v1/transactions/{transaction_id}/integrity-sla", response_model=IntegritySLAMetricsReport)
async def get_transaction_integrity_sla(
    transaction_id: str,
    service: TransactionService = Depends(get_transaction_service),
) -> IntegritySLAMetricsReport:
    """
    Integrity SLA Metrics endpoint (I15).
    Deterministic SLA measurement covering detection latency, checkpoint coverage,
    trace completeness, UNKNOWN duration, and policy compliance.
    """
    try:
        return service.get_integrity_sla_metrics(transaction_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Transaction '{transaction_id}' not found")




@app.post("/api/v1/webhook/razorpay")
async def receive_razorpay_webhook(
    request: Request,
    x_razorpay_signature: Optional[str] = Header(None, alias="X-Razorpay-Signature"),
    provider: PaymentProvider = Depends(get_payment_provider),
):
    """
    Webhook ingestion endpoint for Razorpay asynchronous event delivery.
    Verifies cryptographic signature before ingestion.
    """
    if not x_razorpay_signature:
        raise HTTPException(status_code=400, detail="Missing X-Razorpay-Signature header")

    body_bytes = await request.body()
    body_str = body_bytes.decode("utf-8")

    try:
        event = provider.parse_webhook_payload(body=body_str, signature=x_razorpay_signature)
        return {
            "status": "acknowledged",
            "event_id": event.event_id,
            "event_type": event.event_type,
        }
    except PaymentSignatureError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid webhook signature: {exc}")
    except WebhookValidationError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid webhook payload: {exc}")


@app.post("/api/v1/replay", response_model=ReplayResult)
async def replay_transaction(
    snapshot: ReplaySnapshot,
) -> ReplayResult:
    """
    Deterministic transaction replay and audit endpoint (T13).
    Reconstructs what the system should have decided from recorded history.
    - Zero live network or provider calls.
    - Zero live AI calls.
    - Zero financial side effects.
    - Strictly deterministic MATCH / MISMATCH / INVALID_REPLAY verdict.
    """
    logger.info(
        "Initiating deterministic replay for transaction %s (replay_id=%s)",
        snapshot.transaction_id,
        snapshot.replay_id,
    )
    result = ReplayEngine.replay(snapshot)
    return result


@app.get("/api/v1/scenarios", response_model=List[ScenarioDefinition])
async def list_scenarios(
    category: Optional[ScenarioCategory] = None,
    service: ScenarioLabService = Depends(get_scenario_service),
) -> List[ScenarioDefinition]:
    """Lists canonical scenario definitions in the Scenario Lab (I11)."""
    return service.get_catalog(category=category)


@app.post("/api/v1/scenarios/{scenario_id}/run", response_model=ScenarioResult)
async def run_scenario_endpoint(
    scenario_id: str,
    service: ScenarioLabService = Depends(get_scenario_service),
) -> ScenarioResult:
    """Executes a single scenario deterministically against the authoritative pipeline (I11)."""
    try:
        return service.run_scenario(scenario_id)
    except (KeyError, ValueError):
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found")


@app.post("/api/v1/scenarios/run-all", response_model=ScenarioSuiteResult)
async def run_all_scenarios_endpoint(
    category: Optional[ScenarioCategory] = None,
    service: ScenarioLabService = Depends(get_scenario_service),
) -> ScenarioSuiteResult:
    """Runs all registered canonical scenarios and returns the suite result (I11)."""
    return service.run_all(category=category)


@app.get("/api/v1/certifications", response_model=List[GroundTruthDefinition])
async def list_certifications_endpoint(
    service: GroundTruthCertificationService = Depends(get_certification_service),
) -> List[GroundTruthDefinition]:
    """Lists canonical ground truth definitions for certification (I12)."""
    return service.list_ground_truths()


@app.post("/api/v1/certifications/{scenario_id}/run", response_model=CertificationResult)
async def run_certification_endpoint(
    scenario_id: str,
    service: GroundTruthCertificationService = Depends(get_certification_service),
) -> CertificationResult:
    """Certifies a scenario deterministically against its canonical ground truth (I12)."""
    try:
        return service.certify_scenario(scenario_id)
    except (KeyError, ValueError):
        raise HTTPException(status_code=404, detail=f"Scenario or ground truth for '{scenario_id}' not found")


@app.post("/api/v1/certifications/run-all", response_model=CertificationSuiteResult)
async def run_all_certifications_endpoint(
    service: GroundTruthCertificationService = Depends(get_certification_service),
) -> CertificationSuiteResult:
    """Runs all canonical scenario certifications and returns the suite result with matrix (I12)."""
    return service.certify_all()


# --- I22 Complete Hero Transaction Endpoints ---

class RunHeroTransactionRequest(BaseModel):
    """Payload to trigger a hero transaction journey run."""
    intent: Optional[IntentContract] = None
    simulate_mutation: bool = True
    reference_time: Optional[datetime] = None


def _default_hero_intent(ref_time: datetime) -> IntentContract:
    """Canonical hero purchase intent: 1TB external SSD under ₹8,000."""
    return IntentContract(
        intent_id=f"intent_hero_ssd_{int(ref_time.timestamp())}",
        issued_by="buyer_agent_alice",
        items=[
            IntentItem(
                item_id="item_ssd_1",
                sku="SKU-SSD-1TB",
                name="1TB External SSD",
                quantity=1,
                unit_price=Money(amount=750000, currency="INR"),
                total_price=Money(amount=750000, currency="INR"),
            )
        ],
        max_total=Money(amount=800000, currency="INR"),
        allowed_substitutions=["SKU-SSD-1TB-PRO"],
        issued_at=ref_time,
        expires_at=ref_time + timedelta(hours=4),
    )


@app.post("/api/v1/hero-transaction/run", response_model=HeroTransactionRecord)
async def run_hero_transaction_endpoint(
    request: Optional[RunHeroTransactionRequest] = None,
    orchestrator: HeroTransactionOrchestrator = Depends(get_hero_orchestrator),
) -> HeroTransactionRecord:
    """
    Executes the complete, end-to-end TarkaRaksha Hero Transaction (I22):
    Detect -> Prove -> Repair -> Revalidate -> Execute -> Verify.
    Composes Buyer Agent, Merchant Agent, TIX, T04 Integrity, T07 MRDP, I8 Binding,
    I9 Safety Control, Trace, Checkpoints, SLA, Replay, and Explanation.
    """
    req = request or RunHeroTransactionRequest()
    ref_time = req.reference_time or datetime.now(timezone.utc)
    intent = req.intent or _default_hero_intent(ref_time)
    try:
        return orchestrator.execute_hero_journey(
            intent=intent,
            reference_time=ref_time,
            simulate_mutation=req.simulate_mutation,
        )
    except Exception as e:
        logger.error(f"Hero transaction execution failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/hero-transaction/{hero_transaction_id}", response_model=HeroTransactionRecord)
async def get_hero_transaction_endpoint(
    hero_transaction_id: str,
    orchestrator: HeroTransactionOrchestrator = Depends(get_hero_orchestrator),
) -> HeroTransactionRecord:
    """Retrieves a previously executed hero transaction record (I22)."""
    record = orchestrator.get_hero_record(hero_transaction_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Hero transaction '{hero_transaction_id}' not found")
    return record


