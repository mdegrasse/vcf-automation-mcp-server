from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse

from vcf_automation_mcp.client import VCFAClient
from vcf_automation_mcp.config import load_server_settings, load_settings
from vcf_automation_mcp.tools import catalog as catalog_tools
from vcf_automation_mcp.tools import deployments as deployment_tools
from vcf_automation_mcp.tools import projects as project_tools
from vcf_automation_mcp.tools import requests as request_tools


@dataclass
class AppContext:
    client: VCFAClient


@asynccontextmanager
async def app_lifespan(_server: FastMCP) -> AsyncIterator[AppContext]:
    client = VCFAClient(load_settings())
    try:
        yield AppContext(client=client)
    finally:
        await client.aclose()


_server_settings = load_server_settings()

# FastMCP only auto-enables DNS-rebinding-protection Host checks when constructed with the
# (default) loopback host, using a loopback-only allowlist. This server is deliberately bound
# to 0.0.0.0 for remote access, so that default never matches the Host header real clients
# send and every request gets rejected with HTTP 421. Configure the allowlist explicitly from
# VCFA_MCP_ALLOWED_HOSTS instead; if it's unset, rely on the bearer token for auth and skip
# the Host check rather than silently locking every remote client out.
_transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=bool(_server_settings.allowed_hosts),
    allowed_hosts=_server_settings.allowed_hosts,
)

mcp = FastMCP(
    "vcf-automation",
    lifespan=app_lifespan,
    host=_server_settings.host,
    port=_server_settings.port,
    transport_security=_transport_security,
)


@mcp.custom_route("/healthz", methods=["GET"])
async def health_check(_request: Request) -> JSONResponse:
    """Unauthenticated liveness check for load balancers/orchestrators."""
    return JSONResponse({"status": "ok"})


def _client(ctx: Context) -> VCFAClient:
    return ctx.request_context.lifespan_context.client


@mcp.tool()
async def list_projects(ctx: Context, name: str | None = None, top: int = 100, skip: int = 0) -> dict:
    """List projects (visibility/isolation boundaries for provisioned resources).
    name does an exact match; leave it unset to list all projects."""
    return await project_tools.list_projects(_client(ctx), name=name, top=top, skip=skip)


@mcp.tool()
async def get_project(ctx: Context, project_id: str) -> dict:
    """Get full details for a single project by its identifier."""
    return await project_tools.get_project(_client(ctx), project_id)


@mcp.tool()
async def list_catalog_items(ctx: Context, project_id: str | None = None, search: str | None = None) -> dict:
    """List catalog items (blueprints/templates available to request as deployments),
    optionally scoped to a project and/or filtered by a name search term."""
    return await catalog_tools.list_catalog_items(_client(ctx), project_id=project_id, search=search)


@mcp.tool()
async def get_catalog_item(ctx: Context, item_id: str) -> dict:
    """Get full details for a single catalog item by its identifier."""
    return await catalog_tools.get_catalog_item(_client(ctx), item_id)


@mcp.tool()
async def list_catalog_item_versions(ctx: Context, item_id: str) -> dict:
    """List the published versions of a catalog item that can be requested for deployment."""
    return await catalog_tools.list_catalog_item_versions(_client(ctx), item_id)


@mcp.tool()
async def request_catalog_item(
    ctx: Context,
    item_id: str,
    project_id: str,
    deployment_name: str,
    inputs: dict[str, Any] | None = None,
    version: str | None = None,
    reason: str | None = None,
) -> dict:
    """Request a new deployment from a catalog item. inputs supplies values for the
    blueprint's request-time input fields (e.g. image, flavor, count) - see
    get_catalog_item / list_catalog_item_versions for what a given item expects.
    Returns the new deploymentId; use get_deployment to track progress."""
    return await catalog_tools.request_catalog_item(
        _client(ctx),
        item_id,
        project_id=project_id,
        deployment_name=deployment_name,
        inputs=inputs,
        version=version,
        reason=reason,
    )


