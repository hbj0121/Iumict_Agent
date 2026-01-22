"""
하드웨어 컨트롤러 팩토리
설정에 따라 적절한 하드웨어 구현체 생성
"""
from typing import Dict, Any
from src.config.settings import get_settings
from .interface import HardwareController
from .modbus_plc import ModbusPLCController
from .simulator import PLCSimulator


def create_hardware_controller(config: Dict[str, Any] = None) -> HardwareController:
    """
    설정에 따라 적절한 하드웨어 컨트롤러 생성

    Args:
        config: 선택적 설정 오버라이드

    Returns:
        HardwareController 구현체

    Examples:
        >>> controller = create_hardware_controller()  # 설정 파일 기준
        >>> controller = create_hardware_controller({"type": "simulator"})  # 강제 시뮬레이터
    """
    settings = get_settings()

    # config 파라미터가 있으면 우선 사용
    hw_type = config.get("type") if config else settings.hardware.type

    if hw_type == "plc":
        # 실제 PLC 연결
        plc_config = {
            "host": settings.hardware.plc_host,
            "port": settings.hardware.plc_port,
            "unit_id": settings.hardware.plc_unit_id,
            "timeout": settings.hardware.plc_timeout,
        }
        return ModbusPLCController(plc_config)

    elif hw_type == "simulator":
        # 시뮬레이터 사용
        return PLCSimulator()

    else:
        raise ValueError(
            f"지원하지 않는 하드웨어 타입: {hw_type}. "
            f"사용 가능: 'plc', 'simulator'"
        )


# 편의 함수
async def get_connected_controller() -> HardwareController:
    """
    하드웨어 컨트롤러 생성 및 자동 연결

    Returns:
        연결된 HardwareController

    Raises:
        ConnectionError: 연결 실패 시
    """
    controller = create_hardware_controller()

    connected = await controller.connect()
    if not connected:
        raise ConnectionError("하드웨어 연결 실패")

    return controller
