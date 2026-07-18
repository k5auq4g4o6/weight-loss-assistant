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
        self.timeout = timeout or int(os.getenv("REQUEST_TIMEOUT", "30"))

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def enhance_plan(self, draft: Any, profile: Any) -> dict[str, Any]:
        if not self.configured:
            raise DeepSeekError("DeepSeek API Key 未配置。")
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是谨慎的中文减脂计划助手。只润色和重组用户提供的计划，不提高训练强度，"
                        "不突破热量、蛋白、安全提醒边界，不提供医疗诊断。必须返回严格 JSON。"
                    ),
                },
                {"role": "user", "content": self._prompt(draft, profile)},
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

    def _prompt(self, draft: Any, profile: Any) -> str:
        return json.dumps(
            {
                "profile": profile.to_dict(),
                "draft": draft.to_dict(),
                "required_json_schema": {
                    "coach_note": "一句自然中文提醒，鼓励但不鸡血",
                    "workout_note": "解释今天爬坡强度为什么这样安排",
                    "lunch_options": "午饭外食列表，只能是购买/点餐建议，不能有烹饪步骤",
                    "dinner_recipe": "晚饭自煮菜谱，必须包含 title/ingredients/steps/structure",
                    "adjustments": "今天相比昨天的调整列表",
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

