import urllib.request, json, sys
sys.stdout.reconfigure(encoding='utf-8')

BASE = "http://localhost:8000"
KEY  = "demo_public_key"

def post(path, body):
    req = urllib.request.Request(
        BASE + path, method="POST",
        headers={"Content-Type": "application/json", "x-api-key": KEY}
    )
    try:
        r = urllib.request.urlopen(req, data=json.dumps(body).encode(), timeout=10)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())

tests = [
    ("Intrastate (same state-code '27' == 'Maharashtra')", 200, {
        "seller_state": "Maharashtra", "buyer_state": "27",
        "items": [{"hsn_code": "8415", "quantity": 2, "rate": 10000}]
    }),
    ("Interstate IGST multi-item (MH to KA)", 200, {
        "seller_state": "Maharashtra", "buyer_state": "Karnataka",
        "items": [
            {"hsn_code": "8415", "quantity": 1, "rate": 15000},
            {"hsn_code": "40210100", "quantity": 2, "rate": 500},
        ]
    }),
    ("State aliases (mh / tn)", 200, {
        "seller_state": "mh", "buyer_state": "tn",
        "items": [{"hsn_code": "8415", "quantity": 1, "rate": 5000}]
    }),
    ("Bad state → 400", 400, {
        "seller_state": "InvalidState", "buyer_state": "Maharashtra",
        "items": [{"hsn_code": "8415", "quantity": 1, "rate": 1000}]
    }),
    ("Bad HSN → 404", 404, {
        "seller_state": "Maharashtra", "buyer_state": "Karnataka",
        "items": [{"hsn_code": "000000", "quantity": 1, "rate": 1000}]
    }),
]

all_pass = True
for name, expected, body in tests:
    status, data = post("/api/v1/invoice/classify", body)
    ok = status == expected
    all_pass = all_pass and ok
    icon = "PASS" if ok else "FAIL"
    print(f"{icon}  [{status}] {name}")
    if not ok:
        print(f"    Expected {expected}, got {status}: {json.dumps(data)[:200]}")
    elif status == 200:
        items = data.get("items", [])
        for it in items:
            desc = (it.get('applicable_rate_string','') or '').encode('ascii','replace').decode()
            print(f"    {it['hsn_code']} -- {desc}  taxable={it['taxable_value']}  tax={it['tax_amount']}")
        print(f"    grand_total={data['grand_total']}")

print()
print("ALL TESTS PASSED" if all_pass else "SOME TESTS FAILED")
sys.exit(0 if all_pass else 1)
