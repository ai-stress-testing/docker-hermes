#!/bin/sh
# Runs automatically before nginx starts (the base image's own
# docker-entrypoint.sh executes every executable *.sh in
# /docker-entrypoint.d/). Renders config.js from the BACKEND_URL
# environment variable so the compose file can point the UI at the
# backend service without an image rebuild.
#
# The rendered file is written to a tmpfs path (/run/hermes-config,
# mounted read-write by docker-compose.yml) rather than into
# /usr/share/nginx/html, so the static asset directory shipped in the
# image can stay part of the read-only root filesystem. nginx.conf maps
# /config.js to this path (see hermes/nginx.conf).
set -eu

# Deliberately "${VAR-default}" (no colon): an *unset* BACKEND_URL falls
# back to the default below, but an explicitly empty BACKEND_URL="" (the
# compose default) is preserved as-is. Empty means "same-origin relative
# fetch", proxied by nginx's /v1/ location to the backend container —
# that's what lets a browser reach the backend without publishing it.
BACKEND_URL="${BACKEND_URL-http://localhost:8000}"

mkdir -p /run/hermes-config \
    /tmp/client_temp /tmp/proxy_temp /tmp/fastcgi_temp \
    /tmp/uwsgi_temp /tmp/scgi_temp

cat > /run/hermes-config/config.js <<CONF
// Generated at container startup from the BACKEND_URL environment
// variable (docker-entrypoint.d/20-hermes-config.sh). The committed
// hermes/config.js in the repo is only used when serving these files
// without a container (e.g. a plain local static-file preview).
window.BACKEND_URL = "${BACKEND_URL}";
CONF
