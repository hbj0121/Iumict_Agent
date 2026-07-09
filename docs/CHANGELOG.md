# 📋 Iumict Agent — CHANGELOG

> 기능이 추가/변경될 때마다 아래 형식으로 항목을 추가한다. 최신 항목이 위로 오도록 작성(역순).
> 형식: **무엇을** / **왜** / **어떻게 사용** 3줄 요약 + 관련 커밋.
> 시점 파악용 스냅샷은 [PROJECT_STATUS.md](PROJECT_STATUS.md) 참고 (이 문서는 시간순 이력, 그쪽은 현재 상태).

---

## 🚧 [Unreleased] — 커밋 대기 중 (2026-07-09 기준 staged/미커밋)

- 📦 **무엇을**: `ui/pages/main_dashboard.py`, `ui/pages/settings_page.py` 신규 작성 (staged). `settings.py` DB 비밀번호 기본값 변경(미스테이징).
- 💡 **왜**: Streamlit을 단일 `app.py` 방식에서 `pages/` 표준 멀티페이지 구조로 이전 시도 중으로 추정.
- ▶️ **어떻게 사용**: 아직 `app.py`와 병행 상태라 실제 진입점 정리 필요 (`PROJECT_STATUS.md` 3장 참고). 커밋 전 내비게이션 방식 결정 필요.

---

## ✨ 2026-03-05 — PDF RAG 파이프라인 전체 추가

- 📦 **무엇을**: PDF 업로드 → 파싱/청킹(`pdf_parser.py`) → 임베딩(`embedder.py`, LM Studio/OpenAI 호환) → pgvector 저장·유사도 검색(`vector_store.py`) → LLM 답변 생성(`llm_client.py`, `rag_service.py`) → FastAPI 라우트(`routes/rag.py`) → Streamlit 페이지(`ui/pages/rag_page.py`)까지 RAG 기능 일체를 한 번에 구현.
- 💡 **왜**: 설비 매뉴얼 등 PDF 문서를 업로드해두고 자연어로 질의응답할 수 있게 하기 위함.
- ▶️ **어떻게 사용**: `RAGService`를 `app.state.rag`에 싱글톤으로 올려서 라우터가 참조하는 구조로 설계됨. **⚠️ 단, 현재 `api/main.py`에 `rag.router`가 `include_router`로 등록되어 있지 않아 실제로는 호출 불가 상태** — 사용하려면 등록 작업 필요.
- 🔗 **커밋**: `acf9e1f` (커밋 메시지는 "Streamlit UI"로 되어있으나 실제 diff는 RAG 파이프라인 전체 신규 — 커밋 메시지와 내용 불일치 주의)

---

## ✨ 2026-01-23 ~ 2026-03-04 — Streamlit UI 초기 구현

- 📦 **무엇을**: `app.py` 단일 파일 기반 대시보드 / 수위 모니터링 / 펌프 제어 화면. DB 모델(`models.py`: Reservoir, WaterLevelReading, PumpControlHistory, PredictionHistory) 및 리포지토리 최초 작성.
- 💡 **왜**: 운영자가 웹 UI에서 배수지 수위·펌프 상태를 바로 확인하고 제어할 수 있게 하기 위함.
- ▶️ **어떻게 사용**: `poetry run streamlit run src/application/ui/app.py`
- 🔗 **커밋**: `d0f50ad`, `29374e1`, `9ba77d8`

---

## 🏗️ 2026-01-22 — FastAPI 백엔드 (하드웨어 제어/이벤트)

- 📦 **무엇을**: FastAPI 앱(`api/main.py`) 생성. `lifespan`에서 앱 시작/종료 시 하드웨어 connect/disconnect 자동 처리. `hardware` 라우터(status, water-level 조회, pump 제어) 등록.
- 💡 **왜**: Streamlit UI 외에 다른 클라이언트(외부 시스템, 스크립트)도 HTTP API로 하드웨어를 조회/제어할 수 있게 하기 위함.
- ▶️ **어떻게 사용**: `poetry run uvicorn src.application.api.main:app --reload` → `/docs`에서 Swagger 확인.
- 🔗 **커밋**: `2a55c9b`

---

## 🏗️ 2026-01-22 — 인프라 계층(하드웨어 추상화) 작성

- 📦 **무엇을**: `HardwareController` 추상 인터페이스(`interface.py`), 시뮬레이터 구현체(`simulator.py`), 실 PLC Modbus TCP 구현체(`modbus_plc.py`), 설정값 기반 구현체 선택 팩토리(`factory.py`).
- 💡 **왜**: 실제 PLC 장비 없이도 시뮬레이터로 개발·테스트 가능하게 하고, 실기 연결 시에는 코드 변경 없이 설정만 바꿔 전환할 수 있는 구조가 필요했음.
- ▶️ **어떻게 사용**: `.env`의 `HARDWARE_TYPE=simulator` 또는 `HARDWARE_TYPE=plc`로 전환. PLC 사용 시 `PLC_HOST`/`PLC_PORT`/`PLC_UNIT_ID` 설정.
- 🔗 **커밋**: `1c960c5`

---

## 🌱 2026-01-20 ~ 2026-01-21 — 프로젝트 초기 설정

- 📦 **무엇을**: 디렉토리 구조(Clean Architecture: core/infrastructure/application) 골격, README, 기본 설정 파일.
- 💡 **왜**: 프로젝트 시작 및 아키텍처 방향 설정.
- ▶️ **어떻게 사용**: 해당 없음.
- 🔗 **커밋**: `a831580`, `3847065`, `46803db`, `02aaf1e`, `bf3e311`