@mcp.tool()
async def list_deployments(ctx: Context, name: str | None = None, project_id: str | None = None) -> dict:
    """List deployments (provisioned instances of a blueprint/catalog item), optionally
    filtered by exact name and/or project."""
    return await deployment_tools.list_deployments(_client(ctx), name=name, project_id=project_id)


@mcp.tool()
async def get_deployment(ctx: Context, deployment_id: str) -> dict:
    """Get full details for a single deployment by its identifier."""
    return await deployment_tools.get_deployment(_client(ctx), deployment_id)


@mcp.tool()
async def list_deployment_resources(ctx: Context, deployment_id: str) -> dict:
    """List the resources (VMs, networks, disks, etc.) provisioned by a deployment."""
    return await deployment_tools.list_deployment_resources(_client(ctx), deployment_id)


@mcp.tool()
async def get_deployment_resource(ctx: Context, deployment_id: str, resource_id: str) -> dict:
    """Get full details for a single resource within a deployment."""
    return await deployment_tools.get_deployment_resource(_client(ctx), deployment_id, resource_id)


@mcp.tool()
async def list_deployment_actions(ctx: Context, deployment_id: str) -> dict:
    """List the day-2 actions available on a deployment as a whole (e.g. ChangeLease,
    Delete). Each entry's `valid` field indicates whether it can currently be run."""
    return await deployment_tools.list_deployment_actions(_client(ctx), deployment_id)


@mcp.tool()
async def list_deployment_resource_actions(ctx: Context, deployment_id: str, resource_id: str) -> dict:
    """List the day-2 actions available on a specific resource within a deployment
    (e.g. PowerOn, PowerOff, Add.Disk). Each entry's `valid` field indicates whether it
    can currently be run."""
    return await deployment_tools.list_deployment_resource_actions(_client(ctx), deployment_id, resource_id)


@mcp.tool()
async def run_deployment_action(
    ctx: Context, deployment_id: str, action_id: str, inputs: dict[str, Any] | None = None
) -> dict:
    """Run a day-2 action on a deployment as a whole (e.g. Deployment.ChangeLease). Get
    valid action_id values and their expected inputs from list_deployment_actions.
    Returns a request; poll its status with get_request."""
    return await deployment_tools.run_deployment_action(_client(ctx), deployment_id, action_id, inputs=inputs)


@mcp.tool()
async def run_deployment_resource_action(
    ctx: Context,
    deployment_id: str,
    resource_id: str,
    action_id: str,
    inputs: dict[str, Any] | None = None,
) -> dict:
    """Run a day-2 action on a specific resource within a deployment (e.g. PowerOff,
    Add.Disk). Get valid action_id values and their expected inputs from
    list_deployment_resource_actions. Returns a request; poll its status with get_request."""
    return await deployment_tools.run_deployment_resource_action(
        _client(ctx), deployment_id, resource_id, action_id, inputs=inputs
    )


@mcp.tool()
async def delete_deployment(ctx: Context, deployment_id: str, force: bool = False) -> dict:
    """Delete a deployment and clean up its provisioned resources. This is destructive
    and cannot be undone.

    If a normal delete fails (e.g. due to a stuck dependency), set force=True to fall
    back to the Infrastructure-as-a-Service API's forceDelete, which removes VCF
    Automation's records of the deployment even if cleaning up the underlying cloud
    resources didn't fully succeed - verify manually afterwards that nothing was left
    behind in the cloud account."""
    return await deployment_tools.delete_deployment(_client(ctx), deployment_id, force=force)


@mcp.tool()
async def get_request(ctx: Context, request_id: str) -> dict:
    """Get the status of an asynchronous deployment/day-2-action request (e.g. from
    request_catalog_item, run_deployment_action, run_deployment_resource_action, or
    delete_deployment). status is one of IN_PROGRESS/SUCCESSFUL/FAILED."""
    return await request_tools.get_request(_client(ctx), request_id)
