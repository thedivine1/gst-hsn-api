"""
fix_missing_schedules.py
------------------------
Two fixes in one pass:

FIX 1 — Re-parse Schedules II–VII from gst_related.docx and append them
         to the HSN_RATES sheet of gst_hsn_sac_master_v1.xlsx.

FIX 2 — Correct the incorrectly zero-padded HSN codes that arose from treating
         chapter/heading codes like 8-digit tariff codes.
         e.g.  00000001 → '01'  (chapter, 2-digit)
               00000101 → '0101' (heading, 4-digit)
               00010121 → '01012100' (tariff item, 8-digit)

Run:
    .\\venv\\Scripts\\python.exe fix_missing_schedules.py
"""

import re
import pandas as pd
# pyrefly: ignore [missing-import]
import docx

DOCX_PATH = "gst_related.docx"
EXCEL_PATH = "gst_hsn_sac_master_v1.xlsx"
OUTPUT_PATH = "gst_hsn_sac_master_v1.xlsx"  # overwrite in-place

EFFECTIVE_DATE = "2025-09-22"
NOTIFICATION_REF = "09/2025-CT(Rate)"

# ---------------------------------------------------------------------------
# Schedule definitions (CGST %, IGST %)
# ---------------------------------------------------------------------------
SCHEDULE_RATES = {
    "Schedule I": (2.5, 5.0),
    "Schedule II": (9.0, 18.0),
    "Schedule III": (20.0, 40.0),
    "Schedule IV": (1.5, 3.0),
    "Schedule V": (0.125, 0.25),
    "Schedule VI": (0.75, 1.5),
    "Schedule VII": (14.0, 28.0),
}

# Paragraph indices where each CGST-schedule starts (from docx inspection).
# We parse until the NEXT schedule starts or a terminator is hit.
# We only need II–VII here; Schedule I was already parsed.
SCHEDULE_STARTS = {
    "Schedule II": 1874,
    "Schedule III": 4443,
    "Schedule IV": 4511,
    "Schedule V": 4563,
    "Schedule VI": 4588,
    "Schedule VII": 4600,
}
# Where each schedule ends (exclusive) — next schedule start or end of doc
SCHEDULE_ENDS = {
    "Schedule II": 4443,
    "Schedule III": 4511,
    "Schedule IV": 4563,
    "Schedule V": 4588,
    "Schedule VI": 4600,
    "Schedule VII": 5348,  # Cess section starts around here
}

# ---------------------------------------------------------------------------
# Condition keyword detection
# ---------------------------------------------------------------------------
CONDITION_KEYWORDS = [
    "branded",
    "unbranded",
    "pre-packaged",
    "labelled",
    "other than",
    "excluding",
    "where",
    "registered",
    "unregistered",
    "if ",
    "for use in",
    "used for",
    "for the purpose of",
    "government",
    "authority",
    "municipality",
    "works contract",
    "exceeding",
    "not exceeding",
    "above",
    "below",
    "export",
]


def detect_condition_type(text: str) -> str:
    t = text.lower()
    if any(
        k in t
        for k in ["branded", "unbranded", "pre-packaged and labelled", "pre-packaged"]
    ):
        return "branding"
    if any(k in t for k in ["registered", "unregistered", "composition"]):
        return "registration"
    if any(k in t for k in ["works contract", "with installation", "export"]):
        return "supply_type"
    if any(k in t for k in ["exceeding", "not exceeding", "above", "below"]):
        return "price_threshold"
    if any(k in t for k in ["for use in", "used for", "for the purpose of"]):
        return "end_use"
    if any(k in t for k in ["government", "authority", "municipality"]):
        return "entity_type"
    return "none"


def has_condition(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in CONDITION_KEYWORDS)


# ---------------------------------------------------------------------------
# HSN code normalisation helpers
# ---------------------------------------------------------------------------
def strip_spaces(code: str) -> str:
    """Remove all whitespace from an HSN/tariff string."""
    return re.sub(r"\s+", "", code)


