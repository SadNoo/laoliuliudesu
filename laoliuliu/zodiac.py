"""Per-draw zodiac mapping driven by the source-provided annual anchor."""

from __future__ import annotations

from enum import StrEnum


class ZodiacAnimal(StrEnum):
    """Stable internal zodiac values in canonical order."""

    RAT = "rat"
    OX = "ox"
    TIGER = "tiger"
    RABBIT = "rabbit"
    DRAGON = "dragon"
    SNAKE = "snake"
    HORSE = "horse"
    GOAT = "goat"
    MONKEY = "monkey"
    ROOSTER = "rooster"
    DOG = "dog"
    PIG = "pig"

    @property
    def label(self) -> str:
        """Return the Traditional Chinese label."""

        return _LABELS[self]

    @classmethod
    def from_source_label(cls, value: str) -> ZodiacAnimal:
        """Convert one confirmed source label to a stable value."""

        animal = _SOURCE_LABELS.get(value.strip())
        if animal is None:
            raise ValueError("unsupported zodiac anchor")
        return animal


_SOURCE_LABELS: dict[str, ZodiacAnimal] = {
    "鼠": ZodiacAnimal.RAT,
    "牛": ZodiacAnimal.OX,
    "虎": ZodiacAnimal.TIGER,
    "兔": ZodiacAnimal.RABBIT,
    "龍": ZodiacAnimal.DRAGON,
    "龙": ZodiacAnimal.DRAGON,
    "蛇": ZodiacAnimal.SNAKE,
    "馬": ZodiacAnimal.HORSE,
    "马": ZodiacAnimal.HORSE,
    "羊": ZodiacAnimal.GOAT,
    "猴": ZodiacAnimal.MONKEY,
    "雞": ZodiacAnimal.ROOSTER,
    "鸡": ZodiacAnimal.ROOSTER,
    "狗": ZodiacAnimal.DOG,
    "豬": ZodiacAnimal.PIG,
    "猪": ZodiacAnimal.PIG,
}

_LABELS: dict[ZodiacAnimal, str] = {
    ZodiacAnimal.RAT: "鼠",
    ZodiacAnimal.OX: "牛",
    ZodiacAnimal.TIGER: "虎",
    ZodiacAnimal.RABBIT: "兔",
    ZodiacAnimal.DRAGON: "龍",
    ZodiacAnimal.SNAKE: "蛇",
    ZodiacAnimal.HORSE: "馬",
    ZodiacAnimal.GOAT: "羊",
    ZodiacAnimal.MONKEY: "猴",
    ZodiacAnimal.ROOSTER: "雞",
    ZodiacAnimal.DOG: "狗",
    ZodiacAnimal.PIG: "豬",
}


def zodiac_mapping(anchor: ZodiacAnimal) -> dict[int, ZodiacAnimal]:
    """Build the confirmed 1-49 mapping for one annual zodiac anchor."""

    order = tuple(ZodiacAnimal)
    anchor_index = order.index(anchor)
    assignment = tuple(reversed(order[: anchor_index + 1])) + tuple(
        reversed(order[anchor_index + 1 :])
    )
    mapping: dict[int, ZodiacAnimal] = {}
    for first_number, animal in enumerate(assignment, start=1):
        for number in range(first_number, 50, 12):
            mapping[number] = animal
    return mapping


def zodiac_for_number(number: int, anchor: ZodiacAnimal) -> ZodiacAnimal:
    """Return the zodiac for a validated draw number."""

    if not 1 <= number <= 49:
        raise ValueError("draw number must be between 1 and 49")
    return zodiac_mapping(anchor)[number]
