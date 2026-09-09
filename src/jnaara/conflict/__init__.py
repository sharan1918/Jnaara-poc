"""Conflict detection and resolution subsystem."""

from jnaara.conflict.detector import ConflictDetector
from jnaara.conflict.resolver import ConflictResolver
from jnaara.conflict.strategies import (
    CorroborationWeightedStrategy,
    RecencyWeightedStrategy,
    ResolutionStrategy,
)

__all__ = [
    "ConflictDetector",
    "ConflictResolver",
    "ResolutionStrategy",
    "RecencyWeightedStrategy",
    "CorroborationWeightedStrategy",
]
