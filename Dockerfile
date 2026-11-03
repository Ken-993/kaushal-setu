# Kaushal Setu - one container that trains the models and serves the website + API.
#
# Build:  docker build -t kaushal-setu .        (or: podman build -t kaushal-setu .)
# Run:    docker run --rm -p 8000:10000 kaushal-setu   then open http://localhost:8000
#
# Render builds this same file from your GitHub repo and runs it.

# Full image name (docker.io/library/...) so Podman never stops to ask which registry to use.
FROM docker.io/library/python:3.12-slim

# Python settings for containers: print logs straight away, don't write .pyc files.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=10000

# Run as a normal user, not root (safer).
RUN useradd --create-home --uid 1000 app
WORKDIR /app

# 1) Libraries first. Docker caches this step, so it only re-runs when requirements.txt changes.
COPY requirements.txt .
RUN pip install -r requirements.txt

# 2) Data + analysis code, then run the whole pipeline (phases 1-5) to train the models.
#    Cached too: it only re-runs when the data or the pipeline code changes.
COPY config.py run_all.py ./
COPY data/raw ./data/raw
COPY pipeline ./pipeline
RUN chown -R app:app /app
USER app
RUN python run_all.py

# 3) Website, API and tests. Editing these re-builds in seconds (the models above are reused).
COPY --chown=app:app backend ./backend
COPY --chown=app:app frontend ./frontend
COPY --chown=app:app tests ./tests
COPY --chown=app:app samples ./samples
COPY --chown=app:app pytest.ini ./

# 4) Run the automated tests. If any test fails, the build stops and nothing broken gets deployed.
RUN python -m pytest -q

# Render tells the app which port to use through $PORT (10000 by default).
EXPOSE 10000
CMD ["sh", "-c", "exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-10000} --proxy-headers --forwarded-allow-ips='*'"]
