"""
src/application/ui/pages/main_dashboard.py

메인 대시보드 페이지
- 좌측: PLC 실시간 모니터링 (수위, 펌프 상태, 알람)
- 우측: AI 채팅 (RAG 기반 문서 질의 + 일반 대화)
"""
from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Dict, List, Optional

import httpx
import streamlit as st

try:
    from src.config.settings import get_settings
    _API_BASE = get_settings().API_BASE_URL
except Exception:
    _API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")

_TIMEOUT = 30.0


# ══════════════════════════════════════════════════════════════════════════════
# 진입점
# ══════════════════════════════════════════════════════════════════════════════

def render_main_dashboard() -> None:
    _init_session()

    # 상단 상태 바
    _render_status_bar()

    st.divider()

    # 메인 2열 레이아웃
    col_monitor, col_chat = st.columns([1, 1], gap="large")

    with col_monitor:
        _render_monitoring_panel()

    with col_chat:
        _render_chat_panel()


# ══════════════════════════════════════════════════════════════════════════════
# 세션 초기화
# ══════════════════════════════════════════════════════════════════════════════

def _init_session() -> None:
    defaults = {
        "chat_messages":    [],       # 채팅 메시지 히스토리
        "plc_data":         None,     # 마지막으로 받은 PLC 데이터
        "last_refresh":     0.0,      # 마지막 새로고침 시각
        "auto_refresh":     False,    # 자동 새로고침 여부
        "refresh_interval": 5,        # 새로고침 주기 (초)
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ══════════════════════════════════════════════════════════════════════════════
# 상단: 시스템 상태 바
# ══════════════════════════════════════════════════════════════════════════════

def _render_status_bar() -> None:
    c1, c2, c3, c4, c5 = st.columns([2, 2, 2, 2, 1])

    # PLC 연결 상태
    with c1:
        plc_ok = _check_plc_connection()
        icon = "🟢" if plc_ok else "🔴"
        st.metric("PLC 연결", f"{icon} {'정상' if plc_ok else '단절'}")

    # LLM 연결 상태
    with c2:
        llm_ok = _check_llm_connection()
        icon = "🟢" if llm_ok else "🔴"
        st.metric("LLM 서버", f"{icon} {'정상' if llm_ok else '오프라인'}")

    # 현재 시각
    with c3:
        st.metric("현재 시각", datetime.now().strftime("%H:%M:%S"))

    # 자동 새로고침 토글
    with c4:
        st.session_state.auto_refresh = st.toggle(
            "🔄 자동 새로고침",
            value=st.session_state.auto_refresh,
            help=f"{st.session_state.refresh_interval}초마다 모니터링 갱신",
        )

    # 수동 새로고침
    with c5:
        if st.button("🔄", help="지금 새로고침", use_container_width=True):
            st.session_state.plc_data = _fetch_plc_data()
            st.session_state.last_refresh = time.time()

    # 자동 새로고침 처리
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

    # 데이터 없으면 최초 로드
    if st.session_state.plc_data is None:
        st.session_state.plc_data = _fetch_plc_data()

    data = st.session_state.plc_data

    if data is None:
        st.warning(
            "⚠️ PLC 데이터를 불러올 수 없습니다.\n\n"
            "설정 → 통신 설정에서 PLC 연결 정보를 확인하세요."
        )
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
    """수위 메트릭 카드"""
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

            # 수위에 따른 색상
            if pct >= 90:
                status_color = "🔴"
                status_text  = "위험"
            elif pct >= 75:
                status_color = "🟡"
                status_text  = "주의"
            else:
                status_color = "🟢"
                status_text  = "정상"

            st.metric(
                label=f"{status_color} {name}",
                value=f"{level:.1f}m",
                delta=f"{pct:.0f}% | {status_text}",
            )
            st.progress(min(pct / 100, 1.0))


def _render_pump_status(data: Dict) -> None:
    """펌프 상태"""
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
                f"""
                <div style="
                    border: 2px solid {'#28a745' if running else '#6c757d'};
                    border-radius: 8px;
                    padding: 12px;
                    text-align: center;
                    background: {'#d4edda' if running else '#f8f9fa'};
                ">
                    <div style="font-size: 24px;">{'🟢' if running else '⚫'}</div>
                    <div style="font-weight: bold;">{name}</div>
                    <div style="font-size: 12px; color: gray;">
                        {'가동 중' if running else '정지'} | {rpm} RPM
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _render_alarms(data: Dict) -> None:
    """알람 목록"""
    st.markdown("##### 🔔 알람")
    alarms = data.get("alarms", [])

    if not alarms:
        st.success("✅ 현재 활성 알람 없음")
        return

    for alarm in alarms[:5]:  # 최대 5개 표시
        severity = alarm.get("severity", "info")
        icon_map = {"critical": "🔴", "warning": "🟡", "info": "🔵"}
        icon = icon_map.get(severity, "⚪")
        st.warning(f"{icon} **{alarm.get('title', '알람')}** — {alarm.get('message', '')}")


def _render_water_level_chart(data: Dict) -> None:
    """수위 추이 차트"""
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
    """PLC 연결 전 플레이스홀더"""
    st.markdown(
        """
        <div style="
            border: 2px dashed #dee2e6;
            border-radius: 12px;
            padding: 40px;
            text-align: center;
            color: #6c757d;
        ">
            <div style="font-size: 48px;">📡</div>
            <div style="font-size: 18px; margin-top: 12px;">PLC 연결 대기 중</div>
            <div style="font-size: 14px; margin-top: 8px;">
                설정 → 통신 설정에서<br>PLC IP와 포트를 확인하세요
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# 우측: AI 채팅 패널
# ══════════════════════════════════════════════════════════════════════════════

def _render_chat_panel() -> None:
    # 헤더 + 초기화 버튼
    h1, h2 = st.columns([4, 1])
    with h1:
        st.subheader("💬 AI 어시스턴트")
    with h2:
        if st.button("🗑️ 초기화", use_container_width=True):
            st.session_state.chat_messages = []
            st.rerun()

    # 채팅 모드 선택
    mode = st.radio(
        "검색 모드",
        ["💬 일반 대화", "📚 문서 기반 (RAG)"],
        horizontal=True,
        label_visibility="collapsed",
    )
    is_rag = "RAG" in mode

    # 메시지 히스토리 표시
    msg_container = st.container(height=480)
    with msg_container:
        if not st.session_state.chat_messages:
            st.markdown(
                """
                <div style="text-align:center; color:#adb5bd; padding:60px 0;">
                    <div style="font-size:36px;">🤖</div>
                    <div style="margin-top:8px;">
                        PLC 운영, 수위 현황, 문서 내용에 대해 질문하세요
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        for msg in st.session_state.chat_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                if msg["role"] == "assistant" and msg.get("sources"):
                    with st.expander(
                        f"📎 참고 문서 {len(msg['sources'])}개 | ⏱️ {msg.get('latency_ms', 0)}ms",
                        expanded=False,
                    ):
                        for i, src in enumerate(msg["sources"], 1):
                            st.markdown(
                                f"**{i}. {src['filename']}** p.{src['page_number']} "
                                f"*(유사도 {src['score']:.1%})*"
                            )
                            st.caption(src["content"])

    # 입력창
    placeholder = (
        "문서 내용에 대해 질문하세요 (예: PLC 비상 정지 절차)" if is_rag
        else "배수지 운영 관련 질문을 입력하세요"
    )
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
                resp = httpx.post(
                    f"{_API_BASE}/rag/query",
                    json={
                        "question":     question,
                        "top_k":        5,
                        "chat_history": history,
                    },
                    timeout=120.0,
                )
            else:
                resp = httpx.post(
                    f"{_API_BASE}/chat",
                    json={
                        "message":      question,
                        "chat_history": history,
                    },
                    timeout=120.0,
                )

            resp.raise_for_status()
            r = resp.json()

            if is_rag:
                st.session_state.chat_messages.append({
                    "role":        "assistant",
                    "content":     r["answer"],
                    "sources":     r.get("sources", []),
                    "latency_ms":  r.get("latency_ms", 0),
                })
            else:
                st.session_state.chat_messages.append({
                    "role":    "assistant",
                    "content": r.get("response", r.get("answer", "응답 없음")),
                })

        except httpx.ConnectError:
            st.session_state.chat_messages.append({
                "role":    "assistant",
                "content": "❌ API 서버에 연결할 수 없습니다.",
            })
        except Exception as e:
            st.session_state.chat_messages.append({
                "role":    "assistant",
                "content": f"❌ 오류: {str(e)}",
            })

    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# API 호출 헬퍼
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_plc_data() -> Optional[Dict]:
    """PLC 현황 데이터 조회"""
    try:
        resp = httpx.get(f"{_API_BASE}/plc/status", timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def _check_plc_connection() -> bool:
    try:
        resp = httpx.get(f"{_API_BASE}/plc/ping", timeout=3.0)
        return resp.status_code == 200
    except Exception:
        return False


def _check_llm_connection() -> bool:
    try:
        resp = httpx.get(f"{_API_BASE}/llm/ping", timeout=3.0)
        return resp.status_code == 200
    except Exception:
        return False
