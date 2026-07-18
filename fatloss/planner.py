from __future__ import annotations

from dataclasses import asdict
from datetime import date
from typing import Any

from .deepseek import DeepSeekClient, DeepSeekError
from .menu import dinner_recipe_for, lunch_options_for
from .models import CheckIn, PlanDraft, Profile, WorkoutSegment


class PlanEngine:
    def __init__(self, today: date | None = None):
        self.today = today or date.today()

    def create_draft(self, profile: Profile | None, yesterday: CheckIn | None = None) -> PlanDraft:
        profile = profile or Profile()
        missing = self._missing_fields(profile)
        calorie_range, protein_g = self._nutrition_targets(profile, missing)
        workout, adjustments = self._workout(profile, yesterday)
        risks = [
            "如出现胸闷、头晕、关节刺痛或异常心率，立即停止训练。",
            "本助手仅做普通成年人减脂计划，不替代医生、营养师或康复建议。",
            "午饭外食优先保证蛋白质和蔬菜，酱汁、油炸、含糖饮料主动减量。",
        ]
        if missing:
            risks.insert(0, "档案信息不完整，热量和蛋白目标先按保守默认值生成。")
        return PlanDraft(
            day=self.today.isoformat(),
            calorie_range=calorie_range,
            protein_g=protein_g,
            workout=workout,
            lunch_options=lunch_options_for(profile),
            dinner_recipe=dinner_recipe_for(profile),
            adjustments=adjustments,
            risk_notes=risks,
            profile_missing=missing,
        )

    def _missing_fields(self, profile: Profile) -> list[str]:
        fields = []
        if not profile.age:
            fields.append("年龄")
        if not profile.height_cm:
            fields.append("身高")
        if not profile.current_weight_kg:
            fields.append("当前体重")
        return fields

    def _nutrition_targets(self, profile: Profile, missing: list[str]) -> tuple[tuple[int, int], int]:
        if missing:
            return (1500, 1800), 90
        sex_offset = 5 if profile.sex == "male" else -161
        bmr = 10 * float(profile.current_weight_kg) + 6.25 * float(profile.height_cm) - 5 * int(profile.age) + sex_offset
        tdee = bmr * 1.35
        deficit = min(500, max(250, tdee * 0.18))
        floor = 1400 if profile.sex == "male" else 1200
        target = max(floor, int(round(tdee - deficit)))
        low = max(floor, target - 100)
        high = target + 100
        protein = int(round(min(150, max(70, float(profile.current_weight_kg) * 1.6))))
        return (low, high), protein

    def _workout(self, profile: Profile, yesterday: CheckIn | None) -> tuple[list[WorkoutSegment], list[str]]:
        base_minutes = max(25, min(70, int(profile.treadmill_minutes or 35)))
        base_incline = max(3.0, min(15.0, float(profile.treadmill_incline_pct or 8.0)))
        base_speed = max(3.5, min(7.0, float(profile.treadmill_speed_kmh or 5.2)))
        main_minutes = base_minutes - 10
        incline = base_incline
        speed = base_speed
        adjustments = ["按稳健节奏安排：今天只做爬坡，不额外叠加强刺激训练。"]

        if yesterday:
            hard_day = yesterday.fatigue >= 4 or yesterday.sleep_quality <= 2 or yesterday.rpe >= 9
            easy_success = yesterday.workout_done and yesterday.rpe <= 6 and yesterday.fatigue <= 2 and yesterday.sleep_quality >= 3
            missed = not yesterday.workout_done
            if hard_day:
                main_minutes = max(15, main_minutes - 8)
                incline = max(3.0, incline - 2.0)
                speed = max(3.5, speed - 0.4)
                adjustments.append("昨天恢复状态偏紧，今天降坡度和时长，优先把动作做舒服。")
            elif easy_success:
                main_minutes = min(55, main_minutes + 5)
                incline = min(15.0, incline + 0.5)
                adjustments.append("昨天完成度好且体感不吃力，今天小幅递增 5 分钟或 0.5% 坡度。")
            elif missed:
                main_minutes = max(20, main_minutes - 3)
                adjustments.append("昨天没有完成训练，今天回到可完成版本，不补偿式加练。")

        workout = [
            WorkoutSegment("热身", 5, max(1.0, incline - 4.0), max(3.5, speed - 0.8), "轻松，能完整说话"),
            WorkoutSegment("主训练", main_minutes, incline, speed, "中等偏上，能短句交流"),
            WorkoutSegment("冷却", 5, 1.0, max(3.2, speed - 1.2), "轻松，心率慢慢降下来"),
        ]
        return workout, adjustments


