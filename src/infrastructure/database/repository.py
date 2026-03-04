# """
# 데이터베이스 리포지토리 패턴
# """
# from typing import List, Optional
# from datetime import datetime, timedelta
# from sqlalchemy import select, desc, and_
# from sqlalchemy.ext.asyncio import AsyncSession
# import structlog
#
# from .models import Reservoir, WaterLevelReading, PumpControlHistory
#
# logger = structlog.get_logger(__name__)
#
#
# class ReservoirRepository:
#     """배수지 리포지토리"""
#
#     def __init__(self, session: AsyncSession):
#         self.session = session
#
#     async def get_by_name(self, name: str) -> Optional[Reservoir]:
#         """이름으로 배수지 조회"""
#         result = await self.session.execute(
#             select(Reservoir).where(Reservoir.name == name)
#         )
#         return result.scalar_one_or_none()
#
#     async def get_all(self) -> List[Reservoir]:
#         """모든 배수지 조회"""
#         result = await self.session.execute(select(Reservoir))
#         return list(result.scalars().all())
#
#
# class WaterLevelRepository:
#     """수위 데이터 리포지토리"""
#
#     def __init__(self, session: AsyncSession):
#         self.session = session
#
#     async def add_reading(
#             self,
#             reservoir_id: int,
#             level_meters: float,
#             measured_at: datetime,
#             sensor_status: str = "normal",
#             raw_value: Optional[int] = None
#     ) -> WaterLevelReading:
#         """수위 데이터 추가"""
#         reading = WaterLevelReading(
#             reservoir_id=reservoir_id,
#             level_meters=level_meters,
#             measured_at=measured_at,
#             sensor_status=sensor_status,
#             raw_value=raw_value
#         )
#
#         self.session.add(reading)
#         await self.session.commit()
#         await self.session.refresh(reading)
#
#         logger.info("water_level_saved", reservoir_id=reservoir_id, level=level_meters)
#         return reading
#
#     async def get_latest(self, reservoir_id: int) -> Optional[WaterLevelReading]:
#         """최신 수위 조회"""
#         result = await self.session.execute(
#             select(WaterLevelReading)
#             .where(WaterLevelReading.reservoir_id == reservoir_id)
#             .order_by(desc(WaterLevelReading.measured_at))
#             .limit(1)
#         )
#         return result.scalar_one_or_none()
#
#     async def get_history(
#             self,
#             reservoir_id: int,
#             hours: int = 24,
#             limit: Optional[int] = None
#     ) -> List[WaterLevelReading]:
#         """과거 수위 이력 조회"""
#         since = datetime.now() - timedelta(hours=hours)
#
#         query = (
#             select(WaterLevelReading)
#             .where(and_(
#                 WaterLevelReading.reservoir_id == reservoir_id,
#                 WaterLevelReading.measured_at >= since
#             ))
#             .order_by(desc(WaterLevelReading.measured_at))
#         )
#
#         if limit:
#             query = query.limit(limit)
#
#         result = await self.session.execute(query)
#         return list(result.scalars().all())
#
#     async def get_range(
#             self,
#             reservoir_id: int,
#             start_time: datetime,
#             end_time: datetime
#     ) -> List[WaterLevelReading]:
#         """특정 기간의 수위 데이터 조회"""
#         result = await self.session.execute(
#             select(WaterLevelReading)
#             .where(and_(
#                 WaterLevelReading.reservoir_id == reservoir_id,
#                 WaterLevelReading.measured_at >= start_time,
#                 WaterLevelReading.measured_at <= end_time
#             ))
#             .order_by(WaterLevelReading.measured_at)
#         )
#         return list(result.scalars().all())
#
#
# class PumpControlRepository:
#     """펌프 제어 이력 리포지토리"""
#
#     def __init__(self, session: AsyncSession):
#         self.session = session
#
#     async def add_control(
#             self,
#             reservoir_id: int,
#             action: str,
#             requested_by: str = "system",
#             success: bool = True
#     ) -> PumpControlHistory:
#         """펌프 제어 이력 추가"""
#         control = PumpControlHistory(
#             reservoir_id=reservoir_id,
#             action=action,
#             requested_by=requested_by,
#             success=success
#         )
#
#         self.session.add(control)
#         await self.session.commit()
#         await self.session.refresh(control)
#
#         logger.info("pump_control_logged", reservoir_id=reservoir_id, action=action)
#         return control
#
#     async def get_history(
#             self,
#             reservoir_id: int,
#             hours: int = 24
#     ) -> List[PumpControlHistory]:
#         """펌프 제어 이력 조회"""
#         since = datetime.now() - timedelta(hours=hours)
#
#         result = await self.session.execute(
#             select(PumpControlHistory)
#             .where(and_(
#                 PumpControlHistory.reservoir_id == reservoir_id,
#                 PumpControlHistory.executed_at >= since
#             ))
#             .order_by(desc(PumpControlHistory.executed_at))
#         )
#         return list(result.scalars().all())
"""
데이터베이스 리포지토리 패턴 (동기 버전)
"""
from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy import select, desc, and_
from sqlalchemy.orm import Session
import structlog

