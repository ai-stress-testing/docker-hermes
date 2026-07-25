# syntax=docker/dockerfile:1
#
# Build context is the backend/ directory (see docker-compose.yml:
# services.backend.build.context). Multi-stage: dependencies are resolved
# and installed into a venv in the builder stage; the runtime stage never
# sees pip, a compiler, or the build cache, and runs as a non-root user.

########################################
# Stage 1: builder — resolve and install pinned dependencies
########################################
FROM python:3.12.8-slim-bookworm AS builder

WORKDIR /build

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

########################################
# Stage 2: runtime — minimal, non-root, no build tools, no pip cache
########################################
FROM python:3.12.8-slim-bookworm AS runtime

# PYTHONDONTWRITEBYTECODE: the runtime root filesystem is intended to be
# mounted read-only (see docker-compose.yml); don't try to write .pyc
# files. PYTHONUNBUFFERED: flush stdout/stderr immediately so container
# log capture doesn't buffer/delay the structured request logs.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:${PATH}"

RUN groupadd --system --gid 10001 hermes \
    && useradd --system --uid 10001 --gid hermes --no-create-home \
       --shell /usr/sbin/nologin hermes

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY app ./app
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chown -R hermes:hermes /app \
    && chmod +x /usr/local/bin/docker-entrypoint.sh

USER hermes

EXPOSE 8000

# No curl/wget in the slim base; use the stdlib so the image doesn't need
# an extra package just for the healthcheck.
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status == 200 else 1)"]

# docker-entrypoint.sh computes --timeout-graceful-shutdown from
# REQUEST_TIMEOUT and then `exec`s uvicorn, which replaces the shell
# process (same PID) — uvicorn still receives SIGTERM directly, so
# graceful shutdown of in-flight requests still works exactly as if it
# were the literal CMD.
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
