import pandas as pd
import pdfplumber
import re

pdf_igst = r"C:\Users\chaitanya.patankar\gst-hsn-api\NOTIFICATION NO. 9_2025-INTEGRATED TAX (RATE) -1759486719.pdf"
pdf_reckoner = r"C:\Users\chaitanya.patankar\gst-hsn-api\CBIC-GST-Ready-Reckoner-indicating-updated-Central-Goods-and-Services-Tax-CGST-rates-on-goods.pdf"
pdf_cess_nil = (
    r"C:\Users\chaitanya.patankar\gst-hsn-api\03-2025-CompensationCess-Rate-Eng.pdf"
)
master_file = r"C:\Users\chaitanya.patankar\gst-hsn-api\HSN_SAC.xlsx"
output_file = r"C:\Users\chaitanya.patankar\gst-hsn-api\gst_hsn_sac_master_v1.xlsx"

print("Loading Master Data...")
master_df = pd.read_excel(master_file, sheet_name="HSN_MSTR")
# Ensure hsn_code is string and zero padded to 8 digits
master_df["hsn_code"] = master_df["HSN_CD"].astype(str).str.zfill(8)
master_df["hsn_description"] = master_df["HSN_Description"]

rules = []


def determine_condition(text):
    text_lower = str(text).lower()
    if any(
        k in text_lower for k in ["branded", "unbranded", "pre-packaged and labelled"]
    ):
        return "branding"
    if any(k in text_lower for k in ["registered", "unregistered", "composition"]):
        return "registration"
    if any(k in text_lower for k in ["works contract", "with installation", "export"]):
        return "supply_type"
    if any(k in text_lower for k in ["exceeding", "not exceeding", "above", "below"]):
        return "price_threshold"
    if any(k in text_lower for k in ["for use in", "used for", "for the purpose of"]):
        return "end_use"
    if any(k in text_lower for k in ["government", "authority", "municipality"]):
        return "entity_type"
    return "none"


def has_condition(text):
    text_lower = str(text).lower()
    keywords = [
        "branded",
        "unbranded",
        "pre-packaged",
        "labelled",
        "other than",
        "not",
        "excluding",
        "if",
        "where",
        "registered",
        "unregistered",
    ]
    return any(k in text_lower for k in keywords)


# Parse Notification 9/2025 (IGST Rates)
print("Parsing Notification 9/2025 (IGST Rates)...")
current_schedule = None
current_rate = None

# Schedule mapping
schedule_map = {
    "Schedule I": 5,
    "Schedule II": 18,
    "Schedule III": 40,
    "Schedule IV": 3,
    "Schedule V": 0.25,
    "Schedule VI": 1.5,
    "Schedule VII": 28,
}

with pdfplumber.open(pdf_igst) as pdf:
    for page in pdf.pages:
        text = page.extract_text()
        if text:
            for s_name, s_rate in schedule_map.items():
                if (
                    f"{s_name} –" in text
                    or f"{s_name} -" in text
                    or f"{s_name}" in text
                ):
                    # simplistic check, might be triggered multiple times per schedule
                    pass

        tables = page.extract_tables()
        for table in tables:
            for row in table:
                if not row or len(row) < 3:
                    continue
                s_no, hsn, desc = row[0], row[1], row[2]
                if s_no is None:
                    continue
                s_no = s_no.replace("\n", " ").strip()
                if "Schedule" in s_no:
                    match = re.search(r"(Schedule\s+[IVX]+)", s_no, re.IGNORECASE)
                    if match:
                        current_schedule = match.group(1).title()
                        current_rate = schedule_map.get(current_schedule)
                    continue

                # if there is a schedule in the page text before the table
                # we'll also try to detect it from the page text
                if not current_schedule and text:
                    for s_name, s_rate in schedule_map.items():
                        if s_name in text:
                            current_schedule = s_name
                            current_rate = s_rate
                            break

                if not current_schedule:
                    continue

                if s_no.isdigit() or s_no.endswith("."):
                    if hsn:
                        hsn = hsn.replace("\n", " ").strip()
                    if desc:
                        desc = desc.replace("\n", " ").strip()

                    rules.append(
                        {
                            "hsn_raw": hsn,
                            "description_notification": desc,
                            "cgst_rate": current_rate / 2 if current_rate else None,
                            "igst_rate": current_rate,
                            "cess_rate": None,
                            "schedule": current_schedule,
                            "condition_text": desc,
                            "condition_type": determine_condition(desc),
                            "has_condition": has_condition(desc),
                            "notification_ref": "09/2025-CT(Rate)",
                            "effective_date": "2025-09-22",
                        }
                    )