def normalise_hsn(raw: str) -> tuple[str, bool, bool]:
    """
    Given a raw code string (possibly space-separated, e.g. '0515 12 20'),
    return (normalised_code, is_chapter_level, is_heading_level).

    Rules:
      2-digit numeric → chapter level, return as-is (e.g. '07')
      4-digit         → heading level
      6-digit         → subheading (pad to 8 with trailing zeros)
      8-digit         → tariff item
      Anything else   → strip and return as-is, not flagged
    """
    code = strip_spaces(raw).lstrip("0") or "0"  # strip leading zeros
    digits_only = re.sub(r"\D", "", code)

    if not digits_only:
        return raw.strip(), False, False

    length = len(digits_only)

    if length <= 2:
        padded = digits_only.zfill(2)
        return padded, True, False  # chapter

    if length <= 4:
        padded = digits_only.zfill(4)
        return padded, False, True  # heading

    if length <= 6:
        padded = digits_only.ljust(8, "0")  # pad trailing zeros to 8
        return padded, False, False

    # 7 or 8 digit
    padded = digits_only[:8].ljust(8, "0")
    return padded, False, False


# ---------------------------------------------------------------------------
# Paragraph-based parser for the CGST schedule sections
# ---------------------------------------------------------------------------
ROW_PATTERN = re.compile(
    r"^(\d+)\.\s+"  # S.No  e.g. "1. "
    r"([\d\s,/]+?)\s{2,}"  # HSN code(s) — multiple spaces separate from desc
    r"(.+?)(?:\s+[\d.]+%)?$",  # description (rate at end optional)
    re.DOTALL,
)

# Alternative simpler pattern where S.No, code and desc are on ONE line
ROW_SIMPLE = re.compile(r"^(\d+)\.\s+([\d\s,/]+?)\s{2,}(.+)")


def parse_schedule_paragraphs(
    paras: list, start: int, end: int, schedule_name: str
) -> list[dict]:
    """
    Parse the flat paragraph list between `start` and `end` indices.

    The docx has no tables for the CGST schedules — data flows across
    consecutive paragraphs. We use a state-machine:
      - A paragraph starting with '<digits>. ' is a new row.
      - Subsequent paragraphs until the next numbered row are continuations
        of the description or HSN code.
    """
    cgst_rate, igst_rate = SCHEDULE_RATES[schedule_name]
    rows = []

    # State
    cur_sno = None
    cur_codes = []  # list of raw code strings
    cur_desc = []  # list of description lines

    def flush():
        if cur_sno is None:
            return
        # Join codes and descriptions
        codes_str = " ".join(cur_codes)
        desc_str = " ".join(cur_desc).strip()
        # Remove trailing rate like "9%" or "1.5%"
        desc_str = re.sub(r"\s*[\d.]+%\s*$", "", desc_str).strip()

        # Split codes on comma, handle ranges with 'to' or '-'
        for raw_code in re.split(r",", codes_str):
            raw_code = raw_code.strip()
            if not raw_code:
                continue
            norm, is_chap, is_head = normalise_hsn(raw_code)
            rows.append(
                {
                    "hsn_code": norm,
                    "hsn_description": desc_str,
                    "cgst_rate": cgst_rate,
                    "igst_rate": igst_rate,
                    "cess_rate": 0,
                    "schedule": schedule_name,
                    "condition_text": desc_str if has_condition(desc_str) else None,
                    "condition_type": detect_condition_type(desc_str),
                    "has_condition": has_condition(desc_str),
                    "notification_ref": NOTIFICATION_REF,
                    "effective_date": EFFECTIVE_DATE,
                    "needs_review": False,
                    "cess_notification_ref": None,
                    "chapter_level": is_chap,
                    "heading_level": is_head,
                }
            )

    # Patterns to detect a new numbered entry
    new_entry = re.compile(r"^(\d+)\.\s+")
    # Pattern to detect the HSN code token (digits, spaces, commas, slashes)
    re.compile(r"^[\d\s,/]+$")

    # Skip header lines ("S. No.", "(1) (2) (3)", etc.)
    header_done = False

    for i in range(start, min(end, len(paras))):
        line = paras[i].text.strip()
        if not line:
            continue

        # Skip header rows
        if not header_done:
            if re.match(r"^\(1\)", line) or re.match(r"^S\.?\s*No", line, re.I):
                header_done = True
            continue

        m = new_entry.match(line)
        if m:
            flush()
            cur_sno = m.group(1)
            cur_codes = []
            cur_desc = []
            rest = line[m.end() :].strip()

            # Try to split rest into code part and description part
            # The code is purely numeric (with spaces/commas); desc is text
            # Strategy: take longest leading token that is all-digit
            parts = rest.split()
            code_parts = []
            desc_parts = []
            in_code = True
            for part in parts:
                if in_code and re.match(r"^[\d,/]+$", part):
                    code_parts.append(part)
                else:
                    in_code = False
                    desc_parts.append(part)

            if code_parts:
                cur_codes = [" ".join(code_parts)]
            # Remove trailing rate from desc
            desc_line = " ".join(desc_parts)
            desc_line = re.sub(r"\s*[\d.]+%\s*$", "", desc_line).strip()
            if desc_line:
                cur_desc.append(desc_line)
        else:
            # Continuation line
            if cur_sno is None:
                continue
            # Is this a pure-code continuation or desc continuation?
            cleaned = line.replace(",", "").replace("/", "").replace(" ", "")
            if cleaned.isdigit() and not cur_desc:
                # Still collecting HSN codes
                cur_codes.append(line.strip())
            else:
                # Remove trailing rate percentage
                desc_part = re.sub(r"\s*[\d.]+%\s*$", "", line).strip()
                if desc_part:
                    cur_desc.append(desc_part)

    flush()
    return rows


