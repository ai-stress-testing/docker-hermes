#!/bin/sh
# Computes uvicorn's own graceful-shutdown deadline from REQUEST_TIMEOUT so
# it always finishes (and uvicorn exits cleanly) with margin to spare
# before Docker's stop_grace_period (docker-compose.yml derives that from
# the same REQUEST_TIMEOUT) sends SIGKILL. Single source of truth: change
# REQUEST_TIMEOUT in .env and both sides move together, no separate value
# to keep in sync by hand.
#
# `exec` replaces this shell with uvicorn (same PID), so uvicorn still
# receives SIGTERM directly — the point made in the Dockerfile comment
# about exec-form CMD holds; this script only computes a flag value first.
set -eu

REQUEST_TIMEOUT="${REQUEST_TIMEOUT:-30}"

case "$REQUEST_TIMEOUT" in
    ''|*[!0-9]*) REQUEST_TIMEOUT=30 ;;
esac

if [ "$REQUEST_TIMEOUT" -gt 5 ]; then
    GRACEFUL_SHUTDOWN=$((REQUEST_TIMEOUT - 5))
else
    GRACEFUL_SHUTDOWN="$REQUEST_TIMEOUT"
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000 \
    --timeout-graceful-shutdown "$GRACEFUL_SHUTDOWN"
