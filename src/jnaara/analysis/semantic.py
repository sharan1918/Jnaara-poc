import logging
from jnaara.analysis.validator import AnalysisValidator, ValidatedAnalysis, ValidatedInferenceResult
from jnaara.llm.provider import LLMProvider
from jnaara.models.domain import (
    Belief,
    Claim,
    DualAnalysis,
    Fact,
    FactAnalysis,
    InferenceConflictResult,
)

logger = logging.getLogger(__name__)


class SemanticAnalyzer:
    """Semantic analyzer orchestrating LLM calls and output validation."""

    def __init__(
        self,
        primary: LLMProvider,
        secondary: LLMProvider,
        validator: AnalysisValidator | None = None,
    ):
        self.primary = primary
        self.secondary = secondary
        self.validator = validator or AnalysisValidator()

    def extract_claims(self, fact: Fact) -> FactAnalysis:
        """Extract structured claims from a raw fact.
        
        Uses primary provider, falls back to secondary provider if primary fails.
        Validates all output via AnalysisValidator before returning.
        """
        analysis: FactAnalysis | None = None
        errors: list[str] = []

        # 1. Try primary provider
        primary_name = type(self.primary).__name__
        logger.info(
            "[SemanticAnalyzer] Requesting claim extraction for fact '%s' from primary provider (%s)...",
            fact.id,
            primary_name,
        )
        try:
            raw_analysis = self.primary.extract_claims(fact)
            val = self.validator.validate_fact_analysis(raw_analysis, fact)
            if val.is_valid:
                logger.info(
                    "[SemanticAnalyzer] Primary (%s) successfully extracted %d claim(s) for fact '%s'",
                    primary_name,
                    len(val.analysis.claims),
                    fact.id,
                )
                return val.analysis
            logger.warning(
                "[SemanticAnalyzer] Primary (%s) output failed validation for fact '%s': %s. Falling back to secondary...",
                primary_name,
                fact.id,
                val.errors,
            )
            errors.extend(val.errors)
        except Exception as exc:
            logger.warning(
                "[SemanticAnalyzer] Primary (%s) extraction failed for fact '%s': %s. Falling back to secondary...",
                primary_name,
                fact.id,
                exc,
            )
            errors.append(str(exc))

        # 2. Try secondary provider fallback
        secondary_name = type(self.secondary).__name__
        logger.info(
            "[SemanticAnalyzer] Falling back to secondary provider (%s) for fact '%s'...",
            secondary_name,
            fact.id,
        )
        try:
            raw_analysis = self.secondary.extract_claims(fact)
            val = self.validator.validate_fact_analysis(raw_analysis, fact)
            if val.is_valid:
                logger.info(
                    "[SemanticAnalyzer] Secondary (%s) successfully extracted %d claim(s) for fact '%s'",
                    secondary_name,
                    len(val.analysis.claims),
                    fact.id,
                )
                return val.analysis
            logger.error(
                "[SemanticAnalyzer] Secondary (%s) produced invalid analysis for fact '%s': %s",
                secondary_name,
                fact.id,
                val.errors,
            )
            # Use the secondary analysis with best effort
            return val.analysis
        except Exception as exc:
            logger.error(
                "[SemanticAnalyzer] Both LLM providers failed for fact '%s': %s",
                fact.id,
                exc,
            )

        # 3. Graceful fallback if both fail
        fallback_claim = Claim(
            entity="Unknown Entity",
            attribute="statement",
            value=fact.content[:200],
            normalized_value=None,
            unit=None,
            temporal_scope=None,
            claim_type="qualitative",
            confidence=0.5,
            source_fact_id=fact.id,
        )
        return FactAnalysis(
            fact_id=fact.id,
            claims=[fallback_claim],
            entities_mentioned=[],
            analysis_notes=f"Fallback generated due to provider errors: {errors}",
        )

    def analyze_inference_conflicts(
        self,
        claim: Claim,
        existing_beliefs: list[Belief],
        use_dual_analysis: bool = False,
    ) -> InferenceConflictResult | DualAnalysis:
        """Analyze inference-based conflicts between an incoming claim and held beliefs.
        
        If use_dual_analysis is requested, both providers are consulted to obtain
        an independent second opinion.
        """
        logger.info(
            "[SemanticAnalyzer] Checking inference conflicts for claim '%s' (%s - %s) against %d belief(s) (dual=%s)...",
            claim.id,
            claim.entity,
            claim.attribute,
            len(existing_beliefs),
            use_dual_analysis,
        )
        primary_result: InferenceConflictResult | None = None
        primary_errors: list[str] = []

        try:
            res = self.primary.analyze_inference_conflict(claim, existing_beliefs)
            val = self.validator.validate_inference_result(res, claim, existing_beliefs)
            primary_result = val.result
        except Exception as exc:
            logger.warning("Primary inference analysis failed for claim %s: %s", claim.id, exc)
            primary_errors.append(str(exc))

        # Single provider mode (when dual analysis not requested)
        if not use_dual_analysis:
            if primary_result is not None:
                logger.info(
                    "[SemanticAnalyzer] Single-mode inference analysis complete for claim '%s': is_conflict=%s",
                    claim.id,
                    primary_result.is_conflict,
                )
                return primary_result
            # Primary failed, fallback to secondary
            try:
                res = self.secondary.analyze_inference_conflict(claim, existing_beliefs)
                val = self.validator.validate_inference_result(res, claim, existing_beliefs)
                logger.info(
                    "[SemanticAnalyzer] Fallback inference analysis complete for claim '%s': is_conflict=%s",
                    claim.id,
                    val.result.is_conflict,
                )
                return val.result
            except Exception as exc:
                logger.error("Both providers failed inference analysis for claim %s: %s", claim.id, exc)
                return InferenceConflictResult(
                    is_conflict=False,
                    explanation=f"Inference analysis failed across both providers: {exc}",
                    confidence=0.0,
                )

        # Dual analysis mode: consult both
        secondary_result: InferenceConflictResult | None = None
        try:
            res = self.secondary.analyze_inference_conflict(claim, existing_beliefs)
            val = self.validator.validate_inference_result(res, claim, existing_beliefs)
            secondary_result = val.result
        except Exception as exc:
            logger.warning("Secondary provider failed dual inference analysis for claim %s: %s", claim.id, exc)

        if primary_result is None and secondary_result is not None:
            return secondary_result
        if primary_result is not None and secondary_result is None:
            return primary_result
        if primary_result is None and secondary_result is None:
            return InferenceConflictResult(
                is_conflict=False,
                explanation="Both providers failed in dual analysis mode.",
                confidence=0.0,
            )

        # Both succeeded: compare agreement
        agreement = primary_result.is_conflict == secondary_result.is_conflict  # type: ignore
        return DualAnalysis(
            groq_analysis=primary_result,  # type: ignore
            gemini_analysis=secondary_result,
            agreement=agreement,
            combined_notes=f"Primary and Secondary agreement: {agreement}",
        )
