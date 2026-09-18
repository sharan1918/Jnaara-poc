import json
import logging
from pathlib import Path
from typing import Any

from jnaara.evaluation.schemas import EvaluationExample

logger = logging.getLogger("jnaara.evaluation.dataset")

DEFAULT_SPLIT_PATHS = {
    "dev": Path("data/evaluation/dev_set.json"),
    "val": Path("data/evaluation/val_set.json"),
    "test": Path("data/evaluation/held_out_test_set.json"),
}


class EvaluationDatasetLoader:
    """Loader and validator for evaluation dataset splits."""

    @staticmethod
    def load_split(
        split: str = "test",
        custom_path: Path | str | None = None,
    ) -> list[EvaluationExample]:
        """Load and validate an evaluation dataset split."""
        if custom_path:
            file_path = Path(custom_path)
        else:
            clean_split = split.lower().strip()
            if clean_split not in DEFAULT_SPLIT_PATHS:
                raise ValueError(
                    f"Unknown split '{split}'. Available splits: {list(DEFAULT_SPLIT_PATHS.keys())}"
                )
            file_path = DEFAULT_SPLIT_PATHS[clean_split]

        if not file_path.exists():
            raise FileNotFoundError(f"Evaluation dataset file not found: {file_path}")

        logger.info("Loading evaluation dataset from %s", file_path)
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        raw_examples = data.get("examples", [])
        if not raw_examples:
            raise ValueError(f"Dataset {file_path} contains no examples.")

        examples: list[EvaluationExample] = []
        seen_ids: set[str] = set()

        for idx, ex_dict in enumerate(raw_examples):
            ex = EvaluationExample.model_validate(ex_dict)
            if ex.id in seen_ids:
                raise ValueError(f"Duplicate example ID '{ex.id}' at index {idx} in {file_path}")
            seen_ids.add(ex.id)
            examples.append(ex)

        logger.info(
            "Successfully loaded %d evaluation examples from %s",
            len(examples),
            file_path,
        )
        return examples

    @staticmethod
    def get_dataset_metadata(split: str = "test", custom_path: Path | str | None = None) -> dict[str, Any]:
        """Retrieve top-level dataset metadata."""
        if custom_path:
            file_path = Path(custom_path)
        else:
            file_path = DEFAULT_SPLIT_PATHS[split.lower().strip()]

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return data.get("metadata", {})

    @staticmethod
    def check_leakage(dev_path: Path, test_path: Path) -> dict[str, Any]:
        """Verify zero data leakage between development and held-out test splits."""
        dev_exs = EvaluationDatasetLoader.load_split(custom_path=dev_path)
        test_exs = EvaluationDatasetLoader.load_split(custom_path=test_path)

        dev_ids = {e.id for e in dev_exs}
        test_ids = {e.id for e in test_exs}
        id_overlap = dev_ids.intersection(test_ids)

        dev_texts = {(e.memory_a.strip().lower(), e.memory_b.strip().lower()) for e in dev_exs}
        test_texts = {(e.memory_a.strip().lower(), e.memory_b.strip().lower()) for e in test_exs}
        text_overlap = dev_texts.intersection(test_texts)

        return {
            "id_leakage": len(id_overlap) > 0,
            "id_overlap_count": len(id_overlap),
            "text_leakage": len(text_overlap) > 0,
            "text_overlap_count": len(text_overlap),
            "dev_count": len(dev_exs),
            "test_count": len(test_exs),
        }
