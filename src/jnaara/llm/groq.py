import json
import logging
from pydantic import SecretStr
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from jnaara.analysis.prompts import (
    CLAIM_EXTRACTION_SYSTEM_PROMPT,
    CLAIM_EXTRACTION_USER_PROMPT,
    INFERENCE_ANALYSIS_SYSTEM_PROMPT,
    INFERENCE_ANALYSIS_USER_PROMPT,
)
from jnaara.llm.provider import LLMProvider
from jnaara.llm.rate_limiter import ProviderRateLimiter, rate_limited
from jnaara.models.domain import Belief, Claim, Fact, FactAnalysis, InferenceConflictResult

logger = logging.getLogger("jnaara.llm.groq")


def _recover_failed_generation(exc: Exception) -> dict | None:
    """Attempt to recover valid JSON payload when Groq returns tool_use_failed."""
    exc_str = str(exc)
    marker = "'failed_generation': '"
    idx = exc_str.find(marker)
    if idx != -1:
        sub = exc_str[idx + len(marker) :]
        end_idx = sub.rfind("'")
        if end_idx != -1:
            try:
                raw = sub[:end_idx]
                unescaped = raw.encode("utf-8").decode("unicode_escape")
                return json.loads(unescaped)
            except Exception:
                pass
    return None


class GroqProvider(LLMProvider):
    """Primary LLM provider using Groq and LangChain's ChatGroq integration with rate limiting."""

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
        self.rate_limiter = rate_limiter or ProviderRateLimiter(min_interval_seconds=2.0)
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.backoff_factor = backoff_factor
        self._llm = ChatGroq(
            model=model,
            api_key=key_val,
            temperature=0.0,
            max_retries=1,  # Let our custom rate limiter handle intelligent retry logic
        )

    @rate_limited("groq")
    def extract_claims(self, fact: Fact) -> FactAnalysis:
        logger.info("[Groq] Invoking ChatGroq (%s) for claim extraction on fact '%s'...", self.model, fact.id)
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
        try:
            result = structured_llm.invoke(messages)
        except Exception as exc:
            recovered = _recover_failed_generation(exc)
            if recovered:
                logger.info("[Groq] Successfully recovered claim extraction from failed_generation JSON")
                result = recovered
            else:
                raise

        if isinstance(result, dict):
            parsed = FactAnalysis.model_validate(result)
        else:
            parsed = result  # type: ignore
        logger.info("[Groq] Extracted %d claim(s) for fact '%s'", len(parsed.claims), fact.id)
        return parsed

    @rate_limited("groq")
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
            "[Groq] Analyzing inference conflict for claim '%s' (%s - %s) against %d existing belief(s)...",
            claim.id,
            claim.entity,
            claim.attribute,
            len(existing_beliefs),
        )
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
        try:
            result = structured_llm.invoke(messages)
        except Exception as exc:
            recovered = _recover_failed_generation(exc)
            if recovered:
                logger.info("[Groq] Successfully recovered inference conflict from failed_generation JSON")
                result = recovered
            else:
                raise

        if isinstance(result, dict):
            parsed_res = InferenceConflictResult.model_validate(result)
        else:
            parsed_res = result  # type: ignore
        logger.info(
            "[Groq] Inference analysis completed for claim '%s': conflict=%s, type=%s, severity=%s",
            claim.id,
            parsed_res.is_conflict,
            parsed_res.conflict_type,
            parsed_res.severity,
        )
        return parsed_res

    def get_provider_name(self) -> str:
        return "groq"
