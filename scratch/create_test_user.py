import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") # This needs to be the service_role key to bypass email confirmation or we can just use sign_up.

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

email = "t_user@gmail.com"
password = "T_user@4812"

try:
    res = supabase.auth.admin.create_user({
        "email": email,
        "password": password,
        "email_confirm": True
    })
    print("User created successfully!")
    print(res)
except Exception as e:
    print(f"Error creating user: {e}")
