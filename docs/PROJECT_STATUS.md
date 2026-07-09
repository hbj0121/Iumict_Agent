# 📊 Iumict Agent — 프로젝트 현황 문서

> 📅 작성일: 2026-07-09 (프로젝트 재개 시점 기준 코드 스캔 결과)
> 🎯 목적: 중단 기간 이후 시스템을 빠르게 재파악하기 위한 스냅샷. 이후 진행 상황과는 달라질 수 있으니, 실제 개발 재개 전 코드와 다시 대조할 것.

---

## 1. 🏗️ 프로젝트 개요

- **이름**: Smart Water PLC (Iumict Agent)
- **목적**: Modbus PLC 기반 배수지(저수조) 실시간 수위 모니터링 + 펌프 자동/수동 제어, 여기에 LLM 기반 PDF 문서 RAG Q&A를 결합한 설비관리 에이전트
- **스택**: Python 3.11, FastAPI(백엔드 API), Streamlit(UI), SQLAlchemy + PostgreSQL(pgvector), pymodbus, LangChain, LM Studio(로컬 LLM, OpenAI 호환 API)
- **아키텍처**: Clean Architecture 지향 — `core`(도메인/서비스) / `infrastructure`(DB, 하드웨어, AI 연동) / `application`(API, UI) 3계층 분리
- **원격 저장소**: `https://github.com/hbj0121/Iumict_Agent` (branch: `master`)

---

## 2. 📁 디렉토리 구조

```
Iumict Agent/
├── main.py                        # (미추적) 임시 수동 테스트 스크립트
├── check_settings.py / debug_connection.py / test_db.py  # (미추적) 개발용 스크립트
├── docker-compose.yml              # PostgreSQL(pgvector) 컨테이너 정의
├── pyproject.toml / poetry.lock    # (⚠ git 미추적, 아래 4장 참고)
├── src/
│   ├── config/settings.py          # Pydantic Settings (Hardware/Database/AI/App)
│   ├── core/
│   │   ├── domain/                 # 비어있음 (__init__.py만 존재)
│   │   └── services/rag_service.py # RAG 오케스트레이션 서비스
│   ├── infrastructure/
│   │   ├── ai/
│   │   │   ├── llm_client.py       # LM Studio/OpenAI 호환 챗 클라이언트
│   │   │   └── rag/                # pdf_parser / embedder / vector_store
│   │   ├── database/
│   │   │   ├── connection.py       # SQLAlchemy 동기 엔진 (psycopg)
│   │   │   ├── models.py           # Reservoir / WaterLevelReading / PumpControlHistory / PredictionHistory
│   │   │   └── repository.py       # Reservoir/WaterLevel/PumpControl 리포지토리 (동기)
│   │   └── hardware/
│   │       ├── interface.py        # HardwareController 추상 클래스 (ABC)
│   │       ├── modbus_plc.py       # 실제 PLC(Modbus TCP) 구현체
│   │       ├── simulator.py        # 시뮬레이터 구현체
│   │       └── factory.py          # 설정값에 따라 구현체 선택 생성
│   └── application/
│       ├── api/
│       │   ├── main.py             # FastAPI 앱 (lifespan에서 하드웨어 connect/disconnect)
│       │   └── routes/{hardware,rag}.py
│       └── ui/
│           ├── app.py              # Streamlit 진입점 (사이드바 라디오 방식)
│           └── pages/              # main_dashboard / settings_page / rag_page (멀티페이지 방식)
└── tests/                          # unit/integration 폴더만 존재, 실제 테스트 없음
```

---

## 3. 📋 기능별 구현 현황

| 영역 | 상태 | 비고 |
|---|:---:|---|
| 하드웨어 추상화 (`interface.py`) | ✅ 완료 | `WaterLevelReading`/`PumpCommand`/`PumpStatus` dataclass + `HardwareController` ABC(6개 메서드) |
| 시뮬레이터 (`simulator.py`) | ✅ 완료 | 139줄, 인터페이스 6개 메서드 모두 구현 |
| 실 PLC 제어 (`modbus_plc.py`) | ✅ 구현됨 (실기 검증 필요) | 283줄, Modbus TCP 레지스터 read/write + `_health_check` 포함. 실제 PLC 연동 테스트 여부는 문서상 확인 불가 |
| 팩토리 (`factory.py`) | ✅ 완료 | `HARDWARE_TYPE` 설정값으로 simulator/plc 전환 |
| DB 모델/리포지토리 | ⚠️ 전환 중 | 원래 `asyncpg` 비동기로 설계됐다가 `repository.py`에 async 버전 전체가 **주석 처리**되고 동기(`Session`) 버전으로 교체됨. `connection.py`도 동기 엔진(psycopg)으로 전환 완료 |
| RAG 파이프라인 | ✅ 코드 완료 | PDF 파싱(SHA256 중복 체크, 청크 분할) → 임베딩(LM Studio/OpenAI) → pgvector 유사도 검색 → LLM 답변 생성까지 전체 파이프라인 존재 |
| RAG API (`routes/rag.py`) | ⚠️ 미연결 | upload/query/list/delete 엔드포인트는 구현됐지만, **`api/main.py`에 라우터가 등록되어 있지 않아 실제로는 호출 불가** (`include_router(hardware.router)`만 있음) |
| 하드웨어 API (`routes/hardware.py`) | ✅ 등록됨 | status/water-level/pump 제어 엔드포인트 |
| Streamlit UI | ⚠️ 이중 구조 | `app.py`(사이드바 라디오) + `ui/pages/`(표준 멀티페이지)가 병행. 진입점 정리 필요 |
| 예측 기능 (`PredictionHistory`) | ❌ 미구현 | DB 테이블 스키마만 존재, 서비스/API/UI 로직 없음. `app.py`의 "📈 실시간 차트" 페이지도 "구현 예정" 안내만 표시 |
| 테스트 | ❌ 없음 | `tests/unit`, `tests/integration` 폴더는 있으나 `__init__.py` 외 파일 없음. pytest 의존성만 설정됨 |

