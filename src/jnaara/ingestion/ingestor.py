import json
from pathlib import Path
from typing import Any
from jnaara.models.domain import Fact


class FactIngestor:
    """Ingests, parses, and validates facts from the JSON dataset."""

    def load_dataset(self, path: Path | str) -> dict[str, list[Fact]]:
        """Load and validate all sequences from the JSON dataset file."""
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"Dataset file not found at: {file_path.resolve()}")

        with open(file_path, "r", encoding="utf-8") as f:
            data: dict[str, Any] = json.load(f)

        dataset: dict[str, list[Fact]] = {}
        for seq_name, seq_content in data.items():
            if seq_name == "metadata":
                continue
            raw_list = []
            if isinstance(seq_content, dict) and "facts" in seq_content:
                raw_list = seq_content["facts"]
            elif isinstance(seq_content, list):
                raw_list = seq_content

            if raw_list:
                facts: list[Fact] = []
                for item in raw_list:
                    fact = Fact.model_validate(item)
                    facts.append(fact)
                dataset[seq_name] = sorted(facts, key=lambda f: f.timestamp)

        return dataset

    def load_sequence(self, path: Path | str, sequence_name: str) -> list[Fact]:
        """Load and validate a single sequence from the dataset file."""
        dataset = self.load_dataset(path)
        if sequence_name not in dataset:
            available = list(dataset.keys())
            raise KeyError(
                f"Sequence '{sequence_name}' not found in dataset. Available sequences: {available}"
            )
        return dataset[sequence_name]

    def get_sequence_names(self, path: Path | str) -> list[str]:
        """List all sequence keys in the dataset file."""
        dataset = self.load_dataset(path)
        return list(dataset.keys())
