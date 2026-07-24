import re

with open("main.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update autocomplete to use db_pool for async operation
autocomplete_new = """@app.get("/api/v1/autocomplete")
async def autocomplete(q: str, _: dict = Depends(verify_api_key), limit: int = 10):
    if not q or len(q.strip()) < 2:
        return []
    
    q_lower = q.strip().lower()
    
    global db_pool
    if db_pool:
        async with db_pool.acquire() as conn:
            exact_start = await conn.fetch(
                "SELECT hsn_code, hsn_description FROM hsn_rates WHERE hsn_description ILIKE $1 LIMIT 5",
                f"{q}%"
            )
            contains = await conn.fetch(
                "SELECT hsn_code, hsn_description FROM hsn_rates WHERE hsn_description ILIKE $1 LIMIT 10",
                f"% {q}%"
            )
            data_exact = [dict(r) for r in exact_start]
            data_contains = [dict(r) for r in contains]
    else:
        exact_start = supabase.table("hsn_rates")\\
            .select("hsn_code,hsn_description")\\
            .ilike("hsn_description", f"{q}%")\\
            .limit(5)\\
            .execute()
        
        contains = supabase.table("hsn_rates")\\
            .select("hsn_code,hsn_description")\\
            .ilike("hsn_description", f"% {q}%")\\
            .limit(10)\\
            .execute()
        data_exact = exact_start.data or []
        data_contains = contains.data or []
        
    # Step 3: Merge, deduplicate, prefer shorter descriptions
    seen = set()
    results = []
    for row in data_exact + data_contains:
        code = row["hsn_code"]
        if code not in seen:
            seen.add(code)
            results.append(row)
    
    # Sort: exact word match first, then by description length
    def score(r):
        desc = r["hsn_description"].lower()
        if desc.startswith(q_lower):
            return (0, len(desc))
        elif f" {q_lower}" in desc or f"/{q_lower}" in desc:
            return (1, len(desc))
        return (2, len(desc))
    
    results.sort(key=score)
    return results[:limit]"""

content = re.sub(
    r'@app\.get\("/api/v1/autocomplete"\).*?return results\[:limit\]',
    autocomplete_new.strip(),
    content,
    flags=re.DOTALL
)

with open("main.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Autocomplete patched for async.")
