from __future__ import annotations

from typing import Any

from ..client import Service, VCFAClient


async def get_request(client: VCFAClient, request_id: str) -> Any:
    """Get the status of an asynchronous deployment/day-2-action request (e.g. from
    request_catalog_item, run_deployment_action, run_deployment_resource_action, or
    delete_deployment). status is one of IN_PROGRESS/SUCCESSFUL/FAILED."""
    return await client.get(Service.DEPLOYMENT, f"/requests/{request_id}")
