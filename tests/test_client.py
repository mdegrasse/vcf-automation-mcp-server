import httpx
import pytest
import respx

from vcf_automation_mcp.client import Service, VCFAAPIError, VCFAAuthError, VCFAClient
from vcf_automation_mcp.config import Settings


def make_settings(**overrides) -> Settings:
    defaults = dict(
        base_url="https://vcfa.example.com",
        refresh_token="refresh-tok",
        org="myorg",
        verify_ssl=True,
        timeout=5.0,
    )
    defaults.update(overrides)
    return Settings(**defaults)


@pytest.mark.asyncio
@respx.mock
async def test_acquires_token_and_calls_api_with_api_version():
    respx.post("https://vcfa.example.com/tm/oauth/tenant/myorg/token").mock(
        return_value=httpx.Response(200, json={"access_token": "tok-1", "token_type": "Bearer", "expires_in": 3600})
    )
    route = respx.get("https://vcfa.example.com/iaas/api/projects").mock(
        return_value=httpx.Response(200, json={"content": [{"id": "p1"}]})
    )

    client = VCFAClient(make_settings())
    try:
        data = await client.get(Service.IAAS, "/projects")
    finally:
        await client.aclose()

    assert data["content"][0]["id"] == "p1"
    request = route.calls.last.request
    assert request.headers["Authorization"] == "Bearer tok-1"
    assert request.url.params["apiVersion"] == "2021-07-15"


@pytest.mark.asyncio
@respx.mock
async def test_provider_level_uses_provider_token_endpoint():
    respx.post("https://vcfa.example.com/oauth/provider/token").mock(
        return_value=httpx.Response(200, json={"access_token": "provider-tok", "token_type": "Bearer"})
    )
    route = respx.get("https://vcfa.example.com/deployment/api/deployments").mock(
        return_value=httpx.Response(200, json={"content": []})
    )

    client = VCFAClient(make_settings(org=None))
    try:
        await client.get(Service.DEPLOYMENT, "/deployments")
    finally:
        await client.aclose()

    assert route.calls.last.request.headers["Authorization"] == "Bearer provider-tok"


@pytest.mark.asyncio
@respx.mock
async def test_retries_once_on_401_with_fresh_token():
    respx.post("https://vcfa.example.com/tm/oauth/tenant/myorg/token").mock(
        side_effect=[
            httpx.Response(200, json={"access_token": "stale", "token_type": "Bearer"}),
            httpx.Response(200, json={"access_token": "fresh", "token_type": "Bearer"}),
        ]
    )

    calls = []

    def responder(request: httpx.Request) -> httpx.Response:
        calls.append(request.headers["Authorization"])
        if request.headers["Authorization"] == "Bearer stale":
            return httpx.Response(401, json={"message": "expired"})
        return httpx.Response(200, json={"content": []})

    respx.get("https://vcfa.example.com/iaas/api/projects").mock(side_effect=responder)

    client = VCFAClient(make_settings())
    try:
        data = await client.get(Service.IAAS, "/projects")
    finally:
        await client.aclose()

    assert data == {"content": []}
    assert calls == ["Bearer stale", "Bearer fresh"]


@pytest.mark.asyncio
@respx.mock
async def test_auth_failure_raises():
    respx.post("https://vcfa.example.com/tm/oauth/tenant/myorg/token").mock(
        return_value=httpx.Response(401, text="bad refresh token")
    )

    client = VCFAClient(make_settings())
    try:
        with pytest.raises(VCFAAuthError):
            await client.get(Service.IAAS, "/projects")
    finally:
        await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_api_error_raises_with_status_code():
    respx.post("https://vcfa.example.com/tm/oauth/tenant/myorg/token").mock(
        return_value=httpx.Response(200, json={"access_token": "tok-1", "token_type": "Bearer"})
    )
    respx.get("https://vcfa.example.com/deployment/api/deployments/missing").mock(
        return_value=httpx.Response(404, json={"message": "not found"})
    )

    client = VCFAClient(make_settings())
    try:
        with pytest.raises(VCFAAPIError) as excinfo:
            await client.get(Service.DEPLOYMENT, "/deployments/missing")
        assert excinfo.value.status_code == 404
    finally:
        await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_token_url_override():
    respx.post("https://vcfa.example.com/custom/token/path").mock(
        return_value=httpx.Response(200, json={"access_token": "tok-1", "token_type": "Bearer"})
    )
    respx.get("https://vcfa.example.com/catalog/api/items").mock(return_value=httpx.Response(200, json={}))

    client = VCFAClient(make_settings(token_url="/custom/token/path"))
    try:
        await client.get(Service.CATALOG, "/items")
    finally:
        await client.aclose()
