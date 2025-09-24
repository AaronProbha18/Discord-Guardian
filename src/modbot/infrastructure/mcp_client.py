"""MCP Client to interact with the tool server."""
from __future__ import annotations

import httpx
from typing import Any, Dict

class MCPClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.client = httpx.AsyncClient()

    async def get_tools(self) -> Dict[str, Any]:
        try:
            response = await self.client.get(f"{self.base_url}/mcp/tools")
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as e:
            print(f"An error occurred while requesting {e.request.url!r}.")
            return {}

    async def process(self, prompt: str, tools: Dict[str, Any]) -> Dict[str, Any]:
        request_payload = {
            "context": {
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            },
            "tools": tools
        }
        try:
            response = await self.client.post(f"{self.base_url}/mcp", json=request_payload)
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as e:
            print(f"An error occurred while requesting {e.request.url!r}.")
            return {}

