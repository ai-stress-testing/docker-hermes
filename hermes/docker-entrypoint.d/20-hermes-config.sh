#!/bin/sh
# Runs automatically before nginx starts (the base image's own
# docker-entrypoint.sh executes every executable *.sh in
# /docker-entrypoint.d/). Renders config.js from the BACKEND_URL
# environment variable, and nginx's proxy timeout / body-size-limit
# directives from REQUEST_TIMEOUT / MAX_REQUEST_BODY_BYTES, so the
# compose file can point the UI at the backend and match its limits
# without an image rebuild.
#
# Rendered files live under tmpfs paths (mounted read-write by
# docker-compose.yml) rather than the image's own read-only paths.
# nginx.conf maps /config.js to /run/hermes-config/config.js and
# `include`s /tmp/hermes-proxy.conf inside its /v1/ proxy location.
set -eu

# Deliberately "${VAR-default}" (no colon): an *unset* BACKEND_URL falls
# back to the default below, but an explicitly empty BACKEND_URL="" (the
# compose default) is preserved as-is. Empty means "same-origin relative
# fetch", proxied by nginx's /v1/ location to the backend container —
# that's what lets a browser reach the backend without publishing it.
BACKEND_URL="${BACKEND_URL-http://localhost:8000}"
REQUEST_TIMEOUT="${REQUEST_TIMEOUT:-30}"
MAX_REQUEST_BODY_BYTES="${MAX_REQUEST_BODY_BYTES:-2000000}"

case "$REQUEST_TIMEOUT" in
    ''|*[!0-9]*) REQUEST_TIMEOUT=30 ;;
esac
case "$MAX_REQUEST_BODY_BYTES" in
    ''|*[!0-9]*) MAX_REQUEST_BODY_BYTES=2000000 ;;
esac

# A little more generous than the backend's own REQUEST_TIMEOUT so nginx
# doesn't cut the connection before the backend's own timeout has a
# chance to fire and return a clean, standardized error body.
PROXY_TIMEOUT=$((REQUEST_TIMEOUT + 15))

mkdir -p /run/hermes-config \
    /tmp/client_temp /tmp/proxy_temp /tmp/fastcgi_temp \
    /tmp/uwsgi_temp /tmp/scgi_temp

cat > /tmp/hermes-proxy.conf <<PROXYCONF
# Generated at container startup from REQUEST_TIMEOUT /
# MAX_REQUEST_BODY_BYTES (docker-entrypoint.d/20-hermes-config.sh).
proxy_send_timeout ${PROXY_TIMEOUT}s;
proxy_read_timeout ${PROXY_TIMEOUT}s;
client_max_body_size ${MAX_REQUEST_BODY_BYTES};
PROXYCONF

# BACKEND_URL is operator-controlled (via .env) but still gets embedded
# in a JS string literal below — escape backslashes and double quotes so
# a value containing either can't break out of the string and inject
# arbitrary script.
ESCAPED_BACKEND_URL=$(printf '%s' "$BACKEND_URL" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g')

cat > /run/hermes-config/config.js <<CONF
// Generated at container startup from the BACKEND_URL environment
// variable (docker-entrypoint.d/20-hermes-config.sh). The committed
// hermes/config.js in the repo is only used when serving these files
// without a container (e.g. a plain local static-file preview).
window.BACKEND_URL = "${ESCAPED_BACKEND_URL}";
CONF
