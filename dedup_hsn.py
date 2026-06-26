"""
dedup_hsn.py
De-duplicates HSN_RATES based on the GST 2.0 reform rules.
"""

import pandas as pd
import numpy as np

INPUT_FILE = 'gst_hsn_sac_master_v1.xlsx'
OUTPUT_FILE = 'gst_hsn_sac_master_v2.xlsx'

def main():
    print("Loading HSN_RATES...")
    with pd.ExcelFile(INPUT_FILE) as xf:
        hsn_df = pd.read_excel(xf, sheet_name="HSN_RATES")
        sac_df = pd.read_excel(xf, sheet_name="SAC_RATES")
        cond_df = pd.read_excel(xf, sheet_name="CONDITIONS_REFERENCE")
        stats_df = pd.read_excel(xf, sheet_name="SUMMARY_STATS")
        unmatched_df = pd.read_excel(xf, sheet_name="UNMATCHED_NOTIFICATIONS")

    print(f"Initial HSN_RATES rows: {len(hsn_df)}")

    # Clean up NaNs in condition_text to empty strings for easier comparison
    hsn_df['condition_text'] = hsn_df['condition_text'].fillna('')
    hsn_df['effective_date'] = hsn_df['effective_date'].fillna('2017-07-01') # Default old date if missing

    # Identify duplicates based on hsn_code
    counts = hsn_df['hsn_code'].value_counts()
    dup_codes = counts[counts > 1].index

    archived_rows = []
    kept_rows = []

    # Non-duplicates go straight to kept
    kept_rows.append(hsn_df[~hsn_df['hsn_code'].isin(dup_codes)])

    dual_rate_count = 0

    print(f"Found {len(dup_codes)} HSN codes with multiple entries.")
    
    for code in dup_codes:
        group = hsn_df[hsn_df['hsn_code'] == code].copy()
        
        # Rule 1: If effective_date = '2025-09-22' exists, keep only that row(s), archive the rest
        if '2025-09-22' in group['effective_date'].values:
            latest_group = group[group['effective_date'] == '2025-09-22']
            archived_group = group[group['effective_date'] != '2025-09-22']
            if not archived_group.empty:
                archived_rows.append(archived_group)
            group = latest_group
            
        # Deduplicate identical rows (Rule 3)
        # Identical rate and identical condition text
        dedup_mask = ~group.duplicated(subset=['igst_rate', 'condition_text'], keep='first')
        archived_rows.append(group[~dedup_mask])
        group = group[dedup_mask]

        # Rule 2: If both rows have same effective_date but different rates -> genuine condition-based
        if len(group) > 1:
            rates = group['igst_rate'].dropna().unique()
            if len(rates) > 1:
                # Ensure has_condition = True on both
                group['has_condition'] = True
                dual_rate_count += len(group)
        
        kept_rows.append(group)

    kept_df = pd.concat(kept_rows, ignore_index=True)
    if archived_rows:
        archived_df = pd.concat(archived_rows, ignore_index=True)
    else:
        archived_df = pd.DataFrame(columns=hsn_df.columns)

    print(f"\nRows moved to SUPERSEDED_RATES: {len(archived_df)}")
    print(f"Legitimate dual-rate (condition-based) rows retained: {dual_rate_count}")
    print(f"Final HSN_RATES rows: {len(kept_df)}")

    # Validations
    ac_rows = kept_df[kept_df['hsn_code'].astype(str).str.startswith('8415', na=False)]
    if not ac_rows.empty:
        ac_rates = ac_rows['igst_rate'].dropna().unique()
        print(f"ACs (8415) rates present: {ac_rates.tolist()}")
    else:
        print("ACs (8415) not found.")

    meat_rows = kept_df[kept_df['hsn_code'] == '02021000']
    if not meat_rows.empty:
        meat_rates = meat_rows['igst_rate'].dropna().unique()
        print(f"Branded meat (02021000) rates present: {meat_rates.tolist()}")
    else:
        print("Meat (02021000) not found.")

    print(f"\nWriting to {OUTPUT_FILE}...")
    with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
        kept_df.to_excel(writer, sheet_name="HSN_RATES", index=False)
        sac_df.to_excel(writer, sheet_name="SAC_RATES", index=False)
        cond_df.to_excel(writer, sheet_name="CONDITIONS_REFERENCE", index=False)
        stats_df.to_excel(writer, sheet_name="SUMMARY_STATS", index=False)
        unmatched_df.to_excel(writer, sheet_name="UNMATCHED_NOTIFICATIONS", index=False)
        if not archived_df.empty:
            archived_df.to_excel(writer, sheet_name="SUPERSEDED_RATES", index=False)

    print("Done!")

if __name__ == "__main__":
    main()
