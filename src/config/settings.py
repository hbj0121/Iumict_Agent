"""
애플리케이션 설정 관리
Pydantic Settings를 사용한 환경변수 관리
"""
from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class HardwareSettings(BaseSettings):
    """하드웨어 관련 설정"""
    type: Literal['simulator', 'plc', 'arduino']= Field(
        default='simulator',
        description="하드웨어 타입")
# PLC 설정
    plc_host:str= Field(default='192.168.1.100')
    plc_port: int= Field(default=502)
    plc_unit_id: int= Field(default=1)
    plc_timeout: int= Field(default=5)
    model_config = SettingsConfigDict(
        env_prefix='',
        case_sensitive=False)

class DatabaseSettings(BaseSettings):
    """데이터베이스 설정"""
    host:str= Field(default='localhost', alias='POSTGRES_HOST')
    port: int= Field(default=5432, alias='POSTGRES_PORT')
    database:str= Field(default='water_management', alias='POSTGRES_DB')
    user:str= Field(default='postgres', alias='POSTGRES_USER')
    password:str= Field(default='changeme', alias='POSTGRES_PASSWORD')
    @property
    def url(self)->str:
        """데이터베이스 연결 URL 생성"""
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

    model_config = SettingsConfigDict(
        env_prefix='',
        case_sensitive=False
)
class AISettings(BaseSettings):
    """AI/LLM 설정"""
    lm_studio_url:str= Field(default='http://localhost:1234/v1')
    lm_studio_model:str= Field(default='exaone-4.0')
    embedding_model:str= Field(default='jhgan/ko-sroberta-multitask')
    model_config = SettingsConfigDict(
        env_prefix='',
        case_sensitive=False)

class AppSettings(BaseSettings):
    """전체 애플리케이션 설정"""
    # 기본 설정
    app_name:str="Smart Water PLC"
    debug:bool= Field(default=False)
    log_level:str= Field(default='INFO')
    # API 서버
    api_host:str= Field(default='0.0.0.0')
    api_port: int= Field(default=8000)
    # 보안
    secret_key:str= Field(default='dev-secret-key')
    # 하위 설정
    hardware: HardwareSettings = Field(default_factory=HardwareSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    ai: AISettings = Field(default_factory=AISettings)
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore'
)
# 싱글톤 인스턴스
_settings: AppSettings |None=None
def get_settings()-> AppSettings:
    """설정 인스턴스 반환 (싱글톤)"""
    global _settings
    if _settings is None:
            _settings = AppSettings()
    return _settings

# 편의를 위한 직접 접근
settings = get_settings()