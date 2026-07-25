"""Hermes Local LM Studio Connector backend.

Stateless FastAPI service that forwards OpenAI-format chat completion
requests to a locally-hosted LM Studio instance.
"""
import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .body_limit_middleware import MaxBodySizeMiddleware
from .config import settings
from .errors import (
    BackendError,
    UpstreamError,
    UpstreamTimeoutError,
    UpstreamUnavailableError,
    backend_error_handler,
    unhandled_exception_handler,
    validation_error_handler,
)
from .logging_middleware import RequestLoggingMiddleware
from .schemas import ChatCompletionRequest

logging.basicConfig(level=settings.log_level.upper(), format="%(message)s")
logger = logging.getLogger("hermes.backend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http_client = httpx.AsyncClient(base_url=settings.lmstudio_base_url)
    try:
        yield
    finally:
        await app.state.http_client.aclose()


# docs/redoc/openapi are disabled: this MVP has no auth (explicit
# non-goal) and the PRD requires no debug endpoints exposed. They're not
# reachable through nginx's default proxy path anyway (only /v1/ is
# forwarded), but the backend shouldn't rely on that as its only control.
app = FastAPI(
    title="Hermes Local LM Studio Connector",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

# Middleware order: added last runs outermost, so the body-size guard runs
# before the request is logged/routed at all.
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(MaxBodySizeMiddleware, max_bytes=settings.max_request_body_bytes)

app.add_exception_handler(BackendError, backend_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/ready")
async def ready(request: Request):
    client: httpx.AsyncClient = request.app.state.http_client
    try:
        response = await client.get(
            "/v1/models", timeout=settings.ready_check_timeout
        )
    except httpx.RequestError:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "reason": "lmstudio_unreachable"},
        )

    if 200 <= response.status_code < 300:
        return {"status": "ready"}

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "not_ready", "reason": "lmstudio_unavailable"},
    )


@app.post("/v1/chat/completions")
async def chat_completions(payload: ChatCompletionRequest, request: Request):
    client: httpx.AsyncClient = request.app.state.http_client

    body = payload.model_dump(exclude_none=True)
    if not body.get("model"):
        body["model"] = settings.default_model

    request_id = getattr(request.state, "request_id", None)

    try:
        upstream_response = await client.post(
            "/v1/chat/completions",
            json=body,
            timeout=settings.request_timeout,
        )
    except httpx.TimeoutException:
        raise UpstreamTimeoutError()
    except httpx.RequestError:
        raise UpstreamUnavailableError()

    if not (200 <= upstream_response.status_code < 300):
        logger.warning(
            "LM Studio returned non-2xx status=%s request_id=%s",
            upstream_response.status_code,
            request_id,
        )
        raise UpstreamError()

    try:
        upstream_json = upstream_response.json()
    except ValueError:
        logger.warning(
            "LM Studio returned a non-JSON response request_id=%s", request_id
        )
        raise UpstreamError("LM Studio returned an unexpected response.")

    return JSONResponse(status_code=upstream_response.status_code, content=upstream_json)
