"""
데이터베이스 연결 관리 (psycopg 동기 버전 사용)
"""
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
import structlog

from src.config.settings import get_settings
from .models import Base

logger = structlog.get_logger(__name__)
settings = get_settings()

# 동기 엔진 생성 (asyncpg 대신 psycopg 사용)
DATABASE_URL = settings.database.url.replace(
    "postgresql+asyncpg://",
    "postgresql+psycopg://"
)

engine = create_engine(
    DATABASE_URL,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False
)


def init_db():
    """데이터베이스 초기화 및 테이블 생성"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("database_tables_created")

        _insert_initial_data()
        logger.info("database_initialized")

    except Exception as e:
        logger.error("database_init_failed", error=str(e))
        raise


def _insert_initial_data():
    """초기 배수지 데이터 삽입"""
    from sqlalchemy import text
    from .models import Reservoir

    with SessionLocal() as session:
        # 이미 데이터가 있는지 확인
        result = session.execute(text("SELECT COUNT(*) FROM reservoirs"))
        count = result.scalar()

        if count == 0:
            reservoirs = [
                Reservoir(
                    name="gagok",
                    location="Gyeongnam Jinju",
                    capacity_m3=5000.0,
                    normal_level_min=40.0,
                    normal_level_max=70.0,
                    warning_level=75.0,
                    critical_level=80.0
                ),
                Reservoir(
                    name="haeryong",
                    location="Gyeongnam Jinju",
                    capacity_m3=3000.0,
                    normal_level_min=55.0,
                    normal_level_max=75.0,
                    warning_level=78.0,
                    critical_level=82.0
                )
            ]
            session.add_all(reservoirs)
            session.commit()
            logger.info("initial_reservoirs_created", count=len(reservoirs))


def get_db() -> Generator[Session, None, None]:
    """FastAPI 의존성 주입용 세션"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_session():
    """일반 컨텍스트 매니저 (Streamlit 등)"""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def close_db():
    """DB 연결 종료"""
    engine.dispose()
    logger.info("database_connections_closed")