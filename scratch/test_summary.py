import urllib.request
import time
import json

BASE_URL = "http://localhost:8000"
HEADERS = {"X-API-Key": "demo_public_key"}

def test_summary():
    print("Testing GET /api/v1/rates/summary...")
    
    t0 = time.time()
    req = urllib.request.Request(f"{BASE_URL}/api/v1/rates/summary", headers=HEADERS)
    with urllib.request.urlopen(req) as response:
        response.read()
    t1 = time.time()
    print(f"First request (uncached): {t1 - t0:.3f}s")
    
    t2 = time.time()
    req = urllib.request.Request(f"{BASE_URL}/api/v1/rates/summary", headers=HEADERS)
    with urllib.request.urlopen(req) as response:
        response.read()
    t3 = time.time()
    print(f"Second request (cached): {t3 - t2:.3f}s")

if __name__ == "__main__":
    test_summary()
