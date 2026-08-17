"""Deterministic next-draw regular-zodiac transition analysis."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from laoliuliu.config import (
    APPROVED_DATA_START_ISSUE_ID,
    APPROVED_DATA_YEAR,
)
from laoliuliu.errors import AnalysisError
from laoliuliu.models import DrawRecord
from laoliuliu.zodiac import ZodiacAnimal, zodiac_for_number


@dataclass(frozen=True)
class RankedNumber:
    """One regular number occurrence count within a zodiac bucket."""

    number: int
    occurrences: int

    def to_dict(self) -> dict[str, int]:
        return {"number": self.number, "occurrences": self.occurrences}


@dataclass(frozen=True)
class RankedZodiac:
    """One zodiac count and empirical occurrence share."""

    rank: int
    zodiac: ZodiacAnimal
    occurrences: int
    frequency: float
    number_occurrences: tuple[RankedNumber, ...]

    def to_dict(self, *, include_number_breakdown: bool = True) -> dict[str, Any]:
        result: dict[str, Any] = {
            "rank": self.rank,
            "zodiac": self.zodiac.value,
            "label": self.zodiac.label,
            "occurrences": self.occurrences,
            "frequency": self.frequency,
        }
        if include_number_breakdown:
            result["number_occurrences"] = [
                item.to_dict() for item in self.number_occurrences
            ]
        return result


@dataclass(frozen=True)
class TransitionAnalysis:
    """Complete, reproducible transition analysis result."""

    latest_issue: str
    latest_regular_numbers: tuple[int, ...]
    latest_special_number: int
    latest_special_zodiac: ZodiacAnimal
    sample_count: int
    total_regular_occurrences: int
    matched_transitions: tuple[tuple[str, str], ...]
    ranking: tuple[RankedZodiac, ...]

    def to_dict(self, *, include_number_breakdown: bool = True) -> dict[str, Any]:
        ranking = [
            entry.to_dict(include_number_breakdown=include_number_breakdown)
            for entry in self.ranking
        ]
        return {
            "algorithm_version": "zodiac-transition-2026-v3",
            "data_year": APPROVED_DATA_YEAR,
            "data_start_issue": APPROVED_DATA_START_ISSUE_ID,
            "latest_issue": self.latest_issue,
            "latest_regular_numbers": list(self.latest_regular_numbers),
            "latest_special_number": self.latest_special_number,
            "latest_special_zodiac": self.latest_special_zodiac.value,
            "latest_special_zodiac_label": self.latest_special_zodiac.label,
            "sample_count": self.sample_count,
            "total_regular_occurrences": self.total_regular_occurrences,
            "matched_transitions": [
                {"condition_issue": current, "next_issue": following}
                for current, following in self.matched_transitions
            ],
            "top_six": ranking[:6],
            "ranking": ranking,
            "disclaimer": "结果仅表示2026年第48期起的历史条件频率，不保证未来开奖。",
        }


def calculate_latest_transition(db: Session) -> TransitionAnalysis:
    """Rank next-draw regular zodiacs using the approved transition rule."""

    return _calculate_transition(_ordered_records(db))


def calculate_transition_for_issue(db: Session, issue: str) -> TransitionAnalysis:
    """Calculate one historical issue using only data available through that issue."""

    return _calculate_transition(_ordered_records(db), target_issue=issue)


def list_historical_analysis_issues(db: Session) -> list[dict[str, Any]]:
    """List historical issues that have at least one valid transition sample."""

    records = _ordered_records(db)
    previously_seen: set[ZodiacAnimal] = set()
    eligible: list[dict[str, Any]] = []
    for index, record in enumerate(records[:-1]):
        anchor = ZodiacAnimal(record.zodiac_anchor)
        special_zodiac = zodiac_for_number(record.special_number, anchor)
        if index > 0 and special_zodiac in previously_seen:
            eligible.append(
                {
                    "issue": record.issue,
                    "open_time": record.open_time.isoformat(),
                    "special_number": record.special_number,
                    "special_zodiac": special_zodiac.value,
                    "special_zodiac_label": special_zodiac.label,
                }
            )
        previously_seen.add(special_zodiac)
    eligible.reverse()
    return eligible


def _ordered_records(db: Session) -> list[DrawRecord]:
    return list(
        db.scalars(
            select(DrawRecord)
            .where(DrawRecord.issue >= APPROVED_DATA_START_ISSUE_ID)
            .order_by(DrawRecord.open_time, DrawRecord.issue)
        )
    )


def _calculate_transition(
    records: list[DrawRecord], target_issue: str | None = None
) -> TransitionAnalysis:
    if target_issue is not None:
        target_index = next(
            (
                index
                for index, record in enumerate(records)
                if record.issue == target_issue
            ),
            None,
        )
        if target_index is None:
            raise AnalysisError(
                "ANALYSIS_ISSUE_NOT_FOUND", "查询的2026年第48期起期号不存在", 404
            )
        records = records[: target_index + 1]
    if len(records) < 2:
        raise AnalysisError(
            "INSUFFICIENT_HISTORY", "至少需要两期2026年第48期起数据才能分析", 409
        )

    latest = records[-1]
    latest_anchor = ZodiacAnimal(latest.zodiac_anchor)
    current_special_zodiac = zodiac_for_number(latest.special_number, latest_anchor)
    counts: Counter[ZodiacAnimal] = Counter()
    number_counts: dict[ZodiacAnimal, Counter[int]] = {
        animal: Counter() for animal in ZodiacAnimal
    }
    transitions: list[tuple[str, str]] = []

    for index, record in enumerate(records[:-1]):
        record_anchor = ZodiacAnimal(record.zodiac_anchor)
        if (
            zodiac_for_number(record.special_number, record_anchor)
            != current_special_zodiac
        ):
            continue
        following = records[index + 1]
        following_anchor = ZodiacAnimal(following.zodiac_anchor)
        for number in following.regular_numbers:
            animal = zodiac_for_number(number, following_anchor)
            counts[animal] += 1
            number_counts[animal][number] += 1
        transitions.append((record.issue, following.issue))

    if not transitions:
        raise AnalysisError(
            "INSUFFICIENT_MATCHED_HISTORY",
            "2026年第48期起没有可用的同特码生肖下一期样本",
            409,
        )

    total = len(transitions) * 6
    canonical = tuple(ZodiacAnimal)
    ordered = sorted(
        canonical, key=lambda animal: (-counts[animal], canonical.index(animal))
    )
    ranking = tuple(
        RankedZodiac(
            rank=index,
            zodiac=animal,
            occurrences=counts[animal],
            frequency=round(counts[animal] / total, 6),
            number_occurrences=tuple(
                RankedNumber(number=number, occurrences=occurrences)
                for number, occurrences in sorted(
                    number_counts[animal].items(),
                    key=lambda item: (-item[1], item[0]),
                )
            ),
        )
        for index, animal in enumerate(ordered, start=1)
    )
    return TransitionAnalysis(
        latest_issue=latest.issue,
        latest_regular_numbers=tuple(latest.regular_numbers),
        latest_special_number=latest.special_number,
        latest_special_zodiac=current_special_zodiac,
        sample_count=len(transitions),
        total_regular_occurrences=total,
        matched_transitions=tuple(transitions),
        ranking=ranking,
    )
