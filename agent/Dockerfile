# syntax=docker/dockerfile:1

# --- Stage 1: build a self-contained virtualenv with the agent's deps ---
FROM python:3.12-slim-bookworm AS builder

# Build tools live only in this stage; the runtime image never sees them.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build
COPY requirements.txt .
RUN pip install -r requirements.txt

# --- Stage 2: minimal runtime image ---
FROM python:3.12-slim-bookworm AS runtime

# Non-root, non-privileged user (fixed uid/gid so the workspace bind mount
# has predictable ownership across environments).
RUN groupadd --gid 10001 hermes \
    && useradd --uid 10001 --gid hermes --no-create-home --shell /usr/sbin/nologin hermes

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    WORKSPACE_DIR=/workspace \
    LMSTUDIO_URL=http://host.docker.internal:1234/v1

WORKDIR /app
COPY . ./agent/

RUN mkdir -p /workspace && chown -R hermes:hermes /workspace /app

USER hermes

ENTRYPOINT ["python", "-m", "agent.main"]
