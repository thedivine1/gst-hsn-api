"""
Unit tests for price_threshold, end_use, supply_type condition resolvers.
Run: .\\venv\\Scripts\\python.exe test_conditions.py
"""
import os
os.environ['SUPABASE_URL'] = 'https://stub.supabase.co'
os.environ['SUPABASE_KEY'] = 'stub_key'

from unittest.mock import MagicMock, patch
with patch('supabase.create_client', return_value=MagicMock()):
    from main import (
        _evaluate_price_threshold,
        _evaluate_end_use,
        _evaluate_supply_nature,
        _parse_price_threshold,
        SupplyNature,
        LookupRequest,
        _evaluate_condition,
    )

errors = []

def check(label, condition, detail=""):
    if not condition:
        errors.append(f"FAIL: {label} {detail}")
        print(f"  FAIL  {label} {detail}")
    else:
        print(f"  PASS  {label}")

print("\n=== _parse_price_threshold ===")
r = _parse_price_threshold("not exceeding Rs. 7500 per unit per day")
check("parse not_exceeding 7500", r == ("not_exceeding", 7500.0), str(r))

r = _parse_price_threshold("exceeding Rs.1000")
check("parse exceeding 1000", r == ("exceeding", 1000.0), str(r))

r = _parse_price_threshold("above Rs 2500")
check("parse above 2500", r == ("exceeding", 2500.0), str(r))

r = _parse_price_threshold("up to Rs. 10,000")
check("parse up_to 10000", r == ("not_exceeding", 10000.0), str(r))

r = _parse_price_threshold("some other text with no rupees")
check("parse no threshold returns None", r is None, str(r))


print("\n=== _evaluate_price_threshold ===")
# PASS: 5000 <= 7500
p, n, w = _evaluate_price_threshold("not exceeding Rs. 7500", 5000.0)
check("5000 <= 7500 passes", p is True)
check("5000 <= 7500 no warning", w is None, w)

# FAIL: 9000 > 7500
p, n, w = _evaluate_price_threshold("not exceeding Rs. 7500", 9000.0)
check("9000 > 7500 does NOT pass", p is False)
check("9000 > 7500 has warning", w is not None)
check("9000 > 7500 warning mentions 'exceeds'", w and "exceeds" in w)

# PASS: exceeding 1000 with value 2000
p, n, w = _evaluate_price_threshold("exceeding Rs. 1000", 2000.0)
check("2000 > 1000 passes (exceeding)", p is True)
check("2000 > 1000 no warning", w is None, w)

# FAIL: exceeding 5000 with value 3000
p, n, w = _evaluate_price_threshold("exceeding Rs. 5000", 3000.0)
check("3000 not > 5000 does NOT pass", p is False)
check("3000 not > 5000 has warning", w is not None)

# No value provided
p, n, w = _evaluate_price_threshold("not exceeding Rs. 7500", None)
check("no value -> still passes", p is True)
check("no value -> warns with 'Provide'", w and "Provide" in w, w)

# Unparseable condition text
p, n, w = _evaluate_price_threshold("some threshold condition", None)
check("unparseable -> passes", p is True)
check("unparseable -> warning", w is not None)


print("\n=== _evaluate_end_use ===")
# Keyword match
p, n, w = _evaluate_end_use("for use in agriculture and allied activities", "agriculture")
check("agriculture matches", p is True)
check("agriculture -> no warning", w is None, w)

# Multi-token: one token matches
p, n, w = _evaluate_end_use("for use in agriculture and allied activities", "organic agriculture")
check("organic agriculture -> partial match ok", p is True)
check("organic agriculture -> no warning", w is None, w)

# No match -> warning
p, n, w = _evaluate_end_use("for use in agriculture and allied activities", "defence")
check("defence no-match -> still passes", p is True)
check("defence no-match -> warning with 'verification'", w and "verification" in w, w)

# No end_use provided
p, n, w = _evaluate_end_use("for use in agriculture", None)
check("no end_use -> passes", p is True)
check("no end_use -> warning with 'Provide'", w and "Provide" in w, w)

# Stop words only (edge case)
p, n, w = _evaluate_end_use("for use in agriculture", "for the")
check("stop-words-only end_use -> passes", p is True)
# No meaningful tokens -> won't match
check("stop-words-only -> warning", w is not None, w)


print("\n=== _evaluate_supply_nature ===")
# export -> zero-rated note always
p, n, w = _evaluate_supply_nature("goods for domestic use", SupplyNature.export)
check("export -> passes", p is True)
check("export -> zero-rated in warning", w and "zero-rated" in w, w)

# sez -> zero-rated note always
p, n, w = _evaluate_supply_nature("domestic goods", SupplyNature.sez)
check("sez -> passes", p is True)
check("sez -> zero-rated in warning", w and "zero-rated" in w, w)

# works_contract + matching text -> no warning
p, n, w = _evaluate_supply_nature("works contract for construction of building", SupplyNature.works_contract)
check("works_contract match -> passes", p is True)
check("works_contract match -> no warning", w is None, w)

# works_contract + non-matching text -> warning
p, n, w = _evaluate_supply_nature("textile goods supply condition", SupplyNature.works_contract)
check("works_contract no-match -> passes", p is True)
check("works_contract no-match -> has warning", w is not None)

# with_installation match
p, n, w = _evaluate_supply_nature("supply with installation and commissioning", SupplyNature.with_installation)
check("with_installation match -> no warning", w is None, w)

# domestic -> no keywords, no warning
p, n, w = _evaluate_supply_nature("any condition text", SupplyNature.domestic)
check("domestic -> passes", p is True)
check("domestic -> no warning", w is None, w)


print("\n=== _evaluate_condition (dispatcher) ===")
req_base = LookupRequest(description="test")

# price_threshold dispatch
row = {"has_condition": True, "condition_type": "price_threshold",
       "condition_text": "not exceeding Rs. 7500"}
req = LookupRequest(description="hotel", sale_value_inr=5000.0)
passes, note, warning = _evaluate_condition(row, req)
check("dispatch price_threshold 5000<=7500 passes", passes is True)
check("dispatch price_threshold note contains PASSED", note and "PASSED" in note, note)
check("dispatch price_threshold no warning", warning is None, warning)

# end_use dispatch
row = {"has_condition": True, "condition_type": "end_use",
       "condition_text": "for use in agriculture"}
req = LookupRequest(description="fertiliser", end_use="agriculture")
passes, note, warning = _evaluate_condition(row, req)
check("dispatch end_use match -> no warning", warning is None, warning)

# supply_type dispatch
row = {"has_condition": True, "condition_type": "supply_type",
       "condition_text": "works contract for construction"}
req = LookupRequest(description="construction", supply_nature=SupplyNature.works_contract)
passes, note, warning = _evaluate_condition(row, req)
check("dispatch supply_type works_contract match -> no warning", warning is None, warning)

# no condition
row = {"has_condition": False}
passes, note, warning = _evaluate_condition(row, req_base)
check("no condition -> passes, note=None, warning=None",
      passes is True and note is None and warning is None)


print()
if errors:
    print(f"=== {len(errors)} TEST(S) FAILED ===")
    for e in errors:
        print(f"  {e}")
    raise SystemExit(1)
else:
    print(f"=== All tests passed ===")
