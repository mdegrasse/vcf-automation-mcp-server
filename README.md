# vcf-automation-mcp

An MCP server that wraps the VCF Automation (formerly Aria Automation) REST API,
exposing projects, catalog items, and deployments as MCP tools so an LLM client can
browse and manage provisioned infrastructure directly.

This is the counterpart to [vcf-ops-mcp](../vcf-ops-mcp-server), which wraps VCF
Operations (vROps) instead.

**This server can provision and delete real infrastructure** (`request_catalog_item`,
`run_deployment_action`/`run_deployment_resource_action`, `delete_deployment`). Treat
its bearer token and the underlying VCF Automation refresh token with the same care as
credentials that can create and destroy VMs across your monitored environment - because
that's exactly what they are.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # then fill in your VCF Automation details
```

Required configuration (via `.env` or real environment variables):

| Variable                      | Description                                                        |
|--------------------------------|----------------------------------------------------------------------|
| `VCFA_BASE_URL`                | Base URL of the VCF Automation appliance, e.g. `https://vcfa.example.com` |
| `VCFA_REFRESH_TOKEN`           | API refresh token generated in the UI (My Account > API Tokens)      |
| `VCFA_ORG`                     | Tenant org name to authenticate as. Leave unset for provider ("system") level |
| `VCFA_TOKEN_URL`               | Advanced: override the computed OAuth token endpoint                 |
| `VCFA_VERIFY_SSL`              | Set `false` to skip TLS verification against self-signed lab instances |
| `VCFA_TIMEOUT`                 | Per-request timeout in seconds (default `30`)                        |
| `VCFA_API_VERSION_IAAS`        | `?apiVersion=` for the IaaS API (default `2021-07-15`)               |
| `VCFA_API_VERSION_CATALOG`     | `?apiVersion=` for the Catalog API (default `2020-08-25`)            |
| `VCFA_API_VERSION_DEPLOYMENT`  | `?apiVersion=` for the Deployment API (default `2020-08-25`)         |

### Getting a refresh token

Unlike VCF Operations (username/password), VCF Automation authenticates with a
long-lived **API refresh token** that you generate once in the UI, which this server
exchanges for short-lived (~1 hour) bearer access tokens on your behalf, caching and
renewing them transparently:

1. Sign in to the VCF Automation UI as the org (tenant) you want the server to act as.
2. Click your username in the top-right corner > **My Account** > **API Tokens** > **New**.
3. Name and create the token, then copy it into `VCFA_REFRESH_TOKEN`.
4. Set `VCFA_ORG` to that org's name (as shown in the Provider Management Portal), or
   leave it unset if you generated the token at the provider ("system") level instead.

The exact token-exchange path (`VCFA_TOKEN_URL`) has been documented inconsistently
across VCF Automation releases; this server defaults to `/tm/oauth/tenant/<org>/token`
(tenant) or `/oauth/provider/token` (provider) and lets you override it if your
instance's actual path differs.

Server transport/auth configuration (also via `.env` or real environment variables):

| Variable                  | Description                                                              |
|---------------------------|---------------------------------------------------------------------------|
| `VCFA_MCP_TRANSPORT`      | `streamable-http` (default) or `stdio`                                    |
| `VCFA_MCP_HOST`           | Bind host for streamable-http (default `127.0.0.1`)                       |
| `VCFA_MCP_PORT`           | Bind port for streamable-http (default `8000`)                            |
| `VCFA_MCP_BEARER_TOKEN`   | Required for streamable-http. Clients must send `Authorization: Bearer <value>` |
| `VCFA_MCP_ALLOWED_HOSTS`  | Comma-separated Host-header allowlist for DNS-rebinding protection        |

## Running

By default this runs as a standalone **remote server** over streamable-http, bound to
`127.0.0.1:8000`, requiring a bearer token on every request:

```bash
export VCFA_MCP_BEARER_TOKEN="$(openssl rand -hex 32)"
vcf-automation-mcp
# or
python -m vcf_automation_mcp
```

