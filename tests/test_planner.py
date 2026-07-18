from __future__ import annotations

from datetime import date

from fatloss.deepseek import parse_json_object
from fatloss.models import CheckIn, Profile
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
    profile = Profile(age=32, height_cm=165, current_weight_kg=70, treadmill_incline_pct=10, treadmill_speed_kmh=5.5, treadmill_minutes=40)
    hard_yesterday = CheckIn(day="2026-07-17", workout_done=True, rpe=9, fatigue=5, sleep_quality=1)
    draft = PlanEngine(date(2026, 7, 18)).create_draft(profile, hard_yesterday)
    main = next(segment for segment in draft.workout if segment.name == "主训练")
    assert main.incline_pct == 8
    assert main.speed_kmh == 5.1
    assert main.minutes == 22
    assert any("降坡度" in item for item in draft.adjustments)


def test_treadmill_plan_progresses_after_easy_success():
    profile = Profile(age=32, height_cm=165, current_weight_kg=70, treadmill_incline_pct=8, treadmill_speed_kmh=5.2, treadmill_minutes=35)
    easy_yesterday = CheckIn(day="2026-07-17", workout_done=True, rpe=5, fatigue=2, sleep_quality=4)
    draft = PlanEngine(date(2026, 7, 18)).create_draft(profile, easy_yesterday)
    main = next(segment for segment in draft.workout if segment.name == "主训练")
    assert main.incline_pct == 8.5
    assert main.minutes == 30


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


def test_parse_json_object_accepts_fenced_json():
    parsed = parse_json_object('```json\n{"coach_note":"ok"}\n```')
    assert parsed == {"coach_note": "ok"}

