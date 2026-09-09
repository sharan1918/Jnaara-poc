from dataclasses import dataclass, field
from jnaara.models.domain import (
    Belief,
    Claim,
    Fact,
    FactAnalysis,
    InferenceConflictResult,
)


@dataclass
class ValidatedAnalysis:
    """Container for validated FactAnalysis with validation error messages."""

    analysis: FactAnalysis
    errors: list[str] = field(default_factory=list)
    is_valid: bool = True


@dataclass
class ValidatedInferenceResult:
    """Container for validated InferenceConflictResult with validation error messages."""

    result: InferenceConflictResult
    errors: list[str] = field(default_factory=list)
    is_valid: bool = True


class AnalysisValidator:
    """Validates LLM output before it reaches the conflict engine.
    
    A valid JSON response from an LLM is not automatically a valid business input.
    """

    def validate_fact_analysis(self, analysis: FactAnalysis, fact: Fact) -> ValidatedAnalysis:
        """Validate claim extraction result against business integrity rules."""
        errors: list[str] = []

        if analysis.fact_id != fact.id:
            errors.append(f"FactAnalysis fact_id '{analysis.fact_id}' does not match expected '{fact.id}'")

        if not analysis.claims:
            errors.append(f"Fact '{fact.id}' produced 0 claims")

        for i, claim in enumerate(analysis.claims):
            # source_fact_id must match fact.id
            if claim.source_fact_id != fact.id:
                errors.append(
                    f"Claim[{i}] references source_fact_id '{claim.source_fact_id}' instead of '{fact.id}'"
                )

            # Confidence bounds
            if not 0.0 <= claim.confidence <= 1.0:
                errors.append(f"Claim[{i}] confidence {claim.confidence} out of [0.0, 1.0] bounds")

            # Entity must not be empty
            if not claim.entity or not claim.entity.strip():
                errors.append(f"Claim[{i}] entity is empty")

            # Attribute must not be empty
            if not claim.attribute or not claim.attribute.strip():
                errors.append(f"Claim[{i}] attribute is empty")

            # Quantitative claim checks
            if claim.claim_type == "quantitative":
                if claim.normalized_value is None or not claim.normalized_value.strip():
                    errors.append(
                        f"Quantitative claim '{claim.attribute}' value '{claim.value}' missing normalized_value"
                    )

        return ValidatedAnalysis(
            analysis=analysis,
            errors=errors,
            is_valid=len(errors) == 0,
        )

    def validate_inference_result(
        self,
        result: InferenceConflictResult,
        claim: Claim,
        beliefs: list[Belief],
    ) -> ValidatedInferenceResult:
        """Validate a Tier 2 inference contradiction analysis."""
        errors: list[str] = []

        # Confidence bounds
        if not 0.0 <= result.confidence <= 1.0:
            errors.append(f"Inference result confidence {result.confidence} out of [0.0, 1.0] bounds")

        # Referenced beliefs must exist in candidate set if specified
        known_ids = {b.id for b in beliefs}
        for bid in result.related_belief_ids:
            if known_ids and bid not in known_ids:
                errors.append(f"Referenced belief ID '{bid}' is not in candidate beliefs")

        # If conflict flagged, must have conflict_type and severity
        if result.is_conflict:
            if not result.conflict_type:
                errors.append("is_conflict=True but conflict_type is missing")
            if not result.severity:
                errors.append("is_conflict=True but severity is missing")
            if not result.explanation or not result.explanation.strip():
                errors.append("is_conflict=True but explanation is empty")

        return ValidatedInferenceResult(
            result=result,
            errors=errors,
            is_valid=len(errors) == 0,
        )
