import urllib.request
import json
import sys

BASE_URL = "http://localhost:8000"
HEADERS = {"X-API-Key": "demo_public_key", "Content-Type": "application/json"}

def test_autocomplete():
    print("Testing Autocomplete for 'mobile'...")
    req = urllib.request.Request(f"{BASE_URL}/api/v1/autocomplete?q=mobile", headers=HEADERS)
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
        print(f"Got {len(data)} results.")
        for item in data[:3]:
            print(f" - {item['hsn_code']}: {item['hsn_description'][:50]}")
        
def test_bulk():
    print("\nTesting Bulk Lookup...")
    payload = [
        {"description": "smartphone", "supply_type": "interstate"},
        {"description": "laptop", "supply_type": "interstate"},
        {"description": "keyboard", "supply_type": "interstate"}
    ]
    req = urllib.request.Request(f"{BASE_URL}/api/v1/bulk", data=json.dumps(payload).encode(), headers=HEADERS)
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
        print(f"Bulk returned {len(data)} results.")

def test_hsn_headers():
    print("\nTesting HSN headers...")
    req = urllib.request.Request(f"{BASE_URL}/api/v1/hsn/8517", headers=HEADERS)
    with urllib.request.urlopen(req) as response:
        print("Cache-Control:", response.headers.get("Cache-Control"))
        print("X-Robots-Tag:", response.headers.get("X-Robots-Tag"))

try:
    test_autocomplete()
    test_bulk()
    test_hsn_headers()
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
