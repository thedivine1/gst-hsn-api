"""
repair_hsn_codes.py — Fix right-padded HSN codes in gst_hsn_sac_master_v2_final.xlsx.

Corruption pattern (from ljust(8,'0')):
  real code   "08109030"
  int cast  →  8109030   (leading zero dropped)
  ljust(8)  → "81090300"  (right-padded, now looks like a different 8-char code)

Recovery: corrupt[:7] == str(int(real_code)), so lookup by corrupt[:7] in source.
"""
import os
import math
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

# ── 1. Build authoritative lookup from HSN_SAC.xlsx ──────────────────────────
print("Loading authoritative HSN codes from HSN_SAC.xlsx ...")
src = pd.read_excel("HSN_SAC.xlsx", sheet_name="HSN_MSTR", dtype={"HSN_CD": str})

# Key = str(int(HSN_CD))  →  the 7-digit (or less) digits without leading zero
# This is exactly what the corrupt code's first 7 chars are.
lookup = {}
for _, row in src.iterrows():
    raw = str(row["HSN_CD"]).strip()
    correct = raw.zfill(8)          # left-pad to 8: the authoritative code
    key = str(int(raw)) if raw.isdigit() else raw   # drop leading zeros (same as what int() does)
    lookup[key] = correct

print(f"  Source codes loaded: {len(src)}, lookup entries: {len(lookup)}")

# Spot check
for test_corrupt, expected in [("81090300", "08109030"), ("80390100", "08039010")]:
    key = test_corrupt[:7]           # first 7 chars = the int-cast digits
    got = lookup.get(key, "NOT FOUND")
    print(f"  test: corrupt={test_corrupt} → key={key} → got={got} (expected {expected})")

# ── 2. Load the corrupt v2_final.xlsx ────────────────────────────────────────
print("\nLoading gst_hsn_sac_master_v2_final.xlsx ...")
xl = pd.read_excel(
    "gst_hsn_sac_master_v2_final.xlsx",
    sheet_name=None,
    dtype={"hsn_code": str, "sac_code": str},
)
hsn_df = xl["HSN_RATES"].copy()
print(f"  HSN_RATES rows: {len(hsn_df)}")

before = hsn_df[hsn_df["hsn_code"].isin(["81090300", "80390100"])][["hsn_code","hsn_description"]].head(5)
print("\nBefore repair (corrupted rows):")
print(before.to_string())

# ── 3. Repair function ────────────────────────────────────────────────────────
def repair(code: str) -> str:
    code = str(code).strip()

    if not code.isdigit():
        return code  # non-numeric (shouldn't happen), leave alone

    # Check if already correct: leading-zero 8-digit code found in source
    already_key = str(int(code)) if code.isdigit() else code
    if already_key in lookup and lookup[already_key] == code:
        return code  # already correct

    if len(code) == 8:
        # Try the corruption recovery: first 7 chars are str(int(real_code))
        key7 = code[:7].lstrip("0") or "0"
        full7 = code[:7]   # keep leading zeros in key7 as-is
        # look up by both forms
        if full7 in lookup:
            return lookup[full7]
        if key7 in lookup:
            return lookup[key7]
        # Also try: strip trailing zeros iteratively (for codes ending in 00)
        stripped = code.rstrip("0")
        if stripped in lookup:
            return lookup[stripped]
        stripped_key = stripped.lstrip("0") or "0"
        if stripped_key in lookup:
            return lookup[stripped_key]
        # Not in source — keep as-is (may be a synthetic/heading code)
        return code

    # Short codes (chapter/heading): just ensure left-zero-pad
    return code.zfill(len(code))

repair_count = 0
def repair_counted(code):
    global repair_count
    original = str(code).strip()
    fixed = repair(original)
    if fixed != original:
        repair_count += 1
    return fixed

hsn_df["hsn_code"] = hsn_df["hsn_code"].apply(repair_counted)
print(f"\nRepaired {repair_count} codes.")

after = hsn_df[hsn_df["hsn_code"].isin(["08109030", "08039010"])][["hsn_code","hsn_description"]].head(5)
print("\nAfter repair (should show 08109030 / 08039010):")
print(after.to_string())

still_corrupt = hsn_df[hsn_df["hsn_code"].str.match(r"^[1-9]\d{5}00$", na=False)]
print(f"\nStill right-padded ending in '00': {len(still_corrupt)}")
if len(still_corrupt) > 0:
    print(still_corrupt[["hsn_code","hsn_description"]].head(10).to_string())

# ── 4. Save repaired Excel ────────────────────────────────────────────────────
print("\nSaving repaired Excel ...")
xl["HSN_RATES"] = hsn_df
with pd.ExcelWriter("gst_hsn_sac_master_v2_final.xlsx", engine="openpyxl") as writer:
    for sheet_name, df in xl.items():
        df.to_excel(writer, sheet_name=sheet_name, index=False)
print("  Saved.")

# ── 5. Clear Supabase in batches then reload ──────────────────────────────────
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
if not url or not key:
    print("ERROR: SUPABASE_URL / SUPABASE_KEY not set.")
    raise SystemExit(1)

supabase: Client = create_client(url, key)

print("\nDeleting existing hsn_rates rows in batches ...")
deleted_total = 0
while True:
    # Fetch a batch of IDs
    result = supabase.table("hsn_rates").select("id").limit(1000).execute()
    batch_ids = [r["id"] for r in result.data]
    if not batch_ids:
        break
    supabase.table("hsn_rates").delete().in_("id", batch_ids).execute()
    deleted_total += len(batch_ids)
    print(f"  Deleted {deleted_total} rows so far ...")

print(f"  Total deleted: {deleted_total}")

# Clean + insert
def clean_df(df):
    df = df.replace({float("nan"): None})
    for col in ["has_condition", "needs_review", "chapter_level", "heading_level"]:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: bool(x) if x is not None else False)
    if "cess_rate" in df.columns:
        def clean_cess(val):
            if val is None: return None
            if isinstance(val, (int, float)): return val
            s = str(val).strip().replace("%", "")
            if s.lower() in ("nil","n/a","na",""): return None
            try: return float(s)
            except ValueError: return None
        df["cess_rate"] = df["cess_rate"].apply(clean_cess)
    return df

def make_json_safe(records):
    return [{k: (None if isinstance(v, float) and (math.isnan(v) or math.isinf(v)) else v)
             for k, v in row.items()} for row in records]

hsn_df2 = clean_df(pd.read_excel("gst_hsn_sac_master_v2_final.xlsx", sheet_name="HSN_RATES", dtype={"hsn_code": str}))

print(f"\nInserting {len(hsn_df2)} HSN_RATES rows into Supabase ...")
records = make_json_safe(hsn_df2.to_dict(orient="records"))
batch_size = 1000
for i in range(0, len(records), batch_size):
    supabase.table("hsn_rates").insert(records[i:i+batch_size]).execute()
    print(f"  Inserted {min(i+batch_size, len(records))}/{len(records)}")

print("\n✅ Complete! Run these to verify:")
print("  SELECT hsn_code, hsn_description FROM hsn_rates WHERE hsn_code = '08109030';")
print("  SELECT hsn_code, hsn_description FROM hsn_rates WHERE hsn_code = '08039010';")
