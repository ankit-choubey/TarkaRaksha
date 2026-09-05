"""
FastAPI Application and API Endpoints for TarkaRaksha (T10).
Exposes the first complete real transaction slice:
- Protected Order Creation
- Server-Side Payment Verification & Integrity Evaluation
- Webhook Ingestion
- Real-Time Control Plane State Inspection
"""
from datetime import datetime, timezone
import logging
from typing import Any, Dict, Optional
from fastapi import FastAPI, Depends, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.core.config import settings
from backend.app.domain.models import (
    CreateTransactionRequest,
    CreateTransactionResponse,
    CompleteTransactionRequest,
    CompleteTransactionResponse,
    RecoverTransactionRequest,
    ResolveTransactionRequest,
    IntentContract,
    TransactionState,
)
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
