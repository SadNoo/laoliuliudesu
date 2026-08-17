"""Deterministic top-ten number comparison and 3-of-3 combinations."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from itertools import combinations
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from laoliuliu.analysis import TransitionAnalysis, calculate_latest_transition
from laoliuliu.config import APPROVED_DATA_START_ISSUE_ID, APPROVED_DATA_YEAR
from laoliuliu.errors import AnalysisError
from laoliuliu.models import DrawRecord
from laoliuliu.zodiac import ZodiacAnimal

RECENT_DRAW_COUNT = 20
CANDIDATE_COUNT = 10
COMBINATION_COUNT = 10


@dataclass(frozen=True)
class RankedCandidateNumber:
    """One number ranked by historical and recent regular-number counts."""

    rank: int
    number: int
    zodiacs: tuple[ZodiacAnimal, ...]
    historical_occurrences: int
    recent_occurrences: int
    combined_score: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "number": self.number,
            "zodiacs": [animal.value for animal in self.zodiacs],
            "zodiac_labels": [animal.label for animal in self.zodiacs],
            "historical_occurrences": self.historical_occurrences,
            "recent_occurrences": self.recent_occurrences,
            "combined_score": self.combined_score,
        }


@dataclass(frozen=True)
class RankedThreeNumberCombination:
    """One deterministic three-number reference combination."""

    rank: int
    numbers: tuple[int, int, int]
    historical_occurrences: int
    recent_occurrences: int
    combined_score: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "numbers": list(self.numbers),
            "historical_occurrences": self.historical_occurrences,
            "recent_occurrences": self.recent_occurrences,
            "combined_score": self.combined_score,
        }


@dataclass(frozen=True)
class NumberCombinationAnalysis:
    """Complete reproducible latest-issue number comparison result."""

    latest_issue: str
    transition_sample_count: int
    top_six_zodiacs: tuple[ZodiacAnimal, ...]
    recent_issue_start: str
    recent_issue_end: str
    candidates: tuple[RankedCandidateNumber, ...]
    combinations: tuple[RankedThreeNumberCombination, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "algorithm_version": "top-six-zodiac-20-regular-3of3-v1",
            "data_year": APPROVED_DATA_YEAR,
            "data_start_issue": APPROVED_DATA_START_ISSUE_ID,
            "latest_issue": self.latest_issue,
            "transition_sample_count": self.transition_sample_count,
            "top_six_zodiacs": [
                {"zodiac": animal.value, "label": animal.label}
                for animal in self.top_six_zodiacs
            ],
            "recent_draw_count": RECENT_DRAW_COUNT,
            "recent_issue_start": self.recent_issue_start,
            "recent_issue_end": self.recent_issue_end,
            "candidate_count": len(self.candidates),
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "combination_count": len(self.combinations),
            "combinations": [item.to_dict() for item in self.combinations],
            "disclaimer": "组合仅为历史数据筛选结果，不保证未来开奖或3中3。",
        }


def calculate_latest_number_combinations(db: Session) -> NumberCombinationAnalysis:
    """Calculate ten 3-of-3 groups using the approved latest-issue rule."""

    records = list(
        db.scalars(
            select(DrawRecord)
            .where(DrawRecord.issue >= APPROVED_DATA_START_ISSUE_ID)
            .order_by(DrawRecord.open_time, DrawRecord.issue)
        )
    )
    if len(records) < RECENT_DRAW_COUNT + 1:
        raise AnalysisError(
            "INSUFFICIENT_RECENT_HISTORY",
            "至少需要当前期及此前20期数据才能生成号码组合",
            409,
        )

    transition = calculate_latest_transition(db)
    recent_records = records[-(RECENT_DRAW_COUNT + 1) : -1]
    return build_number_combinations(
        transition,
        recent_issues=tuple(record.issue for record in recent_records),
        recent_regular_numbers=tuple(
            tuple(record.regular_numbers) for record in recent_records
        ),
    )


def build_number_combinations(
    transition: TransitionAnalysis,
    *,
    recent_issues: tuple[str, ...],
    recent_regular_numbers: tuple[tuple[int, ...], ...],
) -> NumberCombinationAnalysis:
    """Build the deterministic candidate and combination rankings."""

    if (
        len(recent_issues) != RECENT_DRAW_COUNT
        or len(recent_regular_numbers) != RECENT_DRAW_COUNT
    ):
        raise AnalysisError(
            "INSUFFICIENT_RECENT_HISTORY",
            "必须提供当期之前完整20期平码数据",
            409,
        )

    recent_counts: Counter[int] = Counter(
        number for numbers in recent_regular_numbers for number in numbers
    )
    historical_counts: Counter[int] = Counter()
    number_zodiacs: dict[int, list[ZodiacAnimal]] = {}
    top_six = transition.ranking[:6]
    for ranked_zodiac in top_six:
        for ranked_number in ranked_zodiac.number_occurrences:
            historical_counts[ranked_number.number] += ranked_number.occurrences
            animals = number_zodiacs.setdefault(ranked_number.number, [])
            if ranked_zodiac.zodiac not in animals:
                animals.append(ranked_zodiac.zodiac)

    comparable_numbers = [
        number for number in historical_counts if recent_counts[number] > 0
    ]
    comparable_numbers.sort(
        key=lambda number: (
            -(historical_counts[number] + recent_counts[number]),
            -historical_counts[number],
            -recent_counts[number],
            number,
        )
    )
    selected_numbers = comparable_numbers[:CANDIDATE_COUNT]
    if len(selected_numbers) < CANDIDATE_COUNT:
        raise AnalysisError(
            "INSUFFICIENT_COMBINATION_CANDIDATES",
            "历史前六生肖号码与近20期热门平码交集中不足10个号码",
            409,
        )

    candidates = tuple(
        RankedCandidateNumber(
            rank=rank,
            number=number,
            zodiacs=tuple(number_zodiacs[number]),
            historical_occurrences=historical_counts[number],
            recent_occurrences=recent_counts[number],
            combined_score=historical_counts[number] + recent_counts[number],
        )
        for rank, number in enumerate(selected_numbers, start=1)
    )

    combination_scores: list[tuple[tuple[int, int, int], int, int, int]] = []
    for group in combinations(candidates, 3):
        numbers = tuple(sorted(candidate.number for candidate in group))
        historical_total = sum(candidate.historical_occurrences for candidate in group)
        recent_total = sum(candidate.recent_occurrences for candidate in group)
        combination_scores.append(
            (
                (numbers[0], numbers[1], numbers[2]),
                historical_total,
                recent_total,
                historical_total + recent_total,
            )
        )
    combination_scores.sort(key=lambda item: (-item[3], -item[1], -item[2], item[0]))
    ranked_combinations = tuple(
        RankedThreeNumberCombination(
            rank=rank,
            numbers=item[0],
            historical_occurrences=item[1],
            recent_occurrences=item[2],
            combined_score=item[3],
        )
        for rank, item in enumerate(combination_scores[:COMBINATION_COUNT], start=1)
    )
    return NumberCombinationAnalysis(
        latest_issue=transition.latest_issue,
        transition_sample_count=transition.sample_count,
        top_six_zodiacs=tuple(entry.zodiac for entry in top_six),
        recent_issue_start=recent_issues[0],
        recent_issue_end=recent_issues[-1],
        candidates=candidates,
        combinations=ranked_combinations,
    )
