markdown
# Iumict_Agent - Smart Water PLC - 스마트 배수지 관리 시스템
PLC(Modbus) 기반 실시간 수위 모니터링 및 자동 제어 시스템

## 🛠 설치 및 실행
### 1. 저장소 클론
```bash
git clone https://github.com/hbj0121/Iumict_Agent
cd Iumict_Agent
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
## 📄 라이선스
MIT License
