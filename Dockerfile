FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies first — cached independently of source for fast rebuilds.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Runtime modules. ALL eight Python files are required: app.py imports
# classifier, matcher, reply, safety, selftest, metrics. selftest.py
# also reads hostile_cases.json at import time (CASES_PATH), so the JSON
# must be in the image for /selftest to work.
COPY app.py classifier.py matcher.py reply.py safety.py selftest.py metrics.py ./
COPY hostile_cases.json ./

EXPOSE 8000

# Hit /health — the cheapest endpoint. If this fails the container will
# be marked unhealthy by any orchestrator (Docker / k8s / ECS).
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=3).status==200 else 1)"

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
