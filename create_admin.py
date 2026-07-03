import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(url, key)

try:
    # Try admin creation first (bypasses email confirmation and allows setting roles)
    res = supabase.auth.admin.create_user({
        "email": "coepianraider@gmail.com",
        "password": "l%8Sb3*e1ERZ32i",
        "email_confirm": True,
        "user_metadata": {"role": "admin"}
    })
    print("User created via admin API:", res.user.email)
except Exception as e:
    print("Admin creation failed, trying standard signup...")
    try:
        res = supabase.auth.sign_up({
            "email": "coepianraider@gmail.com",
            "password": "l%8Sb3*e1ERZ32i"
        })
        print("User created via sign_up:", res.user.email)
        print("Note: Email confirmation is required.")
    except Exception as e2:
        print("Sign up failed:", str(e2))