# Parse Notification 10/2025 Exemptions (from Ready Reckoner)
print("Parsing Exemptions (Notification 10/2025)...")
with pdfplumber.open(pdf_reckoner) as pdf:
    parsing_exemptions = False
    for page in pdf.pages:
        text = page.extract_text()
        if text and "10/2025-Central Tax (Rate)" in text and "Exempted" in text:
            parsing_exemptions = True

        if parsing_exemptions:
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if not row or len(row) < 3:
                        continue
                    s_no, hsn, desc = row[0], row[1], row[2]
                    if s_no and (s_no.strip().isdigit() or s_no.strip().endswith(".")):
                        if hsn:
                            hsn = hsn.replace("\n", " ").strip()
                        if desc:
                            desc = desc.replace("\n", " ").strip()

                        rules.append(
                            {
                                "hsn_raw": hsn,
                                "description_notification": desc,
                                "cgst_rate": 0,
                                "igst_rate": 0,
                                "cess_rate": None,
                                "schedule": "Exempted",
                                "condition_text": desc,
                                "condition_type": determine_condition(desc),
                                "has_condition": has_condition(desc),
                                "notification_ref": "10/2025-CT(Rate)",
                                "effective_date": "2025-09-22",
                            }
                        )

# Parse Compensation Cess (from Ready Reckoner)
print("Parsing Compensation Cess...")
cess_rules = []
with pdfplumber.open(pdf_reckoner) as pdf:
    parsing_cess = False
    for page in pdf.pages:
        text = page.extract_text()
        if text and "Compensation Cess" in text and "1/2017" in text:
            parsing_cess = True

        if parsing_cess:
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if not row or len(row) < 4:
                        continue
                    s_no, hsn, desc, rate = row[0], row[1], row[2], row[3]
                    if s_no and (s_no.strip().isdigit() or s_no.strip().endswith(".")):
                        if hsn:
                            hsn = hsn.replace("\n", " ").strip()
                        if desc:
                            desc = desc.replace("\n", " ").strip()
                        if rate:
                            rate = rate.replace("\n", " ").strip()

                        cess_rules.append(
                            {
                                "hsn_raw": hsn,
                                "description_notification": desc,
                                "cess_rate": rate,
                                "s_no": s_no.strip().replace(".", ""),
                                "notification_ref": "1/2017-Compensation Cess",
                            }
                        )

# Find Cess Nil substitutions from 03-2025
print("Parsing Cess Nil substitutions from 03/2025...")
nil_s_nos = []
with pdfplumber.open(pdf_cess_nil) as pdf:
    for page in pdf.pages:
        text = page.extract_text()
        if text:
            matches = re.findall(
                r"against S\. No\. ([\w\d]+), for the entry in column \(4\), the entry “Nil” shall be substituted",
                text,
            )
            nil_s_nos.extend(matches)

for cr in cess_rules:
    if cr["s_no"] in nil_s_nos:
        cr["cess_rate"] = "Nil"
        cr["notification_ref"] = "03/2025-Compensation Cess (Rate)"

print(f"Extracted {len(rules)} main rules and {len(cess_rules)} cess rules.")


# Normalize HSN Codes and expand ranges
def expand_hsn(raw_hsn):
    if not raw_hsn:
        return []
    # Handle ranges like "0201 to 0210"
    raw_hsn = str(raw_hsn).strip().lower().replace(" or ", ",").replace(" and ", ",")
    parts = []

    # Split by comma
    for p in raw_hsn.split(","):
        p = p.strip()
        if "to" in p or "-" in p:
            delim = "to" if "to" in p else "-"
            start, end = p.split(delim, 1)
            start = re.sub(r"\D", "", start)
            end = re.sub(r"\D", "", end)
            if start and end and len(start) == len(end):
                try:
                    s_int, e_int = int(start), int(end)
                    for val in range(s_int, e_int + 1):
                        parts.append(str(val).zfill(len(start)))
                except:
                    parts.append(start)
        else:
            code = re.sub(r"\D", "", p)
            if code:
                parts.append(code)

    return parts


print("Expanding HSN Codes and matching...")
expanded_rules = []
for r in rules:
    hsns = expand_hsn(r["hsn_raw"])
    for hsn in hsns:
        new_r = r.copy()
        new_r["expanded_hsn"] = hsn
        expanded_rules.append(new_r)

expanded_cess = []
for cr in cess_rules:
    hsns = expand_hsn(cr["hsn_raw"])
    for hsn in hsns:
        new_cr = cr.copy()
        new_cr["expanded_hsn"] = hsn
        expanded_cess.append(new_cr)

# Match with master
master_hsn_list = master_df["hsn_code"].tolist()
final_results = []
unmatched = []

