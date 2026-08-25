from __future__ import annotations

from typing import Any

from ..client import Service, VCFAClient


async def list_deployments(
    client: VCFAClient,
    *,
    name: str | None = None,
    project_id: str | None = None,
) -> dict[str, Any]:
    """List deployments (provisioned instances of a blueprint/catalog item), optionally
    filtered by exact name and/or project."""
    data = await client.get(
        Service.DEPLOYMENT,
        "/deployments",
        params={"name": name, "projectId": project_id},
    )
    return {"deployments": data.get("content", data), "totalElements": data.get("totalElements")}


async def get_deployment(client: VCFAClient, deployment_id: str) -> Any:
    """Get full details for a single deployment by its identifier."""
    return await client.get(Service.DEPLOYMENT, f"/deployments/{deployment_id}")


async def list_deployment_resources(client: VCFAClient, deployment_id: str) -> Any:
    """List the resources (VMs, networks, disks, etc.) provisioned by a deployment."""
    return await client.get(Service.DEPLOYMENT, f"/deployments/{deployment_id}/resources")


async def get_deployment_resource(client: VCFAClient, deployment_id: str, resource_id: str) -> Any:
    """Get full details for a single resource within a deployment."""
    return await client.get(Service.DEPLOYMENT, f"/deployments/{deployment_id}/resources/{resource_id}")


async def list_deployment_actions(client: VCFAClient, deployment_id: str) -> Any:
    """List the day-2 actions available on a deployment as a whole (e.g. ChangeLease,
    Delete). Each entry's `valid` field indicates whether it can currently be run."""
    return await client.get(Service.DEPLOYMENT, f"/deployments/{deployment_id}/actions")


async def list_deployment_resource_actions(client: VCFAClient, deployment_id: str, resource_id: str) -> Any:
    """List the day-2 actions available on a specific resource within a deployment
    (e.g. PowerOn, PowerOff, Add.Disk). Each entry's `valid` field indicates whether it
    can currently be run."""
    return await client.get(Service.DEPLOYMENT, f"/deployments/{deployment_id}/resources/{resource_id}/actions")


async def run_deployment_action(
    client: VCFAClient,
    deployment_id: str,
    action_id: str,
    *,
    inputs: dict[str, Any] | None = None,
) -> Any:
    """Run a day-2 action on a deployment as a whole (e.g. Deployment.ChangeLease). Get
    valid action_id values and their expected inputs from list_deployment_actions.
    Returns a request; poll its status with get_request."""
    body: dict[str, Any] = {"actionId": action_id}
    if inputs:
        body["inputs"] = inputs
    return await client.post(Service.DEPLOYMENT, f"/deployments/{deployment_id}/requests", json=body)


async def run_deployment_resource_action(
    client: VCFAClient,
    deployment_id: str,
    resource_id: str,
    action_id: str,
    *,
    inputs: dict[str, Any] | None = None,
) -> Any:
    """Run a day-2 action on a specific resource within a deployment (e.g. PowerOff,
    Add.Disk). Get valid action_id values and their expected inputs from
    list_deployment_resource_actions. Returns a request; poll its status with get_request."""
    body: dict[str, Any] = {"actionId": action_id}
    if inputs:
        body["inputs"] = inputs
    return await client.post(
        Service.DEPLOYMENT, f"/deployments/{deployment_id}/resources/{resource_id}/requests", json=body
    )


async def delete_deployment(
    client: VCFAClient,
    deployment_id: str,
    *,
    force: bool = False,
) -> Any:
    """Delete a deployment and clean up its provisioned resources. This is destructive
    and cannot be undone.

    If a normal delete fails (e.g. due to a stuck dependency), set force=True to fall
    back to the Infrastructure-as-a-Service API's forceDelete, which removes VCF
    Automation's records of the deployment even if cleaning up the underlying cloud
    resources didn't fully succeed - verify manually afterwards that nothing was left
    behind in the cloud account."""
    if force:
        return await client.delete(Service.IAAS, f"/deployments/{deployment_id}", params={"forceDelete": True})
    return await client.delete(Service.DEPLOYMENT, f"/deployments/{deployment_id}")
