import os
import sys
from mcp.server.fastmcp import FastMCP
from .client import GSTAccelerator

def main():
    api_key = os.environ.get("GST_API_KEY")
    if not api_key:
        print("GST_API_KEY environment variable is required to run the MCP server.", file=sys.stderr)
        print("Usage: GST_API_KEY=your_key gstaccelerator-mcp", file=sys.stderr)
        sys.exit(1)
        
    gst = GSTAccelerator(api_key=api_key)
    mcp = FastMCP("gstaccelerator-mcp")
    
    @mcp.tool()
    def hsn_lookup(code: str) -> str:
        """Look up Indian GST rate for a specific HSN code"""
        import json
        result = gst.hsn.get(code)
        return json.dumps(result, indent=2)
        
    @mcp.tool()
    def gst_search(description: str, supply_type: str = None, branded: bool = None, sale_value_inr: float = None) -> str:
        """Search GST HSN codes by product description"""
        import json
        result = gst.lookup(description, supply_type=supply_type, branded=branded, sale_value_inr=sale_value_inr)
        return json.dumps(result, indent=2)
        
    @mcp.tool()
    def gstin_validate(gstin: str) -> str:
        """Validate an Indian GSTIN number and extract components"""
        import json
        result = gst.gstin.validate(gstin)
        return json.dumps(result, indent=2)
        
    mcp.run()

if __name__ == "__main__":
    main()
