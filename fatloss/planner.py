from __future__ import annotations

from dataclasses import asdict
from datetime import date
from typing import Any

from .deepseek import DeepSeekClient, DeepSeekError
from .menu import dinner_recipe_for, lunch_options_for
from .models import CheckIn, DailyContext, PlanDraft, Profile, WorkoutSegment


class PlanEngine:
    def __init__(self, today: date | None = None):
        self.today = today or date.today()

    def create_draft(self, profile: Profile | None, yesterday: CheckIn | None = None, context: DailyContext | None = None) -> PlanDraft:
        profile = profile or Profile()
        context = context or DailyContext(day=self.today.isoformat())
        missing = self._missing_fields(profile)
        calorie_range, protein_g = self._nutrition_targets(profile, missing)
        workout, adjustments = self._workout(yesterday, context)
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

    def _workout(self, yesterday: CheckIn | None, context: DailyContext) -> tuple[list[WorkoutSegment], list[str]]:
        available_minutes = max(15, min(90, int(context.available_minutes or 35)))
        main_minutes = max(10, available_minutes - 10)
        incline = 8.0
        speed = 5.2
        if available_minutes <= 25:
            incline = 6.5
            speed = 4.8
        elif available_minutes >= 50:
            incline = 8.5
            speed = 5.3

        adjustments = ["按今天实际状态生成：只安排爬坡，不额外叠加强刺激训练。"]
        hard_context = (
            context.fatigue >= 4
            or context.sleep_quality <= 2
            or _has_body_warning(context.body_status)
        )
        hungry_context = context.hunger >= 4

        if yesterday:
            hard_day = yesterday.fatigue >= 4 or yesterday.sleep_quality <= 2 or yesterday.rpe >= 9
            easy_success = (
                yesterday.workout_done
                and yesterday.rpe <= 6
                and yesterday.fatigue <= 2
                and yesterday.sleep_quality >= 3
            )
            missed = not yesterday.workout_done
            if hard_day and not hard_context:
                main_minutes = max(12, main_minutes - 5)
                incline = max(3.0, incline - 1.0)
                speed = max(3.5, speed - 0.2)
                adjustments.append("昨天恢复状态偏紧，今天先小幅降强度。")
            elif easy_success and not hard_context and not hungry_context:
                incline = min(15.0, incline + 0.5)
                adjustments.append("昨天完成度好且今天状态稳定，坡度只小幅递增 0.5%。")
            elif missed:
                main_minutes = max(12, main_minutes - 3)
                adjustments.append("昨天没有完成训练，今天回到可完成版本，不补偿式加练。")

        if hard_context:
            main_minutes = max(10, main_minutes - 8)
            incline = max(3.0, incline - 2.0)
            speed = max(3.5, speed - 0.4)
            adjustments.append("今天睡眠、疲劳或身体状态不适合硬顶，降低坡度和主训练时长。")
        elif hungry_context:
            main_minutes = max(10, main_minutes - 5)
            speed = max(3.5, speed - 0.2)
            adjustments.append("今天饥饿感偏高，训练稍微收一点，避免越练越饿。")

        if context.notes.strip():
            adjustments.append(f"今日备注：{context.notes.strip()}")

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


def build_plan_view(
    draft: PlanDraft,
    profile: Profile | None,
    use_ai: bool = True,
    client: DeepSeekClient | None = None,
    context: DailyContext | None = None,
) -> dict[str, Any]:
    profile = profile or Profile()
    if not use_ai:
        return _sanitize_plan_view(draft, profile, fallback_ai_plan(draft))
    client = client or DeepSeekClient()
    if not client.configured:
        view = fallback_ai_plan(draft)
        view["ai_status"] = "not_configured"
        return _sanitize_plan_view(draft, profile, view)
    try:
        enhanced = client.enhance_plan(draft, profile, context)
        return _sanitize_plan_view(draft, profile, _merge_enhancement(draft, enhanced))
    except (DeepSeekError, ValueError, KeyError, TypeError):
        return _sanitize_plan_view(draft, profile, fallback_ai_plan(draft))


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


def _blocked_terms(profile: Profile) -> list[str]:
    seen = set()
    terms = []
    for item in profile.avoid_foods + profile.disliked_foods:
        term = str(item).strip().lower()
        if term and term not in seen:
            seen.add(term)
            terms.append(term)
    return terms


def _stringify(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(_stringify(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_stringify(item) for item in value)
    return str(value)


def _has_blocked_food(value: Any, blocked: list[str]) -> bool:
    text = _stringify(value).lower()
    return any(term in text for term in blocked)


def _sanitize_plan_view(draft: PlanDraft, profile: Profile, view: dict[str, Any]) -> dict[str, Any]:
    blocked = _blocked_terms(profile)
    if not blocked:
        return view

    fallback = fallback_ai_plan(draft)
    changed = False
    safe_lunch = [
        item for item in view.get("lunch_options", [])
        if isinstance(item, dict) and not _has_blocked_food(item, blocked)
    ]
    for item in fallback["lunch_options"]:
        if len(safe_lunch) >= 4:
            break
        if not _has_blocked_food(item, blocked) and item not in safe_lunch:
            safe_lunch.append(item)
    if len(safe_lunch) != len(view.get("lunch_options", [])):
        changed = True
        view["lunch_options"] = safe_lunch

    if _has_blocked_food(view.get("dinner_recipe", {}), blocked):
        changed = True
        view["dinner_recipe"] = fallback["dinner_recipe"]

    if changed:
        adjustments = view.get("adjustments", [])
        if not isinstance(adjustments, list):
            adjustments = []
        adjustments.append("已按忌口/不喜欢食物硬过滤，含禁用食材的 AI 菜单已替换。")
        view["adjustments"] = adjustments
    return view


def _has_body_warning(text: str) -> bool:
    normalized = text.strip().lower()
    if not normalized or normalized in {"无", "没有", "无明显不适", "正常", "ok"}:
        return False
    return True


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
