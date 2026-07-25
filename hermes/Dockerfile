# syntax=docker/dockerfile:1
#
# Build context is the hermes/ directory (see docker-compose.yml:
# services.hermes.build.context). Static files, no build step. Uses the
# "unprivileged" nginx variant so the container runs as a non-root user
# out of the box, listening on 8080 (an unprivileged port — no
# NET_BIND_SERVICE capability needed, consistent with cap_drop: [ALL] in
# docker-compose.yml).

FROM nginxinc/nginx-unprivileged:1.27-alpine

# Own nginx.conf: routes /config.js to a writable tmpfs path and points
# nginx's own temp/pid files at /tmp so the rest of the filesystem can
# stay read-only. See hermes/nginx.conf for details.
COPY nginx.conf /etc/nginx/nginx.conf

# Hook script the base image's entrypoint runs automatically before
# starting nginx; renders config.js from BACKEND_URL at container start.
COPY docker-entrypoint.d/20-hermes-config.sh /docker-entrypoint.d/20-hermes-config.sh
RUN chmod +x /docker-entrypoint.d/20-hermes-config.sh

# Static app files only — config.js is intentionally NOT copied here. The
# committed hermes/config.js is the local/no-container default; inside the
# container it's regenerated at startup (see 20-hermes-config.sh) and
# served from a separate writable path that nginx.conf aliases to
# /config.js.
COPY index.html style.css app.js /usr/share/nginx/html/

EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD ["wget", "--quiet", "--tries=1", "--spider", "http://127.0.0.1:8080/"]
