from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from vcf_automation_mcp.http_auth import BearerAuthMiddleware


async def _ok(_request):
    return PlainTextResponse("ok")


def make_app() -> Starlette:
    app = Starlette(routes=[Route("/protected", _ok), Route("/healthz", _ok)])
    app.add_middleware(BearerAuthMiddleware, token="secret-token", exempt_paths=frozenset({"/healthz"}))
    return app


def test_rejects_missing_authorization_header():
    client = TestClient(make_app())
    response = client.get("/protected")
    assert response.status_code == 401


def test_rejects_wrong_token():
    client = TestClient(make_app())
    response = client.get("/protected", headers={"Authorization": "Bearer wrong"})
    assert response.status_code == 401


def test_accepts_correct_token():
    client = TestClient(make_app())
    response = client.get("/protected", headers={"Authorization": "Bearer secret-token"})
    assert response.status_code == 200
    assert response.text == "ok"


def test_exempt_path_bypasses_auth():
    client = TestClient(make_app())
    response = client.get("/healthz")
    assert response.status_code == 200
