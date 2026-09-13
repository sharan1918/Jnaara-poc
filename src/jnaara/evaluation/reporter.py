import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from jnaara.models.domain import utc_now

logger = logging.getLogger("jnaara.evaluation")


def _sanitize_name(name: str) -> str:
    """Sanitize a file or sequence name to safe characters."""
    clean = re.sub(r"[^\w\-_.]", "_", name)
    return clean.strip("._") or "eval"


def save_evaluation_report(
    output_dir: Path | str,
    source_name: str,
    summary: dict[str, Any],
    results: list[Any],
    active_beliefs: list[Any] | None = None,
    sequence: str | None = None,
    strategy: str | None = None,
) -> Path:
    """Save evaluation results to the output folder with date_time and file name.

    File format: {YYYY-MM-DD_HH-MM-SS}_{source_name}[_{sequence}].json
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    timestamp_dt = utc_now()
    timestamp_prefix = timestamp_dt.strftime("%Y-%m-%d_%H-%M-%S")
    clean_stem = _sanitize_name(Path(source_name).stem if source_name else "evaluation")

    if sequence and sequence.strip():
        clean_seq = _sanitize_name(sequence.strip())
        target_filename = f"{timestamp_prefix}_{clean_stem}_{clean_seq}.json"
    else:
        target_filename = f"{timestamp_prefix}_{clean_stem}.json"

    file_path = out_path / target_filename

    # Helper to serialize Pydantic models or dicts
    def _to_serializable(obj: Any) -> Any:
        if hasattr(obj, "model_dump"):
            return obj.model_dump(mode="json")
        if hasattr(obj, "__dict__"):
            return {
                k: _to_serializable(v)
                for k, v in obj.__dict__.items()
                if not k.startswith("_")
            }
        if isinstance(obj, (list, tuple)):
            return [_to_serializable(item) for item in obj]
        if isinstance(obj, dict):
            return {str(k): _to_serializable(v) for k, v in obj.items()}
        if isinstance(obj, datetime):
            return obj.isoformat()
        return obj

    report_payload = {
        "evaluation_timestamp": timestamp_dt.isoformat(),
        "source_file": source_name,
        "sequence": sequence or "all",
        "strategy_used": strategy or "recency",
        "summary": _to_serializable(summary),
        "results": _to_serializable(results),
        "active_beliefs": _to_serializable(active_beliefs or []),
    }

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(report_payload, f, indent=2, default=str)
        logger.info("Evaluation report successfully saved to %s", file_path)
    except Exception as exc:
        logger.error("Failed to write evaluation report to %s: %s", file_path, exc)
        raise

    return file_path
