from jnaara.conflict.strategies.base import ResolutionStrategy
from jnaara.conflict.strategies.corroboration import CorroborationWeightedStrategy
from jnaara.conflict.strategies.recency import RecencyWeightedStrategy
from jnaara.models.domain import Conflict, Resolution, ResolutionContext


class ConflictResolver:
    """Orchestrator for pluggable deterministic conflict resolution strategies."""

    def __init__(self, default_strategy: str = "recency"):
        self._strategies: dict[str, ResolutionStrategy] = {
            "recency": RecencyWeightedStrategy(),
            "corroboration": CorroborationWeightedStrategy(),
        }
        self.switch_strategy(default_strategy)

    def resolve(self, conflict: Conflict, context: ResolutionContext) -> Resolution:
        """Resolve a conflict using the currently active strategy."""
        strategy = self._strategies[self._active_strategy_name]
        return strategy.resolve(conflict, context)

    def switch_strategy(self, name: str) -> None:
        """Switch active resolution strategy by name."""
        clean_name = name.lower().strip()
        if clean_name not in self._strategies:
            raise ValueError(
                f"Unknown strategy '{name}'. Available strategies: {list(self._strategies.keys())}"
            )
        self._active_strategy_name = clean_name

    @property
    def active_strategy(self) -> str:
        """Return the name of the currently active strategy."""
        return self._active_strategy_name

    def list_strategies(self) -> list[str]:
        """Return names of all available strategies."""
        return list(self._strategies.keys())
