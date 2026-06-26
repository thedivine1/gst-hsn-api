import pandas as pd

xl = pd.read_excel('gst_hsn_sac_master_v2.xlsx', sheet_name=None, dtype={'hsn_code': str})
df = xl['HSN_RATES']

# Fix 1: Remove corrupt rice row (1006 with 28% rate)
corrupt = (df['hsn_code'] == '1006') & (df['igst_rate'] == 28.0)
print(f"Removing {corrupt.sum()} corrupt rice row(s)")
df = df[~corrupt]

# Fix 2: Add missing milk/dairy chapter codes (all Nil-rated)
milk_codes = [
    ('0401', 'MILK AND CREAM, NOT CONCENTRATED NOR CONTAINING ADDED SUGAR', 0.0),
    ('0402', 'MILK AND CREAM, CONCENTRATED OR CONTAINING ADDED SUGAR', 0.0),
    ('0403', 'BUTTERMILK, CURDLED MILK AND CREAM, YOGURT, KEPHIR', 0.0),
    ('0404', 'WHEY, WHETHER OR NOT CONCENTRATED OR CONTAINING ADDED SUGAR', 0.0),
]
milk_rows = [{
    'hsn_code': code, 'hsn_description': desc,
    'cgst_rate': 0.0, 'igst_rate': igst,
    'cess_rate': 0.0, 'schedule': 'Exempted',
    'condition_text': 'Fresh milk and pasteurised milk, not containing added sugar',
    'condition_type': 'none', 'has_condition': False,
    'notification_ref': '10/2025-CT(Rate)',
    'effective_date': '2025-09-22', 'needs_review': False,
    'cess_notification_ref': None,
    'chapter_level': False, 'heading_level': True
} for code, desc, igst in milk_codes]

df = pd.concat([df, pd.DataFrame(milk_rows)], ignore_index=True)
print(f"Added {len(milk_rows)} milk/dairy heading rows")
print(f"Final HSN_RATES rows: {len(df)}")

# Write back
xl['HSN_RATES'] = df
with pd.ExcelWriter('gst_hsn_sac_master_v2_final.xlsx', engine='openpyxl') as writer:
    for sheet_name, sheet_df in xl.items():
        sheet_df.to_excel(writer, sheet_name=sheet_name, index=False)
print("Saved: gst_hsn_sac_master_v2_final.xlsx")
