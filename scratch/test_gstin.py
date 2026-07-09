import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/..")

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

# GSTIN generated with valid checksum: 07AAAAA0000A1Z5
# Let's verify a real looking GSTIN: 27AAPFU0939F1ZV
# Wait, GSTIN checksum logic.

gstins = [
    "27AAPFU0939F1ZV", # 27, AAPFU0939F, 1, Z, V
]

for g in gstins:
    print(f"\nTesting {g}")
    resp = client.get(f"/api/v1/gstin/{g}/validate", headers={"X-API-Key": "demo_public_key"})
    print("Validate:", resp.json())
    
    resp = client.get(f"/api/v1/gstin/{g}/state", headers={"X-API-Key": "demo_public_key"})
    print("State:", resp.json())
    
    resp = client.get(f"/api/v1/gstin/{g}/pan", headers={"X-API-Key": "demo_public_key"})
    print("PAN:", resp.json())

# Test some invalids
print("\nTesting Invalid length:")
print(client.get("/api/v1/gstin/27AAPFU0939F1Z/validate", headers={"X-API-Key": "demo_public_key"}).json())

print("\nTesting Invalid state:")
print(client.get("/api/v1/gstin/98AAPFU0939F1ZV/validate", headers={"X-API-Key": "demo_public_key"}).json())

print("\nTesting Invalid PAN:")
print(client.get("/api/v1/gstin/27AAPF00939F1ZV/validate", headers={"X-API-Key": "demo_public_key"}).json())
