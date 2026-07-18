# SDK Bug Report: gstaccelerator Python (PyPI) v0.3.0 & JS (npm) v0.3.0
# Generated: 2026-07-19

## Bug 1 — Wrong auth header (both packages)

### Python (client.py line 146):
CURRENT (BROKEN):
    headers["Authorization"] = f"Bearer {api_key}"

CORRECT:
    headers["X-API-Key"] = api_key

### JS (index.js line 185):
CURRENT (BROKEN):
    "Authorization": `Bearer ${this.apiKey}`

CORRECT:
    "X-API-Key": this.apiKey

---

## Bug 2 — Wrong bulk() payload (both packages)

API expects: POST /api/v1/bulk  Body: [{description: str, supply_type?: str, ...}, ...]
(A list of LookupRequest objects — same schema as POST /api/v1/lookup)

### Python (client.py line 184):
CURRENT (BROKEN):
    return base._request("POST", "/api/v1/bulk", json={"descriptions": descriptions})

CORRECT:
    # descriptions should be a list of dicts: [{"description": "..."}, ...]
    return base._request("POST", "/api/v1/bulk", json=descriptions)

### JS (index.js line 268):
CURRENT (BROKEN):
    return this.request("POST", "/api/v1/bulk", { descriptions });

CORRECT:
    // descriptions should be an array of objects: [{description: "..."}, ...]
    return this.request("POST", "/api/v1/bulk", descriptions);

---

## Additions needed in both SDKs

1. gst.sac.get(code) — already exists ✅
2. gst.invoice.classify(...) — already exists ✅
3. gst.autocomplete(query) — already exists ✅
4. MCP tool: sac_lookup — check if present in mcp_server
5. MCP tool: invoice_classify — check if present in mcp_server

These fixes need to go into the source repos:
  - Python: github.com/thedivine1/gstaccelerator-python
  - JS:     github.com/thedivine1/gstaccelerator-js

Then publish:
  - Python: bump to 0.3.1, run: python -m build && twine upload dist/*
  - JS:     bump to 0.3.1, run: npm publish
