import secrets

from starlette.datastructures import Headers
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class BearerAuthMiddleware:
    """Raw ASGI middleware enforcing a single static bearer token.

    Deliberately not starlette.middleware.base.BaseHTTPMiddleware: that buffers
    the response body, which breaks the long-lived streaming responses the
    streamable-http transport relies on.
    """

    def __init__(self, app: ASGIApp, *, token: str, exempt_paths: frozenset[str] = frozenset()):
        self.app = app
        self.token = token
        self.exempt_paths = exempt_paths

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] in self.exempt_paths:
            await self.app(scope, receive, send)
            return

        expected = f"Bearer {self.token}"
        provided = Headers(scope=scope).get("authorization")
        if provided is None or not secrets.compare_digest(provided, expected):
            response = PlainTextResponse("Unauthorized", status_code=401, headers={"WWW-Authenticate": "Bearer"})
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
