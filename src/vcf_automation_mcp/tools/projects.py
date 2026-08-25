from __future__ import annotations

from typing import Any

from ..client import Service, VCFAClient


async def list_projects(
    client: VCFAClient,
    *,
    name: str | None = None,
    top: int = 100,
    skip: int = 0,
) -> dict[str, Any]:
    """List projects (visibility/isolation boundaries for provisioned resources).

    name does an exact match; leave it unset to list all projects."""
    params: dict[str, Any] = {"$top": top, "$skip": skip}
    if name:
        params["$filter"] = f"name eq '{name}'"
    data = await client.get(Service.IAAS, "/projects", params=params)
    return {"projects": data.get("content", data), "totalElements": data.get("totalElements")}


async def get_project(client: VCFAClient, project_id: str) -> Any:
    """Get full details for a single project by its identifier."""
    return await client.get(Service.IAAS, f"/projects/{project_id}")
