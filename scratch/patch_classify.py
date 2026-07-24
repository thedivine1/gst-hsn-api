import re

with open("main.py", "r", encoding="utf-8") as f:
    content = f.read()

sac_lookup = """
async def _lookup_sac_rate_raw(code: str, conn) -> dict | None:
    \"\"\"
    Internal SAC DB lookup - returns the first matching row dict or None.
    Falls back from exact -> 4-digit heading.
    \"\"\"
    code = code.strip()
    if db_pool and conn:
        rows = await conn.fetch("SELECT * FROM sac_rates WHERE sac_code = $1 LIMIT 1", code)
        if rows:
            return dict(rows[0])
        if len(code) >= 4:
            heading = code[:4]
            rows = await conn.fetch(
                "SELECT * FROM sac_rates WHERE sac_code LIKE $1 LIMIT 50",
                f"{heading}%"
            )
            if rows:
                return dict(rows[0])
    else:
        # Supabase PostgREST fallback
        try:
            res = (
                supabase.table("sac_rates")
                .select("*")
                .eq("sac_code", code)
                .limit(1)
                .execute()
            )
            if res.data:
                return res.data[0]
            if len(code) >= 4:
                res2 = (
                    supabase.table("sac_rates")
                    .select("*")
                    .like("sac_code", f"{code[:4]}%")
                    .limit(50)
                    .execute()
                )
                if res2.data:
                    return res2.data[0]
        except Exception:
            pass
    return None

async def _lookup_hsn_rate_raw"""

content = content.replace("async def _lookup_hsn_rate_raw", sac_lookup, 1)

old_process = """
    async def _process(item: InvoiceItemRequest, conn) -> InvoiceItemResponse:
        row = await _lookup_hsn_rate_raw(item.hsn_code, conn)
        if row is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": f"HSN code '{item.hsn_code}' not found in database.",
                    "code": 404,
                    "suggestions": []
                },
            )

        igst_pct: float = float(row.get("igst_rate") or 0.0)
        cgst_pct: float = float(row.get("cgst_rate") or (igst_pct / 2))
        cess_pct: float = float(row.get("cess_rate") or 0.0)
        description: str = row.get("description") or ""
"""

new_process = """
    async def _process(item: InvoiceItemRequest, conn) -> InvoiceItemResponse:
        is_service = item.hsn_code.startswith("99")
        if is_service:
            row = await _lookup_sac_rate_raw(item.hsn_code, conn)
            code_type = "SAC"
            description_key = "sac_description"
        else:
            row = await _lookup_hsn_rate_raw(item.hsn_code, conn)
            code_type = "HSN"
            description_key = "hsn_description"

        if row is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": f"{code_type} code '{item.hsn_code}' not found in database.",
                    "code": 404,
                    "suggestions": []
                },
            )

        igst_pct: float = float(row.get("igst_rate") or 0.0)
        cgst_pct: float = float(row.get("cgst_rate") or (igst_pct / 2))
        cess_pct: float = float(row.get("cess_rate") or 0.0)
        description: str = row.get(description_key) or row.get("description") or ""
"""

if old_process.strip("\n") in content:
    content = content.replace(old_process.strip("\n"), new_process.strip("\n"), 1)
else:
    print("WARNING: Could not find old _process implementation to replace!")

with open("main.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Updated successfully")
