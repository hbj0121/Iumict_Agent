markdown
# Smart Water PLC - 스마트 배수지 관리 시스템
PLC(Modbus) 기반 실시간 수위 모니터링 및 자동 제어 시스템
## 🚀 기술 스택- **PLC 통신**: Pymodbus- **백엔드**: FastAPI, SQLAlchemy- **프론트엔드**: Streamlit- **AI/ML**: PyTorch (LSTM), LangChain (RAG)- **데이터베이스**: PostgreSQL + pgvector- **인프라**: Docker, Docker Compose
## 📦 프로젝트 구조
smart-water-plc/
├── src/
│   ├── core/              
# 비즈니스 로직
│   ├── infrastructure/    # 외부 시스템 (PLC, DB, AI)
│   ├── application/       # API & UI
│   └── config/           
# 설정 관리
├── tests/                
├── docs/                 
└── scripts/              
# 테스트
# 문서
# 유틸리티 스크립트

## 🛠 설치 및 실행
### 1. 저장소 클론
```bash
git clone <repository-url>
cd smart-water-plc
```
### 2. Poetry 설치
```bash
pip install poetry
```
### 3. 의존성 설치
```bash
poetry install
```
### 4. 환경변수 설정
```bash
copy .env.example .env
# .env 파일을 열어 설정 수정
```
### 5. 실행
```bash
# API 서버
poetry run uvicorn src.application.api.main:app --reload
# Streamlit UI
poetry run streamlit run src/application/ui/app.py
```
## 📝 개발 상태- [x] 프로젝트 구조 설정- [x] 의존성 관리 (Poetry)- [x] 설정 시스템 (Pydantic)- [ ] PLC 통신 레이어- [ ] 데이터베이스 모델- [ ] LSTM 예측 모델- [ ] RAG 시스템- [ ] FastAPI 백엔드- [ ] Streamlit 프론트엔드- [ ] Docker 환경 구성
## 📄 라이선스
MIT License
