"""The tasting requirements and the one formula every part of the demo shares."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Requirements:
    participants: int = 8
    pour_ml: int = 20
    whisky_count: int = 4
    budget_cents: int = 20_000
    max_abv: float = 50.0
    required_type: str = "single_malt"

    @property
    def required_ml(self) -> int:
        return self.participants * self.pour_ml


DEFAULT_REQUIREMENTS = Requirements()


def bottles_needed(participants: int, pour_ml: int, bottle_ml: int) -> int:
    """Whole bottles needed so every participant gets one pour; always rounds up."""
    if participants < 0 or pour_ml < 0 or bottle_ml <= 0:
        raise ValueError("participants and pour_ml must be >= 0, bottle_ml must be > 0")
    return math.ceil(participants * pour_ml / bottle_ml)
