"""
src/application/ui/pages/settings_page.py

통신 설정 페이지
- PLC Modbus TCP / LLM 서버 / DB 접속 / 시리얼 COM 설정
- 저장 시 DB에 기록 → 재시작 없이 즉시 반영
- 각 섹션별 연결 테스트 버튼 포함
"""
from __future__ import annotations

import os
from typing import Dict, List

import httpx
import streamlit as st

try:
    from src.config.settings import get_settings
    _API_BASE = get_settings().API_BASE_URL
except Exception:
    _API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")

_TIMEOUT = 10.0

# 카테고리 순서 및 메타
_CATEGORIES = {
    "plc":    ("📡 PLC Modbus TCP",        "PLC 장비와의 Modbus TCP 통신 설정"),
    "llm":    ("🤖 LLM / 임베딩 서버",      "LM Studio 로컬 LLM 및 임베딩 모델 설정"),
    "db":     ("🗄️  DB 접속 정보",           "PostgreSQL 데이터베이스 연결 정보"),
    "serial": ("🔌 시리얼 / COM 포트",       "RS-232/485 시리얼 통신 포트 설정"),
}

# 카테고리별 입력 타입 오버라이드 (기본: text)
_INPUT_TYPES: Dict[str, str] = {
    "db_password":   "password",
    "plc_port":      "number",
    "plc_slave_id":  "number",
    "plc_timeout":   "number",
    "serial_baudrate": "number",
    "serial_timeout":  "number",
}

# 보드레이트 선택 옵션
_BAUDRATE_OPTIONS = ["1200", "2400", "4800", "9600", "19200", "38400", "57600", "115200"]


# ══════════════════════════════════════════════════════════════════════════════
# 진입점
# ══════════════════════════════════════════════════════════════════════════════

def render_settings_page() -> None:
    st.title("⚙️ 통신 설정")
    st.caption("변경 후 저장하면 서버 재시작 없이 즉시 반영됩니다.")

    # 탭으로 카테고리 분리
    tab_labels = [meta[0] for meta in _CATEGORIES.values()]
    tabs = st.tabs(tab_labels)

    for (category, (label, desc)), tab in zip(_CATEGORIES.items(), tabs):
        with tab:
            _render_category_tab(category, label, desc)


# ══════════════════════════════════════════════════════════════════════════════
# 카테고리 탭 렌더
# ══════════════════════════════════════════════════════════════════════════════

def _render_category_tab(category: str, label: str, desc: str) -> None:
    st.markdown(f"**{desc}**")
    st.divider()

    # 설정값 로드
    items = _fetch_category(category)
    if items is None:
        st.error("설정값을 불러올 수 없습니다. API 서버 상태를 확인하세요.")
        return

    # 입력 폼
    with st.form(key=f"form_{category}"):
        new_values: Dict[str, str] = {}

        for item in items:
            key   = item["key"]
            value = item.get("value", "")
            lbl   = item.get("label", key)
            tip   = item.get("description", "")

            input_type = _INPUT_TYPES.get(key, "text")

            # 보드레이트는 selectbox
            if key == "serial_baudrate":
                idx = _BAUDRATE_OPTIONS.index(value) if value in _BAUDRATE_OPTIONS else 3
                new_values[key] = st.selectbox(
                    lbl, _BAUDRATE_OPTIONS, index=idx, help=tip, key=f"input_{key}"
                )
            elif input_type == "password":
                new_values[key] = st.text_input(
                    lbl, value=value, type="password", help=tip, key=f"input_{key}"
                )
            elif input_type == "number":
                new_values[key] = str(st.number_input(
                    lbl, value=int(value) if value.isdigit() else 0,
                    min_value=0, step=1, help=tip, key=f"input_{key}"
                ))
            else:
                new_values[key] = st.text_input(
                    lbl, value=value, help=tip, key=f"input_{key}"
                )

        st.divider()
        col_save, col_test = st.columns([1, 1])

        with col_save:
            submitted = st.form_submit_button(
                "💾 저장",
                type="primary",
                use_container_width=True,
            )

        with col_test:
            test_clicked = st.form_submit_button(
                "🔌 연결 테스트",
                use_container_width=True,
            )

    # 저장 처리 (폼 외부)
    if submitted:
        _save_category(category, new_values)

    if test_clicked:
        _save_category(category, new_values)   # 테스트 전 먼저 저장
        _run_connection_test(category)


# ══════════════════════════════════════════════════════════════════════════════
# 연결 테스트
# ══════════════════════════════════════════════════════════════════════════════

def _run_connection_test(category: str) -> None:
    endpoint_map = {
        "plc":    "/plc/ping",
        "llm":    "/llm/ping",
        "db":     "/health/db",
        "serial": "/serial/ping",
    }
    endpoint = endpoint_map.get(category)
    if not endpoint:
        return

    label = _CATEGORIES[category][0]

    with st.spinner(f"{label} 연결 테스트 중..."):
        try:
            resp = httpx.get(f"{_API_BASE}{endpoint}", timeout=_TIMEOUT)
            if resp.status_code == 200:
                result = resp.json()
                st.success(f"✅ {label} 연결 성공! {result.get('message', '')}")
            else:
                st.error(f"❌ 연결 실패: HTTP {resp.status_code}")
        except httpx.ConnectError:
            st.error(f"❌ API 서버({_API_BASE})에 연결할 수 없습니다.")
        except httpx.TimeoutException:
            st.error(f"❌ 연결 타임아웃 — 장비가 응답하지 않습니다.")
        except Exception as e:
            st.error(f"❌ 테스트 중 오류: {str(e)}")


# ══════════════════════════════════════════════════════════════════════════════
# API 호출 헬퍼
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_category(category: str) -> List[Dict] | None:
    try:
        resp = httpx.get(f"{_API_BASE}/config/{category}", timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.warning(f"설정 로드 실패: {e}")
        return None


def _save_category(category: str, values: Dict[str, str]) -> None:
    try:
        resp = httpx.post(
            f"{_API_BASE}/config/{category}",
            json={"values": values},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        st.success(f"✅ 설정이 저장되었습니다. (즉시 반영)")
    except httpx.ConnectError:
        st.error("❌ API 서버에 연결할 수 없습니다.")
    except Exception as e:
        st.error(f"❌ 저장 실패: {str(e)}")
