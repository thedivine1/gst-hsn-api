import os
import math
import pandas as pd
from supabase import create_client, Client
from dotenv import load_dotenv

def load_data():
    load_dotenv()
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        print("Error: SUPABASE_URL and SUPABASE_KEY must be set in .env")
        return

    supabase: Client = create_client(url, key)

    file_path = "gst_hsn_sac_master_v2_final.xlsx"
    print(f"Loading data from {file_path}...")

    # Confirm dtype={'hsn_code': str} to preserve leading zeros
    hsn_df = pd.read_excel(file_path, sheet_name="HSN_RATES", dtype={'hsn_code': str})
    sac_df = pd.read_excel(file_path, sheet_name="SAC_RATES", dtype={'sac_code': str})

    # Clean data (replace NaN with None for JSON serialization)
    hsn_df = hsn_df.replace({float('nan'): None})
    sac_df = sac_df.replace({float('nan'): None})

    # Cast boolean columns — Excel stores them as 0.0/1.0 floats
    hsn_bool_cols = ['has_condition', 'needs_review', 'chapter_level', 'heading_level']
    for col in hsn_bool_cols:
        if col in hsn_df.columns:
            hsn_df[col] = hsn_df[col].apply(lambda x: bool(x) if x is not None else False)

    sac_bool_cols = ['has_condition', 'needs_review']
    for col in sac_bool_cols:
        if col in sac_df.columns:
            sac_df[col] = sac_df[col].apply(lambda x: bool(x) if x is not None else False)

    # Convert dirty numeric strings in cess_rate to None or float
    # e.g. "89%", "Nil", "NIL", "N/A" → None or a clean number
    def clean_cess(val):
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return val
        s = str(val).strip()
        if s.lower() in ('nil', 'n/a', 'na', ''):
            return None
        # Strip trailing/leading % and whitespace
        s = s.replace('%', '').strip()
        try:
            return float(s)
        except ValueError:
            return None  # anything else we can't parse → NULL

    if 'cess_rate' in hsn_df.columns:
        hsn_df['cess_rate'] = hsn_df['cess_rate'].apply(clean_cess)
    if 'cess_rate' in sac_df.columns:
        sac_df['cess_rate'] = sac_df['cess_rate'].apply(clean_cess)

    print(f"Loaded HSN_RATES: {len(hsn_df)} rows")
    print(f"Loaded SAC_RATES: {len(sac_df)} rows")

    # Final safety pass: replace any remaining NaN/inf with None before JSON serialization
    def make_json_safe(records):
        clean = []
        for row in records:
            clean_row = {}
            for k, v in row.items():
                if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                    clean_row[k] = None
                else:
                    clean_row[k] = v
            clean.append(clean_row)
        return clean

    # Batch insert HSN_RATES (chunk size 1000 to avoid request too large errors)
    batch_size = 1000
    hsn_records = make_json_safe(hsn_df.to_dict(orient="records"))

    print("\nInserting HSN_RATES into Supabase...")
    for i in range(0, len(hsn_records), batch_size):
        batch = hsn_records[i:i + batch_size]
        supabase.table("hsn_rates").insert(batch).execute()
        print(f"  Inserted {min(i + batch_size, len(hsn_records))}/{len(hsn_records)}")

    # Insert SAC_RATES
    print("\nInserting SAC_RATES into Supabase...")
    sac_records = make_json_safe(sac_df.to_dict(orient="records"))
    for i in range(0, len(sac_records), batch_size):
        batch = sac_records[i:i + batch_size]
        supabase.table("sac_rates").insert(batch).execute()
        print(f"  Inserted {min(i + batch_size, len(sac_records))}/{len(sac_records)}")

    print("\nUpload complete! Please run the following verifications in Supabase SQL Editor:")
    print("  SELECT COUNT(*) FROM hsn_rates;                    -- Should be 48752")
    print("  SELECT DISTINCT igst_rate FROM hsn_rates ORDER BY 1; -- 0,0.25,1.5,3,5,18,28,40")
    print("  SELECT * FROM hsn_rates WHERE hsn_code = '10063012'; -- Basmati: 0% and 5% rows")
    print("  SELECT * FROM hsn_rates WHERE hsn_code = '8415';     -- AC heading: 18%")
    print("  SELECT * FROM hsn_rates WHERE hsn_code = '0401';     -- Milk: 0%")

if __name__ == "__main__":
    load_data()
