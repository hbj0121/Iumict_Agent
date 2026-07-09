"""
수위 모니터링 페이지 — /api/hardware/water-level 엔드포인트 사용
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent.parent))

import os
import time
import httpx
import streamlit as st

try:
    from src.config.settings import get_settings
    _API_BASE = get_settings().api_base_url
except Exception:
    _API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")

_HW_URL = f"{_API_BASE}/api/hardware"

st.set_page_config(page_title="수위 모니터링", page_icon="💧", layout="wide")
st.title("💧 수위 모니터링")


def fetch_water_level(reservoir_id: str):
    try:
        resp = httpx.get(f"{_HW_URL}/water-level/{reservoir_id}", timeout=5.0)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def fetch_all_water_levels():
    try:
        resp = httpx.get(f"{_HW_URL}/water-level", timeout=5.0)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


# ── 컨트롤 ───────────────────────────────────────────────────────────────────
col_sel, col_refresh, col_auto = st.columns([3, 1, 2])

with col_sel:
    view_mode = st.radio("조회 방식", ["전체 배수지", "개별 배수지"], horizontal=True)

with col_refresh:
    manual_refresh = st.button("🔄 새로고침", use_container_width=True)

with col_auto:
    auto_refresh = st.toggle("⏱️ 자동 새로고침 (5초)", value=False)

st.divider()

# ── 데이터 조회 및 표시 ───────────────────────────────────────────────────────
if view_mode == "전체 배수지":
    data = fetch_all_water_levels()

    if data is None:
        st.error("❌ 수위 데이터를 불러올 수 없습니다. API 서버 또는 하드웨어 연결을 확인하세요.")
    else:
        cols = st.columns(len(data))
        for col, (reservoir_id, reading) in zip(cols, data.items()):
            with col:
                st.subheader(f"🏞️ {reservoir_id.upper()}")
                st.metric("현재 수위", f"{reading['level_meters']:.2f} m")
                st.metric("센서 상태", reading['sensor_status'])
                st.caption(f"측정 시각: {reading['measured_at'][11:19]}")

else:
    reservoir_id = st.selectbox(
        "배수지 선택",
        ["gagok", "haeryong"],
        format_func=lambda x: x.upper()
    )

    data = fetch_water_level(reservoir_id)

    if data is None:
        st.error("❌ 수위 데이터를 불러올 수 없습니다.")
    else:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("현재 수위", f"{data['level_meters']:.2f} m")
        with c2:
            st.metric("센서 상태", data['sensor_status'])
        with c3:
            st.metric("측정 시각", data['measured_at'][11:19])

        st.line_chart([data['level_meters']] * 10)

# ── 자동 새로고침 ─────────────────────────────────────────────────────────────
if auto_refresh:
    time.sleep(5)
    st.rerun()