---

## 4. ⚠️ 정합성 이슈 / 확인이 필요한 부분

> 🔴 즉시 조치 권장 &nbsp;|&nbsp; 🟡 개발 재개 전 확인 &nbsp;|&nbsp; 🔵 기술 부채

1. 🔴 **RAG 라우터 미등록** — [src/application/api/main.py](../src/application/api/main.py)에 `app.include_router(rag.router)` 추가 필요. 현재는 `hardware.router`만 등록됨.
2. 🟡 **UI 내비게이션 이중화** — `app.py`(사이드바 라디오)와 `ui/pages/`(Streamlit 자동 멀티페이지)가 공존. 실행 시 Streamlit이 `pages/`를 자동 인식해 좌측에 별도 페이지 목록도 함께 뜰 가능성 있음. 하나의 방식으로 통일 필요.
3. 🔴 **`pyproject.toml` / `poetry.lock` / `poetry.toml`이 git에 한 번도 커밋된 적 없음** (`git log`상 이력 없음). README의 `git clone` → `poetry install` 절차를 그대로 따르면 의존성 정의 파일이 없어 실패함.
4. 🔴 **DB 자격 증명 노출** — [docker-compose.yml](../docker-compose.yml)에 실 비밀번호(`iumict00609`)가 평문으로 커밋 이력에 3회 이상 남아있음. `src/config/settings.py`의 기본값만 로컬에서 `changeme`로 수정된 상태(미커밋)이고, `docker-compose.yml` 자체는 그대로. 원격 저장소가 GitHub이므로 노출 위험 있음 — 교체 및 `.env` 이전 권장.
5. 🟡 **DB 레이어 async → sync 전환 미완료 파급** — `connection.py`/`repository.py`는 동기로 전환됐는데, 루트의 `main.py`(미추적 스크립트)는 여전히 `await init_db()`, `async with get_session()` 형태로 호출하고 있어 **그대로 실행하면 에러**. 전환 이후 관련 스크립트가 갱신되지 않은 상태.
6. 🔵 **`settings.py`에 `API_BASE_URL` 필드 없음** — `ui/pages/settings_page.py`, `ui/pages/rag_page.py`가 `get_settings().API_BASE_URL`을 참조하지만 현재 `AppSettings`에는 해당 필드가 정의되어 있지 않음. `try/except`로 감싸 환경변수 fallback 처리는 되어 있어 즉시 죽지는 않지만, 의도한 설정값이 조용히 무시되는 상태.
7. 🔵 **테스트 커버리지 없음** — 하드웨어 시뮬레이터, RAG 파이프라인, 리포지토리 등 핵심 로직에 대한 자동화 테스트 전무.

---

## 5. 🔀 Git 상태 (스캔 시점)

**최근 커밋 (최신순)**
```
acf9e1f  Streamlit UI
9ba77d8  Streamlit UI
29374e1  Streamlit UI
d0f50ad  Streamlit UI
2a55c9b  FastAPI Backend - HW제어, 이벤트
1c960c5  src-infrastructure 작성
bf3e311 / 02aaf1e / 46803db  Readme 수정
3847065  기본설정 Readme.md 추가
a831580  mkdir 작업
```

**📥 Staged (커밋 대기)**
- `src/application/ui/pages/main_dashboard.py` (신규)
- `src/application/ui/pages/settings_page.py` (신규)

**✏️ Modified (미스테이징)**
- `.idea/Iumict Agent.iml`
- `src/config/settings.py` (DB 비밀번호 기본값 `iumict00609` → `changeme`)

**❓ Untracked**
- `.gitignore`, `check_settings.py`, `debug_connection.py`, `main.py`, `test_db.py`
- `poetry.lock`, `poetry.toml`, `pyproject.toml` ← 위 4장 3번 이슈

---

## 6. 🗺️ 다음 개발 후보 (우선순위 미정, 논의용)

- [ ] RAG 라우터를 API에 등록하고 UI(`rag_page.py`)와 실제 연결 확인
- [ ] Streamlit 내비게이션 방식 하나로 통일 (`app.py` 단일 진입 vs `pages/` 표준 멀티페이지)
- [ ] `pyproject.toml` 등 의존성 파일 커밋 + `docker-compose.yml` 비밀번호를 `.env`/환경변수로 이전
- [ ] `settings.py`에 `API_BASE_URL` 필드 추가
- [ ] DB 레이어 동기 전환에 맞춰 루트 스크립트(`main.py` 등) 정리 또는 삭제
- [ ] `PredictionHistory` 관련 예측 기능 구현 (모델은 이미 존재)
- [ ] 하드웨어/RAG/리포지토리 계층 pytest 테스트 추가