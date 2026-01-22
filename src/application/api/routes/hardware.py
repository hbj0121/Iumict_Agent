"""
하드웨어 제어 API 라우터
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, List
from pydantic import BaseModel
from datetime import datetime

from src.infrastructure.hardware.factory import create_hardware_controller
from src.infrastructure.hardware.interface import (
    HardwareController,
    PumpCommand
)

router = APIRouter(
    prefix="/api/hardware",
    tags=["Hardware Control"]
)

# 전역 컨트롤러 인스턴스 (싱글톤)
_controller: HardwareController | None = None


async def get_controller() -> HardwareController:
    """하드웨어 컨트롤러 의존성 주입"""
    global _controller

    if _controller is None:
        _controller = create_hardware_controller()
        connected = await _controller.connect()
        if not connected:
            raise HTTPException(
                status_code=503,
                detail="하드웨어 연결 실패"
            )

    if not await _controller.is_connected():
        # 재연결 시도
        connected = await _controller.connect()
        if not connected:
            raise HTTPException(
                status_code=503,
                detail="하드웨어 연결이 끊어졌습니다"
            )

    return _controller


# ============================================
# Request/Response 모델
# ============================================

class WaterLevelResponse(BaseModel):
    """수위 응답 모델"""
    reservoir_id: str
    level_meters: float
    measured_at: datetime
    sensor_status: str
    raw_value: int | None = None


class PumpControlRequest(BaseModel):
    """펌프 제어 요청 모델"""
    action: str  # start, stop, auto
    requested_by: str = "api_user"


class PumpStatusResponse(BaseModel):
    """펌프 상태 응답 모델"""
    reservoir_id: str
    is_running: bool
    mode: str
    last_changed: datetime | None


# ============================================
# API 엔드포인트
# ============================================

@router.get("/status")
async def get_hardware_status(
        controller: HardwareController = Depends(get_controller)
):
    """
    하드웨어 연결 상태 확인

    Returns:
        연결 상태 및 타입 정보
    """
    is_connected = await controller.is_connected()

    return {
        "connected": is_connected,
        "controller_type": type(controller).__name__,
        "timestamp": datetime.now().isoformat()
    }


@router.get("/water-level/{reservoir_id}", response_model=WaterLevelResponse)
async def read_water_level(
        reservoir_id: str,
        controller: HardwareController = Depends(get_controller)
):
    """
    특정 배수지의 수위 조회

    Args:
        reservoir_id: 배수지 ID (예: gagok, haeryong)

    Returns:
        수위 측정 데이터
    """
    try:
        reading = await controller.read_water_level(reservoir_id)

        return WaterLevelResponse(
            reservoir_id=reading.reservoir_id,
            level_meters=reading.level_meters,
            measured_at=reading.measured_at,
            sensor_status=reading.sensor_status,
            raw_value=reading.raw_value
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"수위 읽기 실패: {str(e)}")


@router.get("/water-level", response_model=Dict[str, WaterLevelResponse])
async def read_all_water_levels(
        controller: HardwareController = Depends(get_controller)
):
    """
    모든 배수지의 수위 일괄 조회

    Returns:
        배수지별 수위 데이터 딕셔너리
    """
    try:
        all_readings = await controller.get_all_sensors()

        return {
            reservoir_id: WaterLevelResponse(
                reservoir_id=reading.reservoir_id,
                level_meters=reading.level_meters,
                measured_at=reading.measured_at,
                sensor_status=reading.sensor_status,
                raw_value=reading.raw_value
            )
            for reservoir_id, reading in all_readings.items()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"수위 읽기 실패: {str(e)}")


@router.post("/pump/{reservoir_id}/control")
async def control_pump(
        reservoir_id: str,
        request: PumpControlRequest,
        controller: HardwareController = Depends(get_controller)
):
    """
    펌프 제어

    Args:
        reservoir_id: 배수지 ID
        request: 제어 명령 (start, stop, auto)

    Returns:
        제어 결과
    """
    if request.action not in ["start", "stop", "auto"]:
        raise HTTPException(
            status_code=400,
            detail="유효하지 않은 명령입니다. start, stop, auto 중 하나를 선택하세요."
        )

    try:
        command = PumpCommand(
            action=request.action,
            target_reservoir=reservoir_id,
            requested_by=request.requested_by,
            timestamp=datetime.now()
        )

        success = await controller.send_pump_command(command)

        if success:
            return {
                "success": True,
                "message": f"{reservoir_id} 펌프 {request.action} 명령 전송 완료",
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="펌프 제어 명령 전송 실패"
            )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"펌프 제어 실패: {str(e)}")


@router.get("/pump/{reservoir_id}/status", response_model=PumpStatusResponse)
async def get_pump_status(
        reservoir_id: str,
        controller: HardwareController = Depends(get_controller)
):
    """
    펌프 상태 조회

    Args:
        reservoir_id: 배수지 ID

    Returns:
        펌프 운전 상태
    """
    try:
        status = await controller.get_pump_status(reservoir_id)

        return PumpStatusResponse(
            reservoir_id=reservoir_id,
            is_running=status.is_running,
            mode=status.mode,
            last_changed=status.last_changed
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"펌프 상태 조회 실패: {str(e)}")