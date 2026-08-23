# 빌드 컨텍스트는 **repo 루트** (docker-compose 의 context: .) — data/knowledge 를 이미지에 담아야 하기 때문 (ISSUE A6).
# compose 는 ./data 를 볼륨으로 덮어써서 재빌드 없이 지식 문서를 고칠 수 있고, OpenShift 는 이미지 안의 것을 쓴다.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN groupadd --system app && useradd --system --gid app --create-home app
COPY api/requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt
COPY api/app ./app
COPY api/mock ./mock
COPY data ./data
RUN chown -R app:app /app
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
