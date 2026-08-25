"""Quick manual check against a real VCF Automation server.

Bypasses the MCP protocol entirely - just exercises the client and tool
functions directly, using whatever VCFA_* config is set (.env or real
env vars). Useful for confirming auth and basic API calls work before
wiring up an MCP client.

Usage:
    python scripts/smoke_test.py
"""

import asyncio

from vcf_automation_mcp.client import VCFAClient
from vcf_automation_mcp.config import load_settings
from vcf_automation_mcp.tools import projects


async def main() -> None:
    client = VCFAClient(load_settings())
    try:
        print("Acquiring access token and listing projects...")
        result = await projects.list_projects(client, top=5)
        for p in result["projects"]:
            print(f"  - {p.get('name')} ({p.get('id')})")
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
