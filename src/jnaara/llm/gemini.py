import logging
from pydantic import SecretStr
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from jnaara.analysis.prompts import (
    CLAIM_EXTRACTION_SYSTEM_PROMPT,
    CLAIM_EXTRACTION_USER_PROMPT,
    INFERENCE_ANALYSIS_SYSTEM_PROMPT,
    INFERENCE_ANALYSIS_USER_PROMPT,
)
from jnaara.llm.provider import LLMProvider
from jnaara.llm.rate_limiter import ProviderRateLimiter, rate_limited
from jnaara.models.domain import Belief, Claim, Fact, FactAnalysis, InferenceConflictResult

logger = logging.getLogger("jnaara.llm.gemini")


class GeminiProvider(LLMProvider):
    """Secondary LLM provider using Google Gemini and LangChain's ChatGoogleGenerativeAI with rate limiting."""

    def __init__(
        self,
        api_key: SecretStr,
        model: str,
        rate_limiter: ProviderRateLimiter | None = None,
        max_retries: int = 5,
        initial_delay: float = 3.0,
        backoff_factor: float = 2.0,
    ):
        key_val = api_key.get_secret_value() if isinstance(api_key, SecretStr) else str(api_key)
        self.model = model
        self.rate_limiter = rate_limiter or ProviderRateLimiter(min_interval_seconds=4.0)
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.backoff_factor = backoff_factor
        self._llm = ChatGoogleGenerativeAI(
            model=model,
            google_api_key=key_val,
            temperature=0.0,
            max_retries=1,  # Let our custom rate limiter handle intelligent retry logic
        )

    @rate_limited("gemini")
    def extract_claims(self, fact: Fact) -> FactAnalysis:
        logger.info("[Gemini] Invoking ChatGoogleGenerativeAI (%s) for claim extraction on fact '%s'...", self.model, fact.id)
        structured_llm = self._llm.with_structured_output(FactAnalysis)
        system_prompt = CLAIM_EXTRACTION_SYSTEM_PROMPT
        user_prompt = CLAIM_EXTRACTION_USER_PROMPT.format(
            fact_id=fact.id,
            timestamp=fact.timestamp.isoformat(),
            source=fact.source,
            reliability=fact.source_reliability,
            content=fact.content,
        )
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
        result = structured_llm.invoke(messages)
        if isinstance(result, dict):
            parsed = FactAnalysis.model_validate(result)
        else:
            parsed = result  # type: ignore
        logger.info("[Gemini] Extracted %d claim(s) for fact '%s'", len(parsed.claims), fact.id)
        return parsed

    @rate_limited("gemini")
    def analyze_inference_conflict(
        self, claim: Claim, existing_beliefs: list[Belief]
    ) -> InferenceConflictResult:
        structured_llm = self._llm.with_structured_output(InferenceConflictResult)
        system_prompt = INFERENCE_ANALYSIS_SYSTEM_PROMPT
        beliefs_text = "\n".join(
            f"- Belief ID: {b.id} | Entity: {b.entity} | Attribute: {b.attribute} | Value: {b.value} | Confidence: {b.confidence}"
            for b in existing_beliefs
        )
        user_prompt = INFERENCE_ANALYSIS_USER_PROMPT.format(
            entity=claim.entity,
            attribute=claim.attribute,
            value=claim.value,
            normalized_value=claim.normalized_value or "N/A",
            unit=claim.unit or "N/A",
            temporal_scope=claim.temporal_scope or "N/A",
            claim_type=claim.claim_type,
            beliefs_summary=beliefs_text or "None",
        )
        logger.info(
            "[Gemini] Analyzing inference conflict for claim '%s' (%s - %s) against %d existing belief(s)...",
            claim.id,
            claim.entity,
            claim.attribute,
            len(existing_beliefs),
        )
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
        result = structured_llm.invoke(messages)
        if isinstance(result, dict):
            parsed_res = InferenceConflictResult.model_validate(result)
        else:
            parsed_res = result  # type: ignore
        logger.info(
            "[Gemini] Inference analysis completed for claim '%s': conflict=%s, type=%s, severity=%s",
            claim.id,
            parsed_res.is_conflict,
            parsed_res.conflict_type,
            parsed_res.severity,
        )
        return parsed_res

    def get_provider_name(self) -> str:
        return "gemini"