from .models import Reservoir, WaterLevelReading, PumpControlHistory

logger = structlog.get_logger(__name__)


class ReservoirRepository:
    """배수지 리포지토리"""

    def __init__(self, session: Session):
        self.session = session

    def get_by_name(self, name: str) -> Optional[Reservoir]:
        """이름으로 배수지 조회"""
        return self.session.execute(
            select(Reservoir).where(Reservoir.name == name)
        ).scalar_one_or_none()

    def get_all(self) -> List[Reservoir]:
        """모든 배수지 조회"""
        return list(self.session.execute(select(Reservoir)).scalars().all())


class WaterLevelRepository:
    """수위 데이터 리포지토리"""

    def __init__(self, session: Session):
        self.session = session

    def add_reading(
            self,
            reservoir_id: int,
            level_meters: float,
            measured_at: datetime,
            sensor_status: str = "normal",
            raw_value: Optional[int] = None
    ) -> WaterLevelReading:
        """수위 데이터 추가"""
        reading = WaterLevelReading(
            reservoir_id=reservoir_id,
            level_meters=level_meters,
            measured_at=measured_at,
            sensor_status=sensor_status,
            raw_value=raw_value
        )

        self.session.add(reading)
        self.session.commit()
        self.session.refresh(reading)

        logger.info("water_level_saved", reservoir_id=reservoir_id, level=level_meters)
        return reading

    def get_latest(self, reservoir_id: int) -> Optional[WaterLevelReading]:
        """최신 수위 조회"""
        return self.session.execute(
            select(WaterLevelReading)
            .where(WaterLevelReading.reservoir_id == reservoir_id)
            .order_by(desc(WaterLevelReading.measured_at))
            .limit(1)
        ).scalar_one_or_none()

    def get_history(
            self,
            reservoir_id: int,
            hours: int = 24,
            limit: Optional[int] = None
    ) -> List[WaterLevelReading]:
        """과거 수위 이력 조회"""
        since = datetime.now() - timedelta(hours=hours)

        query = (
            select(WaterLevelReading)
            .where(and_(
                WaterLevelReading.reservoir_id == reservoir_id,
                WaterLevelReading.measured_at >= since
            ))
            .order_by(desc(WaterLevelReading.measured_at))
        )

        if limit:
            query = query.limit(limit)

        return list(self.session.execute(query).scalars().all())


class PumpControlRepository:
    """펌프 제어 이력 리포지토리"""

    def __init__(self, session: Session):
        self.session = session

    def add_control(
            self,
            reservoir_id: int,
            action: str,
            requested_by: str = "system",
            success: bool = True
    ) -> PumpControlHistory:
        """펌프 제어 이력 추가"""
        control = PumpControlHistory(
            reservoir_id=reservoir_id,
            action=action,
            requested_by=requested_by,
            success=success
        )

        self.session.add(control)
        self.session.commit()
        self.session.refresh(control)

        logger.info("pump_control_logged", reservoir_id=reservoir_id, action=action)
        return control

    def get_history(
            self,
            reservoir_id: int,
            hours: int = 24
    ) -> List[PumpControlHistory]:
        """펌프 제어 이력 조회"""
        since = datetime.now() - timedelta(hours=hours)

        return list(self.session.execute(
            select(PumpControlHistory)
            .where(and_(
                PumpControlHistory.reservoir_id == reservoir_id,
                PumpControlHistory.executed_at >= since
            ))
            .order_by(desc(PumpControlHistory.executed_at))
        ).scalars().all())