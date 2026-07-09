"""
FastAPI 메인 애플리케이션
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from src.config.settings import get_settings
from src.application.api.routes import hardware

settings = get_settings()

# 전역 하드웨어 컨트롤러
from src.infrastructure.hardware.factory import create_hardware_controller

_controller = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    애플리케이션 시작/종료 시 실행되는 이벤트
    """
    # Startup
    global _controller
    _controller = create_hardware_controller()
    await _controller.connect()
    print(f"✅ 하드웨어 연결 완료: {type(_controller).__name__}")

    yield

    # Shutdown
    if _controller:
        await _controller.disconnect()
        print("✅ 하드웨어 연결 해제")


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="PLC 기반 스마트 배수지 관리 시스템 API",
    lifespan=lifespan
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 운영 환경에서는 구체적인 도메인 지정
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================
# 기본 엔드포인트
# ============================================

@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "message": "Smart Water PLC API",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
        "hardware": settings.hardware.type
    }


@app.get("/health")
async def health_check():
    """헬스체크"""
    return {
        "status": "healthy",
        "hardware_connected": await _controller.is_connected() if _controller else False
    }


# ============================================
# 라우터 등록
# ============================================

app.include_router(hardware.router)

# ============================================
# 개발 서버 실행
# ============================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.application.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug
    )