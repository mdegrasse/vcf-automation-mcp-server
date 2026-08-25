from __future__ import annotations

from typing import Any

from ..client import Service, VCFAClient


async def list_catalog_items(
    client: VCFAClient,
    *,
    project_id: str | None = None,
    search: str | None = None,
) -> dict[str, Any]:
    """List catalog items (blueprints/templates available to request as deployments),
    optionally scoped to a project and/or filtered by a name search term.

    The Catalog API's projectId query parameter does not reliably scope /items results
    server-side, so when project_id is given this walks the full paginated catalog and
    filters client-side on each item's projectIds (the projects it's entitled/shared to)."""
    items: list[dict[str, Any]] = []
    page = 0
    size = 100
    while True:
        data = await client.get(
            Service.CATALOG,
            "/items",
            params={"projectId": project_id, "search": search, "page": page, "size": size},
        )
        page_items = data.get("content", data if isinstance(data, list) else [])
        items.extend(page_items)
        total = data.get("totalElements") if isinstance(data, dict) else None
        if not page_items or total is None or len(items) >= total:
            break
        page += 1

    if project_id:
        items = [item for item in items if project_id in (item.get("projectIds") or [])]

    return {"items": items, "totalElements": len(items)}


async def get_catalog_item(client: VCFAClient, item_id: str) -> Any:
    """Get full details for a single catalog item by its identifier."""
    return await client.get(Service.CATALOG, f"/items/{item_id}")


async def list_catalog_item_versions(client: VCFAClient, item_id: str) -> Any:
    """List the published versions of a catalog item that can be requested for deployment."""
    return await client.get(Service.CATALOG, f"/items/{item_id}/versions")


async def request_catalog_item(
    client: VCFAClient,
    item_id: str,
    *,
    project_id: str,
    deployment_name: str,
    inputs: dict[str, Any] | None = None,
    version: str | None = None,
    reason: str | None = None,
) -> Any:
    """Request a new deployment from a catalog item.

    inputs supplies values for the blueprint's request-time input fields (e.g. image,
    flavor, count) - see get_catalog_item / list_catalog_item_versions for what a given
    item expects. Returns the new deploymentId; use get_deployment to track progress."""
    body = {
        "deploymentName": deployment_name,
        "projectId": project_id,
        "inputs": inputs or {},
        "version": version,
        "reason": reason,
    }
    body = {k: v for k, v in body.items() if v is not None}
    return await client.post(Service.CATALOG, f"/items/{item_id}/request", json=body)
