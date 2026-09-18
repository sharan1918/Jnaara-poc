from datetime import datetime, timezone
import logging
from typing import Any, Callable

from jnaara.analysis.semantic import SemanticAnalyzer
from jnaara.analysis.validator import AnalysisValidator
from jnaara.belief.manager import BeliefManager
from jnaara.conflict.detector import ConflictDetector
from jnaara.conflict.resolver import ConflictResolver
from jnaara.db.engine import get_db_engine, get_session_factory, init_db
from jnaara.db.repository import Repository
from jnaara.evaluation.schemas import (
    ConfusionMatrix,
    EvaluationExample,
    EvaluationMetrics,
    EvaluationReportPayload,
    ExampleEvaluationResult,
    FailureCategory,
    FailureRecord,
    PredictedLabel,
)
from jnaara.llm.mock import MockLLMProvider
from jnaara.llm.provider import LLMProvider
from jnaara.models.domain import Fact

logger = logging.getLogger("jnaara.evaluation.evaluator")


def _diagnose_failure_category(
    example: EvaluationExample,
    predicted: PredictedLabel,
    action_taken: str,
) -> FailureCategory:
    """Classify why the engine produced a prediction mismatch."""
    if example.expected_failure_mode:
        return example.expected_failure_mode

    cat = example.category.lower()
    if "temporal" in cat:
        return "temporal_reasoning_error"
    if "negation" in cat or "polarity" in cat:
        return "negation_error"
    if "numeric" in cat:
        return "numeric_reasoning"
    if "ambiguous" in cat or "abstention" in cat:
        return "ambiguity"
    if "location" in cat or "preference" in cat:
        return "semantic_misunderstanding"
    if "adversarial" in cat:
        return "llm_classification_error"
    if "entity" in cat:
        return "entity_mismatch"
    if "multi_memory" in cat or "context" in cat:
        return "context_limitation"

    if predicted == "CONTRADICTION" and example.ground_truth == "NO_CONTRADICTION":
        return "semantic_misunderstanding"
    if predicted == "NO_CONTRADICTION" and example.ground_truth == "CONTRADICTION":
        return "llm_classification_error"

    return "other"


