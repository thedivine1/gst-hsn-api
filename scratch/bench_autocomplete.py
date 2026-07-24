import requests
import time

BASE = "http://127.0.0.1:8000"
HEADERS = {"X-API-Key": "demo_public_key"}
QUERIES = ["rice", "cotton", "chemical", "machine", "textile", "steel", "plastic", "cement"]

print(f"{'Query':<12} {'Status':<8} {'Time (ms)':<12} {'Results'}")
print("-" * 50)
for q in QUERIES:
    t0 = time.perf_counter()
    r = requests.get(f"{BASE}/api/v1/autocomplete", params={"q": q}, headers=HEADERS)
    elapsed = (time.perf_counter() - t0) * 1000
    data = r.json() if r.ok else []
    status = "OK" if r.ok else str(r.status_code)
    print(f"{q:<12} {status:<8} {elapsed:<12.1f} {len(data)} results")
