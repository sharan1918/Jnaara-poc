import json
import logging
from pydantic import SecretStr
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from jnaara.llm.provider import LLMProvider
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
    """Primary LLM provider using Groq and LangChain's ChatGroq integration."""

    def __init__(self, api_key: SecretStr, model: str):
        key_val = api_key.get_secret_value() if isinstance(api_key, SecretStr) else str(api_key)
        self.model = model
        self._llm = ChatGroq(
            model=model,
            api_key=key_val,
            temperature=0.0,
        )

    def extract_claims(self, fact: Fact) -> FactAnalysis:
        logger.info("[Groq] Invoking ChatGroq (%s) for claim extraction on fact '%s'...", self.model, fact.id)
        structured_llm = self._llm.with_structured_output(FactAnalysis)
        system_prompt = (
            "You are an expert fact extractor. Extract ALL factual claims from the given fact "
            "into structured data. For each claim, identify the entity, attribute, stated value, "
            "normalized numeric value (if quantitative, e.g., '$480M' -> '480000000'), unit, "
            "temporal scope, claim_type (quantitative, qualitative, relational, event), and confidence (0.0 to 1.0). "
            "Ensure source_fact_id matches the fact ID."
        )
        user_prompt = (
            f"Fact ID: {fact.id}\n"
            f"Timestamp: {fact.timestamp.isoformat()}\n"
            f"Source: {fact.source} (Reliability: {fact.source_reliability})\n"
            f"Content: {fact.content}\n"
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

    def analyze_inference_conflict(
        self, claim: Claim, existing_beliefs: list[Belief]
    ) -> InferenceConflictResult:
        structured_llm = self._llm.with_structured_output(InferenceConflictResult)
        system_prompt = (
            "You are a semantic contradiction analyzer. Given an incoming claim and existing held beliefs, "
            "determine whether there is a logical, indirect, cross-entity, or inference-based contradiction. "
            "Do not flag obvious direct quantitative differences (e.g. $480M vs $412M for the same attribute), "
            "as those are handled deterministically. Focus on nuanced logical incompatibilities across multiple statements.\n"
            "If a contradiction exists, set is_conflict=True, specify conflict_type ('inference' or 'source_disagreement'), "
            "severity ('high', 'medium', or 'low'), list related_belief_ids, and explain the logical conflict clearly."
        )
        beliefs_text = "\n".join(
            f"- Belief ID: {b.id} | Entity: {b.entity} | Attribute: {b.attribute} | Value: {b.value} | Confidence: {b.confidence}"
            for b in existing_beliefs
        )
        user_prompt = (
            f"Incoming Claim:\n"
            f"ID: {claim.id} | Entity: {claim.entity} | Attribute: {claim.attribute} | Value: {claim.value} | Temporal Scope: {claim.temporal_scope}\n\n"
            f"Existing Beliefs for comparison:\n{beliefs_text}\n"
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

