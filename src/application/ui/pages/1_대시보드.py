"""
대시보드 페이지 — 실시간 PLC 모니터링 + AI 어시스턴트
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent.parent))

import os
import time
from datetime import datetime
from typing import Dict, List, Optional

import httpx
import streamlit as st

try:
    from src.config.settings import get_settings
    _API_BASE = get_settings().api_base_url
except Exception:
    _API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")

_TIMEOUT = 30.0

st.set_page_config(page_title="대시보드", page_icon="📊", layout="wide")


# ══════════════════════════════════════════════════════════════════════════════
# 세션 초기화
# ══════════════════════════════════════════════════════════════════════════════

def _init_session() -> None:
    defaults = {
        "chat_messages":    [],
        "plc_data":         None,
        "last_refresh":     0.0,
        "auto_refresh":     False,
        "refresh_interval": 5,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ══════════════════════════════════════════════════════════════════════════════
# 상단: 시스템 상태 바
# ══════════════════════════════════════════════════════════════════════════════

def _render_status_bar() -> None:
    c1, c2, c3, c4, c5 = st.columns([2, 2, 2, 2, 1])

    with c1:
        plc_ok = _check_plc_connection()
        st.metric("PLC 연결", f"{'🟢 정상' if plc_ok else '🔴 단절'}")

    with c2:
        llm_ok = _check_llm_connection()
        st.metric("LLM 서버", f"{'🟢 정상' if llm_ok else '🔴 오프라인'}")

    with c3:
        st.metric("현재 시각", datetime.now().strftime("%H:%M:%S"))

    with c4:
        st.session_state.auto_refresh = st.toggle(
            "🔄 자동 새로고침",
            value=st.session_state.auto_refresh,
            help=f"{st.session_state.refresh_interval}초마다 갱신",
        )

    with c5:
        if st.button("🔄", help="지금 새로고침", use_container_width=True):
            st.session_state.plc_data = _fetch_plc_data()
            st.session_state.last_refresh = time.time()

    if st.session_state.auto_refresh:
        elapsed = time.time() - st.session_state.last_refresh
        if elapsed >= st.session_state.refresh_interval:
            st.session_state.plc_data = _fetch_plc_data()
            st.session_state.last_refresh = time.time()
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# 좌측: PLC 모니터링 패널
# ══════════════════════════════════════════════════════════════════════════════

def _render_monitoring_panel() -> None:
    st.subheader("📊 실시간 모니터링")

    if st.session_state.plc_data is None:
        st.session_state.plc_data = _fetch_plc_data()

    data = st.session_state.plc_data

    if data is None:
        st.warning("⚠️ PLC 데이터를 불러올 수 없습니다.\n\n설정 → 통신 설정에서 PLC 연결 정보를 확인하세요.")
        _render_monitoring_placeholder()
        return

    _render_water_levels(data)
    st.divider()
    _render_pump_status(data)
    st.divider()
    _render_alarms(data)
    st.divider()
    _render_water_level_chart(data)


def _render_water_levels(data: Dict) -> None:
    st.markdown("##### 💧 배수지 수위")
    reservoirs = data.get("reservoirs", [])
    if not reservoirs:
        st.info("배수지 데이터 없음")
        return

    cols = st.columns(len(reservoirs))
    for i, res in enumerate(reservoirs):
        with cols[i]:
            level    = res.get("water_level", 0.0)
            capacity = res.get("capacity", 100.0)
            pct      = (level / capacity * 100) if capacity else 0
            name     = res.get("name", f"배수지 {i+1}")

            if pct >= 90:
                status_color, status_text = "🔴", "위험"
            elif pct >= 75:
                status_color, status_text = "🟡", "주의"
            else:
                status_color, status_text = "🟢", "정상"

            st.metric(label=f"{status_color} {name}", value=f"{level:.1f}m", delta=f"{pct:.0f}% | {status_text}")
            st.progress(min(pct / 100, 1.0))


def _render_pump_status(data: Dict) -> None:
    st.markdown("##### ⚙️ 펌프 상태")
    pumps = data.get("pumps", [])
    if not pumps:
        st.info("펌프 데이터 없음")
        return

    cols = st.columns(len(pumps))
    for i, pump in enumerate(pumps):
        with cols[i]:
            running = pump.get("is_running", False)
            name    = pump.get("name", f"펌프 {i+1}")
            rpm     = pump.get("rpm", 0)
            st.markdown(
                f"""<div style="border:2px solid {'#28a745' if running else '#6c757d'};
                border-radius:8px;padding:12px;text-align:center;
                background:{'#d4edda' if running else '#f8f9fa'};">
                <div style="font-size:24px;">{'🟢' if running else '⚫'}</div>
                <div style="font-weight:bold;">{name}</div>
                <div style="font-size:12px;color:gray;">{'가동 중' if running else '정지'} | {rpm} RPM</div>
                </div>""",
                unsafe_allow_html=True,
            )


def _render_alarms(data: Dict) -> None:
    st.markdown("##### 🔔 알람")
    alarms = data.get("alarms", [])
    if not alarms:
        st.success("✅ 현재 활성 알람 없음")
        return
    icon_map = {"critical": "🔴", "warning": "🟡", "info": "🔵"}
    for alarm in alarms[:5]:
        icon = icon_map.get(alarm.get("severity", "info"), "⚪")
        st.warning(f"{icon} **{alarm.get('title', '알람')}** — {alarm.get('message', '')}")


def _render_water_level_chart(data: Dict) -> None:
    st.markdown("##### 📈 수위 추이 (최근 1시간)")
    history = data.get("history", [])
    if not history:
        st.info("이력 데이터 없음")
        return
    try:
        import pandas as pd
        df = pd.DataFrame(history)
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.set_index("timestamp")
        st.line_chart(df)
    except Exception:
        st.info("차트 렌더링 실패")


def _render_monitoring_placeholder() -> None:
    st.markdown(
        """<div style="border:2px dashed #dee2e6;border-radius:12px;padding:40px;text-align:center;color:#6c757d;">
        <div style="font-size:48px;">📡</div>
        <div style="font-size:18px;margin-top:12px;">PLC 연결 대기 중</div>
        <div style="font-size:14px;margin-top:8px;">설정 → 통신 설정에서<br>PLC IP와 포트를 확인하세요</div>
        </div>""",
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# 우측: AI 채팅 패널
# ══════════════════════════════════════════════════════════════════════════════

def _render_chat_panel() -> None:
    h1, h2 = st.columns([4, 1])
    with h1:
        st.subheader("💬 AI 어시스턴트")
    with h2:
        if st.button("🗑️ 초기화", use_container_width=True):
            st.session_state.chat_messages = []
            st.rerun()

    mode = st.radio("검색 모드", ["💬 일반 대화", "📚 문서 기반 (RAG)"], horizontal=True, label_visibility="collapsed")
    is_rag = "RAG" in mode

    msg_container = st.container(height=480)
    with msg_container:
        if not st.session_state.chat_messages:
            st.markdown(
                """<div style="text-align:center;color:#adb5bd;padding:60px 0;">
                <div style="font-size:36px;">🤖</div>
                <div style="margin-top:8px;">PLC 운영, 수위 현황, 문서 내용에 대해 질문하세요</div>
                </div>""",
                unsafe_allow_html=True,
            )
        for msg in st.session_state.chat_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                if msg["role"] == "assistant" and msg.get("sources"):
                    with st.expander(f"📎 참고 문서 {len(msg['sources'])}개 | ⏱️ {msg.get('latency_ms', 0)}ms", expanded=False):
                        for i, src in enumerate(msg["sources"], 1):
                            st.markdown(f"**{i}. {src['filename']}** p.{src['page_number']} *(유사도 {src['score']:.1%})*")
                            st.caption(src["content"])

    placeholder = "문서 내용에 대해 질문하세요" if is_rag else "배수지 운영 관련 질문을 입력하세요"
    user_input = st.chat_input(placeholder, key="main_chat_input")
    if user_input:
        _handle_chat(user_input, is_rag)


def _handle_chat(question: str, is_rag: bool) -> None:
    st.session_state.chat_messages.append({"role": "user", "content": question})
    history = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.chat_messages[-13:-1]
        if m["role"] in ("user", "assistant")
    ]

    with st.spinner("🤔 답변 생성 중..."):
        try:
            if is_rag:
                resp = httpx.post(f"{_API_BASE}/rag/query", json={"question": question, "top_k": 5, "chat_history": history}, timeout=120.0)
            else:
                resp = httpx.post(f"{_API_BASE}/chat", json={"message": question, "chat_history": history}, timeout=120.0)
            resp.raise_for_status()
            r = resp.json()
            if is_rag:
                st.session_state.chat_messages.append({"role": "assistant", "content": r["answer"], "sources": r.get("sources", []), "latency_ms": r.get("latency_ms", 0)})
            else:
                st.session_state.chat_messages.append({"role": "assistant", "content": r.get("response", r.get("answer", "응답 없음"))})
        except httpx.ConnectError:
            st.session_state.chat_messages.append({"role": "assistant", "content": "❌ API 서버에 연결할 수 없습니다."})
        except Exception as e:
            st.session_state.chat_messages.append({"role": "assistant", "content": f"❌ 오류: {str(e)}"})
    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# API 헬퍼
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_plc_data() -> Optional[Dict]:
    try:
        resp = httpx.get(f"{_API_BASE}/api/hardware/status", timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def _check_plc_connection() -> bool:
    try:
        resp = httpx.get(f"{_API_BASE}/api/hardware/status", timeout=3.0)
        return resp.status_code == 200
    except Exception:
        return False


def _check_llm_connection() -> bool:
    try:
        resp = httpx.get(f"{_API_BASE}/health", timeout=3.0)
        return resp.status_code == 200
    except Exception:
        return False


# ══════════════════════════════════════════════════════════════════════════════
# 진입점
# ══════════════════════════════════════════════════════════════════════════════

_init_session()
_render_status_bar()
st.divider()

col_monitor, col_chat = st.columns([1, 1], gap="large")
with col_monitor:
    _render_monitoring_panel()
with col_chat:
    _render_chat_panel()