from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
ENV_PATH = ROOT / ".env"


def load_env_file(path: Path = ENV_PATH) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def save_env_values(values: Mapping[str, str], path: Path = ENV_PATH) -> None:
    existing: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                existing[key.strip()] = value.strip()
    for key, value in values.items():
        if value.strip():
            existing[key] = value.strip()
            os.environ[key] = value.strip()
    path.write_text("\n".join(f"{key}={value}" for key, value in sorted(existing.items())) + "\n", encoding="utf-8")


def get_secret(name: str, default: str = "") -> str:
    env_value = os.getenv(name, "").strip()
    if env_value:
        return env_value
    try:
        import streamlit as st

        value = st.secrets.get(name, default)
        return str(value).strip() if value else default
    except Exception:
        return default

