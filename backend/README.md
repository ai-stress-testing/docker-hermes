# Hermes Backend

FastAPI service that forwards OpenAI-format chat completion requests from
the Hermes frontend to a locally-hosted LM Studio instance. Stateless: no
database, no session state, no auth.

## Endpoints

- `POST /v1/chat/completions` — accepts an OpenAI-format chat completion
  request body. If `model` is omitted, `DEFAULT_MODEL` is used. Forwards
  to LM Studio and returns its response body/status as-is on success.
- `GET /health` — always `200 {"status": "healthy"}` once the process is up.
- `GET /ready` — `200 {"status": "ready"}` if LM Studio is reachable,
  otherwise `503 {"status": "not_ready", "reason": "..."}`.

Errors (invalid payload, upstream timeout, upstream unreachable, upstream
non-2xx) are always returned as:

```json
{"error": {"type": "upstream_timeout", "message": "..."}}
```

No stack traces or raw upstream error text are ever returned to the
client.

## Configuration (environment variables)

| Variable                 | Default                 | Meaning                                                    |
|---------------------------|--------------------------|--------------------------------------------------------------|
| `LMSTUDIO_URL`            | `http://localhost:1234` | Base URL of LM Studio's OpenAI-compatible API                |
| `DEFAULT_MODEL`           | `default`                | Model used when a request omits `model`                      |
| `REQUEST_TIMEOUT`         | `30`                      | Seconds to wait for LM Studio on `/v1/chat/completions`      |
| `LOG_LEVEL`               | `INFO`                    | Python logging level                                          |
| `READY_CHECK_TIMEOUT`     | `2`                       | Seconds to wait for LM Studio on `/ready`                     |
| `MAX_REQUEST_BODY_BYTES`  | `2000000`                 | Requests larger than this are rejected with `413`            |

## Run locally

```bash
pip install -r backend/requirements.txt
LMSTUDIO_URL=http://localhost:1234 DEFAULT_MODEL=your-model-name \
  uvicorn backend.app.main:app --reload
```

## Notes / limitations

- Streaming responses (`"stream": true`) are not supported in this MVP;
  the backend always makes a single non-streaming call to LM Studio and
  returns a single JSON body.
- Request/response body content (prompts) is never logged.
