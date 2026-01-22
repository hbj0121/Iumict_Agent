"""
Modbus PLC 통신 구현체
실제 PLC 하드웨어와 통신
"""
from typing import Optional, Dict, Any
from datetime import datetime
import structlog
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException
import struct

from .interface import (
    HardwareController,
    WaterLevelReading,
    PumpCommand,
    PumpStatus
)

logger = structlog.get_logger(__name__)


class ModbusPLCController(HardwareController):
    """Modbus TCP 기반 PLC 제어기"""

    def __init__(self, config: Dict[str, Any]):
        """
        PLC 컨트롤러 초기화

        Args:
            config: {
                "host": "192.168.1.100",
                "port": 502,
                "unit_id": 1,
                "timeout": 5,
                "register_map": {...}
            }
        """
        self.host = config.get("host", "192.168.1.100")
        self.port = config.get("port", 502)
        self.timeout = config.get("timeout", 5)
        self.unit_id = config.get("unit_id", 1)

        # 레지스터 매핑 (실제 PLC 사양에 맞춰 수정 필요)
        self.register_map = config.get("register_map", {
            "gagok": {
                "water_level": 0,  # 수위 센서 레지스터 주소
                "pump_control": 100,  # 펌프 제어 레지스터
                "pump_status": 101  # 펌프 상태 레지스터
            },
            "haeryong": {
                "water_level": 10,
                "pump_control": 110,
                "pump_status": 111
            }
        })

        self.client: Optional[AsyncModbusTcpClient] = None
        logger.info("plc_controller_initialized", host=self.host, port=self.port)

    async def connect(self) -> bool:
        """PLC에 연결"""
        try:
            self.client = AsyncModbusTcpClient(
                host=self.host,
                port=self.port,
                timeout=self.timeout
            )
            connected = await self.client.connect()

            if connected:
                logger.info("plc_connected", host=self.host, port=self.port)
                # 연결 후 헬스체크
                await self._health_check()
            else:
                logger.error("plc_connection_failed", host=self.host, port=self.port)

            return connected
        except Exception as e:
            logger.error("plc_connection_error", error=str(e), host=self.host)
            return False

    async def disconnect(self) -> None:
        """PLC 연결 해제"""
        if self.client:
            self.client.close()
            logger.info("plc_disconnected")

    async def is_connected(self) -> bool:
        """연결 상태 확인"""
        return self.client is not None and self.client.connected

    async def read_water_level(self, reservoir_id: str) -> WaterLevelReading:
        """
        PLC에서 수위 레지스터 읽기

        Args:
            reservoir_id: 배수지 ID (예: "gagok")

        Returns:
            WaterLevelReading 객체
        """
        if not await self.is_connected():
            raise ConnectionError("PLC가 연결되지 않았습니다")

        if reservoir_id not in self.register_map:
            raise ValueError(f"알 수 없는 배수지: {reservoir_id}")

        try:
            reg_addr = self.register_map[reservoir_id]["water_level"]

            # Holding Register 읽기 (Function Code 03)
            # 32비트 Float이면 count=2
            result = await self.client.read_holding_registers(
                address=reg_addr,
                count=2,  # Float32 = 2 레지스터
                slave=self.unit_id
            )

            if result.isError():
                logger.error("modbus_read_error", reservoir=reservoir_id, error=result)
                raise ModbusException(f"레지스터 읽기 실패: {result}")

            # Raw 레지스터 값을 Float로 변환
            raw_value = result.registers[0]
            water_level = self._convert_to_water_level(result.registers)

            logger.debug("water_level_read", reservoir=reservoir_id, level=water_level)

            return WaterLevelReading(
                level_meters=round(water_level, 2),
                measured_at=datetime.now(),
                reservoir_id=reservoir_id,
                raw_value=raw_value,
                sensor_status="normal"
            )

        except ModbusException as e:
            logger.error("modbus_exception", reservoir=reservoir_id, error=str(e))
            return WaterLevelReading(
                level_meters=0.0,
                measured_at=datetime.now(),
                reservoir_id=reservoir_id,
                sensor_status="error"
            )
        except Exception as e:
            logger.exception("water_level_read_failed", reservoir=reservoir_id)
            return WaterLevelReading(
                level_meters=0.0,
                measured_at=datetime.now(),
                reservoir_id=reservoir_id,
                sensor_status="error"
            )

    async def send_pump_command(self, command: PumpCommand) -> bool:
        """
        펌프 제어 명령 전송

        Args:
            command: PumpCommand 객체

        Returns:
            성공 여부
        """
        if not await self.is_connected():
            raise ConnectionError("PLC가 연결되지 않았습니다")

        if command.target_reservoir not in self.register_map:
            logger.error("invalid_reservoir", reservoir=command.target_reservoir)
            return False

        try:
            reg_addr = self.register_map[command.target_reservoir]["pump_control"]

            # 명령을 PLC 제어 값으로 변환
            control_value = {
                "start": 1,
                "stop": 0,
                "auto": 2
            }.get(command.action.lower(), 0)

            # Coil 쓰기 (Function Code 05) 또는 Register 쓰기 (Function Code 06)
            result = await self.client.write_register(
                address=reg_addr,
                value=control_value,
                slave=self.unit_id
            )

            if result.isError():
                logger.error("pump_command_failed", reservoir=command.target_reservoir, error=result)
                return False

            logger.info(
                "pump_command_sent",
                reservoir=command.target_reservoir,
                action=command.action,
                requested_by=command.requested_by
            )
            return True

        except Exception as e:
            logger.error("pump_command_exception", reservoir=command.target_reservoir, error=str(e))
            return False

    async def get_pump_status(self, reservoir_id: str) -> PumpStatus:
        """펌프 상태 조회"""
        if not await self.is_connected():
            raise ConnectionError("PLC가 연결되지 않았습니다")

        if reservoir_id not in self.register_map:
            raise ValueError(f"알 수 없는 배수지: {reservoir_id}")

        try:
            reg_addr = self.register_map[reservoir_id]["pump_status"]

            result = await self.client.read_holding_registers(
                address=reg_addr,
                count=1,
                slave=self.unit_id
            )

            if result.isError():
                raise ModbusException(f"상태 읽기 실패: {result}")

            status_value = result.registers[0]

            return PumpStatus(
                is_running=(status_value == 1),
                mode="auto" if status_value == 2 else "manual",
                last_changed=datetime.now()
            )

        except Exception as e:
            logger.error("pump_status_failed", reservoir=reservoir_id, error=str(e))
            return PumpStatus(is_running=False, mode="unknown")

    async def get_all_sensors(self) -> Dict[str, WaterLevelReading]:
        """모든 배수지 센서 데이터 일괄 조회"""
        results = {}
        for reservoir_id in self.register_map.keys():
            results[reservoir_id] = await self.read_water_level(reservoir_id)

        logger.info("all_sensors_read", count=len(results))
        return results

    def _convert_to_water_level(self, registers: list) -> float:
        """
        Modbus 레지스터 값을 실제 수위(m)로 변환

        Args:
            registers: 레지스터 값 리스트 (2개 = Float32)

        Returns:
            변환된 수위 값 (미터)
        """
        # IEEE 754 Float32 변환 (Big-endian)
        # PLC 사양에 따라 Little-endian으로 변경 필요할 수 있음
        try:
            bytes_data = struct.pack('>HH', registers[0], registers[1])
            float_value = struct.unpack('>f', bytes_data)[0]
            return float_value
        except:
            # 변환 실패 시 단순 스케일링
            # 예: 0~65535 -> 0~100m
            raw_value = registers[0]
            return (raw_value / 65535.0) * 100.0

    async def _health_check(self) -> bool:
        """
        PLC 헬스체크
        시스템 레지스터를 읽어서 정상 작동 확인
        """
        try:
            # 레지스터 0번을 읽어서 응답 확인
            result = await self.client.read_holding_registers(
                address=0,
                count=1,
                slave=self.unit_id
            )
            is_healthy = not result.isError()
            logger.info("plc_health_check", healthy=is_healthy)
            return is_healthy
        except:
            logger.warning("plc_health_check_failed")
            return False