"""
SQLAlchemy 데이터베이스 모델
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Reservoir(Base):
    """배수지 정보 테이블"""
    __tablename__ = "reservoirs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    location = Column(String(200))
    capacity_m3 = Column(Float)  # 용량 (세제곱미터)

    # 수위 임계값
    normal_level_min = Column(Float, default=40.0)
    normal_level_max = Column(Float, default=70.0)
    warning_level = Column(Float, default=75.0)
    critical_level = Column(Float, default=80.0)

    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # 관계
    water_levels = relationship("WaterLevelReading", back_populates="reservoir")
    pump_controls = relationship("PumpControlHistory", back_populates="reservoir")

    def __repr__(self):
        return f"<Reservoir(name='{self.name}', location='{self.location}')>"


class WaterLevelReading(Base):
    """수위 측정 데이터 테이블 (시계열)"""
    __tablename__ = "water_level_readings"

    id = Column(Integer, primary_key=True, index=True)
    reservoir_id = Column(Integer, ForeignKey("reservoirs.id"), nullable=False)

    level_meters = Column(Float, nullable=False)
    measured_at = Column(DateTime, nullable=False, index=True)
    sensor_status = Column(String(50), default="normal")
    raw_value = Column(Integer)

    created_at = Column(DateTime, default=datetime.now)

    # 관계
    reservoir = relationship("Reservoir", back_populates="water_levels")

    # 복합 인덱스 (배수지 + 시간 역순 조회 최적화)
    __table_args__ = (
        Index('ix_reservoir_time', 'reservoir_id', 'measured_at'),
    )

    def __repr__(self):
        return f"<WaterLevel(reservoir_id={self.reservoir_id}, level={self.level_meters}m, at={self.measured_at})>"


class PumpControlHistory(Base):
    """펌프 제어 이력 테이블"""
    __tablename__ = "pump_control_history"

    id = Column(Integer, primary_key=True, index=True)
    reservoir_id = Column(Integer, ForeignKey("reservoirs.id"), nullable=False)

    action = Column(String(50), nullable=False)  # start, stop, auto
    requested_by = Column(String(100))  # system, user_id, api, etc.
    success = Column(Boolean, default=True)

    executed_at = Column(DateTime, default=datetime.now, index=True)

    # 관계
    reservoir = relationship("Reservoir", back_populates="pump_controls")

    def __repr__(self):
        return f"<PumpControl(reservoir_id={self.reservoir_id}, action='{self.action}', at={self.executed_at})>"


class PredictionHistory(Base):
    """예측 이력 테이블"""
    __tablename__ = "prediction_history"

    id = Column(Integer, primary_key=True, index=True)
    reservoir_id = Column(Integer, ForeignKey("reservoirs.id"), nullable=False)

    model_type = Column(String(50))  # lstm, hybrid, etc.
    forecast_hours = Column(Integer)
    predicted_levels = Column(String)  # JSON array로 저장

    predicted_at = Column(DateTime, default=datetime.now, index=True)

    def __repr__(self):
        return f"<Prediction(reservoir_id={self.reservoir_id}, model={self.model_type}, at={self.predicted_at})>"