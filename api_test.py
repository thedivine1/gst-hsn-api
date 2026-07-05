"""
GST Accelerator API - Complete Test Suite
=========================================
Run this with your real API key to verify all endpoints are working correctly.
Usage: python api_test.py <YOUR_API_KEY>
       python api_test.py  (uses demo key for public endpoints)
"""

import sys
import json
import time
import urllib.request
import urllib.error

# Force utf-8 output on Windows
sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None

# ─────────────────────────────────────────────
# Force utf-8 output
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ---------------------------------------------
# CONFIG
# ---------------------------------------------
BASE_URL = "https://gstaccelerator.in"
API_KEY  = sys.argv[1] if len(sys.argv) > 1 else "gsta_demo_frontend"
HEADERS  = {"X-API-Key": API_KEY, "Content-Type": "application/json"}

PASS = "[PASS]"
FAIL = "[FAIL]"
WARN = "[WARN]"
INFO = "[INFO]"

results = {"pass": 0, "fail": 0, "warn": 0}

def req(method, path, body=None, expected_status=200, label=""):
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode() if body else None
    r = urllib.request.Request(url, data=data, headers=HEADERS, method=method)
    t0 = time.time()
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            elapsed = round((time.time() - t0) * 1000)
            payload = json.loads(resp.read())
            ok = resp.status == expected_status
            status = PASS if ok else FAIL
            if ok:
                results["pass"] += 1
            else:
                results["fail"] += 1
            print(f"  {status}  [{resp.status}] {method} {path} — {elapsed}ms")
            return payload, resp.status
    except urllib.error.HTTPError as e:
        elapsed = round((time.time() - t0) * 1000)
        payload = {}
        try:
            payload = json.loads(e.read())
        except:
            pass
        ok = e.code == expected_status
        status = PASS if ok else FAIL
        if ok:
            results["pass"] += 1
        else:
            results["fail"] += 1
        print(f"  {status}  [{e.code}] {method} {path} — {elapsed}ms")
        return payload, e.code
    except Exception as e:
        results["fail"] += 1
        print(f"  {FAIL}  [ERR] {method} {path} — {e}")
        return {}, 0

def section(title):
    print(f"\n{'-'*55}")
    print(f"  {title}")
    print(f"{'-'*55}")

def check(condition, label, got=None):
    if condition:
        results["pass"] += 1
        print(f"  {PASS}  {label}")
    else:
        results["fail"] += 1
        print(f"  {FAIL}  {label}" + (f" (got: {got!r})" if got is not None else ""))

# ---------------------------------------------
# 1. HEALTH & META
# ---------------------------------------------
section("1. Health & Meta")
data, _ = req("GET", "/api/v1/health")
check(data.get("status") == "ok", "Health status = ok", data.get("status"))

data, _ = req("GET", "/api/v1/meta")
check(data.get("total_hsn", 0) > 40000, f"total_hsn > 40,000 (got {data.get('total_hsn')})", data.get("total_hsn"))
check(data.get("total_sac", 0) > 500, f"total_sac > 500 (got {data.get('total_sac')})", data.get("total_sac"))
# API uses 'source' and 'last_updated' (not 'data_source' / 'effective_from')
check("source" in data, "meta has source field", list(data.keys()))
check("last_updated" in data, "meta has last_updated field", list(data.keys()))

# ---------------------------------------------
# 2. HSN LOOKUP BY CODE
# ---------------------------------------------
section("2. HSN Code Lookup")
# AC unit
data, _ = req("GET", "/api/v1/hsn/84151010")
if isinstance(data, list) and len(data) > 0:
    row = data[0]
    check(row.get("hsn_code") == "84151010", "HSN 84151010 returns correct code")
    # Field is 'igst' (not 'igst_rate') in the API response
    igst = row.get("igst") or (row.get("tax_rates") or {}).get("igst")
    check(igst is not None and igst > 0, f"AC unit has IGST rate (got igst={igst})")
    check("tax_rates" in row, "Result has nested tax_rates object")
    check("applicable_rate" in row, "Result has applicable_rate object")
elif isinstance(data, dict) and data.get("hsn_code") == "84151010":
    check(True, "HSN 84151010 returns correct code")
else:
    check(False, "HSN 84151010 returned unexpected format", data)

# Basmati rice
data, _ = req("GET", "/api/v1/hsn/10063012")
check(isinstance(data, (list, dict)) and len(data) > 0 if isinstance(data, list) else bool(data),
      "HSN 10063012 (basmati rice) returns result")

# Invalid HSN → expect 404
data, status = req("GET", "/api/v1/hsn/00000000", expected_status=404)
check(status == 404, "Non-existent HSN returns 404")

# ---------------------------------------------
# 3. SAC LOOKUP BY CODE
# ---------------------------------------------
section("3. SAC Code Lookup")
data, _ = req("GET", "/api/v1/sac/997212")
check(isinstance(data, (list, dict)) and (len(data) > 0 if isinstance(data, list) else bool(data)),
      "SAC 997212 (real estate services) returns result")

# ---------------------------------------------
# 4. DESCRIPTION-BASED LOOKUP (POST)
# ---------------------------------------------
section("4. POST /api/v1/lookup — Description Search")
# Simple
data, _ = req("POST", "/api/v1/lookup", {"description": "basmati rice"})
check(isinstance(data, list) and len(data) > 0, f"'basmati rice' returns ≥1 result (got {len(data) if isinstance(data, list) else data})")

