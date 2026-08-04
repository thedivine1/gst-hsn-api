import asyncio
from main import supabase

async def main():
    res = supabase.table("hsn_rates").select("hsn_code").like("hsn_code", "%8109030%").limit(10).execute()
    print([r["hsn_code"] for r in res.data])

asyncio.run(main())
