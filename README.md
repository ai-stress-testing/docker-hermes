# docker-hermes

Hermes is a small, framework-free chat UI backed by a stateless FastAPI
service that forwards OpenAI-format chat requests to a locally hosted
[LM Studio](https://lmstudio.ai/) instance. This repo containerizes both
pieces and wires them into a Docker Compose stack: a stable interface to
LM Studio that Hermes never has to know is swappable for another
inference provider later. LM Studio itself is not part of this stack —
it's your existing local install; the backend just connects out to it.

## Prerequisites

- Docker and Docker Compose (the `docker compose` CLI plugin).
- A local [LM Studio](https://lmstudio.ai/) instance running its local
  server (LM Studio's "Local Server" tab) with a model loaded.

## Setup

```bash
cp .env.example .env
# Edit .env if your LM Studio host/port or model name differs from the
# defaults, or if you want to change the published UI port.
docker compose up -d --build
```

This brings up two services on a dedicated bridge network (`hermes-net`):

- `hermes` — the static chat UI, served by nginx, published to the host
  (`http://localhost:8080` by default).
- `backend` — the FastAPI connector, internal to `hermes-net` only. It is
  **not** published to the host in the default stack.

Both containers run as non-root, with `cap_drop: [ALL]`, a read-only root
filesystem (writable paths are explicit `tmpfs` mounts), and
`restart: unless-stopped`. There's no `lmstudio` service to build — see
the comment at the top of `docker-compose.yml` for why.

## Verifying it's working

Check both containers report healthy:

```bash
docker compose ps
```

The UI should be reachable:

```bash
curl -i http://localhost:8080/
```

### Backend health/readiness (debugging only — not published to the host)

The backend has no host port by default. To check it directly, run a
command inside its container (or any container on `hermes-net`):

```bash
docker compose exec backend python -c \
  "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health').read())"

docker compose exec backend python -c \
  "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/ready').read())"
```

`/ready` returns `503 {"status": "not_ready", ...}` if LM Studio isn't
reachable at `LMSTUDIO_URL` — useful for confirming the backend can see
your LM Studio instance before testing a chat request.

### Chat request

The Hermes UI at `http://localhost:8080` already works end-to-end: open
it in a browser and send a message. The browser only ever talks to
`hermes` (same origin); nginx reverse-proxies `/v1/` internally to
`backend` on `hermes-net` (see `hermes/nginx.conf`), so the backend still
never needs a host port.

To send a chat request without a browser, from the host, through the
same proxied path:

```bash
curl -i http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Say hi in five words."}]}'
```

If you specifically need to reach the backend directly (bypassing the UI
and its proxy — e.g. to isolate whether an issue is in nginx or the
backend), see `docker-compose.override.yml.example`. That's a
debugging-only opt-in; it's not required for normal use.

## Tearing down

```bash
docker compose down
```

## Note on network isolation

Only `hermes` is published to the host in the default `docker-compose.yml`.
`backend` and LM Studio are reachable only from inside `hermes-net` (or,
for LM Studio, via the backend's outbound connection to your host) — this
is intentional, not an oversight. The browser never talks to `backend`
directly: `hermes/nginx.conf` reverse-proxies `/v1/` to it internally, so
`BACKEND_URL` defaults to an empty string (same-origin relative fetch)
rather than an address the browser would need to resolve itself. See the
top-of-file comment in `docker-compose.yml` and the `BACKEND_URL` note in
`.env.example`.

## Repo layout

- `backend/` — FastAPI connector service. See `backend/README.md` for
  its API and configuration reference, and `backend/Dockerfile`.
- `hermes/` — static chat UI. See `hermes/Dockerfile`; `BACKEND_URL` is
  templated into `config.js` at container startup by
  `hermes/docker-entrypoint.d/20-hermes-config.sh` (see that file and
  `hermes/nginx.conf` for how).
- `docker-compose.yml` — the stack definition.
- `.env.example` — every environment variable the stack reads, with
  defaults and comments.
- `docker-compose.override.yml.example` — optional opt-in override for
  local browser-based end-to-end testing (see above).
