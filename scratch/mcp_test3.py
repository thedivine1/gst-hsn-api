from mcp.server.fastmcp import FastMCP
from fastapi import FastAPI
app = FastAPI()
mcp = FastMCP("test")
@mcp.tool()
def test_tool() -> str:
    return "ok"

# Check if mcp can be mounted or added as a route
print(dir(mcp))
if hasattr(mcp, "get_starlette_app"):
    print("Has get_starlette_app")
if hasattr(mcp, "_mcp_server"):
    print("Has _mcp_server")
