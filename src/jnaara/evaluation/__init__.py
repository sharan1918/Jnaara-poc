"""Evaluation and reporting utilities for the Jnaara belief engine."""

from jnaara.evaluation.dataset import EvaluationDatasetLoader
from jnaara.evaluation.evaluator import EvaluatorEngine
from jnaara.evaluation.reporter import (
    generate_markdown_report,
    save_evaluation_report,
    save_markdown_report,
)
from jnaara.evaluation.schemas import (
    ConfusionMatrix,
    EvaluationExample,
    EvaluationMetrics,
    EvaluationReportPayload,
    ExampleEvaluationResult,
    FailureCategory,
    FailureRecord,
)

__all__ = [
    "ConfusionMatrix",
    "EvaluationDatasetLoader",
    "EvaluationExample",
    "EvaluationMetrics",
    "EvaluationReportPayload",
    "EvaluatorEngine",
    "ExampleEvaluationResult",
    "FailureCategory",
    "FailureRecord",
    "generate_markdown_report",
    "save_evaluation_report",
    "save_markdown_report",
]
