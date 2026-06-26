# GST HSN & SAC API - Implementation Summary

This document outlines the end-to-end fixes and enhancements applied to the GST HSN-SAC master data and the FastAPI backend, aligning with the new GST 2.0 rate structure.

## 1. Missing Goods Schedules Parsed (Schedules II - VII)
Initially, only the 5% (Schedule I) and 0% rates were present in the master Excel. The base notification (`gst_related.docx`) was re-parsed to extract all remaining schedules.
- **Schedule II (18%)**: 651 entries extracted.
- **Schedule III (40%)**: 15 entries extracted.
- **Schedule IV (3%)**: 15 entries extracted.
- **Schedule V (0.25%)**: 3 entries extracted.
- **Schedule VI (1.5%)**: 2 entries extracted.
- **Schedule VII (28%)**: 210 entries extracted.
- **Total New Goods Added**: 896 entries merged into `HSN_RATES`.

## 2. HSN Code Normalization & Zero-Padding Bug Fix
A critical bug caused 2-digit chapter codes and 4-digit heading codes to be incorrectly padded with leading zeros (e.g., `01` became `00000001`).
- **Fix Applied**: 1,446 codes were corrected.
- **New Logic**:
  - 2-digit strings (Chapters) are preserved as `01`, `02` and marked with `chapter_level=True`.
  - 4-digit strings (Headings) are preserved as `0101`, `0102` and marked with `heading_level=True`.
  - 6 to 8-digit strings (Tariff items) are correctly right-padded with trailing zeros to exactly 8 digits.

## 3. SAC (Services) Rates Populated
The `SAC_RATES` sheet was initially empty. 
- Loaded 681 SAC codes from the `SAC_MSTR` sheet.
- Mapped rates against **Notification 3/2017-CT(Rate)**, accounting for the recent **11/2025-CT(Rate)** amendment (which reduced construction works contract from 18% to 9% CGST).
- **Matching Logic**: Implemented prefix matching (e.g., matching the 6-digit SAC `995411` first, falling back to the 4-digit heading `9954` if no specific sub-heading exists).
- **Result**: 100% of the 681 SAC codes successfully matched and assigned rates and conditional text. 

## 4. API Condition Resolvers Upgraded (`main.py`)
The full-text-search endpoint (`/v1/lookup`) was enhanced to intelligently evaluate notification conditions based on the request body.

- **`price_threshold`**: Accepts `sale_value_inr` (float). The API parses the notification text (e.g., "not exceeding Rs. 7500") via regex, compares it against the user's declared value, and outputs a clear PASSED/FAILED flag.
- **`end_use`**: Accepts `end_use` (string). Tokens are checked against the condition text. If no overlap is found, it issues a warning that manual verification is required.
- **`supply_type`**: Accepts an Enum (`domestic`, `export`, `sez`, `works_contract`, `with_installation`). 
  - `export` and `sez` automatically append a note that these are zero-rated under IGST.
  - Matches specific keywords in the notification to ensure the user's supply type is eligible for the returned rate.

## 5. Current Database Snapshot
- **Total HSN Codes**: 53,060
- **Total SAC Codes**: 681
- **Rate Slabs Captured**: 0%, 0.25%, 1.5%, 3%, 5%, 12%, 18%, 28%, 40%.


## 6. GST 2.0 Deduplication (v2 Master)
A comprehensive deduplication was applied to gst_hsn_sac_master_v1.xlsx to generate 2, enforcing the new GST 2.0 rate structure:
- **Superseding Old Rates**: Conflicting pre-reform rates (e.g. 5% for ACs, TVs, Consumer Electronics) were superseded by the new GST 2.0 standard rates (e.g. 18%). The older rates were safely archived to a new SUPERSEDED_RATES sheet (4,311 rows moved).
- **Condition-Based Dual Rates Retained**: Genuine duplicate entries sharing the same effective date but differing in rates were recognized as condition-based splits (e.g., branded vs. unbranded meat). These were retained with has_condition=True set to ensure the API resolves them properly (19,083 rows retained).
- **Final Database Size**: The deduplication reduced the active HSN_RATES table down to a clean, accurate 48,749 rows, completely aligned with the recent GST council reforms.
