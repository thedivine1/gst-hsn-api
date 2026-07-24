import re

with open("main.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update autocomplete
autocomplete_old = r'''async def autocomplete\(q: str, _: dict = Depends\(verify_api_key\)\):
    if not q\.strip\(\):
        return \[\]
        
    global db_pool
    if not db_pool:
        # Fallback to Supabase PostgREST client
        try:
            res = supabase\.table\("hsn_rates"\)\.select\("hsn_code,hsn_description"\)\.ilike\("hsn_description", f"%\{q\}%"\)\.limit\(10\)\.execute\(\)
            return res\.data or \[\]
        except Exception as e:
            raise HTTPException\(status_code=503, detail=f"Database unavailable: \{e\}"\)
        
    async with db_pool\.acquire\(\) as conn:
        rows = await conn\.fetch\(
            "SELECT hsn_code, hsn_description FROM hsn_rates WHERE hsn_description ILIKE \$1 LIMIT 10", 
            f"%\{q\}%"
        \)
        return \[dict\(row\) for row in rows\]'''

autocomplete_new = '''async def autocomplete(q: str, _: dict = Depends(verify_api_key), limit: int = 10):
    if not q or len(q.strip()) < 2:
        return []
    
    q_lower = q.strip().lower()
    
    # Step 1: Exact word match at start (highest priority)
    exact_start = supabase.table("hsn_rates")\\
        .select("hsn_code,hsn_description")\\
        .ilike("hsn_description", f"{q}%")\\
        .limit(5)\\
        .execute()
    
    # Step 2: Contains word (medium priority)
    contains = supabase.table("hsn_rates")\\
        .select("hsn_code,hsn_description")\\
        .ilike("hsn_description", f"% {q}%")\\
        .limit(10)\\
        .execute()
    
    # Step 3: Merge, deduplicate, prefer shorter descriptions
    seen = set()
    results = []
    for row in (exact_start.data or []) + (contains.data or []):
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
    return results[:limit]'''

content = re.sub(autocomplete_old, autocomplete_new, content)

# 2. Update bulk_lookup
bulk_old = r'''async def bulk_lookup\(requests: List\[LookupRequest\], _: dict = Depends\(verify_api_key\)\):
    """
    Accepts up to 100 lookup requests and returns an array of result arrays\.
    """
    if len\(requests\) > 100:
        raise HTTPException\(
            status_code=400, detail="Maximum 100 items per bulk request\."
        \)
    if len\(requests\) == 0:
        raise HTTPException\(status_code=400, detail="Request list cannot be empty\."\)

    import asyncio
    
    async def process_one\(req\):
        if not req\.description\.strip\(\):
            return \[\]
        return await _async_lookup\(req\)
        
    results = await asyncio\.gather\(\*\[process_one\(req\) for req in requests\]\)
    return list\(results\)'''

bulk_new = '''async def bulk_lookup(requests: List[LookupRequest], _: dict = Depends(verify_api_key)):
    """
    Accepts up to 100 lookup requests and returns an array of result arrays.
    """
    if len(requests) > 100:
        raise HTTPException(
            status_code=400, detail="Maximum 100 items per bulk request."
        )
    if len(requests) == 0:
        raise HTTPException(status_code=400, detail="Request list cannot be empty.")

    import asyncio
    
    async def process_one(req):
        if not req.description.strip():
            return []
        return await _async_lookup(req)
        
    # Run all lookups in parallel, not sequentially
    tasks = [process_one(req) for req in requests]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Handle any individual failures gracefully
    response = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            response.append({
                "input": requests[i].dict(),
                "error": str(result),
                "hsn_code": None
            })
        else:
            response.append(result)
            
    return response'''

content = re.sub(bulk_old, bulk_new, content)

# 3. Update get_hsn caching
hsn_cache_old = r'''    # HSN codes are static data — cache aggressively at CDN \+ browser level
    if response:
        response\.headers\["Cache-Control"\] = "public, max-age=86400, s-maxage=86400, stale-while-revalidate=3600"'''

hsn_cache_new = '''    # HSN codes are static data — cache aggressively at CDN + browser level
    if response:
        response.headers["Cache-Control"] = "public, max-age=86400"
        response.headers["X-Robots-Tag"] = "noindex"'''

content = re.sub(hsn_cache_old, hsn_cache_new, content)

# 4. Update get_sac caching
sac_cache_old = r'''    # SAC codes are static — cache at CDN level
    if response:
        response\.headers\["Cache-Control"\] = "public, max-age=86400, s-maxage=86400, stale-while-revalidate=3600"'''

sac_cache_new = '''    # SAC codes are static — cache at CDN level
    if response:
        response.headers["Cache-Control"] = "public, max-age=86400"
        response.headers["X-Robots-Tag"] = "noindex"'''

content = re.sub(sac_cache_old, sac_cache_new, content)


with open("main.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Updated successfully")
