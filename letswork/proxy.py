"""
LetsWork stdio MCP proxy.

Claude Code connects to this as a stdio MCP server (reliable, no streaming issues).
This proxy forwards all tool calls to the host's HTTP MCP server over Cloudflare.

Usage (done automatically by `letswork join`):
    claude mcp add letswork -- letswork-proxy --url <URL> --token <TOKEN>
"""
import sys
import asyncio
import argparse
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types


def make_proxy_server(base_url: str, token: str) -> Server:
    """Create an MCP Server that forwards calls to the remote host."""
    # Ensure URL ends with /mcp
    url = base_url.rstrip("/")
    if not url.endswith("/mcp"):
        url = url + "/mcp"

    server = Server("letswork-proxy")

    async def _http_post(payload: dict) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                },
            )
            r.raise_for_status()
            # Parse SSE response: find 'data: {...}' line
            for line in r.text.splitlines():
                if line.startswith("data: "):
                    import json
                    return json.loads(line[6:])
        raise RuntimeError("No data in response")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        resp = await _http_post({
            "jsonrpc": "2.0", "id": 1,
            "method": "tools/list", "params": {},
        })
        tools = []
        for t in resp.get("result", {}).get("tools", []):
            schema = t.get("inputSchema", {"type": "object", "properties": {}})
            # Strip 'token' from schema — proxy injects it automatically
            schema = dict(schema)
            props = dict(schema.get("properties", {}))
            props.pop("token", None)
            schema["properties"] = props
            required = [r for r in schema.get("required", []) if r != "token"]
            if required:
                schema["required"] = required
            elif "required" in schema:
                del schema["required"]
            tools.append(types.Tool(
                name=t["name"],
                description=t.get("description", ""),
                inputSchema=schema,
            ))
        return tools

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
        # Inject token automatically so guest doesn't have to think about it
        arguments = {**arguments, "token": token}
        resp = await _http_post({
            "jsonrpc": "2.0", "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        })
        result = resp.get("result", {})
        content = result.get("content", [])
        out = []
        for item in content:
            if item.get("type") == "text":
                out.append(types.TextContent(type="text", text=item["text"]))
        if not out:
            out.append(types.TextContent(type="text", text=str(result)))
        return out

    return server


async def _run(url: str, token: str) -> None:
    server = make_proxy_server(url, token)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> None:
    parser = argparse.ArgumentParser(description="LetsWork MCP stdio proxy")
    parser.add_argument("--url", required=True, help="Host MCP URL")
    parser.add_argument("--token", required=True, help="Session token")
    args = parser.parse_args()
    asyncio.run(_run(args.url, args.token))


if __name__ == "__main__":
    main()