# ---------------------------------------------------------------------------
# FIX 2: Normalise badly padded codes in the master
# ---------------------------------------------------------------------------
def fix_hsn_code(raw: str) -> tuple[str, bool, bool]:
    """
    Take a code like '00000101' or '00010121' and return the correct form.
    The original code was produced by: str(int_val).zfill(8)
    where int_val was itself the raw chapter/heading/tariff integer.

    Algorithm:
      1. Strip leading zeros → gives us the "semantic" digits.
      2. Apply normalise_hsn logic.
    """
    digits = str(raw).lstrip("0") or "0"
    return normalise_hsn(digits)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("Loading docx …")
    doc = docx.Document(DOCX_PATH)
    paras = doc.paragraphs
    print(f"  {len(paras)} paragraphs loaded.")

    # --- FIX 1: Parse missing schedules ---
    all_new_rows = []
    for sched_name, start_para in SCHEDULE_STARTS.items():
        end_para = SCHEDULE_ENDS[sched_name]
        cgst, igst = SCHEDULE_RATES[sched_name]
        print(
            f"\nParsing {sched_name} (IGST {igst}%) — paras {start_para}–{end_para} …"
        )
        rows = parse_schedule_paragraphs(paras, start_para + 1, end_para, sched_name)
        print(f"  → {len(rows)} entries extracted")
        all_new_rows.extend(rows)

    new_df = pd.DataFrame(all_new_rows)
    print(f"\nTotal new entries from schedules II–VII: {len(new_df)}")

    # --- FIX 2: Load and fix existing Excel ---
    print("\nLoading existing Excel …")
    with pd.ExcelFile(EXCEL_PATH) as xf:
        hsn_df = pd.read_excel(xf, sheet_name="HSN_RATES")
        sac_df = pd.read_excel(xf, sheet_name="SAC_RATES")
        cond_df = pd.read_excel(xf, sheet_name="CONDITIONS_REFERENCE")
        pd.read_excel(xf, sheet_name="SUMMARY_STATS")
        try:
            unmatched_df = pd.read_excel(xf, sheet_name="UNMATCHED_NOTIFICATIONS")
        except Exception:
            unmatched_df = pd.DataFrame()

    print(f"  Existing HSN_RATES rows: {len(hsn_df)}")

    # Ensure chapter_level / heading_level columns exist
    if "chapter_level" not in hsn_df.columns:
        hsn_df["chapter_level"] = False
    if "heading_level" not in hsn_df.columns:
        hsn_df["heading_level"] = False

    print("Fixing incorrectly padded HSN codes …")
    fixed_codes = []
    chap_flags = []
    head_flags = []
    fix_count = 0

    for code in hsn_df["hsn_code"].astype(str):
        if code.startswith("0000"):
            new_code, is_chap, is_head = fix_hsn_code(code)
            fixed_codes.append(new_code)
            chap_flags.append(is_chap)
            head_flags.append(is_head)
            fix_count += 1
        else:
            # Already correct — but still run through normaliser to flag levels
            new_code, is_chap, is_head = normalise_hsn(code)
            fixed_codes.append(new_code)
            chap_flags.append(is_chap)
            head_flags.append(is_head)

    hsn_df["hsn_code"] = fixed_codes
    hsn_df["chapter_level"] = chap_flags
    hsn_df["heading_level"] = head_flags
    print(f"  Fixed {fix_count} incorrectly padded codes.")

    # --- Append new schedule rows ---
    if "chapter_level" not in new_df.columns:
        new_df["chapter_level"] = False
    if "heading_level" not in new_df.columns:
        new_df["heading_level"] = False

    # Align columns
    for col in hsn_df.columns:
        if col not in new_df.columns:
            new_df[col] = None

    combined = pd.concat([hsn_df, new_df[hsn_df.columns]], ignore_index=True)
    print(f"  Combined HSN_RATES rows: {len(combined)}")

    # --- Rebuild SUMMARY_STATS ---
    total_hsn = len(combined)
    matched = combined["cgst_rate"].notna().sum()
    unmatched = total_hsn - matched
    has_cond = combined["has_condition"].fillna(False).astype(bool).sum()
    # cess_rate may contain strings like "Nil" — coerce to numeric first
    cess_numeric = pd.to_numeric(combined["cess_rate"], errors="coerce").fillna(0)
    cess_app = (cess_numeric > 0).sum()
    total_sac = len(sac_df)

    print("\nIGST rate distribution (after fix):")
    print(combined["igst_rate"].value_counts(dropna=False).to_string())

    sched_counts = (
        combined.groupby("schedule", dropna=False).size().reset_index(name="count")
    )

    summary_rows = [
        ("Total HSN codes", total_hsn),
        ("Total SAC codes", total_sac),
        ("Matched with rate", int(matched)),
        ("Unmatched", int(unmatched)),
        ("Has conditions", int(has_cond)),
        ("Cess applicable count", int(cess_app)),
    ]
    for _, row in sched_counts.iterrows():
        summary_rows.append((f"Schedule: {row['schedule']}", int(row["count"])))

    new_stats_df = pd.DataFrame(summary_rows, columns=["Statistic", "Value"])

    # --- Rebuild CONDITIONS_REFERENCE ---
    cond_rows = combined[combined["has_condition"].fillna(False).astype(bool)].copy()
    if len(cond_rows) > 0:
        new_cond_df = (
            cond_rows.groupby(["condition_text", "condition_type"], dropna=False)
            .agg(
                affected_hsn_count=("hsn_code", "count"),
                example_hsn=("hsn_code", "first"),
            )
            .reset_index()
        )
    else:
        new_cond_df = cond_df  # keep original if nothing

    # --- Write output ---
    print(f"\nWriting output to {OUTPUT_PATH} …")
    with pd.ExcelWriter(OUTPUT_PATH, engine="openpyxl") as writer:
        combined.to_excel(writer, sheet_name="HSN_RATES", index=False)
        sac_df.to_excel(writer, sheet_name="SAC_RATES", index=False)
        new_cond_df.to_excel(writer, sheet_name="CONDITIONS_REFERENCE", index=False)
        new_stats_df.to_excel(writer, sheet_name="SUMMARY_STATS", index=False)
        unmatched_df.to_excel(writer, sheet_name="UNMATCHED_NOTIFICATIONS", index=False)

    print("\n✅ Done!")
    print(f"   HSN_RATES rows : {len(combined)}")
    print(
        f"   IGST rates     : {sorted(combined['igst_rate'].dropna().unique().tolist())}"
    )
    print(f"   Unmatched      : {unmatched}")


if __name__ == "__main__":
    main()
