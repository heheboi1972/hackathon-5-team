# 시작하기

## Docker로 백엔드 실행

```bash
docker compose up --build
```

기본 실행은 `AI_PROVIDER=mock`이며 Postgres, Qdrant, FastAPI만 시작합니다.

- Live: `http://localhost:8000/health/live`
- Ready: `http://localhost:8000/health/ready`
- Swagger UI: `http://localhost:8000/docs`

프론트 최소 골격도 함께 실행하려면 다음 명령을 사용합니다.

```bash
docker compose --profile frontend up --build
```

## Python으로 API만 실행

```bash
python -m venv .venv
.venv/Scripts/activate
pip install -r api/requirements.txt
uvicorn --app-dir api app.main:app --reload
```

macOS/Linux에서는 활성화 명령으로 `source .venv/bin/activate`를 사용합니다. 실제 비밀값이 필요한 경우 `.env.example`을 복사해 `.env`를 만들되, `.env`는 Git에 추가하지 마세요.

## 확인

```bash
python scripts/smoke_test.py
```

현재 단계의 API는 계약 확인용 Mock/stub입니다. 파싱, DB 저장, Qdrant 검색, watsonx 호출은 후속 구현 대상입니다.
