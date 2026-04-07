"""
LetsWork stdio MCP proxy.

Claude Code connects to this as a stdio MCP server (reliable, no streaming issues).
This proxy forwards all tool calls to the host's HTTP MCP server using a proper
MCP client session (required by FastMCP's streamable HTTP transport).

Usage (done automatically by `letswork join`):
    claude mcp add letswork -- letswork-proxy --url <URL> --token <TOKEN>
"""
import sys
import asyncio
import argparse
import logging
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession, types

log = logging.getLogger("letswork.proxy")


def _setup_logging(debug: bool) -> None:
    level = logging.DEBUG if debug else logging.WARNING
    logging.basicConfig(
        stream=sys.stderr,
        level=level,
        format="[proxy %(levelname)s] %(message)s",
    )


def make_proxy_server(base_url: str, token: str) -> tuple:
    """Create an MCP Server that forwards calls to the remote host via a proper session."""
    url = base_url.rstrip("/")
    if not url.endswith("/mcp"):
        url = url + "/mcp"

    server = Server("letswork-proxy")
    # Shared session state — populated once the client connects
    _session: ClientSession | None = None

    async def _get_session() -> ClientSession:
        nonlocal _session
        if _session is None:
            raise RuntimeError("Not connected to host")
        return _session

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        session = await _get_session()
        result = await session.list_tools()
        tools = []
        for t in result.tools:
            schema = t.inputSchema if t.inputSchema else {"type": "object", "properties": {}}
            # Strip 'token' — proxy injects it automatically
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
                name=t.name,
                description=t.description or "",
                inputSchema=schema,
            ))
        return tools

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
        session = await _get_session()
        # Inject token automatically
        arguments = {**arguments, "token": token}
        log.debug(f"→ tool call: {name}({list(k for k in arguments if k != 'token')})")
        try:
            result = await session.call_tool(name, arguments)
        except Exception as e:
            log.error(f"✗ tool call {name} failed: {e}")
            raise
        out = []
        for item in result.content:
            if item.type == "text":
                out.append(types.TextContent(type="text", text=item.text))
        if not out:
            out.append(types.TextContent(type="text", text=str(result)))
        log.debug(f"← {name} OK")
        return out

    async def run(read_stream, write_stream):
        nonlocal _session
        log.debug(f"Connecting to host at {url}")
        try:
            async with streamablehttp_client(url) as (host_read, host_write, _):
                async with ClientSession(host_read, host_write) as session:
                    await session.initialize()
                    _session = session
                    log.debug("Connected to host MCP server")
                    await server.run(
                        read_stream, write_stream,
                        server.create_initialization_options(),
                    )
        except Exception as e:
            log.error(f"Proxy connection failed: {e}")
            raise

    return server, run


async def _main(url: str, token: str, debug: bool) -> None:
    _setup_logging(debug)
    log.debug(f"Starting proxy → {url}")
    _server, run = make_proxy_server(url, token)
    async with stdio_server() as (read_stream, write_stream):
        await run(read_stream, write_stream)


def main() -> None:
    parser = argparse.ArgumentParser(description="LetsWork MCP stdio proxy")
    parser.add_argument("--url", required=True, help="Host MCP URL")
    parser.add_argument("--token", required=True, help="Session token")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()
    asyncio.run(_main(args.url, args.token, args.debug))


if __name__ == "__main__":
    main()
