import asyncio
import asyncpg
import os
import time
from dotenv import load_dotenv
load_dotenv()

async def run():
    pool = await asyncpg.create_pool(
        os.environ["DATABASE_URL"],
        ssl="require",
        statement_cache_size=0,
        server_settings={"search_path": "public"}
    )
    async with pool.acquire() as conn:
        queries = ["rice", "cotton", "machine", "steel", "cement"]
        for q in queries:
            q_lower = q.lower()
            t0 = time.perf_counter()
            prefix_rows = await conn.fetch(
                """
                SELECT hsn_code, hsn_description
                FROM hsn_rates
                WHERE hsn_description ILIKE $1
                ORDER BY length(hsn_description)
                LIMIT 10
                """,
                f"{q}%",
                
            )
            elapsed_prefix = (time.perf_counter() - t0) * 1000

            t1 = time.perf_counter()
            if len(prefix_rows) < 10:
                remaining = 10 - len(prefix_rows)
                trgm_rows = await conn.fetch(
                    """
                    SELECT hsn_code, hsn_description
                    FROM hsn_rates
                    WHERE hsn_description ILIKE $1
                      AND NOT (hsn_description ILIKE $2)
                    ORDER BY length(hsn_description)
                    LIMIT $3
                    """,
                    f"%{q}%",
                    f"{q}%",
                    remaining,
                )
            else:
                trgm_rows = []
            elapsed_trgm = (time.perf_counter() - t1) * 1000

            total = elapsed_prefix + elapsed_trgm
            print(f"{q:<10} prefix={len(prefix_rows)} ({elapsed_prefix:.1f}ms)  trgm={len(trgm_rows)} ({elapsed_trgm:.1f}ms)  total={total:.1f}ms")
    await pool.close()

asyncio.run(run())
