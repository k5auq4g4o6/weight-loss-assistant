from __future__ import annotations

import html
import json
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from fatloss.config import save_env_values
from fatloss.deepseek import DeepSeekClient
from fatloss.menu import DINNER_LIBRARY, LUNCH_LIBRARY
from fatloss.models import CheckIn, Profile
from fatloss.planner import PlanEngine, build_plan_view, plan_to_markdown
from fatloss.storage import AssistantStore


st.set_page_config(page_title="减脂计划小助手", page_icon="L", layout="wide", initial_sidebar_state="expanded")


@st.cache_resource
def store() -> AssistantStore:
    return AssistantStore()


def apply_style() -> None:
    st.markdown(
        """
        <style>
        :root {--ink:#172033;--muted:#667085;--line:#d8e0ea;--blue:#1b69d2;--green:#1f8a58;--red:#c2410c;--bg:#f5f7fb;}
        .stApp {background:var(--bg);font-family:Inter,"PingFang SC",system-ui,sans-serif;color:var(--ink);}
        header[data-testid="stHeader"],[data-testid="stToolbar"],.stDeployButton,[data-testid="stDecoration"]{display:none!important;}
        .main .block-container{max-width:1260px;padding:20px 28px 48px;}
        [data-testid="stSidebar"]{background:#132238;border-right:1px solid rgba(255,255,255,.1);}
        [data-testid="stSidebar"] *{color:#edf4ff!important;}
        [data-testid="stSidebar"] label{border-radius:8px;padding:10px 12px;margin:3px 0;}
        [data-testid="stSidebar"] label:has(input:checked){background:#1b69d2!important;}
        .app-head{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;margin-bottom:18px;}
        .title{font-size:31px;font-weight:900;color:#111827;line-height:1.1;margin:0;}
        .subtitle{color:var(--muted);font-size:14px;margin-top:7px;}
        .status-pill{display:inline-flex;border:1px solid var(--line);border-radius:999px;padding:8px 12px;background:white;color:#344054;font-weight:700;font-size:12px;}
        .metric-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:10px 0 14px;}
        .metric-card{background:white;border:1px solid var(--line);border-radius:8px;padding:15px 16px;min-height:92px;}
        .metric-label{color:var(--muted);font-size:12px;font-weight:750;margin-bottom:8px;}
        .metric-value{font-size:25px;font-weight:900;color:#111827;line-height:1.1;}
        .metric-help{color:var(--muted);font-size:12px;margin-top:7px;}
        .plain-card{background:white;border:1px solid var(--line);border-radius:8px;padding:16px 17px;margin:10px 0;}
        .card-title{font-size:18px;font-weight:900;color:#111827;margin-bottom:8px;}
        .small{font-size:12px;color:var(--muted);}
        .note{border-left:4px solid var(--blue);background:#eef5ff;padding:12px 14px;border-radius:6px;color:#26364f;margin:10px 0;}
        .risk{border-left:4px solid var(--red);background:#fff7ed;padding:12px 14px;border-radius:6px;color:#7c2d12;margin:10px 0;}
        .meal-row{border-top:1px solid #e6ebf2;padding:11px 0;}
        .meal-row:first-child{border-top:0;}
        .meal-title{font-weight:850;color:#111827;}
        .tag{display:inline-block;background:#eef5ff;color:#1552a1;border:1px solid #cfe0ff;border-radius:6px;padding:3px 7px;margin:5px 5px 0 0;font-size:11px;font-weight:700;}
        .source-block{background:#111827;color:#f9fafb;border-radius:8px;padding:13px 14px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px;white-space:pre-wrap;}
        .stButton button,.stDownloadButton button{border-radius:7px;background:#1b69d2;color:white;border:0;font-weight:800;}
        .stButton button:hover,.stDownloadButton button:hover{background:#1557b0;color:white;border:0;}
        [data-testid="stDataFrame"]{border:1px solid var(--line);border-radius:8px;overflow:hidden;}
        @media(max-width:760px){.main .block-container{padding:14px 14px 36px}.app-head{display:block}.metric-grid{grid-template-columns:1fr}.title{font-size:26px}.status-pill{margin-top:10px}}
        </style>
        """,
        unsafe_allow_html=True,
    )


def parse_csv_text(value: str) -> list[str]:
    return [item.strip() for item in value.replace("，", ",").split(",") if item.strip()]


def join_items(items: list[str]) -> str:
    return ", ".join(items)


