"""Rejects oversized request bodies before they are handed to the app.

A Content-Length above the limit is rejected immediately without reading
the body. If Content-Length is absent (e.g. chunked transfer), the body is
buffered while streaming and rejected as soon as the running total exceeds
the limit, without waiting for the full body to arrive.
"""
import json

from starlette.types import ASGIApp, Receive, Scope, Send


class MaxBodySizeMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        content_length = headers.get(b"content-length")
        if content_length is not None:
            try:
                if int(content_length) > self.max_bytes:
                    await self._send_413(send)
                    return
            except ValueError:
                pass  # malformed header; fall through to streaming enforcement

        buffered = []
        total = 0
        more_body = True

        while more_body:
            message = await receive()
            if message["type"] != "http.request":
                buffered.append(message)
                break

            body = message.get("body", b"")
            total += len(body)
            if total > self.max_bytes:
                await self._send_413(send)
                return

            buffered.append(message)
            more_body = message.get("more_body", False)

        index = 0

        async def replay_receive():
            nonlocal index
            if index < len(buffered):
                message = buffered[index]
                index += 1
                return message
            return await receive()

        await self.app(scope, replay_receive, send)

    @staticmethod
    async def _send_413(send: Send) -> None:
        body = json.dumps(
            {
                "error": {
                    "type": "payload_too_large",
                    "message": "Request body exceeds the maximum allowed size.",
                }
            }
        ).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
