"""
generate_api_key.py
--------------------
Utility to create and register a new API key in Supabase.
Prints the raw key ONCE — store it securely. The raw key is never stored.

Usage:
    python generate_api_key.py --tier free --limit 100 --prefix myapp
    python generate_api_key.py --tier pro  --limit 10000 --prefix prod
"""

import os
import secrets
import hashlib
import argparse
from datetime import date
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("ERROR: Set SUPABASE_URL and SUPABASE_KEY in environment or .env file.")
    exit(1)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def generate_key(prefix: str = "gst") -> tuple[str, str, str]:
    """Returns (raw_key, key_hash, key_prefix)."""
    token = secrets.token_urlsafe(32)
    raw_key = f"{prefix}_{token}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    key_prefix = raw_key[:10]
    return raw_key, key_hash, key_prefix


def register_key(tier: str, limit: int, prefix: str):
    raw_key, key_hash, key_prefix = generate_key(prefix)

    # First reset day of next month
    today = date.today()
    reset = date(today.year + (today.month // 12), today.month % 12 + 1, 1)

    record = {
        "key_hash": key_hash,
        "key_prefix": key_prefix,
        "tier": tier,
        "monthly_limit": limit,
        "reset_date": str(reset),
        "is_active": True,
    }

    try:
        res = supabase.table("api_keys").insert(record).execute()
        print("\n✅ API key registered successfully!")
        print(f"   Tier      : {tier}")
        print(f"   Limit     : {limit} calls/month")
        print(f"   Prefix    : {key_prefix}")
        print(f"\n🔑 YOUR RAW API KEY (copy it now — it will NOT be shown again):")
        print(f"\n   {raw_key}\n")
    except Exception as e:
        print(f"ERROR registering key: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a GST API key")
    parser.add_argument("--tier", default="free", choices=["free", "pro", "enterprise"])
    parser.add_argument("--limit", type=int, default=100, help="Monthly call limit")
    parser.add_argument("--prefix", default="gst", help="Key prefix identifier")
    args = parser.parse_args()
    register_key(args.tier, args.limit, args.prefix)
