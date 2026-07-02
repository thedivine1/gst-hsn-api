from mcp.server import Server
from mcp.server.sse import SseServerTransport
import asyncio

server = Server("gst-accelerator")
sse = SseServerTransport("/mcp/messages")
print("SSE Transport imported successfully")
