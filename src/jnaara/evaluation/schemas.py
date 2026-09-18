from datetime import datetime, timezone
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

GroundTruthLabel = Literal["CONTRADICTION", "NO_CONTRADICTION", "UNCERTAIN"]
PredictedLabel = Literal["CONTRADICTION", "NO_CONTRADICTION", "UNCERTAIN"]

FailureCategory = Literal[
    "semantic_misunderstanding",
    "temporal_reasoning_error",
    "negation_error",
    "entity_mismatch",
    "ambiguity",
    "numeric_reasoning",
    "context_limitation",
    "llm_classification_error",
    "retrieval_error",
    "other",
]


class EvaluationExample(BaseModel):
    """A benchmark example consisting of a pair of memories/facts to evaluate."""

    id: str
    category: str
    entity: str
    memory_a: str
    memory_b: str
    ground_truth: GroundTruthLabel
    difficulty: Literal["easy", "medium", "hard", "adversarial"] = "medium"
    memory_a_timestamp: str | None = None
    memory_b_timestamp: str | None = None
    source_a: str = "Primary Source A"
    source_b: str = "Secondary Source B"
    source_b_reliability: Literal["high", "medium", "low"] = "high"
    expected_failure_mode: FailureCategory | None = None
    description: str = ""

    model_config = ConfigDict(extra="ignore")


class FailureRecord(BaseModel):
    """Detailed diagnosis of a prediction failure (FP, FN, or misclassified uncertainty)."""

    example_id: str
    category: str
    memory_a: str
    memory_b: str
    ground_truth: GroundTruthLabel
    predicted: PredictedLabel
    confidence: float = 0.0
    failure_category: FailureCategory
    explanation: str
    model_output_snippet: str | None = None

    model_config = ConfigDict(extra="ignore")


class ExampleEvaluationResult(BaseModel):
    """Result of running a single evaluation example through the belief engine."""

    example_id: str
    category: str
    ground_truth: GroundTruthLabel
    predicted: PredictedLabel
    confidence: float
    is_correct: bool
    action_taken: str
    reason: str
    tier: str
    failure_record: FailureRecord | None = None

    model_config = ConfigDict(extra="ignore")


class ConfusionMatrix(BaseModel):
    """Binary/ternary confusion counts."""

    tp: int = 0
    tn: int = 0
    fp: int = 0
    fn: int = 0
    uncertain_as_contradiction: int = 0
    uncertain_as_no_contradiction: int = 0
    contradiction_as_uncertain: int = 0
    no_contradiction_as_uncertain: int = 0
    correct_uncertain: int = 0
    total: int = 0

    model_config = ConfigDict(extra="ignore")


class EvaluationMetrics(BaseModel):
    """Computed evaluation metrics following standard statistical definitions."""

    total_examples: int = 0
    evaluated_binary: int = 0
    tp: int = 0
    tn: int = 0
    fp: int = 0
    fn: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    accuracy: float = 0.0
    specificity: float = 0.0
    abstention_count: int = 0
    abstention_accuracy: float = 0.0
    confusion_matrix: ConfusionMatrix = Field(default_factory=ConfusionMatrix)
    category_breakdown: dict[str, dict[str, Any]] = Field(default_factory=dict)
    failure_category_breakdown: dict[str, int] = Field(default_factory=dict)
    failures: list[FailureRecord] = Field(default_factory=list)

    model_config = ConfigDict(extra="ignore")


class EvaluationReportPayload(BaseModel):
    """Complete serialized payload of an evaluation run."""

    evaluation_timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    dataset_name: str
    split: str
    provider: str
    metrics: EvaluationMetrics
    failures: list[FailureRecord]
    results: list[ExampleEvaluationResult]

    model_config = ConfigDict(extra="ignore")
