"""Pytest fixtures for the HindClaw Python client test suite.

The generated ``hindclaw_client_api`` wraps an aiohttp ``ClientSession``.
aiohttp does not honour httpx's ``ASGITransport`` pattern, so we cannot
mount an ASGI app directly against the generated client the way an
httpx-based client would allow. Instead these tests spin up a real
uvicorn server on an ephemeral loopback port, serving a tiny
hand-written ASGI callable that captures request state and returns
canned JSON responses for the five HindClaw routes the wrapper
exercises:

* POST   ``/ext/hindclaw/me/templates``
* PATCH  ``/ext/hindclaw/me/templates/{template_id}``
* POST   ``/ext/hindclaw/admin/templates``
* PATCH  ``/ext/hindclaw/admin/templates/{template_id}``
* POST   ``/ext/hindclaw/banks``

The stub app is a raw ASGI callable (no Starlette/FastAPI dependency)
so the test suite can run against the minimal ``[test]`` optional
extras: pytest, pytest-asyncio, pytest-timeout, uvicorn, httpx.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import re
import socket
import threading
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import pytest
import uvicorn

Scope = dict[str, Any]
Receive = Callable[[], Awaitable[dict[str, Any]]]
Send = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass
class StubState:
    """Accumulated request state captured by the stub app."""

    captured_requests: list[dict[str, Any]] = field(default_factory=list)


_TEMPLATE_ID_PATH = re.compile(r"^/ext/hindclaw/(me|admin)/templates/([^/]+)$")


def _template_response_payload(template_id: str, name: str, scope: str) -> dict[str, Any]:
    return {
        "id": template_id,
        "name": name,
        "description": None,
        "category": None,
        "integrations": [],
        "tags": [],
        "scope": scope,
        "owner": "user-1",
        "source_name": None,
        "source_scope": None,
        "source_owner": None,
        "source_revision": None,
        "installed_at": "2026-04-15T00:00:00Z",
        "updated_at": "2026-04-15T00:00:00Z",
        "manifest": {"version": "1"},
    }


async def _read_body(receive: Receive) -> bytes:
    chunks: list[bytes] = []
    while True:
        message = await receive()
        if message["type"] == "http.request":
            chunks.append(message.get("body", b""))
            if not message.get("more_body", False):
                break
        elif message["type"] == "http.disconnect":
            break
    return b"".join(chunks)


async def _send_json(send: Send, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


def _build_stub_app(state: StubState) -> Callable[[Scope, Receive, Send], Awaitable[None]]:
    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            # lifespan or anything else — no-op
            if scope["type"] == "lifespan":
                while True:
                    message = await receive()
                    if message["type"] == "lifespan.startup":
                        await send({"type": "lifespan.startup.complete"})
                    elif message["type"] == "lifespan.shutdown":
                        await send({"type": "lifespan.shutdown.complete"})
                        return
            return

        method: str = scope["method"]
        path: str = scope["path"]
        body_bytes = await _read_body(receive)
        body: Any = json.loads(body_bytes.decode("utf-8")) if body_bytes else None

        path_params: dict[str, str] = {}
        match = _TEMPLATE_ID_PATH.match(path)
        if match is not None:
            path_params["template_id"] = match.group(2)

        state.captured_requests.append(
            {
                "method": method,
                "path": path,
                "body": body,
                "path_params": path_params,
            }
        )

        body_payload: dict[str, Any] = body or {}

        if method == "POST" and path == "/ext/hindclaw/me/templates":
            await _send_json(
                send,
                200,
                _template_response_payload(
                    body_payload.get("id", "tmpl-x"),
                    body_payload.get("name", "x"),
                    "personal",
                ),
            )
            return
        if method == "PATCH" and match is not None and match.group(1) == "me":
            await _send_json(
                send,
                200,
                _template_response_payload(
                    path_params["template_id"], body_payload.get("name") or "x", "personal"
                ),
            )
            return
        if method == "POST" and path == "/ext/hindclaw/admin/templates":
            await _send_json(
                send,
                200,
                _template_response_payload(
                    body_payload.get("id", "tmpl-x"),
                    body_payload.get("name", "x"),
                    "server",
                ),
            )
            return
        if method == "PATCH" and match is not None and match.group(1) == "admin":
            await _send_json(
                send,
                200,
                _template_response_payload(
                    path_params["template_id"], body_payload.get("name") or "x", "server"
                ),
            )
            return
        if method == "POST" and path == "/ext/hindclaw/banks":
            await _send_json(
                send,
                200,
                {
                    "bank_id": body_payload.get("bank_id", "bank-x"),
                    "template": body_payload.get("template", "tmpl-x"),
                    "bank_created": True,
                    "import_result": {
                        "bank_id": body_payload.get("bank_id", "bank-x"),
                        "config_applied": False,
                        "mental_models_created": [],
                        "mental_models_updated": [],
                        "directives_created": [],
                        "directives_updated": [],
                    },
                },
            )
            return

        await _send_json(send, 404, {"detail": "stub route not found"})

    return app


def _reserve_port() -> int:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class _UvicornThread(threading.Thread):
    """Run uvicorn.Server on a background thread with its own event loop."""

    def __init__(
        self,
        app: Callable[[Scope, Receive, Send], Awaitable[None]],
        port: int,
    ) -> None:
        super().__init__(daemon=True)
        config = uvicorn.Config(
            app,
            host="127.0.0.1",
            port=port,
            log_level="warning",
            access_log=False,
        )
        self.server = uvicorn.Server(config)
        # Background-thread-safety: uvicorn installs SIGINT/SIGTERM
        # handlers in __main__, which Python rejects outside the main
        # thread. Replace the installer with a no-op.
        self.server.install_signal_handlers = lambda: None

    def run(self) -> None:
        asyncio.run(self.server.serve())


@pytest.fixture
async def stub_server() -> AsyncIterator[tuple[str, StubState]]:
    """Launch a uvicorn server running the stub app.

    Yields ``(base_url, state)`` where ``base_url`` is the loopback URL
    a ``HindclawClient`` should be pointed at and ``state`` is the
    request-capture object populated by the stub handlers.
    """
    state = StubState()
    app = _build_stub_app(state)
    port = _reserve_port()
    thread = _UvicornThread(app, port)
    thread.start()

    # Poll the server's started flag so the fixture returns as soon as
    # uvicorn finishes startup. 200 iterations at 20ms = 4s hard ceiling.
    for _ in range(200):
        if getattr(thread.server, "started", False):
            break
        await asyncio.sleep(0.02)
    else:
        raise RuntimeError("uvicorn stub server failed to start within timeout")

    try:
        yield f"http://127.0.0.1:{port}", state
    finally:
        thread.server.should_exit = True
        thread.join(timeout=5)
