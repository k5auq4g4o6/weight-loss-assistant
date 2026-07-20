from __future__ import annotations

import html
import json
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from fatloss.config import save_env_values
from fatloss.deepseek import DeepSeekClient
from fatloss.menu import DINNER_LIBRARY, LUNCH_LIBRARY
from fatloss.models import CheckIn, DailyContext, Profile
from fatloss.planner import PlanEngine, build_plan_view
from fatloss.storage import AssistantStore


st.set_page_config(page_title="减肥助手", page_icon="📈", layout="wide", initial_sidebar_state="collapsed")

PAGE_ITEMS = [
    {"key": "today", "label": "今日"},
    {"key": "record", "label": "记录"},
    {"key": "menu", "label": "菜单"},
    {"key": "profile", "label": "我的"},
]
PAGE_LABELS = {item["key"]: item["label"] for item in PAGE_ITEMS}
PAGE_ALIASES = {item["label"]: item["key"] for item in PAGE_ITEMS}
DAILY_CONTEXT_STATE_KEY = "daily_context_payload"


@st.cache_resource
def store() -> AssistantStore:
    return AssistantStore()


def apply_style() -> None:
    st.markdown(
        """
        <style>
        :root {--ink:#14191f;--muted:#71777f;--line:#e8ebee;--coral:#ff5c4d;--coral-dark:#e94a3d;--mint:#35c99a;--cyan:#35aee8;--yellow:#f5bd48;--bg:#f7f8f9;}
        html,body,[class*="css"]{font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;letter-spacing:0;}
        .stApp{background:var(--bg);color:var(--ink);}
        header[data-testid="stHeader"]{height:0;min-height:0;background:transparent!important;}
        [data-testid="stToolbar"],[data-testid="stToolbarActions"],[data-testid="stStatusWidget"],[data-testid="stAppDeployButton"],[data-testid="manage-app-button"],.stDeployButton,[data-testid="stDecoration"],[class*="_viewerBadge_"],[class*="_profileContainer_"],#MainMenu,footer,[data-testid="stSidebar"],[data-testid="collapsedControl"]{display:none!important;visibility:hidden!important;width:0!important;height:0!important;}
        .stMainBlockContainer,.main .block-container{max-width:980px;padding:30px 24px calc(126px + env(safe-area-inset-bottom));}
        .app-head{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin:0 0 16px;}
        .app-title{font-size:38px;font-weight:900;color:#0c1116;line-height:1.05;margin:0;}
        .app-date{color:var(--muted);font-size:15px;margin-top:9px;}
        .assistant-state{display:inline-flex;align-items:center;gap:7px;background:#fff;border:1px solid var(--line);border-radius:8px;padding:9px 11px;color:#454b52;font-size:12px;font-weight:750;white-space:nowrap;}
        .assistant-state:before{content:"";width:8px;height:8px;border-radius:50%;background:var(--mint);}
        .today-brief{background:#10151b;color:#fff;border-radius:8px;padding:18px 20px;margin:16px 0 14px;}
        .today-brief-kicker{font-size:12px;color:#9ee2e4;font-weight:850;margin-bottom:8px;}
        .today-brief-main{font-size:22px;line-height:1.35;font-weight:900;}
        .today-brief-sub{font-size:13px;line-height:1.6;color:#d7dde3;margin-top:8px;}
        .wellness-scene{height:210px;position:relative;overflow:hidden;border-radius:8px;background:#e9f8fb;margin:8px 0 0;}
        .scene-sun{position:absolute;width:92px;height:92px;border-radius:50%;background:#ffab9d;left:45%;top:30px;}
        .scene-hill{position:absolute;border-radius:50% 50% 0 0;bottom:-62px;}
        .scene-hill.a{width:68%;height:190px;left:-16%;background:#9ee2e4;transform:rotate(8deg);}
        .scene-hill.b{width:72%;height:180px;right:-22%;background:#b9eadb;transform:rotate(-8deg);}
        .scene-hill.c{width:70%;height:105px;left:20%;bottom:-50px;background:#ffe29b;transform:rotate(4deg);}
        .scene-path{position:absolute;width:54px;height:260px;left:49%;top:90px;background:#fff;transform:rotate(60deg);border-radius:50%;}
        .metric-shell{position:relative;z-index:2;background:#fff;border:1px solid var(--line);border-radius:8px;margin:-52px 28px 22px;padding:21px 12px;box-shadow:0 8px 24px rgba(26,42,53,.08);display:grid;grid-template-columns:repeat(3,minmax(0,1fr));}
        .metric-item{min-width:0;text-align:center;padding:0 12px;border-left:1px solid var(--line);}
        .metric-item:first-child{border-left:0;}
        .metric-icon{width:34px;height:34px;border-radius:50%;display:flex;align-items:center;justify-content:center;color:#fff;font-size:17px;font-weight:900;margin:0 auto 7px;}
        .metric-icon.mint{background:var(--mint)}.metric-icon.coral{background:var(--coral)}.metric-icon.cyan{background:var(--cyan)}
        .metric-label{color:#454b52;font-size:13px;font-weight:750;}
        .metric-value{font-size:30px;font-weight:900;line-height:1.15;margin-top:5px;white-space:nowrap;}
        .metric-value.mint{color:var(--mint)}.metric-value.coral{color:var(--coral)}.metric-value.cyan{color:var(--cyan)}
        .metric-unit{font-size:13px;color:#343a40;font-weight:750;margin-left:3px;}
        .daily-prompt{margin:2px 0 4px;}
        .daily-prompt-title{font-size:20px;font-weight:900;color:#12171d;}
        .daily-prompt-copy{font-size:13px;color:var(--muted);margin-top:4px;}
        [data-testid="stForm"]{background:#fff;border:1px solid var(--line);border-radius:8px;padding:17px 18px 10px;box-shadow:none;}
        [data-testid="stSlider"]{padding-top:2px;}
        .section-title{font-size:25px;font-weight:900;color:#10151b;margin:26px 0 12px;}
        .workout-card{background:#fff;border:1px solid var(--line);border-radius:8px;padding:20px;margin:0 0 10px;}
        .workout-top{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;}
        .workout-name{font-size:20px;font-weight:900;color:#11161c;}
        .workout-meta{font-size:13px;color:var(--muted);margin-top:5px;line-height:1.55;}
        .duration-badge{background:#fff1ef;color:var(--coral-dark);border-radius:8px;padding:8px 10px;font-size:13px;font-weight:850;white-space:nowrap;}
        .phase-row{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:16px;}
        .phase-chip{background:#eef8f6;border-radius:8px;padding:10px 11px;color:#263c38;min-width:0;}
        .phase-name{display:block;font-size:13px;font-weight:900;color:#153c37;white-space:nowrap;}
        .phase-detail{display:block;font-size:12px;color:#52645f;line-height:1.4;margin-top:4px;word-break:break-word;}
        .phase-line{display:none;}
        .meal-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-top:12px;}
        .meal-card{position:relative;overflow:hidden;background:#fff;border:1px solid var(--line);border-radius:8px;padding:18px;min-height:160px;}
        .meal-kicker{font-size:13px;color:var(--muted);font-weight:750;}
        .meal-name{font-size:20px;font-weight:900;color:#11161c;margin:9px 74px 5px 0;line-height:1.35;}
        .meal-detail{font-size:14px;color:#50565d;line-height:1.6;margin-right:70px;}
        .meal-art{position:absolute;right:17px;bottom:18px;width:62px;height:62px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:26px;font-weight:900;}
        .meal-art.lunch{background:#fff2cf;color:#bd7818}.meal-art.dinner{background:#ffe6e1;color:#d74e40}
        .assistant-note{display:flex;gap:12px;align-items:flex-start;background:#edf8fb;border:1px solid #d8eef4;border-radius:8px;padding:15px 16px;margin:14px 0 12px;color:#34454b;font-size:14px;line-height:1.6;}
        .assistant-mark{width:30px;height:30px;flex:0 0 30px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:var(--mint);color:#fff;font-weight:900;}
        .trend-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:10px 0 8px;}
        .trend-card{background:#fff;border:1px solid var(--line);border-radius:8px;padding:15px;min-width:0;}
        .trend-label{font-size:12px;color:var(--muted);font-weight:800;}
        .trend-value{font-size:24px;color:#11161c;font-weight:900;line-height:1.25;margin-top:7px;word-break:break-word;}
        .trend-note{font-size:12px;color:#68707a;line-height:1.45;margin-top:5px;}
        .qa-card{background:#fff;border:1px solid var(--line);border-radius:8px;padding:16px;margin:14px 0;}
        .qa-title{font-size:18px;font-weight:900;color:#11161c;margin-bottom:5px;}
        .qa-copy{font-size:13px;color:var(--muted);line-height:1.5;margin-bottom:10px;}
        .qa-answer{background:#edf8fb;border:1px solid #d8eef4;border-radius:8px;padding:12px 13px;margin-top:10px;color:#34454b;font-size:14px;line-height:1.6;}
        .small{font-size:12px;color:var(--muted);}
        .risk{border-left:4px solid var(--coral);background:#fff5f3;padding:12px 14px;border-radius:6px;color:#71342e;margin:8px 0;}
        .tag{display:inline-block;background:#eef8f6;color:#25735f;border-radius:6px;padding:4px 7px;margin:5px 5px 0 0;font-size:11px;font-weight:750;}
        .source-block{background:#181d22;color:#f9fafb;border-radius:8px;padding:13px 14px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px;white-space:pre-wrap;}
        .primary-action-link{display:flex;align-items:center;justify-content:center;width:100%;min-height:42px;border-radius:8px;background:var(--coral);color:#fff!important;text-decoration:none!important;font-size:15px;font-weight:850;margin:10px 0 2px;}
        .primary-action-link:hover{background:var(--coral-dark);color:#fff!important;text-decoration:none!important;}
        .stButton button,.stDownloadButton button,[data-testid="stFormSubmitButton"] button{border-radius:8px;background:var(--coral);color:#fff;border:0;font-weight:850;min-height:42px;}
        .stButton button:hover,.stDownloadButton button:hover,[data-testid="stFormSubmitButton"] button:hover{background:var(--coral-dark);color:#fff;border:0;}
        [data-testid="stDataFrame"]{border:1px solid var(--line);border-radius:8px;overflow:hidden;}
        [data-testid="stExpander"]{background:#fff;border:1px solid var(--line);border-radius:8px!important;overflow:hidden;}
        .bottom-nav{position:fixed;left:50%;right:auto;bottom:0;transform:translateX(-50%);z-index:2147483000;width:min(520px,100vw);box-sizing:border-box;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:4px;background:rgba(255,255,255,.98);border-top:1px solid var(--line);box-shadow:0 -6px 20px rgba(30,38,44,.08);padding:7px 8px calc(7px + env(safe-area-inset-bottom));}
        .bottom-nav-link{min-width:0;min-height:56px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;border-radius:8px;color:#7d8288!important;text-decoration:none!important;font-size:13px;font-weight:850;line-height:1;}
        .bottom-nav-link svg{width:22px;height:22px;flex:0 0 22px;display:block;stroke:currentColor;fill:none;stroke-width:2.35;stroke-linecap:round;stroke-linejoin:round;}
        .bottom-nav-link span{display:block;white-space:nowrap;}
        .bottom-nav-link.active{background:#fff1ef;color:var(--coral)!important;}
        @media(max-width:760px){
          .stMainBlockContainer,.main .block-container{padding:22px 13px calc(128px + env(safe-area-inset-bottom));}
          .app-title{font-size:32px}.app-date{font-size:13px}.assistant-state{padding:8px;font-size:11px}
          .wellness-scene{height:176px}.scene-sun{width:76px;height:76px;top:26px}
          .metric-shell{margin:-42px 10px 18px;padding:16px 4px}.metric-item{padding:0 5px}.metric-value{font-size:24px}.metric-unit{display:block;margin:2px 0 0;font-size:11px}
          .today-brief{padding:16px}.today-brief-main{font-size:20px}
          .section-title{font-size:22px;margin-top:22px}.workout-card{padding:16px}.workout-top{display:grid;grid-template-columns:1fr auto;gap:10px}.workout-name{font-size:18px}
          .phase-row{grid-template-columns:1fr;gap:7px}.phase-chip{display:flex;align-items:center;justify-content:space-between;gap:10px}.phase-detail{text-align:right;margin-top:0}
          .meal-grid,.trend-grid{grid-template-columns:1fr}.meal-card{min-height:138px}.meal-name{font-size:18px}
          .bottom-nav{left:0;right:0;width:100vw;transform:none;gap:2px;padding-left:8px;padding-right:8px;}
          .bottom-nav-link{min-height:54px;font-size:13px;}
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def parse_csv_text(value: str) -> list[str]:
    return [item.strip() for item in value.replace("，", ",").split(",") if item.strip()]


def join_items(items: list[str]) -> str:
    return ", ".join(items)


def active_page_from_query() -> str:
    raw_page = st.query_params.get("page", "today")
    if isinstance(raw_page, list):
        raw_page = raw_page[0] if raw_page else "today"
    page = str(raw_page)
    if page in PAGE_LABELS:
        return page
    return PAGE_ALIASES.get(page, "today")


def nav_icon(page: str) -> str:
    icons = {
        "today": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 10.8 12 3l9 7.8"/><path d="M5.5 10.4V20h13v-9.6"/><path d="M9.5 20v-5h5v5"/></svg>',
        "record": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 6 9 17l-5-5"/><path d="M4 21h16"/></svg>',
        "menu": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h16"/><path d="M4 12h16"/><path d="M4 19h16"/><path d="M8 5v14"/></svg>',
        "profile": '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="8" r="4"/><path d="M4.5 21c1.6-4 4.1-6 7.5-6s5.9 2 7.5 6"/></svg>',
    }
    return icons[page]


def render_navigation(active_page: str) -> None:
    links = []
    for item in PAGE_ITEMS:
        key = item["key"]
        active_class = " active" if key == active_page else ""
        current_attr = ' aria-current="page"' if key == active_page else ""
        links.append(
            f'<a class="bottom-nav-link{active_class}" href="?page={key}" target="_self"{current_attr}>'
            f'{nav_icon(key)}<span>{html.escape(item["label"])}</span></a>'
        )
    st.markdown(f'<nav class="bottom-nav" aria-label="底部导航">{"".join(links)}</nav>', unsafe_allow_html=True)


def render_page_link(label: str, page: str) -> None:
    st.markdown(
        f'<a class="primary-action-link" href="?page={html.escape(page)}" target="_self">{html.escape(label)}</a>',
        unsafe_allow_html=True,
    )


def effort_label_from_rpe(rpe: int) -> str:
    if rpe <= 5:
        return "偏轻松"
    if rpe <= 7:
        return "正好"
    if rpe <= 8:
        return "有点吃力"
    return "太累"


def rpe_from_effort(label: str) -> int:
    return {"偏轻松": 5, "正好": 6, "有点吃力": 8, "太累": 9}.get(label, 6)


def fatigue_from_effort(label: str) -> int:
    return {"偏轻松": 2, "正好": 3, "有点吃力": 4, "太累": 5}.get(label, 3)


def feedback_choice(value: str, options: list[str]) -> str:
    return value if value in options else ("自己写" if value else options[0])


def feedback_value(choice: str, custom: str) -> str:
    if choice == "自己写":
        return custom.strip()
    return choice


def top_header(profile: Profile | None, client: DeepSeekClient) -> None:
    weekday = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"][date.today().weekday()]
    name = profile.name if profile and profile.name else "你"
    status = "AI 助手在线" if client.configured else "基础助手在线"
    st.markdown(
        f"""
        <div class="app-head">
          <div>
            <div class="app-title">减肥助手</div>
            <div class="app-date">{date.today().month}月{date.today().day}日 · {weekday} · {html.escape(name)}，今天我来安排</div>
          </div>
          <div class="assistant-state">{status}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def metric_cards(draft) -> None:
    total_minutes = sum(int(item.minutes) for item in draft.workout)
    main_segment = next((item for item in draft.workout if item.name == "主训练"), draft.workout[0])
    st.markdown(
        f"""
        <div class="wellness-scene" aria-hidden="true">
          <div class="scene-sun"></div>
          <div class="scene-hill a"></div><div class="scene-hill b"></div><div class="scene-hill c"></div>
          <div class="scene-path"></div>
        </div>
        <div class="metric-shell">
          <div class="metric-item">
            <div class="metric-icon mint">↗</div><div class="metric-label">爬坡</div>
            <div class="metric-value mint">{total_minutes}<span class="metric-unit">分钟</span></div>
          </div>
          <div class="metric-item">
            <div class="metric-icon coral">%</div><div class="metric-label">主训练坡度</div>
            <div class="metric-value coral">{main_segment.incline_pct:g}<span class="metric-unit">%</span></div>
          </div>
          <div class="metric-item">
            <div class="metric-icon cyan">›</div><div class="metric-label">主训练速度</div>
            <div class="metric-value cyan">{main_segment.speed_kmh:g}<span class="metric-unit">km/h</span></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def lunch_items(view: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in view.get("lunch_options", []) if isinstance(item, dict)]


def dinner_item(view: dict[str, Any]) -> dict[str, Any]:
    dinner = view.get("dinner_recipe", {})
    return dinner if isinstance(dinner, dict) else {}


def compact_sentence(text: str, fallback: str, limit: int = 48) -> str:
    clean = " ".join(str(text or "").split()) or fallback
    first = clean.split("。")[0].strip()
    if first:
        clean = first + "。"
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1].rstrip() + "..."


def render_today_brief(draft, view: dict[str, Any]) -> None:
    total_minutes = sum(int(item.minutes) for item in draft.workout)
    main_segment = next((item for item in draft.workout if item.name == "主训练"), draft.workout[0])
    lunch = (lunch_items(view) or [{"title": "优先选蛋白质和蔬菜"}])[0]
    dinner = dinner_item(view)
    lunch_title = str(lunch.get("title", "午饭按外食原则点"))
    dinner_title = str(dinner.get("title", "晚饭做一份家常高蛋白菜"))
    coach_note = str(view.get("coach_note", "照着今天的安排做就好。"))
    main = f"今天照这个来：爬坡 {total_minutes} 分钟，坡度 {main_segment.incline_pct:g}%，午饭选 {lunch_title}，晚饭做 {dinner_title}。"
    st.markdown(
        f"""
        <div class="today-brief">
          <div class="today-brief-kicker">今日一句话</div>
          <div class="today-brief-main">{html.escape(main)}</div>
          <div class="today-brief-sub">{html.escape(coach_note)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def parse_day(value: str) -> date | None:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def trend_cards(store_: AssistantStore, profile: Profile | None) -> list[dict[str, str]]:
    today = date.today()
    recent = [item for item in store_.checkins(30) if item]
    week = [item for item in recent if (parsed := parse_day(item.day)) and parsed >= today - timedelta(days=6)]
    workout_done = sum(1 for item in week if item.workout_done)
    workout_minutes = sum(int(item.workout_minutes or 0) for item in week)

    weighted = sorted(
        [(parsed, item.weight_kg) for item in recent if item.weight_kg and (parsed := parse_day(item.day))],
        key=lambda pair: pair[0],
    )
    if len(weighted) >= 2:
        oldest_day, oldest_weight = weighted[0]
        newest_day, newest_weight = weighted[-1]
        delta = float(newest_weight) - float(oldest_weight)
        days = max(1, (newest_day - oldest_day).days)
        weekly_rate = delta / days * 7
        weight_value = f"{delta:+.1f} kg"
        weight_note = f"近 {days} 天变化，先看趋势不看单日波动"
    elif profile and profile.current_weight_kg:
        newest_weight = float(profile.current_weight_kg)
        weekly_rate = 0.0
        weight_value = f"{newest_weight:.1f} kg"
        weight_note = "多打卡几天后会显示趋势"
    else:
        newest_weight = None
        weekly_rate = 0.0
        weight_value = "待记录"
        weight_note = "记录体重后自动更新"

    if profile and profile.target_weight_kg and newest_weight:
        remaining = max(0.0, float(newest_weight) - float(profile.target_weight_kg))
        if remaining <= 0:
            goal_value = "已达标"
            goal_note = "接下来重点是稳定保持"
        elif weekly_rate < -0.05:
            weeks = max(1, int(round(remaining / abs(weekly_rate))))
            goal_value = f"约 {weeks} 周"
            goal_note = "按当前趋势粗略估算"
        else:
            goal_value = f"差 {remaining:.1f} kg"
            goal_note = "先稳定记录 7 天再估算时间"
    else:
        goal_value = "先补档案"
        goal_note = "填写目标体重后会估算"

    return [
        {"label": "本周爬坡", "value": f"{workout_done}/7 天", "note": f"累计 {workout_minutes} 分钟"},
        {"label": "体重趋势", "value": weight_value, "note": weight_note},
        {"label": "目标进度", "value": goal_value, "note": goal_note},
    ]


def render_weekly_trend(store_: AssistantStore, profile: Profile | None) -> None:
    cards = trend_cards(store_, profile)
    cards_html = "".join(
        f"""
        <div class="trend-card">
          <div class="trend-label">{html.escape(card["label"])}</div>
          <div class="trend-value">{html.escape(card["value"])}</div>
          <div class="trend-note">{html.escape(card["note"])}</div>
        </div>
        """
        for card in cards
    )
    st.markdown(
        f"""
        <div class="section-title">本周趋势</div>
        <div class="trend-grid">{cards_html}</div>
        """,
        unsafe_allow_html=True,
    )


def local_coach_answer(question: str, draft, view: dict[str, Any]) -> str:
    total_minutes = sum(int(item.minutes) for item in draft.workout)
    lunch = (lunch_items(view) or [{"title": "一份有蛋白质和蔬菜的外食"}])[0]
    dinner = dinner_item(view)
    if any(keyword in question for keyword in ["麦当劳", "肯德基", "汉堡", "快餐"]):
        return "今天快餐也能处理：选一个主蛋白，饮料换无糖，薯条和甜品先不点，主食正常吃半份。晚上按计划吃清淡高蛋白。"
    if any(keyword in question for keyword in ["没时间", "来不及", "只能练", "很忙"]):
        return f"时间不够就保底做 15-20 分钟爬坡：5 分钟热身，10 分钟主训练，最后慢走。今天不补偿式加练。"
    if any(keyword in question for keyword in ["饿", "馋", "想吃"]):
        return "先加蛋白和蔬菜，不先加零食：无糖酸奶、鸡蛋、豆制品或瘦肉都可以。主食别完全不吃，留半份更稳。"
    return f"先按今日主线走：爬坡 {total_minutes} 分钟，午饭优先 {lunch.get('title', '高蛋白外食')}，晚饭做 {dinner.get('title', '家常高蛋白菜')}。临时变化时优先保蛋白、少油酱、主食半份。"


def answer_mentions_blocked_food(answer: str, profile: Profile) -> bool:
    normalized = answer.lower()
    return any(term.strip().lower() in normalized for term in profile.avoid_foods + profile.disliked_foods if term.strip())


def render_coach_question(store_: AssistantStore, draft, view: dict[str, Any]) -> None:
    st.markdown(
        """
        <div class="qa-card">
          <div class="qa-title">临时情况问助理</div>
          <div class="qa-copy">比如午饭只能吃快餐、今天只能练 20 分钟、突然很饿，都可以直接问。</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.form("coach_question"):
        question = st.text_input("今天遇到什么情况？", placeholder="比如：午饭只能吃麦当劳怎么办？")
        submitted = st.form_submit_button("问助理", use_container_width=True)
    if submitted and question.strip():
        profile = store_.get_profile() or Profile()
        recent = store_.checkins(7)
        client = DeepSeekClient(timeout=10)
        with st.spinner("助理正在想最省心的处理法..."):
            try:
                answer = client.answer_question(question.strip(), profile, draft, view, recent_checkins=recent)
                if answer_mentions_blocked_food(answer, profile):
                    answer = local_coach_answer(question.strip(), draft, view)
            except Exception:
                answer = local_coach_answer(question.strip(), draft, view)
        st.session_state.setdefault("coach_answers", [])
        st.session_state["coach_answers"].insert(0, {"question": question.strip(), "answer": answer})
        st.session_state["coach_answers"] = st.session_state["coach_answers"][:3]

    for item in st.session_state.get("coach_answers", [])[:3]:
        st.markdown(
            f"""
            <div class="qa-answer">
              <b>{html.escape(item["question"])}</b><br>{html.escape(item["answer"])}
            </div>
            """,
            unsafe_allow_html=True,
        )


def generate_plan(store_: AssistantStore, use_ai: bool, context: DailyContext | None = None) -> tuple[Any, dict[str, Any]]:
    today = date.today().isoformat()
    profile = store_.get_profile()
    yesterday = store_.latest_checkin_before(today)
    recent = store_.checkins(14)
    context = context or DailyContext(day=today)
    engine = PlanEngine(date.today())
    try:
        draft = engine.create_draft(profile, yesterday, context, recent_checkins=recent)
    except TypeError as exc:
        if "recent_checkins" not in str(exc):
            raise
        draft = engine.create_draft(profile, yesterday, context)
    try:
        view = build_plan_view(draft, profile, use_ai=use_ai, context=context, recent_checkins=recent)
    except TypeError as exc:
        if "recent_checkins" not in str(exc):
            raise
        view = build_plan_view(draft, profile, use_ai=use_ai, context=context)
    store_.save_plan(today, draft.to_dict(), view, view.get("ai_status", "fallback"))
    st.session_state["today_draft"] = draft
    st.session_state["today_view"] = view
    return draft, view


def current_plan(store_: AssistantStore) -> tuple[Any, dict[str, Any]]:
    if "today_draft" not in st.session_state or "today_view" not in st.session_state:
        return generate_plan(store_, use_ai=False, context=current_daily_context(store_))
    return st.session_state["today_draft"], st.session_state["today_view"]


def current_daily_context(store_: AssistantStore) -> DailyContext:
    saved = DailyContext.from_dict(st.session_state.get(DAILY_CONTEXT_STATE_KEY))
    if saved and saved.day == date.today().isoformat():
        return saved
    checkin = store_.get_checkin(date.today().isoformat())
    if checkin:
        return DailyContext(
            day=checkin.day,
            available_minutes=max(15, checkin.workout_minutes or 35),
        )
    return DailyContext.today()


def render_daily_context_form(store_: AssistantStore) -> tuple[Any, dict[str, Any]]:
    context = current_daily_context(store_)
    with st.form("daily_context_form"):
        st.markdown(
            """
            <div class="daily-prompt">
              <div class="daily-prompt-title">今天能练多久？</div>
              <div class="daily-prompt-copy">只填这个就够了，训练强度和三餐由助手安排。</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        available_minutes = st.slider("可爬坡时间", 15, 90, int(context.available_minutes), step=5, format="%d 分钟")
        submitted = st.form_submit_button("让助手安排今天", use_container_width=True)
    if submitted:
        context = DailyContext(
            day=date.today().isoformat(),
            available_minutes=int(available_minutes),
        )
        st.session_state[DAILY_CONTEXT_STATE_KEY] = context.to_dict()
        with st.spinner("助手正在安排今天..."):
            generate_plan(store_, use_ai=True, context=context)
        st.rerun()
    return current_plan(store_)


def plan_snapshot_payload(draft, view: dict[str, Any]) -> dict[str, Any]:
    lunch = []
    for item in view.get("lunch_options", [])[:3]:
        if isinstance(item, dict):
            lunch.append(
                {
                    "title": str(item.get("title", "午饭选择")),
                    "meta": f"约 {item.get('estimate_kcal', '')} kcal · 蛋白 {item.get('protein_g', '')} g",
                    "tips": [str(tip) for tip in item.get("order_tips", [])[:2]],
                }
            )
    dinner = view.get("dinner_recipe", {})
    if not isinstance(dinner, dict):
        dinner = {}
    return {
        "day": draft.day,
        "calories": f"{draft.calorie_range[0]}-{draft.calorie_range[1]} kcal",
        "protein": f"{draft.protein_g} g",
        "coach_note": str(view.get("coach_note", "")),
        "workout_note": str(view.get("workout_note", "")),
        "workout": [
            f"{item.name} {item.minutes} 分钟 · 坡度 {item.incline_pct:.1f}% · 速度 {item.speed_kmh:.1f} km/h"
            for item in draft.workout
        ],
        "lunch": lunch,
        "dinner": {
            "title": str(dinner.get("title", "家常晚饭")),
            "meta": f"约 {dinner.get('estimate_kcal', '')} kcal · 蛋白 {dinner.get('protein_g', '')} g · {dinner.get('cook_minutes', '')} 分钟",
            "ingredients": [str(item) for item in dinner.get("ingredients", [])[:8]],
            "steps": [str(item) for item in dinner.get("steps", [])[:5]],
        },
        "adjustments": [str(item) for item in view.get("adjustments", [])[:4]],
        "risk_notes": [str(item) for item in draft.risk_notes[:3]],
    }


def render_plan_image_button(draft, view: dict[str, Any]) -> None:
    payload = json.dumps(plan_snapshot_payload(draft, view), ensure_ascii=False).replace("</", "<\\/")
    components.html(
        f"""
        <div class="snapshot-tool">
          <button id="save-plan-image" type="button">保存今日计划图片</button>
          <span id="save-plan-status">点击后可直接保存到手机</span>
        </div>
        <script>
        const planData = {payload};
        const button = document.getElementById("save-plan-image");
        const status = document.getElementById("save-plan-status");
        function drawRoundedRect(ctx, x, y, w, h, r, fill) {{
          ctx.beginPath();
          ctx.moveTo(x + r, y);
          ctx.arcTo(x + w, y, x + w, y + h, r);
          ctx.arcTo(x + w, y + h, x, y + h, r);
          ctx.arcTo(x, y + h, x, y, r);
          ctx.arcTo(x, y, x + w, y, r);
          ctx.closePath();
          ctx.fillStyle = fill;
          ctx.fill();
        }}
        function wrapText(ctx, text, x, y, maxWidth, lineHeight) {{
          const chars = String(text || "").split("");
          let line = "";
          for (const ch of chars) {{
            const test = line + ch;
            if (ctx.measureText(test).width > maxWidth && line) {{
              ctx.fillText(line, x, y);
              y += lineHeight;
              line = ch;
            }} else {{
              line = test;
            }}
          }}
          if (line) {{
            ctx.fillText(line, x, y);
            y += lineHeight;
          }}
          return y;
        }}
        function section(ctx, title, lines, y) {{
          ctx.fillStyle = "#172033";
          ctx.font = "700 34px -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Noto Sans CJK SC', sans-serif";
          ctx.fillText(title, 64, y);
          y += 42;
          ctx.font = "400 27px -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Noto Sans CJK SC', sans-serif";
          ctx.fillStyle = "#344054";
          for (const line of lines.filter(Boolean)) {{
            y = wrapText(ctx, line, 64, y, 952, 39);
            y += 8;
          }}
          return y + 28;
        }}
        function makeCanvas() {{
          const width = 1080;
          const temp = document.createElement("canvas");
          temp.width = width;
          temp.height = 2600;
          const ctx = temp.getContext("2d");
          ctx.fillStyle = "#f7f8f9";
          ctx.fillRect(0, 0, temp.width, temp.height);
          drawRoundedRect(ctx, 32, 32, 1016, 220, 28, "#ff5c4d");
          ctx.fillStyle = "#ffffff";
          ctx.font = "800 54px -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Noto Sans CJK SC', sans-serif";
          ctx.fillText("今日减脂计划", 64, 104);
          ctx.font = "400 28px -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Noto Sans CJK SC', sans-serif";
          ctx.fillStyle = "#fff1ef";
          ctx.fillText(planData.day, 64, 150);
          ctx.font = "700 32px -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Noto Sans CJK SC', sans-serif";
          ctx.fillStyle = "#ffffff";
          ctx.fillText("热量 " + planData.calories, 64, 206);
          ctx.fillText("蛋白 " + planData.protein, 560, 206);
          let y = 310;
          y = section(ctx, "今日提醒", [planData.coach_note], y);
          y = section(ctx, "跑步机爬坡", [planData.workout_note, ...planData.workout], y);
          const lunchLines = [];
          for (const item of planData.lunch) {{
            lunchLines.push("• " + item.title + "｜" + item.meta);
            for (const tip of item.tips || []) lunchLines.push("  " + tip);
          }}
          y = section(ctx, "午饭外食", lunchLines, y);
          const dinnerLines = [
            "• " + planData.dinner.title + "｜" + planData.dinner.meta,
            "食材：" + (planData.dinner.ingredients || []).join("、"),
            ...(planData.dinner.steps || []).map((step, idx) => (idx + 1) + ". " + step)
          ];
          y = section(ctx, "晚饭自煮", dinnerLines, y);
          y = section(ctx, "今日调整", planData.adjustments.map(item => "• " + item), y);
          y = section(ctx, "安全边界", planData.risk_notes.map(item => "• " + item), y);
          ctx.fillStyle = "#667085";
          ctx.font = "400 23px -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Noto Sans CJK SC', sans-serif";
          ctx.fillText("减脂计划小助手 · 普通成年人习惯计划，不替代医疗建议", 64, y + 12);
          const finalCanvas = document.createElement("canvas");
          finalCanvas.width = width;
          finalCanvas.height = Math.min(2600, y + 72);
          finalCanvas.getContext("2d").drawImage(temp, 0, 0);
          return finalCanvas;
        }}
        async function savePlanImage() {{
          status.textContent = "正在生成图片...";
          const canvas = makeCanvas();
          canvas.toBlob(async blob => {{
            const fileName = `fatloss-plan-${{planData.day}}.png`;
            const file = new File([blob], fileName, {{ type: "image/png" }});
            try {{
              if (navigator.canShare && navigator.canShare({{ files: [file] }})) {{
                await navigator.share({{ files: [file], title: "今日减脂计划" }});
                status.textContent = "已打开手机分享窗口";
                return;
              }}
            }} catch (error) {{}}
            const url = URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.href = url;
            link.download = fileName;
            link.click();
            status.textContent = "图片已生成，可在下载中查看";
            setTimeout(() => URL.revokeObjectURL(url), 30000);
          }}, "image/png", 0.96);
        }}
        button.addEventListener("click", savePlanImage);
        </script>
        <style>
        .snapshot-tool {{
          display:flex;
          gap:10px;
          align-items:center;
          flex-wrap:wrap;
          font-family:-apple-system,BlinkMacSystemFont,'PingFang SC',sans-serif;
          margin:0;
        }}
        #save-plan-image {{
          appearance:none;
          border:0;
          border-radius:8px;
          background:#ff5c4d;
          color:white;
          padding:12px 16px;
          font-size:15px;
          font-weight:800;
          cursor:pointer;
        }}
        #save-plan-status {{ color:#667085; font-size:13px; }}
        @media(max-width:520px) {{
          #save-plan-image {{ width:100%; }}
          #save-plan-status {{ display:block; width:100%; text-align:center; }}
        }}
        </style>
        """,
        height=78,
    )


def render_today(store_: AssistantStore) -> None:
    profile = store_.get_profile()
    draft, view = current_plan(store_)
    render_today_brief(draft, view)
    metric_cards(draft)
    draft, view = render_daily_context_form(store_)

    if draft.profile_missing:
        st.warning("个人档案还缺：" + "、".join(draft.profile_missing) + "。当前先按保守方案安排，去“我的”补全后会更准确。")

    total_minutes = sum(int(item.minutes) for item in draft.workout)
    phase_html = "".join(
        f"""
        <div class="phase-chip">
          <span class="phase-name">{html.escape(item.name)} {item.minutes} 分</span>
          <span class="phase-detail">坡度 {item.incline_pct:g}% · {item.speed_kmh:g} km/h</span>
        </div>
        """
        for item in draft.workout
    )
    adjustment = next((str(item) for item in view.get("adjustments", []) if item), "已按你的档案和近期记录安排")
    workout_note = compact_sentence(
        str(view.get("workout_note", "")),
        "按热身、主训练、冷却顺序完成。",
        limit=42,
    )
    adjustment_note = compact_sentence(adjustment, "今天按可用时间安排，不加练。", limit=44)
    st.markdown(
        f"""
        <div class="section-title">今日安排</div>
        <div class="workout-card">
          <div class="workout-top">
            <div>
              <div class="workout-name">跑步机爬坡</div>
              <div class="workout-meta">{html.escape(workout_note)}</div>
            </div>
            <div class="duration-badge">共 {total_minutes} 分钟</div>
          </div>
          <div class="phase-row">{phase_html}</div>
          <div class="workout-meta">{html.escape(adjustment_note)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    render_page_link("完成后去打卡", "record")

    lunches = lunch_items(view)
    lunch = lunches[0] if lunches else {"title": "优先选一份蛋白质和蔬菜", "category": "外食", "order_tips": []}
    lunch_tips = [str(item) for item in lunch.get("order_tips", []) if item]
    lunch_detail = " · ".join(lunch_tips[:2]) or "少油少酱，主食吃半份"
    dinner = dinner_item(view)
    dinner_structure = dinner.get("structure", {}) if isinstance(dinner.get("structure", {}), dict) else {}
    dinner_detail = " · ".join(str(value) for value in list(dinner_structure.values())[:2] if value)
    if not dinner_detail:
        dinner_detail = f"约 {dinner.get('cook_minutes', 30)} 分钟做好"

    st.markdown(
        f"""
        <div class="meal-grid">
          <div class="meal-card">
            <div class="meal-kicker">午饭 · 外食</div>
            <div class="meal-name">{html.escape(str(lunch.get('title', '午饭选择')))}</div>
            <div class="meal-detail">{html.escape(lunch_detail)}<br>约 {html.escape(str(lunch.get('estimate_kcal', '')))} kcal · 蛋白 {html.escape(str(lunch.get('protein_g', '')))} g</div>
            <div class="meal-art lunch">午</div>
          </div>
          <div class="meal-card">
            <div class="meal-kicker">晚饭 · 自煮</div>
            <div class="meal-name">{html.escape(str(dinner.get('title', '家常晚饭')))}</div>
            <div class="meal-detail">{html.escape(dinner_detail)}<br>约 {html.escape(str(dinner.get('estimate_kcal', '')))} kcal · 蛋白 {html.escape(str(dinner.get('protein_g', '')))} g</div>
            <div class="meal-art dinner">晚</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    render_weekly_trend(store_, profile)

    detail_left, detail_right = st.columns(2)
    with detail_left:
        with st.expander("查看午饭备选和点单方法"):
            for item in lunches:
                st.markdown(f"**{item.get('title', '午饭选择')}** · 约 {item.get('estimate_kcal', '')} kcal")
                for tip in item.get("order_tips", [])[:3]:
                    st.write("- " + str(tip))
    with detail_right:
        with st.expander("查看晚饭食材和做法"):
            ingredients = [str(item) for item in dinner.get("ingredients", [])]
            if ingredients:
                st.write("食材：" + "、".join(ingredients))
            for index, step in enumerate(dinner.get("steps", []), start=1):
                st.write(f"{index}. {step}")

    ai_label = "AI 已结合你的情况安排" if view.get("ai_status") == "enhanced" else "助手已按安全规则安排"
    st.markdown(
        f"""
        <div class="assistant-note">
          <div class="assistant-mark">助</div>
          <div><b>{ai_label}</b><br>{html.escape(str(view.get('coach_note', '照着今天的安排做就好。')))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    render_coach_question(store_, draft, view)

    render_plan_image_button(draft, view)

    with st.expander("安全提醒"):
        for note in draft.risk_notes:
            st.markdown(f"<div class='risk'>{html.escape(note)}</div>", unsafe_allow_html=True)


def render_checkin(store_: AssistantStore) -> None:
    profile = store_.get_profile()
    day = date.today().isoformat()
    existing = store_.get_checkin(day) or CheckIn.today()
    st.subheader("今日打卡")
    with st.form("checkin"):
        weight_default = float(existing.weight_kg or (profile.current_weight_kg if profile and profile.current_weight_kg else 70.0))
        weight_kg = st.number_input("今日体重 kg", min_value=30.0, max_value=250.0, value=weight_default, step=0.1)
        cols = st.columns(3)
        workout_done = cols[0].checkbox("完成爬坡", value=existing.workout_done)
        workout_minutes = cols[1].number_input("实际爬坡分钟", min_value=0, max_value=180, value=int(existing.workout_minutes), step=5)
        effort_options = ["正好", "偏轻松", "有点吃力", "太累"]
        effort_default = effort_label_from_rpe(int(existing.rpe))
        effort = cols[2].selectbox("练完感觉", effort_options, index=effort_options.index(effort_default))
        lunch_options = ["按计划，挺稳", "主食吃多了", "油/酱偏多", "蛋白不够", "没按计划", "自己写"]
        dinner_options = ["按计划，挺稳", "主食吃多了", "油/酱偏多", "蛋白不够", "太撑了", "没按计划", "自己写"]
        cols_feedback = st.columns(2)
        lunch_choice = cols_feedback[0].selectbox(
            "午饭反馈",
            lunch_options,
            index=lunch_options.index(feedback_choice(existing.lunch_feedback, lunch_options)),
        )
        dinner_choice = cols_feedback[1].selectbox(
            "晚饭反馈",
            dinner_options,
            index=dinner_options.index(feedback_choice(existing.dinner_feedback, dinner_options)),
        )
        lunch_custom = st.text_input(
            "午饭补一句",
            value=existing.lunch_feedback if lunch_choice == "自己写" else "",
            placeholder="可不填",
        )
        dinner_custom = st.text_input(
            "晚饭补一句",
            value=existing.dinner_feedback if dinner_choice == "自己写" else "",
            placeholder="可不填",
        )
        notes = st.text_input("备注", value=existing.notes, placeholder="比如：今天加班、身体不舒服，可不填")
        submitted = st.form_submit_button("保存今日打卡", use_container_width=True)
    if submitted:
        rpe = rpe_from_effort(effort) if workout_done else 6
        checkin = CheckIn(
            day=day,
            weight_kg=weight_kg,
            workout_done=workout_done,
            workout_minutes=int(workout_minutes),
            avg_incline_pct=float(existing.avg_incline_pct),
            avg_speed_kmh=float(existing.avg_speed_kmh),
            rpe=int(rpe),
            sleep_quality=3,
            fatigue=fatigue_from_effort(effort) if workout_done else 3,
            hunger=3,
            lunch_feedback=feedback_value(lunch_choice, lunch_custom),
            dinner_feedback=feedback_value(dinner_choice, dinner_custom),
            notes=notes,
        )
        store_.save_checkin(checkin)
        if profile:
            profile.current_weight_kg = weight_kg
            store_.save_profile(profile)
        st.session_state.pop("today_draft", None)
        st.session_state.pop("today_view", None)
        st.success("已保存。明天的计划会参考这次打卡。")

    recent = store_.checkins(30)
    if recent:
        frame = pd.DataFrame(
            [
                {
                    "日期": item.day,
                    "体重 kg": item.weight_kg,
                    "完成爬坡": "是" if item.workout_done else "否",
                    "实际分钟": item.workout_minutes,
                    "练完感觉": effort_label_from_rpe(item.rpe),
                    "午饭反馈": item.lunch_feedback,
                    "晚饭反馈": item.dinner_feedback,
                    "备注": item.notes,
                }
                for item in recent
            ]
        )
        st.subheader("最近记录")
        st.dataframe(frame, use_container_width=True, hide_index=True)


def render_menu_library() -> None:
    st.subheader("午饭外食库")
    st.dataframe(pd.DataFrame([item.to_dict() for item in LUNCH_LIBRARY]), use_container_width=True, hide_index=True)
    st.subheader("晚饭自煮库")
    st.dataframe(pd.DataFrame([item.to_dict() for item in DINNER_LIBRARY]), use_container_width=True, hide_index=True)


def render_settings(store_: AssistantStore, client: DeepSeekClient) -> None:
    st.subheader("个人档案")
    profile = store_.get_profile() or Profile()
    with st.form("profile"):
        cols = st.columns(3)
        name = cols[0].text_input("昵称", value=profile.name)
        sex = cols[1].selectbox("性别", ["female", "male"], index=0 if profile.sex != "male" else 1, format_func=lambda x: "女" if x == "female" else "男")
        age = cols[2].number_input("年龄", min_value=16, max_value=90, value=int(profile.age or 30), step=1)
        cols2 = st.columns(3)
        height_cm = cols2[0].number_input("身高 cm", min_value=120.0, max_value=230.0, value=float(profile.height_cm or 165.0), step=0.5)
        current_weight = cols2[1].number_input("当前体重 kg", min_value=30.0, max_value=250.0, value=float(profile.current_weight_kg or 70.0), step=0.1)
        target_weight = cols2[2].number_input("目标体重 kg", min_value=30.0, max_value=250.0, value=float(profile.target_weight_kg or max(30.0, current_weight - 5)), step=0.1)
        lunch_budget = st.slider("午饭预算", 15, 100, int(profile.lunch_budget), step=5)
        lunch_places = st.multiselect(
            "常见午饭场景",
            ["食堂", "盖饭", "面/粉", "麻辣烫", "便利店", "快餐", "小店"],
            default=profile.lunch_places or ["食堂", "盖饭", "面/粉", "麻辣烫", "便利店", "快餐", "小店"],
        )
        cols3 = st.columns(2)
        avoid_foods = cols3[0].text_input("忌口/过敏", value=join_items(profile.avoid_foods), placeholder="用逗号分隔")
        disliked_foods = cols3[1].text_input("不喜欢的食物", value=join_items(profile.disliked_foods), placeholder="用逗号分隔")
        dinner_minutes = st.slider("晚饭最多烹饪时间", 10, 60, int(profile.dinner_minutes), step=5)
        cols4 = st.columns(2)
        cookware = cols4[0].text_input("可用厨具", value=join_items(profile.cookware))
        taste_preferences = cols4[1].text_input("口味偏好", value=join_items(profile.taste_preferences))
        submitted = st.form_submit_button("保存档案", use_container_width=True)
    if submitted:
        saved = Profile(
            name=name.strip() or "我",
            age=int(age),
            sex=sex,
            height_cm=float(height_cm),
            current_weight_kg=float(current_weight),
            target_weight_kg=float(target_weight),
            pace="steady",
            lunch_budget=int(lunch_budget),
            lunch_places=lunch_places,
            avoid_foods=parse_csv_text(avoid_foods),
            disliked_foods=parse_csv_text(disliked_foods),
            dinner_minutes=int(dinner_minutes),
            cookware=parse_csv_text(cookware),
            taste_preferences=parse_csv_text(taste_preferences),
        )
        store_.save_profile(saved)
        st.session_state.pop("today_draft", None)
        st.session_state.pop("today_view", None)
        st.success("档案已保存。")

    st.subheader("DeepSeek 设置")
    st.caption("Streamlit Cloud 推荐在应用 Settings 的 Secrets 里配置；本地运行可以在这里保存到 .env。")
    st.write("当前状态：" + ("已配置" if client.configured else "未配置"))
    with st.form("deepseek"):
        key = st.text_input("DEEPSEEK_API_KEY", type="password", placeholder="本地运行时可填写并保存")
        base_url = st.text_input("DEEPSEEK_API_BASE", value=client.base_url or "https://api.deepseek.com")
        model = st.text_input("DEEPSEEK_MODEL", value=client.model or "deepseek-v4-flash")
        saved = st.form_submit_button("保存到本机 .env", use_container_width=True)
    if saved:
        values = {"DEEPSEEK_API_BASE": base_url, "DEEPSEEK_MODEL": model}
        if key.strip():
            values["DEEPSEEK_API_KEY"] = key.strip()
        save_env_values(values)
        st.success("已保存到本机 .env。Streamlit Cloud 请改用 Secrets。")

    st.subheader("手机和云端备份")
    backup = store_.export_backup()
    st.download_button(
        "导出备份 JSON",
        data=json.dumps(backup, ensure_ascii=False, indent=2),
        file_name=f"fatloss-backup-{date.today().isoformat()}.json",
        mime="application/json",
        use_container_width=True,
    )
    uploaded = st.file_uploader("导入备份 JSON", type=["json"])
    if uploaded and st.button("确认导入备份", use_container_width=True):
        payload = json.loads(uploaded.getvalue().decode("utf-8"))
        store_.import_backup(payload)
        st.success("备份已导入。")

    st.subheader("Streamlit Cloud Secrets")
    st.markdown(
        """
        <div class="source-block">DEEPSEEK_API_KEY = "你的 Key"
DEEPSEEK_API_BASE = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-v4-flash"</div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("部署时 Main file path 填：weight-loss-assistant/app.py。手机打开 Streamlit Cloud 分配的网址即可使用。")


def main() -> None:
    apply_style()
    store_ = store()
    client = DeepSeekClient()
    profile = store_.get_profile()
    page = active_page_from_query()
    top_header(profile, client)
    render_navigation(page)
    if page == "today":
        render_today(store_)
    elif page == "record":
        render_checkin(store_)
    elif page == "menu":
        render_menu_library()
    else:
        render_settings(store_, client)


if __name__ == "__main__":
    main()
