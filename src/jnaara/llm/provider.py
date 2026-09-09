from abc import ABC, abstractmethod
from jnaara.models.domain import Belief, Claim, Fact, FactAnalysis, InferenceConflictResult


class LLMProvider(ABC):
    """Abstract interface for LLM providers.
    
    LangChain is confined entirely behind this interface.
    The core application never imports or depends directly on ChatGroq or ChatGoogleGenerativeAI.
    """

    @abstractmethod
    def extract_claims(self, fact: Fact) -> FactAnalysis:
        """Extract structured claims from a raw fact."""
        ...

    @abstractmethod
    def analyze_inference_conflict(
        self, claim: Claim, existing_beliefs: list[Belief]
    ) -> InferenceConflictResult:
        """Analyze whether an incoming claim contradicts existing beliefs via logical inference."""
        ...

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return the name identifier of the provider (e.g., 'groq', 'gemini', 'mock')."""
        ...