for r in expanded_rules:
    prefix = r["expanded_hsn"]
    matched = False
    for mhsn in master_hsn_list:
        if mhsn.startswith(prefix):
            final_results.append(
                {
                    "hsn_code": mhsn,
                    "cgst_rate": r["cgst_rate"],
                    "igst_rate": r["igst_rate"],
                    "schedule": r["schedule"],
                    "condition_text": r["condition_text"],
                    "condition_type": r["condition_type"],
                    "has_condition": r["has_condition"],
                    "notification_ref": r["notification_ref"],
                    "effective_date": r["effective_date"],
                }
            )
            matched = True
    if not matched:
        unmatched.append(r)

# Map cess
cess_map = {}
for cr in expanded_cess:
    prefix = cr["expanded_hsn"]
    for mhsn in master_hsn_list:
        if mhsn.startswith(prefix):
            cess_map[mhsn] = {
                "cess_rate": cr["cess_rate"],
                "cess_notification_ref": cr["notification_ref"],
            }

results_df = pd.DataFrame(final_results)
if not results_df.empty:
    results_df = results_df.drop_duplicates(subset=["hsn_code", "condition_text"])

master_df["needs_review"] = False
if not results_df.empty:
    final_df = master_df.merge(results_df, on="hsn_code", how="left")
else:
    final_df = master_df.copy()
    for col in [
        "cgst_rate",
        "igst_rate",
        "schedule",
        "condition_text",
        "condition_type",
        "has_condition",
        "notification_ref",
        "effective_date",
    ]:
        final_df[col] = None

final_df["cess_rate"] = final_df["hsn_code"].map(
    lambda x: cess_map.get(x, {}).get("cess_rate", None)
)
final_df["cess_notification_ref"] = final_df["hsn_code"].map(
    lambda x: cess_map.get(x, {}).get("cess_notification_ref", None)
)

final_df.loc[final_df["cgst_rate"].isna(), "needs_review"] = True

# Prepare sheets
hsn_rates = final_df[final_df["hsn_code"].str.len() == 8].copy()
sac_rates = final_df[final_df["hsn_code"].str.len() == 6].copy()

# Conditions reference
if not results_df.empty:
    cond_ref = final_df[["condition_text", "condition_type", "hsn_code"]].dropna(
        subset=["condition_text"]
    )
    cond_ref = (
        cond_ref.groupby(["condition_text", "condition_type"])
        .agg(
            affected_hsn_count=("hsn_code", "count"), example_hsn=("hsn_code", "first")
        )
        .reset_index()
    )
else:
    cond_ref = pd.DataFrame(
        columns=[
            "condition_text",
            "condition_type",
            "affected_hsn_count",
            "example_hsn",
        ]
    )

# Summary stats
stats = {
    "Total HSN codes": len(hsn_rates),
    "Total SAC codes": len(sac_rates),
    "Matched with rate": len(hsn_rates[hsn_rates["cgst_rate"].notna()])
    + len(sac_rates[sac_rates["cgst_rate"].notna()]),
    "Unmatched": len(hsn_rates[hsn_rates["cgst_rate"].isna()])
    + len(sac_rates[sac_rates["cgst_rate"].isna()]),
    "Has conditions": len(final_df[final_df["has_condition"]]),
    "Cess applicable count": len(
        final_df[final_df["cess_rate"].notna() & (final_df["cess_rate"] != "Nil")]
    ),
}
summary_df = pd.DataFrame([stats]).T.reset_index()
summary_df.columns = ["Statistic", "Value"]

unmatched_df = pd.DataFrame(unmatched)

# Reorder columns
columns_order = [
    "hsn_code",
    "hsn_description",
    "cgst_rate",
    "igst_rate",
    "cess_rate",
    "schedule",
    "condition_text",
    "condition_type",
    "has_condition",
    "notification_ref",
    "effective_date",
    "needs_review",
    "cess_notification_ref",
]
hsn_rates = hsn_rates[[c for c in columns_order if c in hsn_rates.columns]]
sac_rates = sac_rates[[c for c in columns_order if c in sac_rates.columns]]

print("Saving Excel file...")
with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
    hsn_rates.to_excel(writer, sheet_name="HSN_RATES", index=False)
    sac_rates.to_excel(writer, sheet_name="SAC_RATES", index=False)
    cond_ref.to_excel(writer, sheet_name="CONDITIONS_REFERENCE", index=False)
    summary_df.to_excel(writer, sheet_name="SUMMARY_STATS", index=False)
    unmatched_df.to_excel(writer, sheet_name="UNMATCHED_NOTIFICATIONS", index=False)

print("Done! File saved to:", output_file)