# With condition flags — supply_type must be 'intrastate' or 'interstate' (not 'domestic')
data, _ = req("POST", "/api/v1/lookup", {
    "description": "AC unit",
    "branded": True,
    "b2b": False,
    "supply_type": "intrastate"
})
check(isinstance(data, list) and len(data) > 0, "'AC unit' with condition flags returns result")
if isinstance(data, list) and len(data) > 0:
    check("confidence" in data[0], "Result has confidence score")
    check("applicable_rate" in data[0], "Result has applicable_rate")
    check("description" in data[0], "Result has description field")

# Price threshold
data, _ = req("POST", "/api/v1/lookup", {
    "description": "footwear",
    "sale_value_inr": 500
})
check(isinstance(data, list) and len(data) > 0, "'footwear' with sale_value_inr returns result")

# ---------------------------------------------
# 5. GET ALIAS FOR LOOKUP
# ---------------------------------------------
section("5. GET /api/v1/lookup?q= — Query Alias")
data, _ = req("GET", "/api/v1/lookup?q=mobile+phone")
check(isinstance(data, list) and len(data) > 0, "GET lookup alias for 'mobile phone' works")

data, _ = req("GET", "/api/v1/lookup?q=gold+jewellery")
check(isinstance(data, list) and len(data) > 0, "GET lookup alias for 'gold jewellery' works")

# ---------------------------------------------
# 6. AUTOCOMPLETE
# ---------------------------------------------
section("6. GET /api/v1/autocomplete")
data, _ = req("GET", "/api/v1/autocomplete?q=basm")
check(isinstance(data, list), "Autocomplete returns list")
if isinstance(data, list) and len(data) > 0:
    check(len(data) <= 20, f"Autocomplete returns ≤20 suggestions (got {len(data)})")

# ---------------------------------------------
# 7. BULK LOOKUP
# ---------------------------------------------
section("7. POST /api/v1/bulk — Batch Lookup")
bulk_body = [
    {"description": "basmati rice"},
    {"description": "AC unit"},
    {"description": "gold jewellery"},
]
data, _ = req("POST", "/api/v1/bulk", bulk_body)
check(isinstance(data, list) and len(data) == 3, f"Bulk lookup returns 3 results (got {len(data) if isinstance(data, list) else data})")
if isinstance(data, list) and len(data) == 3:
    check(isinstance(data[0], list), "Each bulk result is a list of matches")

# ---------------------------------------------
# 8. DEMO ENDPOINT (No API key needed)
# ---------------------------------------------
section("8. GET /api/demo/lookup — Public Widget Endpoint")
url = f"{BASE_URL}/api/demo/lookup?q=basmati+rice"
r = urllib.request.Request(url, method="GET")
try:
    with urllib.request.urlopen(r, timeout=10) as resp:
        demo_data = json.loads(resp.read())
        check(isinstance(demo_data, list) and len(demo_data) > 0,
              f"Demo widget returns results for 'basmati rice' (got {len(demo_data) if isinstance(demo_data, list) else demo_data})")
except Exception as e:
    check(False, f"Demo widget error: {e}")

# ---------------------------------------------
# 9. SEO & INFRA ENDPOINTS
# ---------------------------------------------
section("9. SEO & Infrastructure")
for path, label, ct in [
    ("/robots.txt",  "robots.txt accessible", "text/plain"),
    ("/sitemap.xml", "sitemap.xml returns XML", "application/xml"),
    ("/llms.txt",    "llms.txt accessible for AI crawlers", "text/plain"),
]:
    url = f"{BASE_URL}{path}"
    r2 = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(r2, timeout=10) as resp2:
            body = resp2.read().decode()
            ok = resp2.status == 200
            results["pass" if ok else "fail"] += 1
            print(f"  {PASS if ok else FAIL}  [{resp2.status}] GET {path} — {label}")
            if path == "/sitemap.xml":
                check("<urlset" in body, "sitemap.xml contains <urlset> tag")
            if path == "/robots.txt":
                check("Disallow: /admin/" in body, "robots.txt has Disallow: /admin/")
                check("Sitemap:" in body, "robots.txt points to sitemap")
    except Exception as e:
        results["fail"] += 1
        print(f"  {FAIL}  GET {path} — {e}")

# ---------------------------------------------
# 10. ERROR HANDLING
# ---------------------------------------------
section("10. Error Handling")
# Empty description → 400
data, status = req("POST", "/api/v1/lookup", {"description": ""}, expected_status=400)
check(status == 400, "Empty description returns 400")

# No API key → FastAPI validates Header(...) first, returns 422 before reaching auth logic
# This is expected FastAPI behavior: 422 = header is structurally missing
url = f"{BASE_URL}/api/v1/lookup?q=rice"
r3 = urllib.request.Request(url, method="GET")  # no auth header
try:
    with urllib.request.urlopen(r3, timeout=10) as resp3:
        results["warn"] += 1
        print(f"  {WARN}  GET /api/v1/lookup without key returned {resp3.status} (expected 401/403/422)")
except urllib.error.HTTPError as e:
    check(e.code in (401, 403, 422), f"Unauthenticated request rejected (got {e.code}, expected 401/403/422)")

# ---------------------------------------------
# SUMMARY
# ---------------------------------------------
total = results["pass"] + results["fail"] + results["warn"]
print(f"\n{'='*55}")
print(f"  RESULTS: {results['pass']} passed / {results['fail']} failed / {results['warn']} warnings  ({total} total)")
print(f"{'='*55}\n")
if results["fail"] == 0:
    print("  All tests passed! API is healthy.\n")
else:
    print(f"  {results['fail']} test(s) failed. Check output above.\n")