`GET /healthz` is unauthenticated (for load balancer/orchestrator liveness checks);
everything else requires the bearer token. `127.0.0.1` only listens locally - to
actually reach it from another host, bind `VCFA_MCP_HOST=0.0.0.0` (or run it behind a
reverse proxy) and make sure the bearer token is the only thing standing between the
network and credentials capable of provisioning and deleting infrastructure across your
managed environment, so treat it like any other secret and prefer TLS termination (e.g.
a reverse proxy) in front of it rather than plaintext HTTP over an untrusted network.

When `VCFA_MCP_HOST` isn't `127.0.0.1`/`localhost`, FastMCP's own DNS-rebinding
protection (a check against the incoming request's `Host` header) has nothing to
allowlist by default, since it only auto-configures that allowlist for a loopback host.
Left unset, no Host-header check is enforced and the bearer token is your only gate -
fine on a network you trust, but set `VCFA_MCP_ALLOWED_HOSTS` to the hostname(s)/IP:port
clients actually connect through (comma-separated) for defense in depth on a shared or
untrusted network.

Point an MCP client at it as a streamable-http server, e.g. in Claude Code:

```bash
claude mcp add --transport http vcf-automation http://<host>:8000/mcp \
  --header "Authorization: Bearer <your-token>"
```

### Running over stdio instead

For local use where an MCP client spawns the server itself as a subprocess (no network
exposure needed), set `VCFA_MCP_TRANSPORT=stdio` - the bearer token is not required in
this mode. Example Claude Desktop config:

```json
{
  "mcpServers": {
    "vcf-automation": {
      "command": "/absolute/path/to/.venv/bin/vcf-automation-mcp",
      "env": {
        "VCFA_MCP_TRANSPORT": "stdio",
        "VCFA_BASE_URL": "https://vcfa.example.com",
        "VCFA_REFRESH_TOKEN": "changeme",
        "VCFA_ORG": "my-tenant-org"
      }
    }
  }
}
```

## Tools

**Projects**
- `list_projects` — visibility/isolation boundaries for provisioned resources
- `get_project` — full detail for one project

**Catalog**
- `list_catalog_items` — browse blueprints/templates available to request, optionally by project
- `get_catalog_item` — full detail for one catalog item
- `list_catalog_item_versions` — published versions of a catalog item that can be requested
- `request_catalog_item` — **provisions a new deployment** from a catalog item

**Deployments**
- `list_deployments` — provisioned instances of a blueprint/catalog item
- `get_deployment` — full detail for one deployment
- `list_deployment_resources` — resources (VMs, networks, disks, etc.) within a deployment
- `get_deployment_resource` — full detail for one resource within a deployment
- `list_deployment_actions` — day-2 actions available on a deployment (e.g. ChangeLease)
- `list_deployment_resource_actions` — day-2 actions available on a resource (e.g. PowerOff)
- `run_deployment_action` — **runs a day-2 action** on a deployment
- `run_deployment_resource_action` — **runs a day-2 action** on a resource
- `delete_deployment` — **destroys** a deployment and its provisioned resources

**Requests**
- `get_request` — poll the status of an asynchronous request (deployment/day-2 action)

## Testing

```bash
pip install -e ".[dev]"
pytest
```

Tests mock the VCF Automation HTTP API with `respx` - no live instance required.

## Notes

- Pinned to `mcp<2.0.0`: the MCP Python SDK's 2.x line renamed `FastMCP` to
  `MCPServer` and moved it to `mcp.server.mcpserver`. This project targets the
  well-established 1.x `mcp.server.fastmcp.FastMCP` API.
- The VCF Automation REST API surface is large (cloud accounts, networking, policies,
  onboarding, blueprints, etc.); this server intentionally covers only the
  consumption/day-2 path - projects, catalog, deployments, requests - not
  infrastructure setup (cloud accounts, zones, regions).
