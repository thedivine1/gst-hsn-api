import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Re-use the existing logic
def determine_condition(text):
    if not text: return "none"
    text_lower = str(text).lower()
    if any(k in text_lower for k in ["branded", "unbranded", "pre-packaged", "labelled"]):
        return "branding"
    if any(k in text_lower for k in ["registered", "unregistered", "composition"]):
        return "registration"
    if any(k in text_lower for k in ["works contract", "with installation", "export", "sez"]):
        return "supply_type"
    if any(k in text_lower for k in ["exceeding", "not exceeding", "above", "below", "up to", "upto"]):
        return "price_threshold"
    if any(k in text_lower for k in ["for use in", "used for", "for the purpose of"]):
        return "end_use"
    if any(k in text_lower for k in ["government", "authority", "municipality", "recipient"]):
        return "entity_type"
    return "none"

def main():
    load_dotenv()
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    supabase: Client = create_client(url, key)

    print("Fetching HSN rates with conditions...")
    # Fetch all records with conditions to update their condition_type
    res = supabase.table("hsn_rates").select("id, condition_text").eq("has_condition", True).execute()
    hsn_rows = res.data

    updates_hsn = []
    for row in hsn_rows:
        ctype = determine_condition(row.get("condition_text"))
        if ctype != "none":
            updates_hsn.append({"id": row["id"], "condition_type": ctype})

    print(f"Found {len(updates_hsn)} HSN rates to update...")
    for i, row in enumerate(updates_hsn):
        supabase.table("hsn_rates").update({"condition_type": row["condition_type"]}).eq("id", row["id"]).execute()
        if i % 10 == 0:
            print(f"  HSN updated: {i}/{len(updates_hsn)}")

    # Do the same for sac_rates
    print("\nFetching SAC rates with conditions...")
    res = supabase.table("sac_rates").select("id, condition_text").eq("has_condition", True).execute()
    sac_rows = res.data

    updates_sac = []
    for row in sac_rows:
        ctype = determine_condition(row.get("condition_text"))
        if ctype != "none":
            updates_sac.append({"id": row["id"], "condition_type": ctype})

    print(f"Found {len(updates_sac)} SAC rates to update...")
    for i, row in enumerate(updates_sac):
        supabase.table("sac_rates").update({"condition_type": row["condition_type"]}).eq("id", row["id"]).execute()
        if i % 10 == 0:
            print(f"  SAC updated: {i}/{len(updates_sac)}")

    print("Done classifying conditions!")

if __name__ == "__main__":
    main()
