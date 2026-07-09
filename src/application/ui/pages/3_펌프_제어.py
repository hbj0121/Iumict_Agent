"""
펌프 제어 페이지 — /api/hardware/pump 엔드포인트 사용
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent.parent))

import os
import httpx
import streamlit as st

try:
    from src.config.settings import get_settings
    _API_BASE = get_settings().api_base_url
except Exception:
    _API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")

_HW_URL = f"{_API_BASE}/api/hardware"

st.set_page_config(page_title="펌프 제어", page_icon="🔧", layout="wide")
st.title("🔧 펌프 제어")


def fetch_pump_status(reservoir_id: str):
    try:
        resp = httpx.get(f"{_HW_URL}/pump/{reservoir_id}/status", timeout=5.0)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def send_pump_command(reservoir_id: str, action: str) -> tuple[bool, str]:
    try:
        resp = httpx.post(
            f"{_HW_URL}/pump/{reservoir_id}/control",
            json={"action": action, "requested_by": "streamlit_user"},
            timeout=10.0,
        )
        resp.raise_for_status()
        r = resp.json()
        return True, r.get("message", "명령 전송 완료")
    except httpx.HTTPStatusError as e:
        detail = e.response.json().get("detail", str(e))
        return False, detail
    except Exception as e:
        return False, str(e)


# ── 배수지 선택 ───────────────────────────────────────────────────────────────
reservoir_id = st.selectbox(
    "배수지 선택",
    ["gagok", "haeryong"],
    format_func=lambda x: x.upper()
)

st.divider()

# ── 현재 펌프 상태 ────────────────────────────────────────────────────────────
status = fetch_pump_status(reservoir_id)

if status is None:
    st.error("❌ 펌프 상태를 불러올 수 없습니다. API 서버 또는 하드웨어 연결을 확인하세요.")
else:
    c1, c2, c3 = st.columns(3)
    with c1:
        if status["is_running"]:
            st.success("🟢 펌프 가동 중")
        else:
            st.info("⚪ 펌프 정지")
    with c2:
        st.metric("운전 모드", status["mode"])
    with c3:
        last = status.get("last_changed")
        st.metric("마지막 변경", last[11:19] if last else "-")

st.divider()

# ── 제어 버튼 ─────────────────────────────────────────────────────────────────
st.subheader("펌프 제어")
b1, b2, b3 = st.columns(3)

with b1:
    if st.button("▶️ 시작", use_container_width=True, type="primary"):
        ok, msg = send_pump_command(reservoir_id, "start")
        (st.success if ok else st.error)(f"{'✅' if ok else '❌'} {msg}")
        if ok:
            st.rerun()

with b2:
    if st.button("⏹️ 정지", use_container_width=True):
        ok, msg = send_pump_command(reservoir_id, "stop")
        (st.success if ok else st.error)(f"{'✅' if ok else '❌'} {msg}")
        if ok:
            st.rerun()

with b3:
    if st.button("🤖 자동", use_container_width=True):
        ok, msg = send_pump_command(reservoir_id, "auto")
        (st.success if ok else st.error)(f"{'✅' if ok else '❌'} {msg}")
        if ok:
            st.rerun()