def top_header(profile: Profile | None, client: DeepSeekClient) -> None:
    name = profile.name if profile else "未建档"
    status = "DeepSeek 已配置" if client.configured else "本地规则模式"
    st.markdown(
        f"""
        <div class="app-head">
          <div>
            <div class="title">减脂计划小助手</div>
            <div class="subtitle">{html.escape(name)} · 今日计划、外食午饭、家常晚饭、爬坡打卡</div>
          </div>
          <div class="status-pill">{html.escape(status)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def metric_cards(draft, recent: list[CheckIn]) -> None:
    done_count = sum(1 for item in recent[:7] if item.workout_done)
    avg_hunger = [item.hunger for item in recent[:7] if item.hunger]
    hunger_label = f"{sum(avg_hunger) / len(avg_hunger):.1f}/5" if avg_hunger else "待记录"
    st.markdown(
        f"""
        <div class="metric-grid">
          <div class="metric-card"><div class="metric-label">今日热量范围</div><div class="metric-value">{draft.calorie_range[0]}-{draft.calorie_range[1]}</div><div class="metric-help">kcal，稳健缺口</div></div>
          <div class="metric-card"><div class="metric-label">蛋白目标</div><div class="metric-value">{draft.protein_g} g</div><div class="metric-help">优先分配到午饭和晚饭</div></div>
          <div class="metric-card"><div class="metric-label">近 7 天爬坡</div><div class="metric-value">{done_count}/7</div><div class="metric-help">平均饥饿感 {hunger_label}</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def generate_plan(store_: AssistantStore, use_ai: bool) -> tuple[Any, dict[str, Any]]:
    today = date.today().isoformat()
    profile = store_.get_profile()
    yesterday = store_.latest_checkin_before(today)
    draft = PlanEngine(date.today()).create_draft(profile, yesterday)
    view = build_plan_view(draft, profile, use_ai=use_ai)
    store_.save_plan(today, draft.to_dict(), view, view.get("ai_status", "fallback"))
    st.session_state["today_draft"] = draft
    st.session_state["today_view"] = view
    return draft, view


def current_plan(store_: AssistantStore) -> tuple[Any, dict[str, Any]]:
    if "today_draft" not in st.session_state or "today_view" not in st.session_state:
        return generate_plan(store_, use_ai=False)
    return st.session_state["today_draft"], st.session_state["today_view"]


def render_today(store_: AssistantStore, client: DeepSeekClient) -> None:
    profile = store_.get_profile()
    draft, view = current_plan(store_)
    recent = store_.checkins(14)

    if draft.profile_missing:
        st.warning("档案还缺：" + "、".join(draft.profile_missing) + "。先用保守默认值生成，建议去“设置”补全。")

    metric_cards(draft, recent)

    cols = st.columns([1, 1, 3])
    if cols[0].button("生成本地计划", use_container_width=True):
        draft, view = generate_plan(store_, use_ai=False)
    if cols[1].button("用 DeepSeek 润色", use_container_width=True, disabled=not client.configured):
        with st.spinner("正在让 DeepSeek 把计划整理成更顺口的版本..."):
            draft, view = generate_plan(store_, use_ai=True)
    cols[2].caption("本地规则负责热量、蛋白、训练强度和安全边界；DeepSeek 只做表达和菜单重组。")

    status_map = {"fallback": "本地规则版", "not_configured": "未配置 DeepSeek，本地规则版", "enhanced": "DeepSeek 润色版"}
    st.markdown(f"<div class='note'><b>今日提醒</b><br>{html.escape(str(view.get('coach_note', '')))}<br><span class='small'>{status_map.get(view.get('ai_status'), '本地规则版')}</span></div>", unsafe_allow_html=True)

    workout_rows = [
        {
            "阶段": item.name,
            "分钟": item.minutes,
            "坡度": f"{item.incline_pct:.1f}%",
            "速度": f"{item.speed_kmh:.1f} km/h",
            "体感": item.target_rpe,
        }
        for item in draft.workout
    ]
    left, right = st.columns([1.1, 1])
    with left:
        st.markdown("<div class='plain-card'><div class='card-title'>跑步机爬坡</div>", unsafe_allow_html=True)
        st.write(view.get("workout_note", ""))
        st.dataframe(pd.DataFrame(workout_rows), use_container_width=True, hide_index=True)
        for item in view.get("adjustments", []):
            st.markdown(f"<span class='tag'>{html.escape(str(item))}</span>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
    with right:
        st.markdown("<div class='plain-card'><div class='card-title'>安全边界</div>", unsafe_allow_html=True)
        for note in draft.risk_notes:
            st.markdown(f"<div class='risk'>{html.escape(note)}</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    lunch_col, dinner_col = st.columns(2)
    with lunch_col:
        st.markdown("<div class='plain-card'><div class='card-title'>午饭外食</div>", unsafe_allow_html=True)
        for item in view.get("lunch_options", []):
            if not isinstance(item, dict):
                continue
            tips = item.get("order_tips", [])
            avoids = item.get("avoid_tips", [])
            st.markdown(
                f"""
                <div class="meal-row">
                  <div class="meal-title">{html.escape(str(item.get('title', '午饭选择')))}</div>
                  <div class="small">约 {html.escape(str(item.get('estimate_kcal', '')))} kcal · 蛋白 {html.escape(str(item.get('protein_g', '')))} g · {html.escape(str(item.get('category', '外食')))}</div>
                  <div>{''.join(f"<span class='tag'>{html.escape(str(tip))}</span>" for tip in tips[:3])}</div>
                  <div class="small">{html.escape('；'.join(str(tip) for tip in avoids[:2]))}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

    with dinner_col:
        dinner = view.get("dinner_recipe", {})
        st.markdown("<div class='plain-card'><div class='card-title'>晚饭自煮</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='meal-title'>{html.escape(str(dinner.get('title', '家常晚饭')))}</div>", unsafe_allow_html=True)
        st.caption(f"约 {dinner.get('estimate_kcal', '')} kcal · 蛋白 {dinner.get('protein_g', '')} g · {dinner.get('cook_minutes', '')} 分钟")
        st.write("食材：" + "、".join(str(item) for item in dinner.get("ingredients", [])))
        for index, step in enumerate(dinner.get("steps", []), start=1):
            st.write(f"{index}. {step}")
        structure = dinner.get("structure", {})
        if isinstance(structure, dict):
            for key, value in structure.items():
                st.markdown(f"<span class='tag'>{html.escape(str(key))}: {html.escape(str(value))}</span>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.download_button(
        "下载今日计划 Markdown",
        data=plan_to_markdown(draft, view),
        file_name=f"fatloss-plan-{draft.day}.md",
        mime="text/markdown",
        use_container_width=True,
    )


def render_checkin(store_: AssistantStore) -> None:
    profile = store_.get_profile()
    day = date.today().isoformat()
    existing = store_.get_checkin(day) or CheckIn.today()
    st.subheader("今日打卡")
    with st.form("checkin"):
        weight_default = float(existing.weight_kg or (profile.current_weight_kg if profile and profile.current_weight_kg else 70.0))
        weight_kg = st.number_input("今日体重 kg", min_value=30.0, max_value=250.0, value=weight_default, step=0.1)
        cols = st.columns(4)
        workout_done = cols[0].checkbox("完成爬坡", value=existing.workout_done)
        workout_minutes = cols[1].number_input("爬坡分钟", min_value=0, max_value=180, value=int(existing.workout_minutes), step=5)
        avg_incline = cols[2].number_input("平均坡度 %", min_value=0.0, max_value=20.0, value=float(existing.avg_incline_pct), step=0.5)
        avg_speed = cols[3].number_input("平均速度 km/h", min_value=0.0, max_value=12.0, value=float(existing.avg_speed_kmh), step=0.1)
        rpe = st.slider("训练体感 RPE", 1, 10, int(existing.rpe), help="1 很轻松，10 接近极限")
        cols2 = st.columns(3)
        sleep = cols2[0].slider("睡眠质量", 1, 5, int(existing.sleep_quality))
        fatigue = cols2[1].slider("疲劳感", 1, 5, int(existing.fatigue))
        hunger = cols2[2].slider("饥饿感", 1, 5, int(existing.hunger))
        lunch_feedback = st.text_input("午饭反馈", value=existing.lunch_feedback, placeholder="比如：盖饭吃了半份饭，下午不饿")
        dinner_feedback = st.text_input("晚饭反馈", value=existing.dinner_feedback, placeholder="比如：鸡腿饭好做，但饭可以再少一点")
        notes = st.text_area("其他备注", value=existing.notes, height=90)
        submitted = st.form_submit_button("保存今日打卡", use_container_width=True)
    if submitted:
        checkin = CheckIn(
            day=day,
            weight_kg=weight_kg,
            workout_done=workout_done,
            workout_minutes=int(workout_minutes),
            avg_incline_pct=float(avg_incline),
            avg_speed_kmh=float(avg_speed),
            rpe=int(rpe),
            sleep_quality=int(sleep),
            fatigue=int(fatigue),
            hunger=int(hunger),
            lunch_feedback=lunch_feedback,
            dinner_feedback=dinner_feedback,
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
        frame = pd.DataFrame([item.to_dict() for item in recent])
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
        st.markdown("跑步机默认参数")
        cols5 = st.columns(4)
        incline = cols5[0].number_input("坡度 %", min_value=0.0, max_value=20.0, value=float(profile.treadmill_incline_pct), step=0.5)
        speed = cols5[1].number_input("速度 km/h", min_value=2.0, max_value=10.0, value=float(profile.treadmill_speed_kmh), step=0.1)
        minutes = cols5[2].number_input("总时长 分钟", min_value=15, max_value=120, value=int(profile.treadmill_minutes), step=5)
        usual_rpe = cols5[3].slider("常规体感", 1, 10, int(profile.usual_rpe))
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
            treadmill_incline_pct=float(incline),
            treadmill_speed_kmh=float(speed),
            treadmill_minutes=int(minutes),
            usual_rpe=int(usual_rpe),
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
    top_header(profile, client)
    st.sidebar.markdown("<div style='font-size:22px;font-weight:900;margin:4px 2px 20px;'>减脂助手</div>", unsafe_allow_html=True)
    page = st.sidebar.radio("导航", ["今日计划", "打卡记录", "菜单库", "设置"], label_visibility="collapsed")
    if page == "今日计划":
        render_today(store_, client)
    elif page == "打卡记录":
        render_checkin(store_)
    elif page == "菜单库":
        render_menu_library()
    else:
        render_settings(store_, client)


if __name__ == "__main__":
    main()

