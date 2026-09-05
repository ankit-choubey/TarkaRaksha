"""
Replay Engine module exports for TarkaRaksha (T13).
"""
from backend.app.services.replay.contracts import (
    InvalidReplayInputError,
    REPLAY_PROTOCOL_VERSION,
    RULES_VERSION_DEFAULT,
    ReplayAmbiguityError,
    ReplayDiscrepancy,
    ReplayError,
    ReplayResult,
    ReplaySnapshot,
    ReplayVerdict,
)
from backend.app.services.replay.engine import ReplayEngine
from backend.app.services.replay.ordering import (
    order_canonical_events,
    order_evidence_records,
)
from backend.app.services.replay.reconstructor import (
    StateReplayOutcome,
    replay_state_transitions,
)

from backend.app.services.replay.governance_replay import (
    GovernedReplayResult,
    GovernedReplayService,
)

from backend.app.services.replay.counterfactual import (
    CounterfactualComparison,
    CounterfactualMutationType,
    CounterfactualReplayAnalysisService,
)

__all__ = [
    "REPLAY_PROTOCOL_VERSION",
    "RULES_VERSION_DEFAULT",
    "ReplayError",
    "InvalidReplayInputError",
    "ReplayAmbiguityError",
    "ReplayVerdict",
    "ReplayDiscrepancy",
    "ReplaySnapshot",
    "ReplayResult",
    "ReplayEngine",
    "order_canonical_events",
    "order_evidence_records",
    "StateReplayOutcome",
    "replay_state_transitions",
    "GovernedReplayResult",
    "GovernedReplayService",
    "CounterfactualComparison",
    "CounterfactualMutationType",
    "CounterfactualReplayAnalysisService",
]
