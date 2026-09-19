"""
Simple quality metrics, computed from record counts.

    Quality Score = valid_records / total_records * 100
    Error Rate     = invalid_records / total_records * 100
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class QualityMetrics:
    total_records: int
    valid_records: int
    invalid_records: int
    error_rate: float      # percentage, 0-100
    quality_score: float   # percentage, 0-100


def compute_metrics(total_records: int, valid_records: int, invalid_records: int) -> QualityMetrics:
    if total_records == 0:
        return QualityMetrics(0, 0, 0, 0.0, 0.0)

    error_rate = (invalid_records / total_records) * 100
    quality_score = (valid_records / total_records) * 100

    return QualityMetrics(
        total_records=total_records,
        valid_records=valid_records,
        invalid_records=invalid_records,
        error_rate=round(error_rate, 2),
        quality_score=round(quality_score, 2),
    )


def format_metrics(metrics: QualityMetrics) -> str:
    return (
        "\n"
        "===== Quality Metrics =====\n"
        f"Total records   : {metrics.total_records:,}\n"
        f"Valid records   : {metrics.valid_records:,}\n"
        f"Invalid records : {metrics.invalid_records:,}\n"
        f"Error rate      : {metrics.error_rate}%\n"
        f"Quality score   : {metrics.quality_score}%\n"
        "============================\n"
    )
