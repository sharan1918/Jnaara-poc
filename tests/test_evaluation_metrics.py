import json
from pathlib import Path
import pytest

from jnaara.evaluation.dataset import EvaluationDatasetLoader
from jnaara.evaluation.evaluator import EvaluatorEngine
from jnaara.evaluation.schemas import EvaluationExample


def test_confusion_matrix_and_metrics_calculation():
    """Test that EvaluatorEngine computes standard statistical metrics accurately."""
    engine = EvaluatorEngine()

    examples = [
        # Example 1: Clear contradiction on revenue (TP)
        EvaluationExample(
            id="T_TP_1",
            category="numeric_difference",
            entity="AlphaCorp",
            memory_a="AlphaCorp reported FY2024 revenue of $100M.",
            memory_b="AlphaCorp reported FY2024 revenue of $150M.",
            ground_truth="CONTRADICTION",
        ),
        # Example 2: Clear contradiction on CEO (TP)
        EvaluationExample(
            id="T_TP_2",
            category="clear_contradiction",
            entity="AlphaCorp",
            memory_a="Alice Walker was appointed CEO of AlphaCorp.",
            memory_b="Bob Martinez was appointed CEO of AlphaCorp.",
            ground_truth="CONTRADICTION",
        ),
        # Example 3: Non-contradiction (TN)
        EvaluationExample(
            id="T_TN_1",
            category="clear_non_contradiction",
            entity="AlphaCorp",
            memory_a="AlphaCorp operates an office in Seattle.",
            memory_b="AlphaCorp opened a customer center in Boston.",
            ground_truth="NO_CONTRADICTION",
        ),
        # Example 4: Non-contradiction (TN)
        EvaluationExample(
            id="T_TN_2",
            category="clear_non_contradiction",
            entity="AlphaCorp",
            memory_a="AlphaCorp was founded in 2012.",
            memory_b="AlphaCorp has 500 employees.",
            ground_truth="NO_CONTRADICTION",
        ),
        # Example 5: Subtle contradiction (FN)
        EvaluationExample(
            id="T_FN_1",
            category="subtle_contradiction",
            entity="AlphaCorp",
            memory_a="AlphaCorp closed its cloud division.",
            memory_b="AlphaCorp relocated cloud engineering to Austin.",
            ground_truth="CONTRADICTION",
        ),
        # Example 6: Uncertain ground truth that triggers abstention
        EvaluationExample(
            id="T_UNC_1",
            category="abstention_target",
            entity="AlphaCorp",
            memory_a="AlphaCorp confirmed 10% operating margin.",
            memory_b="Unconfirmed rumor that AlphaCorp margin might be negative.",
            ground_truth="UNCERTAIN",
            source_b_reliability="low",
        ),
    ]

    report = engine.evaluate_split(examples, dataset_name="TestMini", split_name="mini")
    metrics = report.metrics

    assert metrics.total_examples == 6
    # Accuracy should be bounded between 0.0 and 1.0
    assert 0.0 <= metrics.accuracy <= 1.0
    # Precision, Recall, Specificity, F1 should be bounded between 0.0 and 1.0
    assert 0.0 <= metrics.precision <= 1.0
    assert 0.0 <= metrics.recall <= 1.0
    assert 0.0 <= metrics.f1 <= 1.0
    assert 0.0 <= metrics.specificity <= 1.0

    # Math invariants
    cm = metrics.confusion_matrix
    assert cm.tp + cm.tn + cm.fp + cm.fn <= metrics.total_examples
    if (cm.tp + cm.fp) > 0:
        expected_precision = round(cm.tp / (cm.tp + cm.fp), 4)
        assert metrics.precision == expected_precision
    if (cm.tp + cm.fn) > 0:
        expected_recall = round(cm.tp / (cm.tp + cm.fn), 4)
        assert metrics.recall == expected_recall


