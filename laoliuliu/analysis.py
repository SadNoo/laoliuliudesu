"""Deterministic next-draw regular-zodiac transition analysis."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from laoliuliu.errors import AnalysisError
from laoliuliu.models import DrawRecord
from laoliuliu.zodiac import ZodiacAnimal, zodiac_for_number


@dataclass(frozen=True)
class RankedZodiac:
    """One zodiac count and empirical occurrence share."""

    rank: int
    zodiac: ZodiacAnimal
    occurrences: int
    frequency: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "zodiac": self.zodiac.value,
            "label": self.zodiac.label,
            "occurrences": self.occurrences,
            "frequency": self.frequency,
        }


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

    def to_dict(self) -> dict[str, Any]:
        ranking = [entry.to_dict() for entry in self.ranking]
        return {
            "algorithm_version": "zodiac-transition-2026-v1",
            "data_year": 2026,
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
            "disclaimer": "结果仅表示2026年历史条件频率，不保证未来开奖。",
        }


def calculate_latest_transition(db: Session) -> TransitionAnalysis:
    """Rank next-draw regular zodiacs using the approved transition rule."""

    records = list(
        db.scalars(select(DrawRecord).order_by(DrawRecord.open_time, DrawRecord.issue))
    )
    if len(records) < 2:
        raise AnalysisError(
            "INSUFFICIENT_HISTORY", "至少需要两期2026年数据才能分析", 409
        )

    latest = records[-1]
    latest_anchor = ZodiacAnimal(latest.zodiac_anchor)
    current_special_zodiac = zodiac_for_number(latest.special_number, latest_anchor)
    counts: Counter[ZodiacAnimal] = Counter()
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
        counts.update(
            zodiac_for_number(number, following_anchor)
            for number in following.regular_numbers
        )
        transitions.append((record.issue, following.issue))

    if not transitions:
        raise AnalysisError(
            "INSUFFICIENT_MATCHED_HISTORY",
            "2026年内没有可用的同特码生肖下一期样本",
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
