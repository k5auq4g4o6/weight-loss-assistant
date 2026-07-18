from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any


def _list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return [str(value).strip()]


@dataclass
class Profile:
    name: str = "我"
    age: int | None = None
    sex: str = "female"
    height_cm: float | None = None
    current_weight_kg: float | None = None
    target_weight_kg: float | None = None
    pace: str = "steady"
    lunch_budget: int = 35
    lunch_places: list[str] = field(default_factory=lambda: ["食堂", "盖饭", "面/粉", "麻辣烫", "便利店", "快餐", "小店"])
    avoid_foods: list[str] = field(default_factory=list)
    disliked_foods: list[str] = field(default_factory=list)
    dinner_minutes: int = 30
    cookware: list[str] = field(default_factory=lambda: ["炒锅", "电饭煲"])
    taste_preferences: list[str] = field(default_factory=lambda: ["清淡", "家常"])
    treadmill_incline_pct: float = 8.0
    treadmill_speed_kmh: float = 5.2
    treadmill_minutes: int = 35
    usual_rpe: int = 6

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "Profile | None":
        if not data:
            return None
        values = dict(data)
        for key in ["lunch_places", "avoid_foods", "disliked_foods", "cookware", "taste_preferences"]:
            values[key] = _list(values.get(key))
        return cls(**{key: values[key] for key in cls.__dataclass_fields__ if key in values})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CheckIn:
    day: str
    weight_kg: float | None = None
    workout_done: bool = False
    workout_minutes: int = 0
    avg_incline_pct: float = 0.0
    avg_speed_kmh: float = 0.0
    rpe: int = 6
    sleep_quality: int = 3
    fatigue: int = 3
    hunger: int = 3
    lunch_feedback: str = ""
    dinner_feedback: str = ""
    notes: str = ""

    @classmethod
    def today(cls) -> "CheckIn":
        return cls(day=date.today().isoformat())

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "CheckIn | None":
        if not data:
            return None
        values = dict(data)
        values["workout_done"] = bool(values.get("workout_done"))
        return cls(**{key: values[key] for key in cls.__dataclass_fields__ if key in values})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DailyContext:
    day: str
    available_minutes: int = 35
    sleep_quality: int = 3
    fatigue: int = 3
    hunger: int = 3
    body_status: str = "无明显不适"
    notes: str = ""

    @classmethod
    def today(cls) -> "DailyContext":
        return cls(day=date.today().isoformat())

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "DailyContext | None":
        if not data:
            return None
        values = dict(data)
        return cls(**{key: values[key] for key in cls.__dataclass_fields__ if key in values})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MealOption:
    category: str
    title: str
    estimate_kcal: int
    protein_g: int
    order_tips: list[str]
    avoid_tips: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DinnerRecipe:
    title: str
    cook_minutes: int
    estimate_kcal: int
    protein_g: int
    ingredients: list[str]
    steps: list[str]
    structure: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WorkoutSegment:
    name: str
    minutes: int
    incline_pct: float
    speed_kmh: float
    target_rpe: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PlanDraft:
    day: str
    calorie_range: tuple[int, int]
    protein_g: int
    workout: list[WorkoutSegment]
    lunch_options: list[MealOption]
    dinner_recipe: DinnerRecipe
    adjustments: list[str]
    risk_notes: list[str]
    profile_missing: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["calorie_range"] = list(self.calorie_range)
        return data
