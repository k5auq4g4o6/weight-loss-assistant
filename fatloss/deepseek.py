from __future__ import annotations

import json
import os
import re
from typing import Any

import requests

from .config import get_secret, load_env_file


class DeepSeekError(RuntimeError):
    pass


class DeepSeekClient:
    def __init__(self, timeout: int | None = None):
        load_env_file()
        self.api_key = get_secret("DEEPSEEK_API_KEY")
        self.base_url = get_secret("DEEPSEEK_API_BASE", "https://api.deepseek.com").rstrip("/")
        self.model = get_secret("DEEPSEEK_MODEL", "deepseek-v4-flash") or "deepseek-v4-flash"
        self.timeout = timeout or int(os.getenv("REQUEST_TIMEOUT", "12"))

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def enhance_plan(
        self,
        draft: Any,
        profile: Any,
        context: Any | None = None,
        recent_checkins: list[Any] | None = None,
    ) -> dict[str, Any]:
        if not self.configured:
            raise DeepSeekError("DeepSeek API Key 未配置。")
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是主动型中文减脂助理。用户每天只输入今天可爬坡时间，其他由你根据档案、近 7 天打卡和规则草案直接安排。"
                        "不要反问用户，不要让用户再做选择；给出清楚、可执行的一版今日计划。"
                        "不得提高训练强度，不突破热量、蛋白、安全提醒边界，不提供医疗诊断。"
                        "用户忌口和不喜欢的食物是硬约束，午饭、晚饭、食材、替代建议里都不得出现。必须返回严格 JSON。"
                    ),
                },
                {"role": "user", "content": self._prompt(draft, profile, context, recent_checkins)},
            ],
            "temperature": 0.4,
        }
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
        except Exception as exc:
            raise DeepSeekError(str(exc)) from exc
        return parse_json_object(content)

    def _prompt(self, draft: Any, profile: Any, context: Any | None = None, recent_checkins: list[Any] | None = None) -> str:
        blocked_foods = list(dict.fromkeys(profile.avoid_foods + profile.disliked_foods))
        history = [
            {
                "day": item.day,
                "weight_kg": item.weight_kg,
                "workout_done": item.workout_done,
                "workout_minutes": item.workout_minutes,
                "effort_rpe": item.rpe,
                "lunch_feedback": item.lunch_feedback,
                "dinner_feedback": item.dinner_feedback,
                "notes": item.notes,
            }
            for item in (recent_checkins or [])[:7]
        ]
        return json.dumps(
            {
                "profile": profile.to_dict(),
                "daily_context": context.to_dict() if context else None,
                "recent_checkins": history,
                "blocked_foods_do_not_use": blocked_foods,
                "draft": draft.to_dict(),
                "required_json_schema": {
                    "coach_note": "一句自然中文提醒，像助理直接安排好，不要提问",
                    "workout_note": "解释今天爬坡强度为什么这样安排，要结合可锻炼时间和近期完成情况",
                    "lunch_options": "午饭外食列表，只能是购买/点餐建议，不能有烹饪步骤，不能出现 blocked_foods_do_not_use",
                    "dinner_recipe": "晚饭自煮菜谱，必须包含 title/ingredients/steps/structure，不能出现 blocked_foods_do_not_use",
                    "adjustments": "根据今天可锻炼时间、档案和近 7 天记录做出的调整列表",
                },
            },
            ensure_ascii=False,
        )


def parse_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    if not cleaned.startswith("{"):
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("No JSON object found")
        cleaned = cleaned[start : end + 1]
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("JSON response is not an object")
    return data
