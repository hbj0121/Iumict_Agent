"""
Streamlit 홈 페이지 — 진입점
실행: poetry run streamlit run src/application/ui/app.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import os
import httpx
import streamlit as st

try:
    from src.config.settings import get_settings
    _settings = get_settings()
    _API_BASE = _settings.api_base_url
except Exception:
    _settings = None
    _API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")

st.set_page_config(
    page_title="Smart Water PLC",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🌊 스마트 배수지 관리 시스템")
st.caption("Iumict Agent — Smart Water PLC v0.1.0")

st.divider()

# ── 시스템 상태 ──────────────────────────────────────────────────────────────
c1, c2, c3 = st.columns(3)

with c1:
    hw_type = _settings.hardware.type.upper() if _settings else "UNKNOWN"
    st.metric("하드웨어 모드", hw_type)

with c2:
    try:
        resp = httpx.get(f"{_API_BASE}/health", timeout=3.0)
        api_ok = resp.status_code == 200
    except Exception:
        api_ok = False
    st.metric("API 서버", "🟢 정상" if api_ok else "🔴 오프라인")

with c3:
    st.metric("API 주소", _API_BASE)

st.divider()

# ── 페이지 안내 ───────────────────────────────────────────────────────────────
st.markdown("""
### 📌 페이지 안내

| 페이지 | 설명 |
|---|---|
| 📊 대시보드 | 실시간 PLC 모니터링 + AI 어시스턴트 |
| 💧 수위 모니터링 | 배수지별 실시간 수위 조회 |
| 🔧 펌프 제어 | 펌프 시작 / 정지 / 자동 제어 |
| 📚 RAG 문서 | PDF 업로드 및 문서 기반 Q&A |
| ⚙️ 설정 | 통신 및 시스템 설정 |

좌측 사이드바에서 페이지를 선택하세요.
""")