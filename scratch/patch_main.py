import re

with open("main.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Imports
if "import traceback" not in content:
    content = content.replace("import os", "import os\nimport traceback\nimport logging\nfrom typing import Optional", 1)
if "from pydantic import validator" not in content:
    content = content.replace("from pydantic import BaseModel, Field", "from pydantic import BaseModel, Field, validator", 1)

# 2. InvoiceItemRequest
new_item_req = """class InvoiceItemRequest(BaseModel):
    hsn_code: str
    quantity: float = 1.0
    rate: Optional[float] = None
    amount: Optional[float] = None

    @validator('amount', always=True)
    def compute_amount(cls, v, values):
        if v is not None:
            return v
        rate = values.get('rate')
        qty = values.get('quantity', 1.0)
        if rate is not None:
            return rate * qty
        raise ValueError("Either 'amount' or 'rate' must be provided")"""
content = re.sub(
    r"class InvoiceItemRequest\(BaseModel\):\n\s+hsn_code: str\n\s+quantity: float\n\s+rate: float",
    new_item_req,
    content
)

# 3. STATE_LOOKUP & resolve_state
old_state_logic = re.search(r"_STATE_NAME_TO_CODE.*?def _resolve_state.*?raise ValueError.*?\)[\s\n]+", content, re.DOTALL)

new_state_logic = """STATE_LOOKUP = {
    # Full names (lowercase for matching)
    "andhra pradesh": "Andhra Pradesh",
    "arunachal pradesh": "Arunachal Pradesh",
    "assam": "Assam",
    "bihar": "Bihar",
    "chhattisgarh": "Chhattisgarh",
    "goa": "Goa",
    "gujarat": "Gujarat",
    "haryana": "Haryana",
    "himachal pradesh": "Himachal Pradesh",
    "jharkhand": "Jharkhand",
    "karnataka": "Karnataka",
    "kerala": "Kerala",
    "madhya pradesh": "Madhya Pradesh",
    "maharashtra": "Maharashtra",
    "manipur": "Manipur",
    "meghalaya": "Meghalaya",
    "mizoram": "Mizoram",
    "nagaland": "Nagaland",
    "odisha": "Odisha",
    "punjab": "Punjab",
    "rajasthan": "Rajasthan",
    "sikkim": "Sikkim",
    "tamil nadu": "Tamil Nadu",
    "telangana": "Telangana",
    "tripura": "Tripura",
    "uttar pradesh": "Uttar Pradesh",
    "uttarakhand": "Uttarakhand",
    "west bengal": "West Bengal",
    "delhi": "Delhi",
    "jammu and kashmir": "Jammu & Kashmir",
    "jammu & kashmir": "Jammu & Kashmir",
    "ladakh": "Ladakh",
    "andaman and nicobar": "Andaman & Nicobar",
    "andaman & nicobar islands": "Andaman & Nicobar",
    "chandigarh": "Chandigarh",
    "dadra and nagar haveli": "Dadra & Nagar Haveli",
    "daman and diu": "Daman & Diu",
    "lakshadweep": "Lakshadweep",
    "puducherry": "Puducherry",
    "pondicherry": "Puducherry",
    # 2-digit GST numeric state codes (as strings)
    "01": "Jammu & Kashmir", "02": "Himachal Pradesh", "03": "Punjab", "04": "Chandigarh", "05": "Uttarakhand",
    "06": "Haryana", "07": "Delhi", "08": "Rajasthan", "09": "Uttar Pradesh",
    "1": "Jammu & Kashmir", "2": "Himachal Pradesh", "3": "Punjab", "4": "Chandigarh", "5": "Uttarakhand",
    "6": "Haryana", "7": "Delhi", "8": "Rajasthan", "9": "Uttar Pradesh",
    "10": "Bihar", "11": "Sikkim", "12": "Arunachal Pradesh", "13": "Nagaland", "14": "Manipur",
    "15": "Mizoram", "16": "Tripura", "17": "Meghalaya", "18": "Assam", "19": "West Bengal", "20": "Jharkhand",
    "21": "Odisha", "22": "Chhattisgarh", "23": "Madhya Pradesh", "24": "Gujarat", "26": "Dadra & Nagar Haveli",
    "27": "Maharashtra", "28": "Andhra Pradesh", "29": "Karnataka", "30": "Goa", "31": "Lakshadweep",
    "32": "Kerala", "33": "Tamil Nadu", "34": "Puducherry", "35": "Andaman & Nicobar", "36": "Telangana",
    "37": "Andhra Pradesh", "38": "Ladakh",
    # Common abbreviations
    "mh": "Maharashtra", "mah": "Maharashtra", "ka": "Karnataka", "kar": "Karnataka", "tn": "Tamil Nadu",
    "dl": "Delhi", "nd": "Delhi", "gj": "Gujarat", "guj": "Gujarat", "rj": "Rajasthan", "raj": "Rajasthan",
    "up": "Uttar Pradesh", "wb": "West Bengal", "pb": "Punjab", "hr": "Haryana", "br": "Bihar",
    "mp": "Madhya Pradesh", "ap": "Andhra Pradesh", "ts": "Telangana", "tg": "Telangana", "kl": "Kerala",
    "od": "Odisha", "or": "Odisha", "uk": "Uttarakhand", "ua": "Uttarakhand", "jk": "Jammu & Kashmir",
    "hp": "Himachal Pradesh", "ga": "Goa", "as": "Assam", "jh": "Jharkhand", "cg": "Chhattisgarh",
    "ct": "Chhattisgarh", "sk": "Sikkim", "mn": "Manipur", "ml": "Meghalaya", "mz": "Mizoram", "nl": "Nagaland",
    "tr": "Tripura", "ar": "Arunachal Pradesh", "py": "Puducherry", "pu": "Puducherry", "ch": "Chandigarh",
    "la": "Ladakh",
}

def _resolve_state(input_str: str) -> str:
    if not input_str:
        raise ValueError("State cannot be empty")
    key = input_str.strip().lower()
    result = STATE_LOOKUP.get(key)
    if not result:
        raise ValueError(
            f"Unrecognised state: '{input_str}'. "
            f"Accepted formats: full name ('Maharashtra'), "
            f"2-digit GST code ('27'), or abbreviation ('mh')."
        )
    return result

"""
if old_state_logic:
    content = content.replace(old_state_logic.group(0), new_state_logic)

# 4. invoice_classify route
old_classify_logic = re.search(r"@app\.post\(\"/api/v1/invoice/classify\".*?return InvoiceResponse\([^)]+\)\n", content, re.DOTALL)

new_classify_logic = '''logger = logging.getLogger(__name__)

@app.post("/api/v1/invoice/classify")
async def classify_invoice(
    payload: InvoiceRequest,
    _: dict = Depends(verify_api_key),
):
    try:
        seller_state = _resolve_state(payload.seller_state)
        buyer_state = _resolve_state(payload.buyer_state)
        is_interstate = seller_state != buyer_state
        transaction_type = "interstate" if is_interstate else "intrastate"
        
        hsn_codes_list = [item.hsn_code for item in payload.items]
        rate_map = {}
        
        # Batch DB Query
        if db_pool:
            async with db_pool.acquire() as conn:
                rows = await conn.fetch("SELECT * FROM hsn_rates WHERE hsn_code = ANY($1)", hsn_codes_list)
                rate_map = {r["hsn_code"]: dict(r) for r in rows}
        else:
            response = supabase.table("hsn_rates").select("hsn_code, igst_rate, cgst_rate, sgst_rate, cess_rate, description").in_("hsn_code", hsn_codes_list).execute()
            rate_map = {row["hsn_code"]: row for row in response.data}
            
        missing = [c for c in hsn_codes_list if c not in rate_map]
        if missing:
            # Maybe fallback to chapter if we want, but user said HTTP 404
            raise HTTPException(status_code=404, detail=f"HSN codes not found: {missing}")
            
        classified_items = []
        totals = {"base": 0.0, "cgst": 0.0, "sgst": 0.0, "igst": 0.0, "cess": 0.0}
        
        for item in payload.items:
            row = rate_map[item.hsn_code]
            igst_pct = row.get("igst_rate") or row.get("igst") or 0.0
            cgst_pct = row.get("cgst_rate") or row.get("cgst") or (igst_pct / 2)
            cess_pct = row.get("cess_rate") or row.get("cess") or 0.0
            
            base = round(item.amount, 2)
            if is_interstate:
                igst_amt = round(base * igst_pct / 100, 2)
                cgst_amt = 0.0
                sgst_amt = 0.0
            else:
                cgst_amt = round(base * cgst_pct / 100, 2)
                sgst_amt = cgst_amt
                igst_amt = 0.0
            cess_amt = round(base * cess_pct / 100, 2)
            
            total_tax = round(cgst_amt + sgst_amt + igst_amt + cess_amt, 2)
            total_amt = round(base + total_tax, 2)
            
            totals["base"] += base
            totals["cgst"] += cgst_amt
            totals["sgst"] += sgst_amt
            totals["igst"] += igst_amt
            totals["cess"] += cess_amt
            
            classified_items.append(InvoiceItemResponse(
                hsn_code=item.hsn_code,
                quantity=item.quantity,
                rate=item.rate or (item.amount/item.quantity if item.quantity else 0.0),
                base_amount=base,
                cgst_amount=cgst_amt,
                sgst_amount=sgst_amt,
                igst_amount=igst_amt,
                cess_amount=cess_amt,
                total_tax_amount=total_tax,
                total_amount=total_amt
            ))
            
        return InvoiceResponse(
            transaction_type=transaction_type,
            seller_state=seller_state,
            buyer_state=buyer_state,
            items=classified_items,
            total_base_amount=round(totals["base"], 2),
            total_cgst_amount=round(totals["cgst"], 2),
            total_sgst_amount=round(totals["sgst"], 2),
            total_igst_amount=round(totals["igst"], 2),
            total_cess_amount=round(totals["cess"], 2),
            grand_total=round(totals["base"] + totals["cgst"] + totals["sgst"] + totals["igst"] + totals["cess"], 2)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Invoice classify failed:\\n"
            f"Request: {payload.dict()}\\n"
            f"Error: {str(e)}\\n"
            f"Traceback:\\n{traceback.format_exc()}"
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": str(e),
                "code": 500,
                "type": type(e).__name__,
                "suggestions": []
            }
        )
'''

if old_classify_logic:
    content = content.replace(old_classify_logic.group(0), new_classify_logic)

with open("main.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Patch applied")