def test_metrics_zero_division_safety():
    """Test that metric computation gracefully handles all-zero confusion matrices without ZeroDivisionError."""
    engine = EvaluatorEngine()

    # Empty list
    empty_report = engine.evaluate_split([], dataset_name="Empty", split_name="empty")
    assert empty_report.metrics.total_examples == 0
    assert empty_report.metrics.precision == 0.0
    assert empty_report.metrics.recall == 0.0
    assert empty_report.metrics.f1 == 0.0
    assert empty_report.metrics.accuracy == 0.0
    assert empty_report.metrics.specificity == 0.0

    # All TN examples -> TP = 0, FP = 0, FN = 0
    tn_only = [
        EvaluationExample(
            id="TN_1",
            category="clear_non_contradiction",
            entity="AlphaCorp",
            memory_a="AlphaCorp was founded in 2012.",
            memory_b="AlphaCorp has 500 employees.",
            ground_truth="NO_CONTRADICTION",
        )
    ]
    report = engine.evaluate_split(tn_only, dataset_name="TNOnly", split_name="test")
    assert report.metrics.tp == 0
    assert report.metrics.fp == 0
    assert report.metrics.precision == 0.0  # Division by zero handled cleanly
    assert report.metrics.recall == 0.0
    assert report.metrics.specificity == 1.0
    assert report.metrics.accuracy == 1.0


def test_dataset_loader_splits_and_categories():
    """Verify that all default dataset splits load correctly and adhere to schema."""
    for split in ["dev", "val", "test"]:
        examples = EvaluationDatasetLoader.load_split(split=split)
        assert len(examples) > 0
        assert all(isinstance(ex, EvaluationExample) for ex in examples)
        assert all(ex.ground_truth in ["CONTRADICTION", "NO_CONTRADICTION", "UNCERTAIN"] for ex in examples)
        assert all(len(ex.id) > 0 for ex in examples)

    # Test invalid split
    with pytest.raises(ValueError, match="Unknown split"):
        EvaluationDatasetLoader.load_split(split="invalid_split_name")


def test_held_out_test_set_covers_15_categories():
    """Verify that the held-out test set covers all 15 required semantic categories."""
    test_examples = EvaluationDatasetLoader.load_split(split="test")
    assert len(test_examples) == 60

    categories = {ex.category for ex in test_examples}
    expected_categories = {
        "clear_contradiction",
        "subtle_contradiction",
        "numeric_difference",
        "temporal_change_non_contradiction",
        "preference_change",
        "location_change",
        "paraphrased_same_meaning",
        "clear_non_contradiction",
        "ambiguous_case",
        "adversarial_confusing",
        "negation",
        "multi_memory_conflict",
        "missing_information",
        "edge_case",
        "abstention_target",
    }
    assert categories == expected_categories


def test_dataset_leakage_detection(tmp_path):
    """Verify that data leakage check returns zero leakage for actual splits and catches synthetic overlap."""
    dev_path = Path("data/evaluation/dev_set.json")
    test_path = Path("data/evaluation/held_out_test_set.json")

    # Real partitions must have zero ID and zero text leakage
    leakage = EvaluationDatasetLoader.check_leakage(dev_path, test_path)
    assert leakage["id_leakage"] is False
    assert leakage["id_overlap_count"] == 0
    assert leakage["text_leakage"] is False
    assert leakage["text_overlap_count"] == 0

    # Create artificial leaky dataset to test that the checker catches contamination
    leaky_file = tmp_path / "leaky_dev.json"
    with open(test_path, "r", encoding="utf-8") as f:
        test_data = json.load(f)

    leaky_data = {
        "metadata": {"split": "leaky_dev"},
        "examples": [test_data["examples"][0]],  # Duplicate first example
    }
    with open(leaky_file, "w", encoding="utf-8") as f:
        json.dump(leaky_data, f)

    leaked = EvaluationDatasetLoader.check_leakage(leaky_file, test_path)
    assert leaked["id_leakage"] is True
    assert leaked["id_overlap_count"] == 1
    assert leaked["text_leakage"] is True
    assert leaked["text_overlap_count"] == 1
