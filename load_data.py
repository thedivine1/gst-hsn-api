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

    print(f"Loaded HSN_RATES: {len(hsn_df)} rows")
    print(f"Loaded SAC_RATES: {len(sac_df)} rows")

    # Batch insert HSN_RATES (chunk size 1000 to avoid request too large errors)
    batch_size = 1000
    hsn_records = hsn_df.to_dict(orient="records")
    
    print("\nInserting HSN_RATES into Supabase...")
    for i in range(0, len(hsn_records), batch_size):
        batch = hsn_records[i:i + batch_size]
        response = supabase.table("hsn_rates").insert(batch).execute()
        print(f"  Inserted {min(i + batch_size, len(hsn_records))}/{len(hsn_records)}")

    # Insert SAC_RATES
    print("\nInserting SAC_RATES into Supabase...")
    sac_records = sac_df.to_dict(orient="records")
    for i in range(0, len(sac_records), batch_size):
        batch = sac_records[i:i + batch_size]
        response = supabase.table("sac_rates").insert(batch).execute()
        print(f"  Inserted {min(i + batch_size, len(sac_records))}/{len(sac_records)}")

    print("\nUpload complete! Please run the following verifications in Supabase SQL Editor:")
    print("  SELECT COUNT(*) FROM hsn_rates;                    -- Should be 48752")
    print("  SELECT DISTINCT igst_rate FROM hsn_rates ORDER BY 1; -- 0,0.25,1.5,3,5,18,28,40")
    print("  SELECT * FROM hsn_rates WHERE hsn_code = '10063012'; -- Basmati: 0% and 5% rows")
    print("  SELECT * FROM hsn_rates WHERE hsn_code = '8415';     -- AC heading: 18%")
    print("  SELECT * FROM hsn_rates WHERE hsn_code = '0401';     -- Milk: 0%")

if __name__ == "__main__":
    load_data()
