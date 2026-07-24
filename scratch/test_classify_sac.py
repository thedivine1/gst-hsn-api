import urllib.request
import json
import sys

BASE_URL = "http://localhost:8000"
HEADERS = {"X-API-Key": "demo_public_key", "Content-Type": "application/json"}

payload = {
  "seller_state": "Maharashtra",
  "buyer_state": "Maharashtra",
  "items": [{"hsn_code": "9983", "quantity": 1, "rate": 5000}]
}

print("Testing Classify with SAC 9983...")
try:
    req = urllib.request.Request(f"{BASE_URL}/api/v1/invoice/classify", data=json.dumps(payload).encode(), headers=HEADERS)
    with urllib.request.urlopen(req, timeout=10) as response:
        data = json.loads(response.read().decode())
        print(json.dumps(data, indent=2))
except urllib.error.HTTPError as e:
    print(f"HTTP Error {e.code}: {e.read().decode()}")
except Exception as e:
    print(f"Error: {e}")
