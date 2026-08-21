FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

WORKDIR /app

COPY requirements.txt pyproject.toml ./
RUN pip install --retries 10 -r requirements.txt

COPY selection_engine ./selection_engine
COPY factor_system ./factor_system

EXPOSE 8000

CMD ["uvicorn", "selection_engine.api:app", "--host", "0.0.0.0", "--port", "8000"]
