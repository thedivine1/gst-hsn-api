import re

with open("main.py", "r", encoding="utf-8") as f:
    content = f.read()

cache_setup = """_key_cache: dict = {}          # {key_hash: (record_dict, expires_at)}
KEY_CACHE_TTL = 60             # seconds - cache entries live for 1 minute
_usage_buffer: dict = {}       # {api_key_id: pending_increment_count}

# ---------------------------------------------------------------------------
# In-memory TTL cache for summary endpoint (24 hours)
# ---------------------------------------------------------------------------
_summary_cache: dict = {"gst:rates:summary": None, "timestamp": 0}
SUMMARY_CACHE_TTL = 86400  # 24 hours"""

content = content.replace(
    "_key_cache: dict = {}          # {key_hash: (record_dict, expires_at)}\nKEY_CACHE_TTL = 60             # seconds - cache entries live for 1 minute\n_usage_buffer: dict = {}       # {api_key_id: pending_increment_count}",
    cache_setup
)

old_summary_start = """async def get_summary(_: dict = Depends(verify_api_key)):
    \"\"\"
    Returns overall statistics: total codes, match rates, schedule breakdown, etc.
    \"\"\"
    global db_pool"""

new_summary_start = """async def get_summary(_: dict = Depends(verify_api_key)):
    \"\"\"
    Returns overall statistics: total codes, match rates, schedule breakdown, etc.
    \"\"\"
    import time
    global _summary_cache
    if _summary_cache["gst:rates:summary"] and time.time() - _summary_cache["timestamp"] < SUMMARY_CACHE_TTL:
        return _summary_cache["gst:rates:summary"]

    global db_pool"""

content = content.replace(old_summary_start, new_summary_start)


old_summary_end = """    return SummaryResponse(
        total_hsn_codes=total_hsn,
        total_sac_codes=total_sac,
        matched_with_rate=matched,
        unmatched=total_hsn - matched,
        has_conditions=has_conditions,
        cess_applicable=cess_count,
        by_schedule=by_schedule,
        rate_slabs=rate_slabs,
        last_updated="2025-09-22",
    )"""

new_summary_end = """    response = SummaryResponse(
        total_hsn_codes=total_hsn,
        total_sac_codes=total_sac,
        matched_with_rate=matched,
        unmatched=total_hsn - matched,
        has_conditions=has_conditions,
        cess_applicable=cess_count,
        by_schedule=by_schedule,
        rate_slabs=rate_slabs,
        last_updated="2025-09-22",
    )
    
    import time
    global _summary_cache
    _summary_cache["gst:rates:summary"] = response
    _summary_cache["timestamp"] = time.time()
    
    return response"""

content = content.replace(old_summary_end, new_summary_end)


with open("main.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Summary cache added.")
