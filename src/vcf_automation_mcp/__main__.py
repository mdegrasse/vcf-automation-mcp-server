import sys

from .config import load_server_settings
from .http_auth import BearerAuthMiddleware
from .server import mcp

HEALTH_CHECK_PATH = "/healthz"


def main() -> None:
    settings = load_server_settings()

    if settings.transport == "stdio":
        mcp.run(transport="stdio")
        return

    if not settings.bearer_token:
        sys.exit(
            "VCFA_MCP_BEARER_TOKEN must be set to run with the streamable-http transport "
            "(or set VCFA_MCP_TRANSPORT=stdio to run locally over stdio instead)."
        )

    import uvicorn

    app = mcp.streamable_http_app()
    app.add_middleware(
        BearerAuthMiddleware,
        token=settings.bearer_token,
        exempt_paths=frozenset({HEALTH_CHECK_PATH}),
    )
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
