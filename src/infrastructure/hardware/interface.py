"""
하드웨어 추상화 인터페이스
모든 하드웨어 구현체가 따라야 할 표준 인터페이스
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict


@dataclass
class WaterLevelReading:
    """수위 측정값 데이터 클래스"""
    level_meters: float
    measured_at: datetime
    reservoir_id: str
    sensor_status: str = "normal"  # normal, warning, error
    raw_value: Optional[int] = None


@dataclass
class PumpCommand:
    """펌프 제어 명령"""
    action: str  # start, stop, auto
    target_reservoir: str
    requested_by: str = "system"
    timestamp: Optional[datetime] = None


@dataclass
class PumpStatus:
    """펌프 상태 정보"""
    is_running: bool
    mode: str = "manual"  # manual, auto
    speed: Optional[int] = None
    last_changed: Optional[datetime] = None


class HardwareController(ABC):
    """하드웨어 제어 추상 인터페이스"""

    @abstractmethod
    async def connect(self) -> bool:
        """하드웨어에 연결"""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """하드웨어 연결 해제"""
        pass

    @abstractmethod
    async def is_connected(self) -> bool:
        """연결 상태 확인"""
        pass

    @abstractmethod
    async def read_water_level(self, reservoir_id: str) -> WaterLevelReading:
        """수위 센서 읽기"""
        pass

    @abstractmethod
    async def send_pump_command(self, command: PumpCommand) -> bool:
        """펌프 제어 명령 전송"""
        pass

    @abstractmethod
    async def get_pump_status(self, reservoir_id: str) -> PumpStatus:
        """펌프 상태 조회"""
        pass

    @abstractmethod
    async def get_all_sensors(self) -> Dict[str, WaterLevelReading]:
        """모든 센서 데이터 일괄 조회"""
        pass