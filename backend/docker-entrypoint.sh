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

# backend/app/config.py types REQUEST_TIMEOUT as a float, so fractional
# values are valid input; shell arithmetic below is integer-only. Drop
# the fractional part rather than rejecting the whole value — see the
# matching comment in hermes/docker-entrypoint.d/20-hermes-config.sh,
# which hit this as a real regression (non-integer REQUEST_TIMEOUT was
# silently resetting the proxy timeout to 30s). Same fix, same reasoning,
# applied here too so this script's fallback can't drift below the
# proxy's.
case "$REQUEST_TIMEOUT" in
    *.*) REQUEST_TIMEOUT="${REQUEST_TIMEOUT%%.*}" ;;
esac
case "$REQUEST_TIMEOUT" in
    ''|*[!0-9]*)
        echo "WARN: REQUEST_TIMEOUT is not a valid number of seconds; using 30s" >&2
        REQUEST_TIMEOUT=30
        ;;
esac

if [ "$REQUEST_TIMEOUT" -gt 5 ]; then
    GRACEFUL_SHUTDOWN=$((REQUEST_TIMEOUT - 5))
else
    GRACEFUL_SHUTDOWN="$REQUEST_TIMEOUT"
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000 \
    --timeout-graceful-shutdown "$GRACEFUL_SHUTDOWN"
