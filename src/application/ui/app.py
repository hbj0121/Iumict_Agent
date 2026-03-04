"""
Streamlit 메인 애플리케이션
"""
import sys
from pathlib import Path

# 프로젝트 루트를 PYTHONPATH에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import streamlit as st
import asyncio
from datetime import datetime

from src.config.settings import get_settings
from src.infrastructure.hardware.factory import create_hardware_controller

settings = get_settings()

# 페이지 설정
st.set_page_config(
    page_title="Smart Water PLC",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 커스텀 CSS
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 5px solid #1f77b4;
    }
    .status-normal {
        color: #28a745;
        font-weight: bold;
    }
    .status-warning {
        color: #ffc107;
        font-weight: bold;
    }
    .status-error {
        color: #dc3545;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# 세션 스테이트 초기화
if 'controller' not in st.session_state:
    st.session_state.controller = None
if 'connected' not in st.session_state:
    st.session_state.connected = False


async def init_hardware():
    """하드웨어 초기화"""
    if st.session_state.controller is None:
        controller = create_hardware_controller()
        connected = await controller.connect()
        st.session_state.controller = controller
        st.session_state.connected = connected
    return st.session_state.controller


def get_status_badge(status: str) -> str:
    """상태 뱃지 HTML 생성"""
    if status == "normal":
        return '<span class="status-normal">● 정상</span>'
    elif status == "warning":
        return '<span class="status-warning">● 경고</span>'
    else:
        return '<span class="status-error">● 오류</span>'


# ============================================
# 헤더
# ============================================
st.markdown('<div class="main-header">🌊 스마트 배수지 관리 시스템</div>', unsafe_allow_html=True)

col1, col2, col3 = st.columns([2, 2, 1])
with col1:
    st.info(f"**환경**: {settings.hardware.type}")
with col2:
    st.info(f"**버전**: 0.1.0")
with col3:
    if st.button("🔄 새로고침", use_container_width=True):
        st.rerun()

st.divider()

# ============================================
# 사이드바
# ============================================
with st.sidebar:
    st.header("⚙️ 제어판")

    page = st.radio(
        "페이지 선택",
        ["📊 대시보드", "💧 수위 모니터링", "🔧 펌프 제어", "📈 실시간 차트"],
        label_visibility="collapsed"
    )

    st.divider()

    # 하드웨어 연결 상태
    st.subheader("하드웨어 상태")

    if st.session_state.connected:
        st.success("✅ 연결됨")
    else:
        st.error("❌ 연결 안 됨")
        if st.button("🔌 재연결"):
            controller = asyncio.run(init_hardware())
            if st.session_state.connected:
                st.success("연결 성공!")
                st.rerun()
            else:
                st.error("연결 실패")

    st.divider()
    st.caption(f"© 2026 {settings.app_name}")

# ============================================
# 메인 콘텐츠
# ============================================

# 하드웨어 초기화
controller = asyncio.run(init_hardware())

if page == "📊 대시보드":
    st.header("📊 실시간 대시보드")

    # 모든 배수지 데이터 조회
    all_data = asyncio.run(controller.get_all_sensors())

    # 배수지별 카드 표시
    cols = st.columns(len(all_data))

    for idx, (reservoir_id, reading) in enumerate(all_data.items()):
        with cols[idx]:
            st.subheader(f"🏞️ {reservoir_id.upper()}")

            # 수위 메트릭
            st.metric(
                label="현재 수위",
                value=f"{reading.level_meters:.2f} m",
                delta=f"± 0.5 m"  # 변화량은 나중에 DB에서 계산
            )

            # 상태 표시
            st.markdown(get_status_badge(reading.sensor_status), unsafe_allow_html=True)

            # 펌프 상태
            pump_status = asyncio.run(controller.get_pump_status(reservoir_id))

            if pump_status.is_running:
                st.warning("🔄 펌프 가동 중")
            else:
                st.info("⏸️ 펌프 정지")

            st.caption(f"측정 시각: {reading.measured_at.strftime('%H:%M:%S')}")

elif page == "💧 수위 모니터링":
    st.header("💧 수위 모니터링")

    # 배수지 선택
    reservoir_id = st.selectbox(
        "배수지 선택",
        ["gagok", "haeryong"],
        format_func=lambda x: x.upper()
    )

    # 자동 새로고침
    auto_refresh = st.checkbox("자동 새로고침 (5초)", value=True)

    if auto_refresh:
        import time

        placeholder = st.empty()

        for _ in range(60):  # 5분 동안
            with placeholder.container():
                reading = asyncio.run(controller.read_water_level(reservoir_id))

                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric("수위", f"{reading.level_meters:.2f} m")
                with col2:
                    st.metric("상태", reading.sensor_status)
                with col3:
                    st.metric("측정 시각", reading.measured_at.strftime('%H:%M:%S'))

                # 간단한 차트 (나중에 DB 연동 시 히스토리 표시)
                st.line_chart([reading.level_meters] * 10)

            time.sleep(5)
            st.rerun()
    else:
        # 수동 조회
        if st.button("조회"):
            reading = asyncio.run(controller.read_water_level(reservoir_id))

            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("수위", f"{reading.level_meters:.2f} m")
            with col2:
                st.metric("상태", reading.sensor_status)
            with col3:
                st.metric("측정 시각", reading.measured_at.strftime('%H:%M:%S'))

elif page == "🔧 펌프 제어":
    st.header("🔧 펌프 제어")

    # 배수지 선택
    reservoir_id = st.selectbox(
        "배수지 선택",
        ["gagok", "haeryong"],
        format_func=lambda x: x.upper(),
        key="pump_reservoir"
    )

    # 현재 펌프 상태 표시
    pump_status = asyncio.run(controller.get_pump_status(reservoir_id))

    col1, col2 = st.columns(2)
    with col1:
        if pump_status.is_running:
            st.success("🟢 펌프 가동 중")
        else:
            st.info("⚪ 펌프 정지")
    with col2:
        st.info(f"모드: {pump_status.mode}")

    st.divider()

    # 제어 버튼
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("▶️ 시작", use_container_width=True, type="primary"):
            from src.infrastructure.hardware.interface import PumpCommand

            command = PumpCommand(
                action="start",
                target_reservoir=reservoir_id,
                requested_by="streamlit_user",
                timestamp=datetime.now()
            )
            success = asyncio.run(controller.send_pump_command(command))

            if success:
                st.success("✅ 펌프를 시작했습니다!")
                st.rerun()
            else:
                st.error("❌ 펌프 시작 실패")

    with col2:
        if st.button("⏹️ 정지", use_container_width=True):
            from src.infrastructure.hardware.interface import PumpCommand

            command = PumpCommand(
                action="stop",
                target_reservoir=reservoir_id,
                requested_by="streamlit_user",
                timestamp=datetime.now()
            )
            success = asyncio.run(controller.send_pump_command(command))

            if success:
                st.success("✅ 펌프를 정지했습니다!")
                st.rerun()
            else:
                st.error("❌ 펌프 정지 실패")

    with col3:
        if st.button("🤖 자동", use_container_width=True):
            from src.infrastructure.hardware.interface import PumpCommand

            command = PumpCommand(
                action="auto",
                target_reservoir=reservoir_id,
                requested_by="streamlit_user",
                timestamp=datetime.now()
            )
            success = asyncio.run(controller.send_pump_command(command))

            if success:
                st.success("✅ 자동 모드로 전환했습니다!")
                st.rerun()
            else:
                st.error("❌ 자동 모드 전환 실패")

elif page == "📈 실시간 차트":
    st.header("📈 실시간 수위 차트")
    st.info("🚧 데이터베이스 연동 후 구현 예정")

    st.markdown("""
    ### 예정 기능
    - 시간별 수위 변화 그래프
    - 펌프 작동 이력
    - 예측 수위 오버레이
    - 다중 배수지 비교
    """)

# ============================================
# 하단 정보
# ============================================
st.divider()
col1, col2, col3 = st.columns(3)
with col1:
    st.caption(f"🖥️ 하드웨어: {settings.hardware.type}")
with col2:
    st.caption(f"⏰ 현재 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
with col3:
    st.caption("📖 [문서 보기](https://github.com/hbj0121/Iumict_Agent)")