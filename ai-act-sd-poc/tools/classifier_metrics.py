"""Utilities to read classifier output CSVs and compute oversight metrics.

Pure Python (stdlib only) to keep compatibility with tooling scripts and Streamlit UI.
"""
from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import IO, Any, Dict, Iterable, List, Optional, Sequence, Union


@dataclass
class ClassifierRecord:
    decision_id: str
    true_label: str
    predicted_label: str
    review_probability: Optional[float]
    metadata: Dict[str, str]


def load_classifier_csv(source: Union[str, Path, IO[str], IO[bytes]]) -> List[ClassifierRecord]:
    """Load classifier output from a CSV file or file-like object."""
    if isinstance(source, (str, Path)):
        path = Path(source)
        with path.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            return list(_rows_from_reader(reader))

    raw = source.read()
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8-sig")
    elif raw is None:
        raw = ""
    text_buffer = StringIO(raw)
    if hasattr(source, "seek"):
        try:
            source.seek(0)
        except Exception:  # pragma: no cover - defensive
            pass
    reader = csv.DictReader(text_buffer)
    return list(_rows_from_reader(reader))


def compute_classifier_metrics(
    records: Sequence[ClassifierRecord],
    positive_label: str = "REVIEW",
    labels: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Return confusion matrix, per-class metrics, and macro/micro indicators."""
    total = len(records)
    if total == 0:
        return {
            "total": 0,
            "labels": [],
            "matrix": {},
            "per_class": {},
            "macro_f1": 0.0,
            "class_distribution": {},
            "binary": {},
        }

    label_set = (
        set(labels) if labels else set(rec.true_label for rec in records) | set(rec.predicted_label for rec in records)
    )
    ordered_labels = sorted(label_set)

    matrix: Dict[str, Dict[str, int]] = {
        true: {pred: 0 for pred in ordered_labels} for true in ordered_labels
    }
    for rec in records:
        matrix.setdefault(rec.true_label, {pred: 0 for pred in ordered_labels})
        matrix[rec.true_label][rec.predicted_label] = matrix[rec.true_label].get(rec.predicted_label, 0) + 1

    per_class: Dict[str, Dict[str, float]] = {}
    for label in ordered_labels:
        tp = matrix.get(label, {}).get(label, 0)
        fp = sum(matrix.get(other, {}).get(label, 0) for other in ordered_labels if other != label)
        fn = sum(matrix.get(label, {}).values()) - tp
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        support = sum(matrix.get(label, {}).values())
        per_class[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": support,
        }

    macro_f1 = sum(metrics["f1"] for metrics in per_class.values()) / len(per_class)
    class_distribution = Counter(rec.true_label for rec in records)

    binary = _compute_binary_metrics(records, positive_label)

    return {
        "total": total,
        "labels": ordered_labels,
        "matrix": matrix,
        "per_class": per_class,
        "macro_f1": macro_f1,
        "class_distribution": dict(class_distribution),
        "binary": binary,
    }


def compute_calibration_bins(
    records: Sequence[ClassifierRecord],
    positive_label: str = "REVIEW",
    bin_count: int = 10,
) -> List[Dict[str, Any]]:
    """Return calibration bins comparing predicted vs. observed REVIEW share."""
    prob_records = [rec for rec in records if rec.review_probability is not None]
    if not prob_records or bin_count <= 0:
        return []

    bins = [
        {
            "index": idx,
            "lower": idx / bin_count,
            "upper": (idx + 1) / bin_count,
            "count": 0,
            "prob_sum": 0.0,
            "positives": 0,
        }
        for idx in range(bin_count)
    ]

    for rec in prob_records:
        prob = max(0.0, min(1.0, float(rec.review_probability)))
        idx = bin_count - 1 if prob == 1.0 else int(prob * bin_count)
        bucket = bins[idx]
        bucket["count"] += 1
        bucket["prob_sum"] += prob
        if rec.true_label == positive_label:
            bucket["positives"] += 1

    result: List[Dict[str, Any]] = []
    for bucket in bins:
        if bucket["count"] == 0:
            continue
        predicted_rate = bucket["prob_sum"] / bucket["count"] * 100.0
        observed_rate = bucket["positives"] / bucket["count"] * 100.0
        result.append(
            {
                "bin_index": bucket["index"],
                "bin_label": f"{bucket['lower']:.1f}–{bucket['upper']:.1f}",
                "count": bucket["count"],
                "predicted_rate": predicted_rate,
                "observed_rate": observed_rate,
                "lower": bucket["lower"],
                "upper": bucket["upper"],
            }
        )
    return result


def _rows_from_reader(reader: csv.DictReader) -> Iterable[ClassifierRecord]:
    base_keys = {"decision_id", "true_label", "predicted_label", "review_probability"}
    for raw in reader:
        if raw is None:
            continue
        decision_id = (raw.get("decision_id") or "").strip()
        true_label = _normalize_label(raw.get("true_label"))
        predicted_label = _normalize_label(raw.get("predicted_label"))
        prob = _to_float(raw.get("review_probability"))
        metadata = {k: v for k, v in raw.items() if k not in base_keys}
        yield ClassifierRecord(
            decision_id=decision_id,
            true_label=true_label,
            predicted_label=predicted_label,
            review_probability=prob,
            metadata=metadata,
        )


def _normalize_label(value: Optional[str]) -> str:
    label = (value or "").strip().upper()
    return label or "UNKNOWN"


def _to_float(value: Optional[str]) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _compute_binary_metrics(records: Sequence[ClassifierRecord], positive_label: str) -> Dict[str, float]:
    if not records:
        return {}
    tp = sum(1 for rec in records if rec.true_label == positive_label and rec.predicted_label == positive_label)
    fp = sum(1 for rec in records if rec.true_label != positive_label and rec.predicted_label == positive_label)
    fn = sum(1 for rec in records if rec.true_label == positive_label and rec.predicted_label != positive_label)
    tn = len(records) - tp - fp - fn
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    accuracy = (tp + tn) / len(records)
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "accuracy": accuracy,
    }


__all__ = [
    "ClassifierRecord",
    "load_classifier_csv",
    "compute_classifier_metrics",
    "compute_calibration_bins",
]