def fallback_ai_plan(draft: PlanDraft) -> dict[str, Any]:
    return {
        "coach_note": "今天按本地规则生成计划：稳一点、能完成、别靠硬扛。",
        "workout_note": "爬坡训练按热身、主训练、冷却执行。主训练保持中等偏上体感，不追求跑到力竭。",
        "lunch_options": [item.to_dict() for item in draft.lunch_options],
        "dinner_recipe": draft.dinner_recipe.to_dict(),
        "adjustments": draft.adjustments,
        "ai_status": "fallback",
    }


def build_plan_view(draft: PlanDraft, profile: Profile | None, use_ai: bool = True, client: DeepSeekClient | None = None) -> dict[str, Any]:
    if not use_ai:
        return fallback_ai_plan(draft)
    client = client or DeepSeekClient()
    if not client.configured:
        view = fallback_ai_plan(draft)
        view["ai_status"] = "not_configured"
        return view
    try:
        enhanced = client.enhance_plan(draft, profile or Profile())
        return _merge_enhancement(draft, enhanced)
    except (DeepSeekError, ValueError, KeyError, TypeError):
        return fallback_ai_plan(draft)


def _merge_enhancement(draft: PlanDraft, enhanced: dict[str, Any]) -> dict[str, Any]:
    required = ["coach_note", "workout_note", "lunch_options", "dinner_recipe", "adjustments"]
    if not all(key in enhanced for key in required):
        raise ValueError("DeepSeek response missing required fields")
    view = fallback_ai_plan(draft)
    view.update(
        {
            "coach_note": str(enhanced["coach_note"]),
            "workout_note": str(enhanced["workout_note"]),
            "lunch_options": enhanced["lunch_options"] if isinstance(enhanced["lunch_options"], list) else view["lunch_options"],
            "dinner_recipe": enhanced["dinner_recipe"] if isinstance(enhanced["dinner_recipe"], dict) else view["dinner_recipe"],
            "adjustments": enhanced["adjustments"] if isinstance(enhanced["adjustments"], list) else view["adjustments"],
            "ai_status": "enhanced",
        }
    )
    return view


def plan_to_markdown(draft: PlanDraft, view: dict[str, Any]) -> str:
    lines = [
        f"# {draft.day} 减脂计划",
        "",
        f"- 热量范围：{draft.calorie_range[0]}-{draft.calorie_range[1]} kcal",
        f"- 蛋白目标：{draft.protein_g} g",
        "",
        "## 今日提醒",
        str(view.get("coach_note", "")),
        "",
        "## 爬坡",
        str(view.get("workout_note", "")),
    ]
    for segment in draft.workout:
        lines.append(f"- {segment.name}：{segment.minutes} 分钟，坡度 {segment.incline_pct:.1f}%，速度 {segment.speed_kmh:.1f} km/h，{segment.target_rpe}")
    lines.extend(["", "## 午饭外食"])
    for item in view.get("lunch_options", []):
        if isinstance(item, dict):
            lines.append(f"- {item.get('title', '')}：约 {item.get('estimate_kcal', '')} kcal，蛋白 {item.get('protein_g', '')} g")
    dinner = view.get("dinner_recipe", {})
    lines.extend(["", "## 晚饭自煮", f"- {dinner.get('title', '')}：约 {dinner.get('estimate_kcal', '')} kcal，蛋白 {dinner.get('protein_g', '')} g"])
    for step in dinner.get("steps", []):
        lines.append(f"- {step}")
    lines.extend(["", "## 安全边界"])
    for note in draft.risk_notes:
        lines.append(f"- {note}")
    return "\n".join(lines) + "\n"

