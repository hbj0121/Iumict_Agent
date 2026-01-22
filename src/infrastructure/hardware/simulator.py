"""
PLC 시뮬레이터 - 실제 하드웨어 없이 개발/테스트
"""
import asyncio
import random
from typing import Dict
from datetime import datetime
import structlog

from .interface import (
    HardwareController,
    WaterLevelReading,
    PumpCommand,
    PumpStatus
)

logger = structlog.get_logger(__name__)


class PLCSimulator(HardwareController):
    """가상 PLC 시뮬레이터"""

    def __init__(self, config: Dict = None):
        """
        초기화

        Args:
            config: 설정 딕셔너리 (시뮬레이터는 무시)
        """
        self.reservoirs = {
            "gagok": {
                "level": 45.0,  # 초기 수위 (m)
                "pump_running": False,
                "trend": 0.1  # 수위 변화 경향
            },
            "haeryong": {
                "level": 62.0,
                "pump_running": False,
                "trend": -0.05
            }
        }
        self.connected = False
        logger.info("simulator_initialized", reservoirs=list(self.reservoirs.keys()))

    async def connect(self) -> bool:
        """연결 시뮬레이션 (항상 성공)"""
        await asyncio.sleep(0.1)  # 연결 지연 시뮬레이션
        self.connected = True
        logger.info("simulator_connected")
        return True

    async def disconnect(self) -> None:
        """연결 해제"""
        self.connected = False
        logger.info("simulator_disconnected")

    async def is_connected(self) -> bool:
        """연결 상태 반환"""
        return self.connected

    async def read_water_level(self, reservoir_id: str) -> WaterLevelReading:
        """
        수위 읽기 시뮬레이션
        실제 센서처럼 약간의 노이즈 추가
        """
        if reservoir_id not in self.reservoirs:
            raise ValueError(f"알 수 없는 배수지: {reservoir_id}")

        reservoir = self.reservoirs[reservoir_id]

        # 펌프 작동에 따른 수위 변화 시뮬레이션
        if reservoir["pump_running"]:
            reservoir["level"] -= 0.2  # 펌프 가동 시 수위 감소
        else:
            reservoir["level"] += reservoir["trend"]  # 자연 증가/감소

        # 현실적인 노이즈 추가
        noise = random.uniform(-0.3, 0.3)
        measured_level = reservoir["level"] + noise

        # 수위 범위 제한 (0~100m)
        measured_level = max(0.0, min(100.0, measured_level))

        return WaterLevelReading(
            level_meters=round(measured_level, 2),
            measured_at=datetime.now(),
            reservoir_id=reservoir_id,
            sensor_status="normal"
        )

    async def send_pump_command(self, command: PumpCommand) -> bool:
        """펌프 제어 시뮬레이션"""
        if command.target_reservoir not in self.reservoirs:
            logger.error("invalid_reservoir", reservoir=command.target_reservoir)
            return False

        reservoir = self.reservoirs[command.target_reservoir]

        if command.action == "start":
            reservoir["pump_running"] = True
            logger.info("pump_started", reservoir=command.target_reservoir)
        elif command.action == "stop":
            reservoir["pump_running"] = False
            logger.info("pump_stopped", reservoir=command.target_reservoir)
        elif command.action == "auto":
            # 자동 모드는 수위에 따라 자동 제어
            current_level = reservoir["level"]
            if current_level > 75.0:
                reservoir["pump_running"] = True
                logger.info("pump_auto_started", reservoir=command.target_reservoir, level=current_level)
            elif current_level < 50.0:
                reservoir["pump_running"] = False
                logger.info("pump_auto_stopped", reservoir=command.target_reservoir, level=current_level)
        else:
            logger.error("invalid_pump_action", action=command.action)
            return False

        return True

    async def get_pump_status(self, reservoir_id: str) -> PumpStatus:
        """펌프 상태 조회"""
        if reservoir_id not in self.reservoirs:
            raise ValueError(f"알 수 없는 배수지: {reservoir_id}")

        reservoir = self.reservoirs[reservoir_id]

        return PumpStatus(
            is_running=reservoir["pump_running"],
            mode="auto",  # 시뮬레이터는 항상 auto 모드
            last_changed=datetime.now()
        )

    async def get_all_sensors(self) -> Dict[str, WaterLevelReading]:
        """모든 센서 데이터 조회"""
        results = {}
        for reservoir_id in self.reservoirs.keys():
            results[reservoir_id] = await self.read_water_level(reservoir_id)

        logger.info("all_sensors_read", count=len(results))
        return results