"""
애플리케이션 설정 관리
Pydantic Settings를 사용한 환경변수 관리
"""
from typing import Literal, Optional
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# 프로젝트 루트 경로 찾기
def get_project_root() -> Path:
    """프로젝트 루트 디렉토리 반환"""
    current = Path(__file__).resolve()
    # settings.py -> config -> src -> 프로젝트 루트
    return current.parent.parent.parent


PROJECT_ROOT = get_project_root()
ENV_FILE = PROJECT_ROOT / ".env"


class HardwareSettings(BaseSettings):
    """하드웨어 관련 설정 - 모두 환경변수로"""

    type: Literal['simulator', 'plc', 'arduino'] = Field(
        default='simulator',
        alias='HARDWARE_TYPE'  # .env에서 읽기
    )

    # PLC 설정 - 모두 .env에서
    plc_host: str = Field(
        default='192.168.1.100',
        alias='PLC_HOST'
    )
    plc_port: int = Field(
        default=502,
        alias='PLC_PORT'
    )
    plc_unit_id: int = Field(
        default=1,
        alias='PLC_UNIT_ID'
    )
    plc_timeout: int = Field(
        default=5,
        alias='PLC_TIMEOUT'
    )

    # Arduino 설정
    arduino_port: str = Field(
        default='COM3',
        alias='ARDUINO_PORT'
    )
    arduino_baudrate: int = Field(
        default=9600,
        alias='ARDUINO_BAUDRATE'
    )

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore',
        populate_by_name=True
    )


class DatabaseSettings(BaseSettings):
    """데이터베이스 설정"""

    host: str = Field(default='localhost', alias='POSTGRES_HOST')
    port: int = Field(default=5432, alias='POSTGRES_PORT')
    database: str = Field(default='water_management', alias='POSTGRES_DB')
    user: str = Field(default='postgres', alias='POSTGRES_USER')
    password: str = Field(default='iumict00609', alias='POSTGRES_PASSWORD')

    @property
    def url(self) -> str:
        """데이터베이스 연결 URL 생성"""
        return (
            f"postgresql+asyncpg://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
        )

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),  # .env 파일 명시
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore',
        populate_by_name=True  # alias 사용 허용
    )


class AISettings(BaseSettings):
    """AI/LLM 설정"""

    lm_studio_url: str = Field(default='http://localhost:1234/v1')
    lm_studio_model: str = Field(default='exaone-4.0')
    embedding_model: str = Field(default='jhgan/ko-sroberta-multitask')

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore'
    )


class AppSettings(BaseSettings):
    """전체 애플리케이션 설정"""

    # 기본 설정
    app_name: str = "Smart Water PLC"
    debug: bool = Field(default=False)
    log_level: str = Field(default='INFO')

    # API 서버
    api_host: str = Field(default='0.0.0.0')
    api_port: int = Field(default=8000)

    # 보안
    secret_key: str = Field(default='dev-secret-key')

    # 하위 설정들 (자동으로 .env 읽음)
    hardware: HardwareSettings = Field(default_factory=HardwareSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    ai: AISettings = Field(default_factory=AISettings)

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore'
    )


# 싱글톤 인스턴스
_settings: Optional[AppSettings] = None


def get_settings() -> AppSettings:
    """설정 인스턴스 반환 (싱글톤)"""
    global _settings
    if _settings is None:
        _settings = AppSettings()
    return _settings


# 편의를 위한 직접 접근
settings = get_settings()


# 디버그: 설정 로드 확인
if __name__ == "__main__":
    print(f"Project Root: {PROJECT_ROOT}")
    print(f".env File: {ENV_FILE}")
    print(f".env Exists: {ENV_FILE.exists()}")
    print()

    s = get_settings()
    print("[Database Settings]")
    print(f"  Host: {s.database.host}")
    print(f"  Port: {s.database.port}")
    print(f"  DB: {s.database.database}")
    print(f"  User: {s.database.user}")
    print(f"  Password: {s.database.password}")
    print(f"  URL: {s.database.url}")