import os
from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://example.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", os.environ.get("SUPABASE_ANON_KEY", ""))

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def test_search():
    res = supabase.table("hsn_rates").select("*").text_search("hsn_description", "basmati & rice").execute()
    print("AND Search:", len(res.data))
    if not res.data:
        res = supabase.table("hsn_rates").select("*").text_search("hsn_description", "basmati | rice").execute()
        print("OR Search:", len(res.data))
        if not res.data:
            res = supabase.table("hsn_rates").select("*").ilike("hsn_description", "%basmati%").execute()
            print("ILIKE Search basmati:", len(res.data))
    
    if res.data:
        print("First result:", res.data[0].get('hsn_description'))

if __name__ == "__main__":
    test_search()
