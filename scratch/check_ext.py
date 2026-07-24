import asyncio
import asyncpg
import os
from dotenv import load_dotenv
load_dotenv()

async def run():
    pool = await asyncpg.create_pool(os.environ["DATABASE_URL"], ssl="require", statement_cache_size=0)
    async with pool.acquire() as conn:
        result = await conn.fetch("SELECT extname FROM pg_extension WHERE extname = 'pg_trgm'")
        print("pg_trgm installed:", bool(result))
        idx = await conn.fetch(
            "SELECT indexname, indexdef FROM pg_indexes WHERE tablename='hsn_rates' AND indexdef ILIKE '%description%'"
        )
        print("Existing indexes on hsn_description:")
        for r in idx:
            print(" ", dict(r))
    await pool.close()

asyncio.run(run())
