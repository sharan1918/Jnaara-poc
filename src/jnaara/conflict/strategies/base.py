from abc import ABC, abstractmethod
from jnaara.models.domain import Conflict, Resolution, ResolutionContext


class ResolutionStrategy(ABC):
    """Abstract base class for conflict resolution strategies.
    
    All strategies are completely deterministic and rely on evidence metrics.
    Strategies NEVER invoke LLMs.
    """

    @abstractmethod
    def resolve(self, conflict: Conflict, context: ResolutionContext) -> Resolution:
        """Resolve a conflict given the full evidence context."""
        ...