class EvaluatorEngine:
    """Independent evaluation runner evaluating belief and contradiction decisions."""

    def __init__(
        self,
        primary_provider_factory: Callable[[], LLMProvider] | None = None,
        secondary_provider_factory: Callable[[], LLMProvider] | None = None,
    ):
        self.primary_factory = primary_provider_factory or (
            lambda: MockLLMProvider("eval-primary")
        )
        self.secondary_factory = secondary_provider_factory or (
            lambda: MockLLMProvider("eval-secondary")
        )

    def _create_isolated_pipeline(self):
        """Create an isolated, in-memory engine pipeline for each test example."""
        engine = get_db_engine(":memory:")
        init_db(engine)
        session = get_session_factory(engine)()
        repo = Repository(session)

        primary = self.primary_factory()
        secondary = self.secondary_factory()
        analyzer = SemanticAnalyzer(primary, secondary, AnalysisValidator())
        detector = ConflictDetector(repo, analyzer)
        resolver = ConflictResolver("recency")
        manager = BeliefManager(repo, analyzer, detector, resolver)

        return repo, manager, session

    def evaluate_example(self, example: EvaluationExample) -> ExampleEvaluationResult:
        """Run a single evaluation example through an isolated belief state."""
        repo, manager, session = self._create_isolated_pipeline()

        try:
            # 1. Ingest Memory A
            ts_a = datetime(2025, 1, 10, 9, 0, tzinfo=timezone.utc)
            content_a = f"[{example.entity}] {example.memory_a}" if example.entity.lower() not in example.memory_a.lower() else example.memory_a
            fact_a = Fact(
                id=f"{example.id}_A",
                timestamp=ts_a,
                source=example.source_a,
                source_reliability="high",
                content=content_a,
            )
            res_a = manager.process_fact(fact_a)

            # 2. Ingest Memory B
            ts_b = datetime(2025, 1, 20, 14, 0, tzinfo=timezone.utc)
            content_b = f"[{example.entity}] {example.memory_b}" if example.entity.lower() not in example.memory_b.lower() else example.memory_b
            fact_b = Fact(
                id=f"{example.id}_B",
                timestamp=ts_b,
                source=example.source_b,
                source_reliability=example.source_b_reliability,
                content=content_b,
            )
            res_b = manager.process_fact(fact_b)

            # 3. Determine system prediction from decisions & conflicts
            conflicts = [c for _, c in res_b.results if c is not None]
            decisions = [d for d, _ in res_b.results]

            actions = [d.action for d in decisions]
            tier_used = decisions[0].tier if decisions else "deterministic"
            reason_given = decisions[0].reason if decisions else "No claims processed"

            if any(a == "CONFLICT" for a in actions) or len(conflicts) > 0:
                predicted: PredictedLabel = "CONTRADICTION"
                action_taken = "CONFLICT"
                confidence = 0.95
            elif any(a == "ABSTAIN" for a in actions):
                predicted = "UNCERTAIN"
                action_taken = "ABSTAIN"
                confidence = 0.50
            else:
                predicted = "NO_CONTRADICTION"
                action_taken = actions[0] if actions else "UPDATE"
                confidence = 0.90

            # Evaluate correctness
            is_correct = predicted == example.ground_truth

            failure_record: FailureRecord | None = None
            if not is_correct:
                fail_cat = _diagnose_failure_category(example, predicted, action_taken)
                explanation = (
                    f"Ground truth was '{example.ground_truth}' but system predicted '{predicted}' "
                    f"(action: {action_taken}, tier: {tier_used}). Reason: {reason_given}"
                )
                failure_record = FailureRecord(
                    example_id=example.id,
                    category=example.category,
                    memory_a=example.memory_a,
                    memory_b=example.memory_b,
                    ground_truth=example.ground_truth,
                    predicted=predicted,
                    confidence=confidence,
                    failure_category=fail_cat,
                    explanation=explanation,
                    model_output_snippet=reason_given,
                )

            return ExampleEvaluationResult(
                example_id=example.id,
                category=example.category,
                ground_truth=example.ground_truth,
                predicted=predicted,
                confidence=confidence,
                is_correct=is_correct,
                action_taken=action_taken,
                reason=reason_given,
                tier=tier_used,
                failure_record=failure_record,
            )
        finally:
            session.close()

    def evaluate_split(
        self,
        examples: list[EvaluationExample],
        dataset_name: str = "Benchmark",
        split_name: str = "test",
        provider_name: str = "MockLLMProvider",
    ) -> EvaluationReportPayload:
        """Run the full evaluation over all examples and compute standard statistical metrics."""
        results: list[ExampleEvaluationResult] = []
        failures: list[FailureRecord] = []

        cm = ConfusionMatrix(total=len(examples))
        category_stats: dict[str, dict[str, int]] = {}
        failure_cat_counts: dict[str, int] = {}

        for ex in examples:
            res = self.evaluate_example(ex)
            results.append(res)

            # Category tracking
            c_name = ex.category
            if c_name not in category_stats:
                category_stats[c_name] = {"total": 0, "correct": 0}
            category_stats[c_name]["total"] += 1
            if res.is_correct:
                category_stats[c_name]["correct"] += 1

            # Confusion matrix counts
            gt = ex.ground_truth
            pred = res.predicted

            if gt == "CONTRADICTION" and pred == "CONTRADICTION":
                cm.tp += 1
            elif gt == "NO_CONTRADICTION" and pred == "NO_CONTRADICTION":
                cm.tn += 1
            elif gt == "NO_CONTRADICTION" and pred == "CONTRADICTION":
                cm.fp += 1
            elif gt == "CONTRADICTION" and pred == "NO_CONTRADICTION":
                cm.fn += 1
            elif gt == "UNCERTAIN" and pred == "UNCERTAIN":
                cm.correct_uncertain += 1
            elif gt == "UNCERTAIN" and pred == "CONTRADICTION":
                cm.uncertain_as_contradiction += 1
                cm.fp += 1  # Flagged contradiction when reality was uncertain
            elif gt == "UNCERTAIN" and pred == "NO_CONTRADICTION":
                cm.uncertain_as_no_contradiction += 1
            elif gt == "CONTRADICTION" and pred == "UNCERTAIN":
                cm.contradiction_as_uncertain += 1
                cm.fn += 1  # Missed contradiction by abstaining
            elif gt == "NO_CONTRADICTION" and pred == "UNCERTAIN":
                cm.no_contradiction_as_uncertain += 1

            if res.failure_record:
                failures.append(res.failure_record)
                fcat = res.failure_record.failure_category
                failure_cat_counts[fcat] = failure_cat_counts.get(fcat, 0) + 1

        # Statistical Metrics Computation
        total_eval = len(examples)
        eval_binary = cm.tp + cm.tn + cm.fp + cm.fn

        precision = cm.tp / (cm.tp + cm.fp) if (cm.tp + cm.fp) > 0 else 0.0
        recall = cm.tp / (cm.tp + cm.fn) if (cm.tp + cm.fn) > 0 else 0.0
        f1 = (
            (2.0 * precision * recall) / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )
        specificity = cm.tn / (cm.tn + cm.fp) if (cm.tn + cm.fp) > 0 else 0.0
        
        # Overall Accuracy across all examples including abstentions
        total_correct = sum(1 for r in results if r.is_correct)
        accuracy = total_correct / total_eval if total_eval > 0 else 0.0

        abstention_examples = [e for e in examples if e.ground_truth == "UNCERTAIN"]
        abstention_count = len(abstention_examples)
        abstention_accuracy = (
            cm.correct_uncertain / abstention_count if abstention_count > 0 else 0.0
        )

        category_breakdown = {
            cat: {
                "total": data["total"],
                "correct": data["correct"],
                "accuracy": round(data["correct"] / data["total"], 3)
                if data["total"] > 0
                else 0.0,
            }
            for cat, data in category_stats.items()
        }

        metrics = EvaluationMetrics(
            total_examples=total_eval,
            evaluated_binary=eval_binary,
            tp=cm.tp,
            tn=cm.tn,
            fp=cm.fp,
            fn=cm.fn,
            precision=round(precision, 4),
            recall=round(recall, 4),
            f1=round(f1, 4),
            accuracy=round(accuracy, 4),
            specificity=round(specificity, 4),
            abstention_count=abstention_count,
            abstention_accuracy=round(abstention_accuracy, 4),
            confusion_matrix=cm,
            category_breakdown=category_breakdown,
            failure_category_breakdown=failure_cat_counts,
            failures=failures,
        )

        return EvaluationReportPayload(
            dataset_name=dataset_name,
            split=split_name,
            provider=provider_name,
            metrics=metrics,
            failures=failures,
            results=results,
        )
