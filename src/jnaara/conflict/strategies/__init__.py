"""Conflict resolution strategy package."""

from jnaara.conflict.strategies.base import ResolutionStrategy
from jnaara.conflict.strategies.corroboration import CorroborationWeightedStrategy
from jnaara.conflict.strategies.recency import RecencyWeightedStrategy

__all__ = ["ResolutionStrategy", "RecencyWeightedStrategy", "CorroborationWeightedStrategy"]
