#!/usr/bin/env python3
"""
Runs each CREATE INDEX statement individually using a separate asyncpg connection
because CONCURRENTLY cannot run inside a transaction block.
"""
import asyncio
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

import asyncpg

STATEMENTS = [
    "CREATE EXTENSION IF NOT EXISTS pg_trgm",
    """
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_hsn_description_trgm
ON public.hsn_rates USING GIN (hsn_description gin_trgm_ops)
""",
    """
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sac_description_trgm
ON public.sac_rates USING GIN (sac_description gin_trgm_ops)
""",
    """
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_hsn_code_btree
ON public.hsn_rates (hsn_code)
""",
    """
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sac_code_btree
ON public.sac_rates (sac_code)
""",
]

VERIFY_QUERY = """
SELECT tablename, indexname, indexdef
FROM pg_indexes
WHERE tablename IN ('hsn_rates', 'sac_rates')
ORDER BY tablename, indexname;
"""

EXPECTED = {
    "idx_hsn_description_trgm",
    "idx_sac_description_trgm",
    "idx_hsn_code_btree",
    "idx_sac_code_btree",
}


async def run():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL not set.")
        sys.exit(1)

    # Each statement needs its own connection — CONCURRENTLY forbids transactions
    for i, stmt in enumerate(STATEMENTS, 1):
        short = stmt.strip().splitlines()[0][:80]
        print(f"[{i}/{len(STATEMENTS)}] {short}...")
        conn = await asyncpg.connect(dsn=database_url, ssl="require")
        try:
            await conn.execute(stmt.strip())
            print(f"        OK")
        except Exception as e:
            print(f"        ERROR: {e}")
        finally:
            await conn.close()

    # Verify
    print("\nVerifying indexes...")
    conn = await asyncpg.connect(dsn=database_url, ssl="require", statement_cache_size=0)
    try:
        rows = await conn.fetch(VERIFY_QUERY)
        found = set()
        print(f"\n{'Table':<15} {'Index':<35} Definition")
        print("-" * 100)
        for row in rows:
            print(f"{row['tablename']:<15} {row['indexname']:<35} {row['indexdef'][:55]}")
            found.add(row["indexname"])
        missing = EXPECTED - found
        print()
        if missing:
            print(f"MISSING indexes: {missing}")
        else:
            print("All 4 trigram / B-tree indexes confirmed present.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run())
