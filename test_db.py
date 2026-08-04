import asyncio
from main import supabase

async def main():
    res = supabase.table("hsn_rates").select("hsn_code").limit(100).execute()
    print([r["hsn_code"] for r in res.data])

asyncio.run(main())
