from __future__ import annotations

from datetime import date

from fatloss.deepseek import parse_json_object
from fatloss.models import CheckIn, DailyContext, Profile
from fatloss.planner import PlanEngine, build_plan_view


def test_missing_profile_fields_are_reported():
    draft = PlanEngine(date(2026, 7, 18)).create_draft(Profile())
    assert "年龄" in draft.profile_missing
    assert "身高" in draft.profile_missing
    assert "当前体重" in draft.profile_missing
    assert draft.calorie_range == (1500, 1800)


def test_calorie_deficit_is_not_aggressive():
    profile = Profile(age=32, sex="female", height_cm=165, current_weight_kg=70)
    draft = PlanEngine(date(2026, 7, 18)).create_draft(profile)
    bmr = 10 * 70 + 6.25 * 165 - 5 * 32 - 161
    tdee = bmr * 1.35
    assert tdee - draft.calorie_range[1] <= 600
    assert draft.calorie_range[0] >= 1200
    assert 70 <= draft.protein_g <= 150


def test_treadmill_plan_deloads_after_hard_day():
    profile = Profile(age=32, height_cm=165, current_weight_kg=70)
    context = DailyContext(day="2026-07-18", available_minutes=40, sleep_quality=1, fatigue=5, hunger=3)
    hard_yesterday = CheckIn(day="2026-07-17", workout_done=True, rpe=9, fatigue=5, sleep_quality=1)
    draft = PlanEngine(date(2026, 7, 18)).create_draft(profile, hard_yesterday, context)
    main = next(segment for segment in draft.workout if segment.name == "主训练")
    assert main.incline_pct == 6
    assert main.speed_kmh == 4.8
    assert main.minutes == 22
    assert any("降低坡度" in item for item in draft.adjustments)


def test_treadmill_plan_progresses_after_easy_success():
    profile = Profile(age=32, height_cm=165, current_weight_kg=70)
    context = DailyContext(day="2026-07-18", available_minutes=35, sleep_quality=4, fatigue=2, hunger=3)
    easy_yesterday = CheckIn(day="2026-07-17", workout_done=True, rpe=5, fatigue=2, sleep_quality=4)
    draft = PlanEngine(date(2026, 7, 18)).create_draft(profile, easy_yesterday, context)
    main = next(segment for segment in draft.workout if segment.name == "主训练")
    assert main.incline_pct == 8.5
    assert main.minutes == 25


def test_lunch_has_no_cooking_steps_and_dinner_has_steps():
    profile = Profile(age=32, height_cm=165, current_weight_kg=70)
    draft = PlanEngine(date(2026, 7, 18)).create_draft(profile)
    assert draft.lunch_options
    assert all(not hasattr(item, "steps") for item in draft.lunch_options)
    assert draft.dinner_recipe.steps
    assert draft.dinner_recipe.cook_minutes <= 30


def test_ai_invalid_json_falls_back():
    class BadClient:
        configured = True

        def enhance_plan(self, draft, profile):
            raise ValueError("bad json")

    profile = Profile(age=32, height_cm=165, current_weight_kg=70)
    draft = PlanEngine(date(2026, 7, 18)).create_draft(profile)
    view = build_plan_view(draft, profile, use_ai=True, client=BadClient())
    assert view["ai_status"] == "fallback"
    assert view["dinner_recipe"]["steps"]


def test_ai_food_blocks_are_hard_filtered():
    class BeefClient:
        configured = True

        def enhance_plan(self, draft, profile, context=None):
            return {
                "coach_note": "ok",
                "workout_note": "ok",
                "lunch_options": [
                    {"category": "盖饭", "title": "牛肉盖饭", "estimate_kcal": 600, "protein_g": 35, "order_tips": ["少饭"], "avoid_tips": []}
                ],
                "dinner_recipe": {
                    "title": "青椒牛肉",
                    "cook_minutes": 20,
                    "estimate_kcal": 620,
                    "protein_g": 40,
                    "ingredients": ["牛肉", "青椒"],
                    "steps": ["炒熟"],
                    "structure": {},
                },
                "adjustments": [],
            }

    profile = Profile(age=32, height_cm=165, current_weight_kg=70, disliked_foods=["牛肉"])
    draft = PlanEngine(date(2026, 7, 18)).create_draft(profile)
    view = build_plan_view(draft, profile, use_ai=True, client=BeefClient())
    rendered = str(view["lunch_options"]) + str(view["dinner_recipe"])
    assert "牛肉" not in rendered
    assert any("硬过滤" in item for item in view["adjustments"])


def test_parse_json_object_accepts_fenced_json():
    parsed = parse_json_object('```json\n{"coach_note":"ok"}\n```')
    assert parsed == {"coach_note": "ok"}
