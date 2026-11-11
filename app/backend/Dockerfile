FROM python:3.12-alpine

RUN apk upgrade --no-cache

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py query_regression.py ./
COPY telemetry/ ./telemetry/

RUN adduser -D -u 10001 appuser
USER appuser
# JIRA-002 learning release: rollback the backend task revision to undo.
ENV QUERY_REGRESSION_DRILL=true

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
