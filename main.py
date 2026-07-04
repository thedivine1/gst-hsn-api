import os
import re
import hashlib
import calendar
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Tuple, Literal
# pyrefly: ignore [missing-import]
from fastapi import FastAPI, Header, HTTPException, Depends, Request, Response
# pyrefly: ignore [missing-import]
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field
from supabase import create_client, Client  # pyright: ignore [missing-import]
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv
import contextvars
import mcp.types as types
from mcp.server import Server
from mcp.server.sse import SseServerTransport
import json

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY")
NEXT_PUBLIC_SITE_URL = os.environ.get("NEXT_PUBLIC_SITE_URL", "http://localhost:8000")

# Razorpay Payment Button IDs
RAZORPAY_BTN_DEVELOPER = os.environ.get("RAZORPAY_BTN_DEVELOPER", "pl_T7XX9dBePAqE3A")
RAZORPAY_BTN_PRO       = os.environ.get("RAZORPAY_BTN_PRO",       "pl_T7XijjsMTRfuBk")
RAZORPAY_BTN_BUSINESS  = os.environ.get("RAZORPAY_BTN_BUSINESS",  "pl_T7Xpk3fkQwHzrt")

# GitHub OAuth
GITHUB_CLIENT_ID     = os.environ.get("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")

supabase: Optional[Client] = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"Failed to initialize Supabase client: {e}")
else:
    print("WARNING: SUPABASE_URL and/or SUPABASE_KEY are missing. Supabase client will be None.")

app = FastAPI(
    title="gstaccelerator.in API",
    version="1.0.0",
    description="Lookup GST CGST/IGST/SGST/Cess rates for Indian goods (HSN) and services (SAC) codes. Powered by gstaccelerator.in.",
    docs_url="/swagger",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://gstaccelerator.in",
        "https://www.gstaccelerator.in",
        "https://gst-hsn-api.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS", "DELETE"],
    allow_headers=["X-API-Key", "Content-Type", "Authorization"],
)

import time
START_TIME = time.time()
rate_limit_db = {}
rate_limit_timestamps = {}
demo_rate_limit_db = {}
demo_rate_limit_timestamps = {}

# ContextVar so verify_api_key can pass monthly quota info to the middleware
_monthly_ratelimit_ctx: contextvars.ContextVar[dict | None] = contextvars.ContextVar("_monthly_ratelimit_ctx", default=None)

class IPRateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith("/api/v1/"):
            return await call_next(request)
            
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        
        # Reset counters every minute
        if client_ip not in rate_limit_timestamps or now - rate_limit_timestamps[client_ip] > 60:
            rate_limit_timestamps[client_ip] = now
            rate_limit_db[client_ip] = 0
            
        rate_limit_db[client_ip] += 1
        remaining = max(0, 100 - rate_limit_db[client_ip])
        
        if rate_limit_db[client_ip] > 100:
            return JSONResponse(
                status_code=429,
                content={"error": "Too Many Requests", "code": 429, "suggestions": ["Please wait a minute before trying again"]},
                headers={
                    "X-RateLimit-Limit": "100",
                    "X-RateLimit-Remaining": str(remaining),
                    "Content-Type": "application/json"
                }
            )
            
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = "100"
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["Content-Type"] = "application/json"
        response.headers["X-Robots-Tag"] = "noindex"
        # Overlay monthly tier headers if verify_api_key populated them
        monthly = _monthly_ratelimit_ctx.get()
        if monthly:
            response.headers["X-RateLimit-Limit"]     = str(monthly["limit"])
            response.headers["X-RateLimit-Remaining"] = str(monthly["remaining"])
            response.headers["X-RateLimit-Reset"]     = str(monthly["reset"])
        return response

app.add_middleware(IPRateLimitMiddleware)

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": str(exc.detail), "code": exc.status_code, "suggestions": []}
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"error": "Validation error", "code": 422, "suggestions": exc.errors()}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "code": 500, "suggestions": []}
    )


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


async def verify_api_key(x_api_key: str = Header(..., description="Your API key")):
    """Dependency: validates X-API-Key, enforces monthly limits, increments usage."""
    if x_api_key in ("gsta_demo_frontend", "demo_public_key"):
        return {"tier": "demo", "api_key_id": "demo"}
        
    key_hash = _hash_key(x_api_key)

    try:
        res = (
            supabase.table("api_keys")
            .select("*")
            .eq("key_hash", key_hash)
            .eq("is_active", True)
            .single()
            .execute()
        )
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or inactive API key.")
        
    if not res.data:
        raise HTTPException(status_code=401, detail="Invalid or inactive API key.")

    record = res.data

    if record["calls_this_month"] >= record["monthly_limit"]:
        raise HTTPException(
            status_code=429,
            detail=f"Monthly limit of {record['monthly_limit']} calls reached for tier '{record['tier']}'.",
        )

    # Increment call counter
    supabase.table("api_keys").update(
        {"calls_this_month": record["calls_this_month"] + 1}
    ).eq("id", record["id"]).execute()

    # Compute X-RateLimit reset: first day of next month at UTC midnight
    now_utc = datetime.now(timezone.utc)
    if now_utc.month == 12:
        reset_dt = datetime(now_utc.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        reset_dt = datetime(now_utc.year, now_utc.month + 1, 1, tzinfo=timezone.utc)
    reset_ts = int(reset_dt.timestamp())

    calls_used = record["calls_this_month"] + 1
    monthly_limit = record["monthly_limit"]

    # Publish monthly quota so IPRateLimitMiddleware can write the headers
    _monthly_ratelimit_ctx.set({
        "limit":     monthly_limit,
        "remaining": max(0, monthly_limit - calls_used),
        "reset":     reset_ts,
    })

    return {
        **record,
        "_ratelimit_limit": monthly_limit,
        "_ratelimit_remaining": max(0, monthly_limit - calls_used),
        "_ratelimit_reset": reset_ts,
    }


# ---------------------------------------------------------------------------
# Health & Meta routes
# ---------------------------------------------------------------------------

@app.get("/health", tags=["Meta"])
async def health():
    """Liveness check — returns API status, version, and uptime."""
    db_status = "connected"
    try:
        supabase.table("hsn_rates").select("id", count="exact").limit(1).execute()
    except Exception:
        db_status = "degraded"
    return {
        "status": "ok",
        "version": "1.0.0",
        "uptime_seconds": round(time.time() - START_TIME),
        "database": db_status,
        "last_updated": "2025-09-22",
        "source": "CBIC 09/2025-CT(Rate)"
    }

@app.get("/meta", tags=["Meta"])
async def meta():
    """API metadata: code counts, rate slabs, data source, and MCP endpoint."""
    return {
        "total_hsn_codes": 48752,
        "total_sac_codes": 681,
        "rate_slabs": [0, 0.25, 1.5, 3, 5, 18, 28, 40],
        "data_source": "CBIC Notification 09/2025-CT(Rate)",
        "effective_from": "2025-09-22",
        "api_version": "v1",
        "mcp_endpoint": "https://gst-hsn-api.vercel.app/mcp/sse"
    }


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class TaxRates(BaseModel):
    igst: Optional[float] = Field(None, description="Interstate supply rate")
    cgst: Optional[float] = Field(None, description="Intrastate centre portion")
    sgst: Optional[float] = Field(None, description="Intrastate state portion")
    utgst: Optional[float] = Field(None, description="Union territory portion")
    cess: Optional[float] = Field(0, description="Compensation cess")
    total_intrastate: Optional[float] = Field(
        None, description="Total intra-state rate (CGST + SGST)"
    )
    total_interstate: Optional[float] = Field(
        None, description="Total inter-state rate (IGST)"
    )


class ApplicableRate(BaseModel):
    intrastate: Optional[str] = None
    interstate: Optional[str] = None
    recommended: Optional[str] = Field(
        None, description="Recommended rate string based on requested supply_type"
    )


class HsnRate(BaseModel):
    id: Optional[int] = None
    hsn_code: str
    hsn_description: str
    description: Optional[str] = None
    schedule: Optional[str] = None
    condition_text: Optional[str] = None
    condition_type: Optional[str] = "none"
    has_condition: Optional[bool] = False
    notification_ref: Optional[str] = None
    effective_date: Optional[str] = None
    needs_review: Optional[bool] = False
    tax_rates: TaxRates
    applicable_rate: ApplicableRate
    last_updated: str = "2025-06-01"
    source: str = "GST Council Notification 09/2025-CT(Rate)"
    gst_rate: Optional[float] = None
    cgst: Optional[float] = None
    sgst: Optional[float] = None
    igst: Optional[float] = None
    condition_warning: Optional[str] = None


class SacRate(BaseModel):
    id: Optional[int] = None
    sac_code: str
    hsn_code: Optional[str] = None
    sac_description: str
    description: Optional[str] = None
    condition_text: Optional[str] = None
    condition_type: Optional[str] = "none"
    has_condition: Optional[bool] = False
    notification_ref: Optional[str] = None
    effective_date: Optional[str] = None
    needs_review: Optional[bool] = False
    tax_rates: TaxRates
    applicable_rate: ApplicableRate
    last_updated: str = "2025-06-01"
    source: str = "GST Council Notification 09/2025-CT(Rate)"
    gst_rate: Optional[float] = None
    cgst: Optional[float] = None
    sgst: Optional[float] = None
    igst: Optional[float] = None
    condition_warning: Optional[str] = None


class SupplyNature(str, Enum):
    domestic = "domestic"
    export = "export"
    sez = "sez"
    works_contract = "works_contract"
    with_installation = "with_installation"


class LookupRequest(BaseModel):
    description: str = Field(..., example="cotton shirt")
    branded: Optional[bool] = Field(
        False,
        description="Is the product branded / pre-packaged and labelled?",
    )
    b2b: Optional[bool] = Field(
        False,
        description="Is this a B2B transaction (registered buyer)?",
    )
    sale_value_inr: Optional[float] = Field(
        None,
        description="Declared sale value in INR — used to resolve price-threshold conditions.",
        ge=0,
    )
    end_use: Optional[str] = Field(
        None,
        description="Intended end-use of the goods (e.g. 'agriculture', 'defence').",
    )
    supply_nature: Optional[SupplyNature] = Field(
        SupplyNature.domestic,
        description="Nature of supply (condition matching). One of: domestic, export, sez, works_contract, with_installation.",
    )
    supply_type: Optional[Literal["intrastate", "interstate"]] = Field(
        None, description="Transaction routing. Dictates the 'recommended' rate output."
    )
    state_code: Optional[str] = Field(
        None, description="For future use (UTGST detection)."
    )


class LookupResult(BaseModel):
    hsn_code: str
    description: str
    tax_rates: TaxRates
    applicable_rate: ApplicableRate
    condition_applied: Optional[str] = None
    condition_warning: Optional[str] = None
    confidence: float
    notification_ref: Optional[str] = None
    needs_review: bool = False
    last_updated: str = "2025-06-01"
    source: str = "GST Council Notification 09/2025-CT(Rate)"
    gst_rate: Optional[float] = None
    cgst: Optional[float] = None
    sgst: Optional[float] = None
    igst: Optional[float] = None


class ScheduleBreakdown(BaseModel):
    schedule: Optional[str]
    count: int


class RateSlabs(BaseModel):
    igst_slabs: List[float]
    cgst_slabs: List[float]
    note: str


class SummaryResponse(BaseModel):
    total_hsn_codes: int
    total_sac_codes: int
    matched_with_rate: int
    unmatched: int
    has_conditions: int
    cess_applicable: int
    by_schedule: List[ScheduleBreakdown]
    rate_slabs: RateSlabs
    last_updated: str


# ---------------------------------------------------------------------------
# Condition evaluation helpers
# ---------------------------------------------------------------------------

# Regex patterns to extract a rupee threshold from notification condition text.
# Handles formats: "not exceeding Rs. 7500", "exceeding Rs.1000", "above Rs 2500"
_RS_PATTERN = re.compile(
    r"(not\s+exceeding|exceeding|above|below|up\s+to|upto|less\s+than)\s+Rs\.?\s*([\d,]+)",
    re.IGNORECASE,
)


def _parse_price_threshold(c_text: str) -> Optional[Tuple[str, float]]:
    """
    Parse the first rupee threshold found in condition_text.
    Returns (operator, amount) e.g. ("not_exceeding", 7500.0)
    or None if no threshold found.
    """
    m = _RS_PATTERN.search(c_text or "")
    if not m:
        return None
    op_raw = m.group(1).lower().replace(" ", "_")
    amount = float(m.group(2).replace(",", ""))
    # Normalise operator
    if any(k in op_raw for k in ["not_exceeding", "up_to", "upto", "less_than"]):
        op = "not_exceeding"
    elif any(k in op_raw for k in ["exceeding", "above"]):
        op = "exceeding"
    elif "below" in op_raw:
        op = "not_exceeding"  # "below X" is same sense as "not exceeding X"
    else:
        op = "not_exceeding"
    return op, amount


def _evaluate_price_threshold(
    c_text: str,
    sale_value: Optional[float],
) -> Tuple[bool, str, Optional[str]]:
    """
    Returns (passes, applied_note, warning).
    Parses 'not exceeding Rs. X' / 'exceeding Rs. X' from condition_text,
    then checks sale_value_inr against the threshold.
    """
    parsed = _parse_price_threshold(c_text)

    if parsed is None:
        # Can't parse threshold — return with warning
        return (
            True,
            "Price threshold condition (threshold not parseable)",
            f"Could not extract Rs. threshold from: '{c_text[:100]}'. Manual review needed.",
        )

    op, threshold = parsed
    threshold_fmt = f"Rs. {threshold:,.0f}"

    if sale_value is None:
        return (
            True,
            f"Price threshold: {op.replace('_', ' ')} {threshold_fmt} — sale_value_inr not provided",
            f"Provide sale_value_inr to resolve this condition ({op.replace('_', ' ')} {threshold_fmt}).",
        )

    if op == "not_exceeding":
        passes = sale_value <= threshold
        direction = (
            f"{sale_value:,.2f} <= {threshold_fmt}"
            if passes
            else f"{sale_value:,.2f} > {threshold_fmt}"
        )
        applied = f"Price threshold (not exceeding {threshold_fmt}): {'PASSED' if passes else 'FAILED'} — {direction}"
        warning = (
            None
            if passes
            else (
                f"Sale value Rs. {sale_value:,.2f} exceeds threshold {threshold_fmt}. "
                "A different rate entry may apply — check for 'exceeding' counterpart."
            )
        )
    else:  # exceeding
        passes = sale_value > threshold
        direction = (
            f"{sale_value:,.2f} > {threshold_fmt}"
            if passes
            else f"{sale_value:,.2f} <= {threshold_fmt}"
        )
        applied = f"Price threshold (exceeding {threshold_fmt}): {'PASSED' if passes else 'FAILED'} — {direction}"
        warning = (
            None
            if passes
            else (
                f"Sale value Rs. {sale_value:,.2f} does not exceed threshold {threshold_fmt}. "
                "A different rate entry may apply — check for 'not exceeding' counterpart."
            )
        )

    return passes, applied, warning


def _evaluate_end_use(
    c_text: str,
    end_use_param: Optional[str],
) -> Tuple[bool, str, Optional[str]]:
    """
    Match the caller's `end_use` string against keywords in condition_text.
    Strategy: tokenise both strings and check for any word overlap.
    Always passes (we don't exclude results), but warns if no match.
    """
    if not end_use_param:
        return (
            True,
            "End-use condition (end_use not provided)",
            f"Provide end_use parameter to verify this condition: '{c_text[:100]}'.",
        )

    # Normalise both texts
    c_lower = (c_text or "").lower()
    eu_lower = end_use_param.lower()
    eu_tokens = set(re.split(r"[\s,/]+", eu_lower)) - {
        "",
        "for",
        "the",
        "in",
        "of",
        "to",
        "and",
        "or",
    }

    matched_tokens = [tok for tok in eu_tokens if tok in c_lower]

    if matched_tokens:
        return (
            True,
            f"End-use condition MATCHED on: {matched_tokens}. Condition: '{c_text[:80]}'",
            None,
        )
    else:
        return (
            True,
            f"End-use condition — no keyword match found for '{end_use_param}'",
            f"end_use '{end_use_param}' did not match condition keywords. "
            f"End-use condition requires verification: '{c_text[:100]}'.",
        )


# Keyword sets that each supply_type maps to in notification text
_SUPPLY_TYPE_KEYWORDS: dict[str, list[str]] = {
    "export": ["export", "zero rated", "lut", "bond"],
    "sez": ["sez", "special economic zone", "zero rated"],
    "works_contract": ["works contract", "works-contract"],
    "with_installation": ["with installation", "with commissioning", "turnkey"],
    "domestic": [],  # domestic is the default; no special keywords needed
}


def _evaluate_supply_nature(
    c_text: str,
    supply_nature: SupplyNature,
) -> Tuple[bool, str, Optional[str]]:
    """
    Check if the requested supply_nature is consistent with the condition_text.
    - export / sez: rate may be 0% (zero-rated); warn if condition doesn't mention it.
    - works_contract / with_installation: rate may differ; check for mention.
    - domestic: default — passes with informational note if condition mentions a type.
    """
    c_lower = (c_text or "").lower()
    st_val = supply_nature.value
    keywords = _SUPPLY_TYPE_KEYWORDS.get(st_val, [])

    # Special handling: export/SEZ supplies are zero-rated under IGST irrespective
    if st_val in ("export", "sez"):
        return (
            True,
            f"Supply type '{st_val}': exports/SEZ supplies are zero-rated under IGST (LUT/Bond route). "
            f"Notify ref rate shown is for domestic supply.",
            "For export/SEZ, IGST = 0% (zero-rated). Confirm LUT/Bond filing. Rate shown is domestic reference.",
        )

    if keywords and any(kw in c_lower for kw in keywords):
        matched_kw = next(kw for kw in keywords if kw in c_lower)
        return (
            True,
            f"Supply type '{st_val}' MATCHED condition keyword '{matched_kw}'. Condition: '{c_text[:80]}'",
            None,
        )

    if keywords:  # supply_type has keywords but none matched
        return (
            True,
            f"Supply type '{st_val}' — condition does not explicitly mention this supply type",
            f"Supply type '{st_val}' not explicitly referenced in condition '{c_text[:100]}'. Verify applicability.",
        )

    # domestic or no keywords — just pass through
    return (
        True,
        f"Supply type: {st_val} (domestic/standard supply)",
        None,
    )


# ---------------------------------------------------------------------------
# Main condition evaluator — dispatches to per-type handlers
# ---------------------------------------------------------------------------


def _evaluate_condition(
    row: dict,
    req: LookupRequest,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Returns (passes, condition_applied_note, condition_warning).

    - passes:                Always True — we never silently drop results;
                             instead we set needs_review or condition_warning.
    - condition_applied_note: Human-readable explanation of which condition fired.
    - condition_warning:      Non-None when the condition could not be fully resolved
                              and manual verification is needed.
    """
    if not row.get("has_condition"):
        return True, None, None

    c_type = row.get("condition_type", "none")
    c_text = row.get("condition_text") or ""

    # ------------------------------------------------------------------
    if c_type == "branding":
        applied = (
            "branded=True (pre-packaged & labelled)"
            if req.branded
            else "branded=False (unbranded)"
        )
        return (
            True,
            f"Branding condition — {applied}. Notification: '{c_text[:80]}'",
            None,
        )

    # ------------------------------------------------------------------
    elif c_type == "registration":
        applied = (
            "b2b=True (registered buyer)" if req.b2b else "b2b=False (unregistered/B2C)"
        )
        return (
            True,
            f"Registration condition — {applied}. Notification: '{c_text[:80]}'",
            None,
        )

    # ------------------------------------------------------------------
    elif c_type == "price_threshold":
        passes, note, warning = _evaluate_price_threshold(c_text, req.sale_value_inr)
        return passes, note, warning

    # ------------------------------------------------------------------
    elif c_type == "end_use":
        passes, note, warning = _evaluate_end_use(c_text, req.end_use)
        return passes, note, warning

    # ------------------------------------------------------------------
    elif c_type == "supply_type":
        passes, note, warning = _evaluate_supply_nature(
            c_text, req.supply_nature or SupplyNature.domestic
        )
        return passes, note, warning

    # ------------------------------------------------------------------
    elif c_type == "entity_type":
        return (
            True,
            f"Entity-type condition — manual review needed. Notification: '{c_text[:80]}'",
            "entity_type conditions depend on the nature of the supplier/recipient. Verify manually.",
        )

    # ------------------------------------------------------------------
    return (
        True,
        f"Condition applies — manual review needed. Notification: '{c_text[:80]}'",
        "Condition type not automatically resolvable. Refer to notification text.",
    )


def _build_tax_info(
    igst_rate: Optional[float],
    cgst_rate: Optional[float],
    cess_rate: Optional[float],
    supply_type: Optional[str],
) -> Tuple[TaxRates, ApplicableRate]:
    """Helper to convert flat DB rates into nested TaxRates and ApplicableRate."""
    tax = TaxRates(
        igst=igst_rate,
        cgst=cgst_rate,
        sgst=cgst_rate,
        utgst=cgst_rate,
        cess=cess_rate if cess_rate is not None else 0,
        total_intrastate=(cgst_rate * 2) if cgst_rate is not None else None,
        total_interstate=igst_rate,
    )

    intra_str = (
        f"CGST {cgst_rate}% + SGST {cgst_rate}% = {cgst_rate * 2}%"
        if cgst_rate is not None
        else None
    )
    inter_str = f"IGST {igst_rate}%" if igst_rate is not None else None

    rec = None
    if supply_type == "intrastate":
        rec = intra_str
    elif supply_type == "interstate":
        rec = inter_str

    app = ApplicableRate(intrastate=intra_str, interstate=inter_str, recommended=rec)
    return tax, app


def _build_lookup_results(
    rows: list,
    req: LookupRequest,
    base_confidence: float = 0.9,
) -> List[LookupResult]:
    # Sort rows by description length so the most direct/specific matches appear first.
    # e.g. "Cigarettes" matches "CIGARETTES" (10 chars) before "Cigars, cheroots, cigarillos and cigarettes" (43 chars)
    rows.sort(key=lambda x: len(x.get("hsn_description", "")))

    results = []
    for i, row in enumerate(rows):
        passes, condition_note, condition_warning = _evaluate_condition(row, req)

        # Slightly decay confidence for each subsequent FTS result
        confidence = round(base_confidence - (i * 0.05), 2)

        # If a condition warning was raised, always flag needs_review
        needs_review = bool(row.get("needs_review", False)) or (
            condition_warning is not None
        )

        tax_rates, applicable_rate = _build_tax_info(
            row.get("igst_rate"),
            row.get("cgst_rate"),
            row.get("cess_rate"),
            req.supply_type,
        )

        results.append(
            LookupResult(
                hsn_code=row["hsn_code"],
                description=row["hsn_description"],
                tax_rates=tax_rates,
                applicable_rate=applicable_rate,
                condition_applied=condition_note,
                condition_warning=condition_warning,
                confidence=max(confidence, 0.1),
                notification_ref=row.get("notification_ref"),
                needs_review=needs_review,
                gst_rate=row.get("igst_rate"),
                cgst=row.get("cgst_rate"),
                sgst=row.get("cgst_rate"),
                igst=row.get("igst_rate"),
            )
        )

    # Return up to 50 results so all conditions per HSN code are visible
    return results[:50]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


DEMO_JS = r"""
function fmt(obj) {
  var json = JSON.stringify(obj, null, 2);
  json = json.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  return json.replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g, function (match) {
      var cls = 'jn';
      if (/^"/.test(match)) {
          if (/:$/.test(match)) {
              cls = 'jk';
          } else {
              cls = 'js';
          }
      } else if (/true|false|null/.test(match)) {
          cls = 'cw';
      }
      return '<span class="' + cls + '">' + match + '</span>';
  });
}

function setQ(v) {
  document.getElementById('qi').value = v;
  runQ();
}

function runQ() {
  var btn = document.getElementById('qb');
  var out = document.getElementById('qo');
  var val = document.getElementById('qi').value.trim();
  if (!val) return;
  btn.disabled = true;
  btn.textContent = '...';
  out.classList.remove('has-result');
  out.innerHTML = '<span style="color:#3D4E6A">// Fetching from CBIC-sourced data...</span>';

  fetch('/api/demo/lookup?q=' + encodeURIComponent(val), {
    method: 'GET'
  })
  .then(function(res) {
    return res.json().then(function(data) {
      if (res.ok && data && data.length > 0) {
        out.innerHTML = fmt(data[0]);
        out.classList.add('has-result');
      } else if (!res.ok && data && data.detail) {
        out.innerHTML = '<span style="color:#F97583">// Error: ' + data.detail + '</span>';
      } else {
        out.innerHTML = '<span style="color:#3D4E6A">// No match found for "' + val + '".\n// Try: AC unit, gold jewellery, basmati rice, namkeen\n// All 48,752 HSN codes available with an API key.</span>';
      }
      btn.disabled = false;
      btn.textContent = 'Lookup \u2192';
    }).catch(function() {
      // JSON parse error
      out.innerHTML = '<span style="color:#F97583">// Error: Unexpected API response</span>';
      btn.disabled = false;
      btn.textContent = 'Lookup \u2192';
    });
  })
  .catch(function(err) {
    out.innerHTML = '<span style="color:#F97583">// Network error: ' + err.message + '</span>';
    btn.disabled = false;
    btn.textContent = 'Lookup \u2192';
  });
}

function switchTab(el, id) {
  document.querySelectorAll('.tab').forEach(function(t) { t.classList.remove('on'); });
  document.querySelectorAll('.code').forEach(function(c) { c.classList.remove('on'); });
  el.classList.add('on');
  document.getElementById(id).classList.add('on');
}

document.addEventListener('DOMContentLoaded', function() {
  document.getElementById('qi').addEventListener('keydown', function(e) {
    if (e.key === 'Enter') runQ();
  });
});
"""


@app.get("/api/v1/health", tags=["Meta"])
async def get_health():
    return {
        "status": "ok",
        "version": "1.0.0",
        "uptime": time.time() - START_TIME
    }

@app.get("/api/v1/meta", tags=["Meta"])
async def get_meta():
    return {
        "total_hsn": 48752,
        "total_sac": 681,
        "last_updated": "2025-09-22",
        "source": "GST Council Notification 09/2025-CT(Rate)"
    }

from fastapi.responses import RedirectResponse
@app.api_route("/v1/{path:path}", methods=["GET", "POST", "PUT", "DELETE"], include_in_schema=False)
async def redirect_old_v1(path: str, request: Request):
    return RedirectResponse(url=f"/api/v1/{path}", status_code=301)

@app.get("/demo.js", include_in_schema=False)
async def demo_js():
    # pyrefly: ignore [missing-import]
    from fastapi.responses import Response
    return Response(content=DEMO_JS, media_type="application/javascript")

@app.get("/llms.txt", include_in_schema=False)
async def llms_txt():
    from fastapi.responses import Response
    content = """# GST Accelerator API
Fast HSN and SAC lookup API for India. 48,000+ codes, GST rates, JSON REST.
Base URL: https://gstaccelerator.in/api/v1
Endpoints: /lookup /hsn/{code} /sac/{code} /autocomplete /bulk /health /meta /gst-rate
Auth: X-API-Key header (free tier available, no key needed for /lookup with demo key)
OpenAPI: https://gstaccelerator.in/openapi.json
Docs: https://gstaccelerator.in/docs
"""
    return Response(content=content.strip(), media_type="text/plain")

@app.get("/robots.txt", include_in_schema=False)
async def robots_txt():
    from fastapi.responses import Response
    content = """User-agent: *
Allow: /
Disallow: /api/
Sitemap: https://gstaccelerator.in/sitemap.xml
"""
    return Response(content=content.strip(), media_type="text/plain")

@app.get("/", include_in_schema=False, response_class=HTMLResponse)
async def root():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>GST Accelerator API — India’s fastest HSN &amp; SAC lookup API</title>
  <meta name="description" content="Free REST API for Indian GST HSN/SAC code lookup. Search 48,000+ codes, get GST rates, CGST/SGST splits, and legal notification references. JSON, fast, CBIC-sourced." />
  <meta name="keywords" content="gst api, hsn api, india gst api, hsn lookup api, sac api, gstin api, gst rate api, hsn code api, sac code api, indian gst rest api" />
  <meta name="robots" content="index, follow" />
  <meta property="og:type" content="website" />
  <meta property="og:url" content="https://gstaccelerator.in/" />
  <meta property="og:title" content="GST Accelerator API — India’s fastest HSN &amp; SAC lookup API" />
  <meta property="og:description" content="Free REST API for Indian GST HSN/SAC code lookup. 48,000+ codes, GST rates, CGST/SGST/IGST splits. CBIC-sourced and condition-aware." />
  <meta property="og:site_name" content="GST Accelerator" />
    <meta property="og:image" content="https://gstaccelerator.in/banner.png" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="GST Accelerator API — India’s fastest HSN &amp; SAC lookup API" />
  <meta name="twitter:description" content="Free REST API for Indian GST HSN/SAC code lookup. 48,000+ HSN/SAC codes, rates, and CBIC notification audit trail." />
  <link rel="canonical" href="https://gstaccelerator.in/" />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "WebAPI",
        "@id": "https://gstaccelerator.in/#api",
        "name": "GST Accelerator API",
        "description": "India's most accurate GST HSN and SAC code lookup API. Covers 48,752 HSN codes and 681 SAC codes with CGST, SGST, IGST, and Cess rates as per CBIC Notification 09/2025-CT(Rate).",
        "url": "https://gstaccelerator.in/",
        "documentation": "https://gstaccelerator.in/docs",
        "termsOfService": "https://gstaccelerator.in/terms",
        "provider": {
          "@type": "Organization",
          "@id": "https://gstaccelerator.in/#org",
          "name": "GST Accelerator",
          "url": "https://gstaccelerator.in",
          "email": "hello@gstaccelerator.in",
          "logo": {
            "@type": "ImageObject",
            "url": "https://gstaccelerator.in/favicon.ico"
          },
          "address": {
            "@type": "PostalAddress",
            "addressLocality": "Pune",
            "addressRegion": "Maharashtra",
            "addressCountry": "IN"
          }
        }
      },
      {
        "@type": "WebSite",
        "@id": "https://gstaccelerator.in/#website",
        "name": "GST Accelerator",
        "url": "https://gstaccelerator.in",
        "potentialAction": {
          "@type": "SearchAction",
          "target": {
            "@type": "EntryPoint",
            "urlTemplate": "https://gstaccelerator.in/api/v2/lookup?q={search_term_string}"
          },
          "query-input": "required name=search_term_string"
        }
      },
      {
        "@type": "SoftwareApplication",
        "@id": "https://gstaccelerator.in/#app",
        "name": "GST Accelerator API",
        "applicationCategory": "BusinessApplication",
        "operatingSystem": "Any",
        "offers": [
          {
            "@type": "Offer",
            "name": "Free",
            "price": "0",
            "priceCurrency": "INR",
            "description": "100 API calls per month, free forever"
          },
          {
            "@type": "Offer",
            "name": "Developer",
            "price": "399",
            "priceCurrency": "INR",
            "description": "5,000 API calls for 30 days access"
          },
          {
            "@type": "Offer",
            "name": "Pro",
            "price": "1499",
            "priceCurrency": "INR",
            "description": "50,000 API calls for 30 days access"
          },
          {
            "@type": "Offer",
            "name": "Business",
            "price": "5999",
            "priceCurrency": "INR",
            "description": "Unlimited API calls for 30 days access"
          }
        ]
      }
    ]
  }
  </script>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    :root {
      /* Backgrounds — layered depth */
      --ink:       #06090F;
      --ink-2:     #0D1220;
      --ink-3:     #141B2D;
      --ink-4:     #1C2A3E;

      /* Amber — brand / action / CTA */
      --amber:     #E8650A;
      --amber-dim: rgba(232,101,10,0.10);
      --amber-mid: rgba(232,101,10,0.25);

      /* Navy / Blue — data / technical / informational */
      --navy:      #1A5FA8;
      --navy-dim:  rgba(26,95,168,0.12);
      --navy-mid:  rgba(26,95,168,0.28);
      --navy-lit:  #4A8FD4;

      /* Green — positive / verified / success */
      --green:     #1A9E72;
      --green-dim: rgba(26,158,114,0.10);
      --green-mid: rgba(26,158,114,0.25);
      --green-lit: #2DC994;

      /* Neutrals */
      --white:     #F2F4F8;
      --muted:     #6B7A99;
      --border:    rgba(107,122,153,0.14);
      --border-md: rgba(107,122,153,0.28);

      --font-serif: 'DM Serif Display', Georgia, serif;
      --font-body:  'Inter', sans-serif;
      --font-mono:  'JetBrains Mono', monospace;
    }

    html { scroll-behavior: smooth; }

    body {
      background: var(--ink);
      color: var(--white);
      font-family: var(--font-body);
      font-size: 16px;
      line-height: 1.65;
      -webkit-font-smoothing: antialiased;
    }

    /* ── NAV ── */
    nav {
      position: fixed; top: 0; left: 0; right: 0; z-index: 100;
      display: flex; align-items: center; justify-content: space-between;
      padding: 0.875rem 2rem;
      background: rgba(6,9,15,0.88);
      backdrop-filter: blur(14px);
      border-bottom: 1px solid var(--border);
    }
    .nav-logo {
      font-family: var(--font-body);
      font-weight: 600; font-size: 1rem;
      color: var(--white); text-decoration: none;
      display: flex; align-items: center; gap: 10px;
      letter-spacing: -0.01em;
    }
    .nav-rupee {
      width: 30px; height: 30px;
      background: var(--amber);
      border-radius: 7px;
      display: flex; align-items: center; justify-content: center;
      font-size: 15px; font-weight: 700; color: #fff;
      font-family: var(--font-mono);
      flex-shrink: 0;
      letter-spacing: 0;
    }
    .nav-name { color: var(--white); }
    .nav-name span { color: var(--amber); }
    .nav-links { display: flex; align-items: center; gap: 1.75rem; }
    .nav-links a {
      color: var(--muted); text-decoration: none;
      font-size: 0.875rem; font-weight: 500;
      transition: color 0.15s;
    }
    .nav-links a:hover { color: var(--white); }
    .nav-cta {
      background: var(--amber) !important;
      color: #fff !important;
      padding: 0.45rem 1.1rem; border-radius: 7px;
      font-weight: 600 !important;
      transition: opacity 0.15s !important;
    }
    .nav-cta:hover { opacity: 0.85 !important; }

    /* ── HERO ── */
    .hero {
      min-height: 100vh;
      display: flex; flex-direction: column;
      align-items: center; justify-content: center;
      padding: 8rem 1.5rem 5rem;
      text-align: center;
    }
    .hero-eyebrow {
      display: inline-flex; align-items: center; gap: 7px;
      background: var(--amber-dim);
      border: 1px solid var(--amber-mid);
      color: var(--amber);
      font-size: 0.72rem; font-weight: 600;
      letter-spacing: 0.09em; text-transform: uppercase;
      padding: 0.3rem 0.85rem; border-radius: 100px;
      margin-bottom: 2rem;
    }
    .hero-eyebrow-dot {
      width: 5px; height: 5px;
      background: var(--amber); border-radius: 50%;
      animation: pulse 2.4s infinite;
      flex-shrink: 0;
    }
    @keyframes pulse {
      0%, 100% { opacity: 1; transform: scale(1); }
      50% { opacity: 0.35; transform: scale(0.7); }
    }
    h1 {
      font-family: var(--font-serif);
      font-size: clamp(3rem, 6.5vw, 5.5rem);
      font-weight: 400;
      line-height: 1.08;
      letter-spacing: -0.01em;
      max-width: 780px;
      margin-bottom: 0.6rem;
      color: var(--white);
    }
    h1 em {
      font-style: italic;
      background: linear-gradient(100deg, var(--amber) 0%, #F9A53A 100%);
      -webkit-background-clip: text; -webkit-text-fill-color: transparent;
      background-clip: text;
    }
    .hero-mantra {
      font-family: var(--font-body);
      font-size: 1rem; font-weight: 500;
      color: var(--muted);
      letter-spacing: 0.04em;
      margin-bottom: 2.75rem;
    }
    .hero-mantra strong { color: var(--white); font-weight: 600; }

    /* ── DEMO CARD ── */
    .demo-card {
      width: 100%; max-width: 600px;
      background: var(--ink-2);
      border: 1px solid var(--navy-mid);
      border-radius: 14px;
      overflow: hidden;
      box-shadow: 0 0 0 1px rgba(26,95,168,0.08), 0 32px 80px rgba(0,0,0,0.5);
    }
    .demo-topbar {
      display: flex; align-items: center; gap: 6px;
      padding: 9px 14px;
      background: var(--ink-4);
      border-bottom: 1px solid var(--navy-mid);
    }
    .dot { width: 9px; height: 9px; border-radius: 50%; }
    .dot-r { background: #FF5F57; }
    .dot-y { background: #FFBD2E; }
    .dot-g { background: #28CA41; }
    .demo-url {
      margin-left: 8px;
      font-family: var(--font-mono);
      font-size: 0.7rem; color: var(--muted);
    }
    .demo-body { padding: 1.25rem 1.5rem; }
    .demo-qs {
      display: flex; gap: 6px;
      margin-bottom: 10px;
      overflow-x: auto;
      -webkit-overflow-scrolling: touch;
      scrollbar-width: none;
      padding-bottom: 2px;
    }
    .demo-qs::-webkit-scrollbar { display: none; }
    .q-btn {
      background: var(--ink-3);
      border: 1px solid var(--border);
      color: var(--muted);
      font-family: var(--font-mono); font-size: 0.7rem;
      padding: 3px 10px; border-radius: 100px;
      cursor: pointer; transition: all 0.15s;
      white-space: nowrap; flex-shrink: 0;
    }
    .q-btn:hover { border-color: var(--amber); color: var(--white); }
    .demo-row { display: flex; gap: 8px; margin-bottom: 10px; }
    .demo-input {
      flex: 1;
      background: var(--ink);
      border: 1px solid var(--border);
      border-radius: 7px;
      padding: 0.6rem 1rem;
      color: var(--white);
      font-family: var(--font-mono); font-size: 0.85rem;
      outline: none; transition: border-color 0.15s;
    }
    .demo-input:focus { border-color: var(--amber); }
    .demo-input::placeholder { color: var(--muted); }
    .demo-go {
      background: var(--amber); color: #fff;
      border: none; cursor: pointer;
      padding: 0.6rem 1.25rem; border-radius: 7px;
      font-family: var(--font-body); font-size: 0.875rem; font-weight: 600;
      transition: opacity 0.15s; white-space: nowrap;
    }
    .demo-go:hover { opacity: 0.85; }
    .demo-go:disabled { opacity: 0.45; cursor: not-allowed; }
    .demo-out {
      background: var(--ink);
      border: 1px solid var(--border);
      border-radius: 8px; padding: 1rem;
      font-family: var(--font-mono); font-size: 0.775rem;
      line-height: 1.8; min-height: 130px;
      color: var(--muted); white-space: pre-wrap;
      text-align: left; overflow-x: auto;
      transition: border-color 0.25s;
    }
    .demo-out.has-result {
      color: var(--white);
      border-color: var(--green-mid);
    }
    .jk { color: var(--navy-lit); }
    .js { color: var(--green-lit); }
    .jn { color: #F97583; }

    /* ── STATS ── */
    .stats {
      display: flex; gap: 0;
      width: 100%; max-width: 600px;
      margin-top: 2.5rem;
      border: 1px solid var(--navy-mid);
      border-radius: 12px; overflow: hidden;
    }
    .stat {
      flex: 1; padding: 1.1rem 0.5rem; text-align: center;
      border-right: 1px solid var(--navy-mid);
      background: var(--navy-dim);
    }
    .stat:last-child { border-right: none; }
    .stat-n {
      font-family: var(--font-mono);
      font-size: 1.35rem; font-weight: 500;
      color: var(--navy-lit); display: block;
      margin-bottom: 2px;
    }
    .stat-l { font-size: 0.68rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.06em; }

    /* ── SECTIONS ── */
    .section { padding: 5.5rem 1.5rem; max-width: 1020px; margin: 0 auto; }
    .section-label {
      font-size: 0.7rem; font-weight: 600; letter-spacing: 0.12em;
      text-transform: uppercase; color: var(--amber);
      margin-bottom: 0.75rem;
    }
    .section-label.blue  { color: var(--navy-lit); }
    .section-label.green { color: var(--green-lit); }
    h2 {
      font-family: var(--font-serif);
      font-size: clamp(1.8rem, 3.5vw, 2.8rem);
      font-weight: 400; line-height: 1.15;
      letter-spacing: -0.01em; margin-bottom: 0.9rem;
    }
    .section-sub { color: var(--muted); max-width: 460px; font-size: 0.95rem; margin-bottom: 3rem; line-height: 1.7; }

    /* ── FEATURES ── */
    .feat-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 1px;
      background: var(--border);
      border: 1px solid var(--border);
      border-radius: 14px; overflow: hidden;
    }
    .feat {
      background: var(--ink-2);
      padding: 1.75rem 1.6rem;
      border-left: 2px solid transparent;
      transition: border-color 0.2s, background 0.2s;
    }
    .feat:hover { background: var(--ink-3); border-left-color: var(--navy-lit); }
    .feat:nth-child(odd):hover { border-left-color: var(--amber); }
    .feat.wide { grid-column: span 2; }
    .feat-ref {
      font-family: var(--font-mono);
      font-size: 0.65rem; color: var(--muted);
      margin-bottom: 1rem;
      letter-spacing: 0.04em;
    }
    .feat-ref span { color: var(--navy-lit); }
    .feat h3 {
      font-family: var(--font-body);
      font-size: 0.95rem; font-weight: 600;
      color: var(--white); margin-bottom: 0.5rem;
    }
    .feat p { font-size: 0.85rem; color: var(--muted); line-height: 1.65; }
    .feat-chip {
      display: inline-flex; align-items: center; gap: 5px;
      margin-top: 10px;
      background: var(--green-dim); border: 1px solid var(--green-mid);
      color: var(--green-lit); font-size: 0.7rem; font-weight: 600;
      padding: 2px 9px; border-radius: 100px;
    }
    .feat-chip.blue {
      background: var(--navy-dim); border-color: var(--navy-mid);
      color: var(--navy-lit);
    }

    /* ── PRICING ── */
    .price-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(215px, 1fr));
      gap: 12px;
    }
    .plan {
      background: var(--ink-2);
      border: 1px solid var(--border);
      border-radius: 12px; padding: 1.5rem;
      position: relative;
    }
    .plan.featured {
      border-color: var(--amber);
      background: linear-gradient(160deg, rgba(232,101,10,0.06), var(--ink-2));
    }
    .plan-badge {
      position: absolute; top: -10px; left: 50%; transform: translateX(-50%);
      background: var(--amber); color: #fff;
      font-size: 0.65rem; font-weight: 700;
      letter-spacing: 0.07em; text-transform: uppercase;
      padding: 2px 12px; border-radius: 100px; white-space: nowrap;
    }
    .plan-tier {
      font-size: 0.7rem; font-weight: 600; text-transform: uppercase;
      letter-spacing: 0.1em; color: var(--muted); margin-bottom: 0.5rem;
    }
    .plan-price {
      font-family: var(--font-serif);
      font-size: 2.4rem; font-weight: 400;
      color: var(--white); line-height: 1;
      margin-bottom: 2px;
    }
    .plan-price sup { font-family: var(--font-body); font-size: 1rem; vertical-align: super; }
    .plan-mo { font-size: 0.78rem; color: var(--muted); margin-bottom: 0.5rem; }
    .plan-quota {
      font-family: var(--font-mono); font-size: 0.72rem;
      color: var(--green-lit); margin-bottom: 1.25rem;
      padding-bottom: 1rem; border-bottom: 1px solid var(--border);
    }
    .plan.featured .plan-quota { color: var(--green-lit); }
    .pf { font-size: 0.82rem; color: var(--muted); padding: 3px 0; display: flex; gap: 8px; }
    .pf::before { content: "✓"; color: var(--green-lit); flex-shrink: 0; }
    .pf.off { opacity: 0.38; }
    .pf.off::before { content: "·"; color: var(--muted); }
    .plan-action {
      display: block; width: 100%; margin-top: 1.25rem;
      padding: 0.6rem; border-radius: 7px; text-align: center;
      font-family: var(--font-body); font-size: 0.875rem; font-weight: 600;
      text-decoration: none; cursor: pointer; border: none;
      transition: all 0.2s;
    }
    .pa-outline { background: transparent; border: 1px solid var(--border-md); color: var(--white); }
    .pa-solid { background: var(--amber); border: 1px solid var(--amber); color: #fff; }
    .pa-outline:hover { background: var(--amber); border-color: var(--amber); color: #fff; }
    .pa-solid:hover { opacity: 0.8; }
    .upi-note {
      font-size: 0.68rem; color: var(--muted);
      text-align: center; margin-top: 8px;
    }

    /* ── CODE ── */
    .tabs { display: flex; gap: 3px; margin-bottom: -1px; }
    .tab {
      font-family: var(--font-mono); font-size: 0.76rem;
      padding: 6px 14px; border-radius: 6px 6px 0 0;
      border: 1px solid var(--border); border-bottom: none;
      color: var(--muted); cursor: pointer; background: var(--ink-2);
      transition: all 0.12s;
    }
    .tab.on { color: var(--white); background: var(--ink-4); border-color: var(--navy); }
    .code {
      background: var(--ink-4); border: 1px solid var(--navy-mid);
      border-radius: 0 10px 10px 10px; padding: 1.5rem;
      font-family: var(--font-mono); font-size: 0.79rem;
      line-height: 1.8; overflow-x: auto; display: none;
      white-space: pre;
    }
    .code.on { display: block; }
    .cc { color: #4A5E82; }
    .ck { color: var(--navy-lit); }
    .cs { color: var(--green-lit); }
    .cn { color: #F97583; }
    .cw { color: #B39DDB; }

    /* ── DIVIDER ── */
    hr { border: none; border-top: 1px solid var(--border); }

    /* ── FOOTER ── */
    footer {
      border-top: 1px solid var(--border);
      padding: 2.5rem 1.5rem; text-align: center;
    }
    .footer-mark {
      display: inline-flex; align-items: center; gap: 8px;
      font-weight: 600; font-size: 0.95rem; margin-bottom: 0.4rem;
    }
    .footer-mark .r {
      width: 24px; height: 24px; background: var(--amber);
      border-radius: 5px; display: flex; align-items: center;
      justify-content: center; font-family: var(--font-mono);
      font-size: 12px; color: #fff;
    }
    .footer-tagline {
      font-size: 0.72rem; color: var(--amber);
      letter-spacing: 0.1em; text-transform: uppercase;
      margin-bottom: 1.5rem;
    }
    .footer-nav {
      display: flex; justify-content: center; gap: 1.5rem;
      flex-wrap: wrap; margin-bottom: 1.5rem;
    }
    .footer-nav a { color: var(--muted); text-decoration: none; font-size: 0.82rem; transition: color 0.15s; }
    .footer-nav a:hover { color: var(--white); }
    .footer-legal { font-size: 0.72rem; color: var(--muted); line-height: 1.7; }

    /* ── RESPONSIVE ── */
    @media (max-width: 900px) {
      .feat-grid { grid-template-columns: repeat(2, 1fr); }
      .feat.wide { grid-column: span 1; }
    }
    @media (max-width: 640px) {
      nav { padding: 0.75rem 1rem; }
      .nav-links a:not(.nav-cta) { display: none; }
      h1 { font-size: clamp(2.4rem, 8vw, 3.2rem); }
      .stats { flex-direction: row; }
      .feat-grid { grid-template-columns: 1fr; }
      .section { padding: 3.5rem 1rem; }
    }
  </style>

  <!-- Schema.org JSON-LD structured data -->
  <script type="application/ld+json">
  [
    {
      "@context": "https://schema.org",
      "@type": "SoftwareApplication",
      "name": "GST Accelerator API",
      "description": "India's fastest HSN and SAC code lookup API. 48,000+ HSN codes, SAC search, GST rates, JSON REST API.",
      "applicationCategory": "DeveloperTool",
      "operatingSystem": "Any",
      "url": "https://gstaccelerator.in",
      "offers": {
        "@type": "Offer",
        "price": "0",
        "priceCurrency": "INR",
        "name": "Free Tier",
        "description": "100 API calls per month, no credit card required"
      },
      "provider": {
        "@type": "Organization",
        "name": "GST Accelerator",
        "url": "https://gstaccelerator.in"
      }
    },
    {
      "@context": "https://schema.org",
      "@type": "APIReference",
      "name": "GST Accelerator REST API",
      "description": "JSON REST API for Indian GST HSN and SAC code lookup. Returns CGST, SGST, IGST rates with CBIC notification references.",
      "url": "https://gstaccelerator.in/docs",
      "documentation": "https://gstaccelerator.in/docs",
      "termsOfService": "https://gstaccelerator.in",
      "provider": {
        "@type": "Organization",
        "name": "GST Accelerator"
      }
    }
  ]
  </script>
</head>
<body>

<!-- NAV -->
<nav>
  <a class="nav-logo" href="#">
    <div class="nav-rupee">₹</div>
    <span class="nav-name">GST <span>Accelerator</span></span>
  </a>
  <div class="nav-links">
    <a href="#features">Features</a>
    <a href="#pricing">Pricing</a>
    <a href="/blog">Blog</a>
    <a href="/docs">Docs</a>
    <a class="nav-cta" href="/login">Get API Key</a>
  </div>
</nav>

<!-- HERO -->
<section class="hero">
  <div class="hero-eyebrow">
    <span class="hero-eyebrow-dot"></span>
    GST 2.0 · 09/2025-CT(Rate) · Updated Sept 2025
  </div>

  <h1>GST at the speed of <em>business</em></h1>

  <p class="hero-mantra">
    <strong>Compliance. Accelerated.</strong> &nbsp;·&nbsp;
    CBIC-sourced · Condition-aware · Agent-native
  </p>

  <!-- LIVE DEMO -->
  <div class="demo-card">
    <div class="demo-topbar">
      <div class="dot dot-r"></div><div class="dot dot-y"></div><div class="dot dot-g"></div>
      <span class="demo-url">POST gstaccelerator.in/v1/lookup</span>
    </div>
    <div class="demo-body">
      <div class="demo-qs">
        <button class="q-btn" onclick="setQ('AC unit')">AC unit</button>
        <button class="q-btn" onclick="setQ('gold jewellery')">Gold jewellery</button>
        <button class="q-btn" onclick="setQ('basmati rice')">Basmati rice</button>
        <button class="q-btn" onclick="setQ('mobile phone')">Mobile phone</button>
        <button class="q-btn" onclick="setQ('cigarettes')">Cigarettes</button>
        <button class="q-btn" onclick="setQ('namkeen')">Namkeen</button>
      </div>
      <div class="demo-row">
        <input class="demo-input" id="qi" type="text" placeholder="Type any product, HSN code, or description..." value="AC unit" />
        <button class="demo-go" id="qb" onclick="runQ()">Lookup →</button>
      </div>
      <div class="demo-out" id="qo"><span style="color:#3D4E6A">// Select a product above or type your own</span></div>
    </div>
  </div>

  <!-- STATS -->
  <div class="stats">
    <div class="stat">
      <span class="stat-n">48,752</span>
      <span class="stat-l">HSN codes</span>
    </div>
    <div class="stat">
      <span class="stat-n">681</span>
      <span class="stat-l">SAC codes</span>
    </div>
    <div class="stat">
      <span class="stat-n">7</span>
      <span class="stat-l">GST schedules</span>
    </div>
    <div class="stat">
      <span class="stat-n">&lt;200ms</span>
      <span class="stat-l">P99 latency</span>
    </div>
  </div>
</section>

<hr />

<!-- FEATURES -->
<section class="section" id="features">
  <div class="section-label blue">Why GST Accelerator</div>
  <h2>Not just a lookup.<br>A compliance engine.</h2>
  <p class="section-sub">Every competitor returns a flat rate. We return the rate that actually applies to your specific transaction — with the notification clause to prove it.</p>

  <div class="feat-grid">

    <div class="feat wide">
      <div class="feat-ref">NOTIFICATION <span>09/2025-CT(Rate)</span></div>
      <h3>Condition resolver</h3>
      <p>Branded vs unbranded. B2B vs B2C. Price thresholds. Supply type. Works contract vs outright sale. We parse the notification conditions from the CBIC source and evaluate them against your transaction — so you don't have to read 200-page PDFs before every invoice.</p>
      <div class="feat-chip">✓ What FastGST can't do</div>
    </div>

    <div class="feat">
      <div class="feat-ref">FORMULA <span>IGST = CGST + SGST</span></div>
      <h3>All three components</h3>
      <p>Inter-state? Intra-state? UT supply? Pass your supply type, get the right split. No manual tax maths.</p>
    </div>

    <div class="feat">
      <div class="feat-ref">STANDARD <span>MCP 2025-03-26</span></div>
      <h3>Agent-native MCP endpoint</h3>
      <p>Claude, GPT-4o, and every major agent framework call our MCP endpoint natively. Your AI invoice workflow gets verified GST rates as a tool call.</p>
      <div class="feat-chip blue">↗ Agent economy ready</div>
    </div>

    <div class="feat">
      <div class="feat-ref">COVERAGE <span>11/2025-CT(Rate)</span></div>
      <h3>SAC for services</h3>
      <p>681 SAC codes. Construction services at 9% (post amendment). IT consulting. Finance. The endpoints competitors skipped.</p>
    </div>

    <div class="feat">
      <div class="feat-ref">EVENT <span>GST Council Notification</span></div>
      <h3>Rate-change webhooks</h3>
      <p>Your application gets a push the moment the CBIC notification goes live. Never serve stale rates after a council meeting.</p>
    </div>

    <div class="feat">
      <div class="feat-ref">AUDIT <span>Notification + Effective Date</span></div>
      <h3>Audit trail built-in</h3>
      <p>Every response carries the exact CBIC notification reference and effective date. Your CA can trace every rate your system ever used.</p>
    </div>

  </div>
</section>

<hr />

<!-- PRICING -->
<section class="section" id="pricing" style="text-align:center;">
  <h2>Start free. Scale as you grow.</h2>
  <p class="section-sub" style="margin:0 auto 3rem;">No contracts. Cancel any time. GST invoice included on all paid plans.</p>

  <div class="price-grid">
    <div class="plan">
      <div class="plan-tier">Free</div>
      <div class="plan-price">₹0</div>
      <div class="plan-mo">forever</div>
      <div class="plan-quota">100 calls / month</div>
      <div class="pf">HSN + SAC lookup</div>
      <div class="pf">CGST / SGST / IGST output</div>
      <div class="pf">JSON + Swagger docs</div>
      <div class="pf off">Condition resolver</div>
      <div class="pf off">MCP endpoint</div>
      <div class="pf off">Rate-change alerts</div>
      <a class="plan-action pa-outline" href="/login">Get free key</a>
    </div>

    <div class="plan featured">
      <div class="plan-badge">Recommended for integration</div>
      <div class="plan-tier">Developer</div>
      <div class="plan-price"><sup>₹</sup>399</div>
      <div class="plan-mo">/ month</div>
      <div class="plan-quota">5,000 calls + ₹0.10/extra</div>
      <div class="pf">Everything in Free</div>
      <div class="pf">Condition resolver</div>
      <div class="pf">MCP endpoint</div>
      <div class="pf">99.5% uptime SLA</div>
      <div class="pf">Rate-change email alerts</div>
      <div class="pf off">Webhooks</div>
      <a class="plan-action pa-solid" href="/pricing">Get started</a>
      <div class="upi-note">Pay via UPI · Cards · Net Banking</div>
    </div>

    <div class="plan">
      <div class="plan-tier">Pro</div>
      <div class="plan-price"><sup>₹</sup>1,499</div>
      <div class="plan-mo">/ month</div>
      <div class="plan-quota">50,000 calls + ₹0.08/extra</div>
      <div class="pf">Everything in Developer</div>
      <div class="pf">Bulk CSV classification</div>
      <div class="pf">Rate-change webhooks</div>
      <div class="pf">99.9% uptime SLA</div>
      <div class="pf">Priority support</div>
      <div class="pf">Superseded rates feed</div>
      <a class="plan-action pa-outline" href="/pricing">Get started</a>
    </div>

    <div class="plan">
      <div class="plan-tier">Business</div>
      <div class="plan-price"><sup>₹</sup>5,999</div>
      <div class="plan-mo">/ month</div>
      <div class="plan-quota">Unlimited calls</div>
      <div class="pf">Everything in Pro</div>
      <div class="pf">White-label option</div>
      <div class="pf">Custom HSN taxonomy</div>
      <div class="pf">Dedicated SLA</div>
      <div class="pf">WhatsApp support</div>
      <div class="pf">GST invoice included</div>
      <a class="plan-action pa-outline" href="/pricing">Get started</a>
    </div>
  </div>
</section>

<hr />

<!-- CODE -->
<section class="section" id="code">
  <div class="section-label green">Integration</div>
  <h2>Live in under 5 minutes.</h2>
  <p class="section-sub">One endpoint. Predictable JSON. Works with any language, framework, or AI agent.</p>

  <div class="tabs">
    <button class="tab on" onclick="switchTab(this,'tc')">cURL</button>
    <button class="tab" onclick="switchTab(this,'tp')">Python</button>
    <button class="tab" onclick="switchTab(this,'tj')">JavaScript</button>
    <button class="tab" onclick="switchTab(this,'tm')">MCP Agent</button>
  </div>

  <div class="code on" id="tc"><span class="cc"># Lookup by product description — intrastate supply</span>
curl -X POST https://gstaccelerator.in/v1/lookup \
  -H <span class="cs">"X-API-Key: gsta_your_key"</span> \
  -H <span class="cs">"Content-Type: application/json"</span> \
  -d <span class="cs">'{
    "description": "split AC unit",
    "supply_type": "intrastate",
    "branded": true
  }'</span>

<span class="cc"># Response</span>
{
  <span class="ck">"hsn_code"</span>: <span class="cs">"84151010"</span>,
  <span class="ck">"description"</span>: <span class="cs">"Air conditioning machines, split system"</span>,
  <span class="ck">"tax_rates"</span>: {
    <span class="ck">"igst"</span>: <span class="cn">18.0</span>,
    <span class="ck">"cgst"</span>: <span class="cn">9.0</span>,
    <span class="ck">"sgst"</span>: <span class="cn">9.0</span>,
    <span class="ck">"cess"</span>: <span class="cn">0.0</span>,
    <span class="ck">"total_intrastate"</span>: <span class="cn">18.0</span>
  },
  <span class="ck">"applicable_rate"</span>: <span class="cs">"CGST 9% + SGST 9% = 18%"</span>,
  <span class="ck">"notification_ref"</span>: <span class="cs">"09/2025-CT(Rate), Schedule II"</span>,
  <span class="ck">"effective_date"</span>: <span class="cs">"2025-09-22"</span>
}</div>

  <div class="code" id="tp"><span class="cw">import</span> requests

session = requests.Session()
session.headers[<span class="cs">"X-API-Key"</span>] = <span class="cs">"gsta_your_key"</span>
BASE = <span class="cs">"https://gstaccelerator.in/v1"</span>

<span class="cc"># Lookup by description</span>
r = session.post(f<span class="cs">"{BASE}/lookup"</span>, json={
    <span class="cs">"description"</span>: <span class="cs">"gold jewellery"</span>,
    <span class="cs">"supply_type"</span>: <span class="cs">"interstate"</span>
})
data = r.json()
<span class="cw">print</span>(data[<span class="cs">"tax_rates"</span>][<span class="cs">"igst"</span>])      <span class="cc"># → 3.0</span>
<span class="cw">print</span>(data[<span class="cs">"notification_ref"</span>])         <span class="cc"># → "09/2025-CT(Rate), Schedule IV"</span>

<span class="cc"># Direct HSN code lookup</span>
rate = session.get(f<span class="cs">"{BASE}/hsn/71081200"</span>).json()
<span class="cw">print</span>(rate[<span class="cs">"applicable_rate"</span>][<span class="cs">"interstate"</span>]) <span class="cc"># → "IGST 3%"</span>

<span class="cc"># Bulk — up to 100 items per call</span>
bulk = session.post(f<span class="cs">"{BASE}/bulk"</span>, json={<span class="cs">"items"</span>: [
    {<span class="cs">"description"</span>: <span class="cs">"cotton shirt"</span>,   <span class="cs">"branded"</span>: <span class="cw">True</span>},
    {<span class="cs">"description"</span>: <span class="cs">"laptop"</span>,          <span class="cs">"supply_type"</span>: <span class="cs">"intrastate"</span>},
    {<span class="cs">"description"</span>: <span class="cs">"construction work"</span>, <span class="cs">"sac"</span>: <span class="cw">True</span>},
]})</div>

  <div class="code" id="tj"><span class="cw">const</span> BASE = <span class="cs">"https://gstaccelerator.in/v1"</span>;
<span class="cw">const</span> headers = {
  <span class="cs">"X-API-Key"</span>: <span class="cs">"gsta_your_key"</span>,
  <span class="cs">"Content-Type"</span>: <span class="cs">"application/json"</span>
};

<span class="cc">// Lookup — intrastate mobile phone</span>
<span class="cw">const</span> res = <span class="cw">await</span> fetch(`${BASE}/lookup`, {
  method: <span class="cs">"POST"</span>, headers,
  body: JSON.stringify({
    description: <span class="cs">"mobile phone"</span>,
    supply_type: <span class="cs">"intrastate"</span>,
    branded: <span class="cw">true</span>
  })
});
<span class="cw">const</span> { tax_rates, applicable_rate } = <span class="cw">await</span> res.json();

<span class="cc">// Auto-calculate invoice tax</span>
<span class="cw">const</span> value = <span class="cn">25000</span>;
<span class="cw">const</span> cgst  = (value * tax_rates.cgst) / <span class="cn">100</span>;  <span class="cc">// ₹2,250</span>
<span class="cw">const</span> sgst  = (value * tax_rates.sgst) / <span class="cn">100</span>;  <span class="cc">// ₹2,250</span>

console.log(applicable_rate);  <span class="cc">// "CGST 9% + SGST 9% = 18%"</span></div>

  <div class="code" id="tm"><span class="cc"># claude_desktop_config.json — or any MCP-compatible agent</span>
{
  <span class="ck">"mcpServers"</span>: {
    <span class="ck">"gst-accelerator"</span>: {
      <span class="ck">"type"</span>: <span class="cs">"url"</span>,
      <span class="ck">"url"</span>: <span class="cs">"https://gstaccelerator.in/mcp"</span>,
      <span class="ck">"headers"</span>: {
        <span class="ck">"X-API-Key"</span>: <span class="cs">"gsta_your_key"</span>
      }
    }
  }
}

<span class="cc"># Tools your agent gets natively:</span>
<span class="cc">#   lookup_hsn_rate(description, supply_type?, branded?, sale_value_inr?)</span>
<span class="cc">#   get_rate_by_hsn(hsn_code, supply_type?)</span>
<span class="cc">#   get_sac_rate(sac_code, supply_type?)</span>
<span class="cc">#   bulk_classify(items[])</span>

<span class="cc"># Example system prompt addition:</span>
<span class="cs">"Before generating any invoice line item, call lookup_hsn_rate
 to retrieve the verified CGST/SGST/IGST rates. Never hardcode
 tax percentages. Use the notification_ref field for audit logs."</span></div>

</section>

<hr />

<footer>
  <div class="footer-mark">
    <div class="r">₹</div>
    GST Accelerator
  </div>
  <div class="footer-tagline">Compliance. Accelerated.</div>
  <div class="footer-nav">
    <a href="/docs">API Docs</a>
    <a href="mailto:hello@gstaccelerator.in">hello@gstaccelerator.in</a>
    <a href="#pricing">Pricing</a>
    <a href="/blog">Blog</a>
    <a href="/terms">Terms</a>
    <a href="/privacy">Privacy</a>
  </div>
  <p class="footer-legal">
    Data source: CBIC Notification 09/2025-CT(Rate) &amp; 10/2025-CT(Rate), effective 22 September 2025.<br />
    GST Accelerator is not a tax advisor. Rates are for informational purposes — verify with a CA for filing decisions.<br />
    &copy; 2026 GST Accelerator · gstaccelerator.in
  </p>
</footer>

<script src="/demo.js"></script>
</body>
</html>

"""


def _map_db_to_hsn_rate(row: dict, supply_type: Optional[str]) -> HsnRate:
    tax_rates, applicable_rate = _build_tax_info(
        row.get("igst_rate"), row.get("cgst_rate"), row.get("cess_rate"), supply_type
    )
    return HsnRate(
        id=row.get("id"),
        hsn_code=row["hsn_code"],
        hsn_description=row["hsn_description"],
        schedule=row.get("schedule"),
        condition_text=row.get("condition_text"),
        condition_type=row.get("condition_type", "none"),
        has_condition=row.get("has_condition", False),
        notification_ref=row.get("notification_ref"),
        effective_date=row.get("effective_date"),
        needs_review=row.get("needs_review", False),
        tax_rates=tax_rates,
        applicable_rate=applicable_rate,
        description=row["hsn_description"],
        gst_rate=row.get("igst_rate"),
        cgst=row.get("cgst_rate"),
        sgst=row.get("cgst_rate"),
        igst=row.get("igst_rate"),
    )


def _map_db_to_sac_rate(row: dict, supply_type: Optional[str]) -> SacRate:
    tax_rates, applicable_rate = _build_tax_info(
        row.get("igst_rate"), row.get("cgst_rate"), row.get("cess_rate"), supply_type
    )
    return SacRate(
        id=row.get("id"),
        sac_code=row["sac_code"],
        sac_description=row["sac_description"],
        condition_text=row.get("condition_text"),
        condition_type=row.get("condition_type", "none"),
        has_condition=row.get("has_condition", False),
        notification_ref=row.get("notification_ref"),
        effective_date=row.get("effective_date"),
        needs_review=row.get("needs_review", False),
        tax_rates=tax_rates,
        applicable_rate=applicable_rate,
        description=row["sac_description"],
        hsn_code=row["sac_code"],
        gst_rate=row.get("igst_rate"),
        cgst=row.get("cgst_rate"),
        sgst=row.get("cgst_rate"),
        igst=row.get("igst_rate"),
    )


@app.get(
    "/api/v1/hsn/{code}",
    response_model=List[HsnRate],
    summary="Lookup HSN rate by code",
    tags=["HSN"],
)
async def get_hsn(
    code: str,
    supply_type: Optional[Literal["intrastate", "interstate"]] = None,
    _: dict = Depends(verify_api_key),
):
    """
    Returns full rate object for a given HSN code.
    Pass `supply_type` to resolve the `applicable_rate.recommended` string for intrastate vs interstate routing.
    Falls back from 8-digit → 6-digit heading → 4-digit chapter if no exact match.
    """
    code = code.strip()

    # Exact match
    res = supabase.table("hsn_rates").select("*").eq("hsn_code", code).execute()
    if res.data:
        return [_map_db_to_hsn_rate(row, supply_type) for row in res.data]

    # Fallback: heading (first 6 digits)
    if len(code) >= 6:
        heading = code[:6]
        res = (
            supabase.table("hsn_rates")
            .select("*")
            .like("hsn_code", f"{heading}%")
            .execute()
        )
        if res.data:
            return [_map_db_to_hsn_rate(row, supply_type) for row in res.data]

    # Fallback: chapter (first 4 digits)
    if len(code) >= 4:
        chapter = code[:4]
        res = (
            supabase.table("hsn_rates")
            .select("*")
            .like("hsn_code", f"{chapter}%")
            .execute()
        )
        if res.data:
            return [_map_db_to_hsn_rate(row, supply_type) for row in res.data]

    raise HTTPException(
        status_code=404,
        detail=f"No rate found for HSN code '{code}' or its heading/chapter.",
    )


@app.get(
    "/api/v1/sac/{code}",
    response_model=List[SacRate],
    summary="Lookup SAC rate by code",
    tags=["SAC"],
)
async def get_sac(
    code: str,
    supply_type: Optional[Literal["intrastate", "interstate"]] = None,
    _: dict = Depends(verify_api_key),
):
    """
    Returns full rate object for a given SAC code (services).
    Pass `supply_type` to resolve the `applicable_rate.recommended` string for intrastate vs interstate routing.
    """
    code = code.strip()

    res = supabase.table("sac_rates").select("*").eq("sac_code", code).execute()
    if res.data:
        return [_map_db_to_sac_rate(row, supply_type) for row in res.data]

    # Fallback: heading (first 4 digits)
    if len(code) >= 4:
        heading = code[:4]
        res = (
            supabase.table("sac_rates")
            .select("*")
            .like("sac_code", f"{heading}%")
            .execute()
        )
        if res.data:
            return [_map_db_to_sac_rate(row, supply_type) for row in res.data]

    raise HTTPException(status_code=404, detail=f"No rate found for SAC code '{code}'.")


@app.get(
    "/api/v1/lookup",
    response_model=List[LookupResult],
    summary="Lookup rate by description keyword",
    tags=["Lookup"],
)
async def get_lookup_rate(q: str, _: dict = Depends(verify_api_key)):
    req = LookupRequest(description=q)
    return await lookup_rate(req, _)


@app.get(
    "/api/demo/lookup",
    response_model=List[LookupResult],
    summary="Public Demo Lookup",
    tags=["Demo"],
)
async def demo_lookup(q: str, request: Request):
    """
    Public endpoint for the landing page demo widget.
    Strictly rate limited to 6 requests per minute per IP.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    now = time.time()
    
    # Clean up old timestamps (older than 60s)
    if now - demo_rate_limit_timestamps.get(client_ip, 0) > 60:
        demo_rate_limit_db[client_ip] = 0
        demo_rate_limit_timestamps[client_ip] = now
        
    demo_rate_limit_db[client_ip] = demo_rate_limit_db.get(client_ip, 0) + 1
    
    if demo_rate_limit_db[client_ip] > 6:
        raise HTTPException(
            status_code=429,
            detail="Demo rate limit reached. Get a free API key for unlimited access."
        )
        
    # Reuse existing lookup logic (pass None or a mock dict for the key dependency)
    req = LookupRequest(description=q)
    return await lookup_rate(req, {"key": "demo_public_key", "tier": "free"})

@app.get(
    "/api/v1/autocomplete",
    summary="Autocomplete suggestions",
    tags=["Lookup"],
)
async def autocomplete(q: str, _: dict = Depends(verify_api_key)):
    if not q.strip():
        return []
    res = (
        supabase.table("hsn_rates")
        .select("hsn_code, hsn_description")
        .ilike("hsn_description", f"%{q}%")
        .limit(10)
        .execute()
    )
    return res.data

@app.get(
    "/api/v1/gst-rate",
    response_model=List[HsnRate],
    summary="Get GST rate by HSN code",
    tags=["HSN"],
)
async def get_gst_rate_hsn(hsn: str, _: dict = Depends(verify_api_key)):
    return await get_hsn(hsn, None, _)


@app.post(
    "/api/v1/lookup",
    response_model=List[LookupResult],
    summary="Lookup rate by description",
    tags=["Lookup"],
)
async def lookup_rate(req: LookupRequest, _: dict = Depends(verify_api_key)):
    """
    Full-text-search based rate lookup. Pass a product description and optional condition flags.

    **Condition parameters:**
    - `branded` — `true` if the product is pre-packaged and labelled (affects branding conditions).
    - `b2b` — `true` for registered buyer (affects registration/composition conditions).
    - `sale_value_inr` — declared sale value in INR; used to resolve *price-threshold* conditions
      (e.g. "not exceeding Rs. 7500"). The API parses the Rs. threshold from the notification
      text and compares it against this value, returning PASSED/FAILED with the direction.
    - `end_use` — free-text intended end-use (e.g. "agriculture", "defence export");
      matched against notification condition keywords. Returns a warning if no keyword overlap.
    - `supply_type` — one of `domestic` (default), `export`, `sez`, `works_contract`,
      `with_installation`. Export/SEZ automatically adds a zero-rated IGST note.

    Returns top 3 FTS matches with confidence score, `condition_applied` note,
    and `condition_warning` (non-null when manual review is needed).
    """
    if not req.description.strip():
        raise HTTPException(status_code=400, detail="description cannot be empty.")

    # Build a tsquery: tokenise and AND-join terms
    # Sanitize to prevent tsquery syntax errors
    clean_desc = re.sub(r"[^\w\s]", " ", req.description)
    terms = [t.strip() for t in clean_desc.split() if t.strip()]
    if not terms:
        return []
    tsquery_and = " & ".join(terms)

    res = (
        supabase.table("hsn_rates")
        .select("*")
        .text_search("hsn_description", tsquery_and)
        .execute()
    )

    if not res.data:
        # Fallback to OR search if strict AND yields nothing
        tsquery_or = " | ".join(terms)
        res = (
            supabase.table("hsn_rates")
            .select("*")
            .text_search("hsn_description", tsquery_or)
            .execute()
        )

    if not res.data:
        return []

    return _build_lookup_results(res.data, req)


@app.post(
    "/api/v1/bulk",
    response_model=List[List[LookupResult]],
    summary="Bulk rate lookup (up to 100 items)",
    tags=["Lookup"],
)
async def bulk_lookup(requests: List[LookupRequest], _: dict = Depends(verify_api_key)):
    """
    Accepts up to 100 lookup requests and returns an array of result arrays.
    """
    if len(requests) > 100:
        raise HTTPException(
            status_code=400, detail="Maximum 100 items per bulk request."
        )
    if len(requests) == 0:
        raise HTTPException(status_code=400, detail="Request list cannot be empty.")

    all_results = []
    for req in requests:
        if not req.description.strip():
            all_results.append([])
            continue
            
        clean_desc = re.sub(r"[^\w\s]", " ", req.description)
        terms = [t.strip() for t in clean_desc.split() if t.strip()]
        if not terms:
            all_results.append([])
            continue
            
        tsquery_and = " & ".join(terms)
        res = (
            supabase.table("hsn_rates")
            .select("*")
            .text_search("hsn_description", tsquery_and)
            .execute()
        )
        
        if not res.data:
            tsquery_or = " | ".join(terms)
            res = (
                supabase.table("hsn_rates")
                .select("*")
                .text_search("hsn_description", tsquery_or)
                .execute()
            )
            
        all_results.append(_build_lookup_results(res.data or [], req))

    return all_results


@app.get(
    "/api/v1/rates/summary",
    response_model=SummaryResponse,
    summary="Rate coverage statistics",
    tags=["Meta"],
)
async def get_summary(_: dict = Depends(verify_api_key)):
    """
    Returns overall statistics: total codes, match rates, schedule breakdown, etc.
    """
    # Total HSN
    res_hsn_total = supabase.table("hsn_rates").select("id", count="exact").execute()
    total_hsn = res_hsn_total.count or 0

    # Total SAC
    res_sac_total = supabase.table("sac_rates").select("id", count="exact").execute()
    total_sac = res_sac_total.count or 0

    # HSN matched (has a cgst_rate)
    res_matched = (
        supabase.table("hsn_rates")
        .select("id", count="exact")
        .not_.is_("cgst_rate", "null")
        .execute()
    )
    matched = res_matched.count or 0

    # Has conditions
    res_cond = (
        supabase.table("hsn_rates")
        .select("id", count="exact")
        .eq("has_condition", True)
        .execute()
    )
    has_conditions = res_cond.count or 0

    # Cess applicable (non-null, non-zero cess)
    res_cess = (
        supabase.table("hsn_rates")
        .select("id", count="exact")
        .not_.is_("cess_rate", "null")
        .gt("cess_rate", 0)
        .execute()
    )
    cess_count = res_cess.count or 0

    # Schedule breakdown
    res_schedules = (
        supabase.table("hsn_rates")
        .select("schedule")
        .not_.is_("schedule", "null")
        .execute()
    )
    schedule_counts: dict = {}
    for row in res_schedules.data or []:
        s = row.get("schedule") or "Unknown"
        schedule_counts[s] = schedule_counts.get(s, 0) + 1

    by_schedule = [
        ScheduleBreakdown(schedule=k, count=v)
        for k, v in sorted(schedule_counts.items())
    ]

    rate_slabs = RateSlabs(
        igst_slabs=[0, 0.25, 1.5, 3, 5, 18, 28, 40],
        cgst_slabs=[0, 0.125, 0.75, 1.5, 2.5, 9, 14, 20],
        note="SGST always equals CGST for intra-state supplies",
    )

    return SummaryResponse(
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


# ---------------------------------------------------------------------------
# Dashboard Endpoints
# ---------------------------------------------------------------------------

from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import secrets

security = HTTPBearer()

async def verify_jwt(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        user_res = supabase.auth.get_user(token)
        if not user_res or not user_res.user:
            raise HTTPException(status_code=401, detail="Invalid or expired JWT")
        return user_res.user
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid or expired JWT: {str(e)}")

# ── GitHub OAuth ──────────────────────────────────────────────────────────────
class GithubCodePayload(BaseModel):
    code: str

@app.post("/api/v1/auth/github", tags=["Auth"], include_in_schema=False)
async def github_oauth_exchange(payload: GithubCodePayload):
    """
    Exchange a GitHub OAuth authorization code for a Supabase session.
    Steps:
      1. Exchange code → GitHub access token
      2. Fetch GitHub user profile + email
      3. Create or update user in Supabase (admin API)
      4. Generate and return a Supabase session
    """
    import urllib.request
    import urllib.parse

    if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="GitHub OAuth not configured")

    # Step 1 — Exchange code for GitHub access token
    token_payload = urllib.parse.urlencode({
        "client_id":     GITHUB_CLIENT_ID,
        "client_secret": GITHUB_CLIENT_SECRET,
        "code":          payload.code,
    }).encode()

    token_req = urllib.request.Request(
        "https://github.com/login/oauth/access_token",
        data=token_payload,
        headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(token_req, timeout=10) as r:
            token_data = json.loads(r.read())
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"GitHub token exchange failed: {e}")

    github_access_token = token_data.get("access_token")
    if not github_access_token:
        raise HTTPException(status_code=400, detail="Invalid authorization code — please try signing in again")

    # Step 2 — Fetch GitHub user profile
    def gh_get(url: str):
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {github_access_token}",
            "Accept":        "application/vnd.github+json",
            "User-Agent":    "GST Accelerator",
        })
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())

    try:
        gh_user = gh_get("https://api.github.com/user")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch GitHub profile: {e}")

    # Resolve email (may be null if user keeps it private)
    email = gh_user.get("email")
    if not email:
        try:
            emails = gh_get("https://api.github.com/user/emails")
            primary = next((e for e in emails if e.get("primary") and e.get("verified")), None)
            email = primary["email"] if primary else None
        except Exception:
            pass

    if not email:
        raise HTTPException(
            status_code=400,
            detail="Could not retrieve a verified email from your GitHub account. "
                   "Please ensure your primary email is verified on GitHub."
        )

    github_id  = str(gh_user.get("id", ""))
    username   = gh_user.get("login", "")
    avatar_url = gh_user.get("avatar_url", "")
    full_name  = gh_user.get("name") or username

    # Step 3 — Create or update Supabase user
    if not supabase:
        raise HTTPException(status_code=500, detail="Database not configured")

    try:
        # Try to get existing user by email
        existing = supabase.auth.admin.list_users(page=1, per_page=1000)
        existing_user = next(
            (u for u in existing if u.email and u.email.lower() == email.lower()), None
        )

        if existing_user:
            # Update metadata
            updated = supabase.auth.admin.update_user_by_id(
                existing_user.id,
                {"user_metadata": {
                    "github_id":  github_id,
                    "avatar_url": avatar_url,
                    "full_name":  full_name,
                    "username":   username,
                }}
            )
            sb_user_id = existing_user.id
        else:
            # Create new user
            new_user = supabase.auth.admin.create_user({
                "email":         email,
                "email_confirm": True,
                "user_metadata": {
                    "github_id":  github_id,
                    "avatar_url": avatar_url,
                    "full_name":  full_name,
                    "username":   username,
                }
            })
            sb_user_id = new_user.user.id
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        raise HTTPException(status_code=500, detail=f"User provisioning failed: {str(e)} | Trace: {tb}")

    # Step 4 — Generate a Supabase magic link to bootstrap a real session
    try:
        link_res = supabase.auth.admin.generate_link({
            "type":  "magiclink",
            "email": email,
        })
        # Use the unhashed email OTP directly
        token = link_res.properties.email_otp

        if not token:
            raise ValueError("No token generated")

        # Exchange the OTP token for a real session
        session_res = supabase.auth.verify_otp({
            "email": email,
            "token": token,
            "type":  "magiclink"
        })

        session = session_res.session
        return {
            "access_token":  session.access_token,
            "refresh_token": session.refresh_token,
            "expires_at":    session.expires_at,
            "user": {
                "id":         sb_user_id,
                "email":      email,
                "username":   username,
                "avatar_url": avatar_url,
                "full_name":  full_name,
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Session creation failed: {e}")

@app.get("/privacy", include_in_schema=False, response_class=HTMLResponse)
async def privacy_page():
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(base_dir, "privacy.html"), "r", encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Privacy template not found.")

@app.get("/blog", include_in_schema=False, response_class=HTMLResponse)
async def blog_index_page():
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(base_dir, "blog.html"), "r", encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Blog template not found.")

@app.get("/contact", include_in_schema=False, response_class=HTMLResponse)
async def serve_contact():
    try:
        with open("contact.html", "r", encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(content)
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Contact template not found.")

@app.get("/terms", include_in_schema=False, response_class=HTMLResponse)
async def terms_page():
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(base_dir, "terms.html"), "r", encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Terms template not found.")

@app.get("/pricing", include_in_schema=False, response_class=HTMLResponse)
async def pricing_page():
    """Razorpay payment page — served as a standalone HTML file with injected keys."""
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(base_dir, "pricing.html"), "r", encoding="utf-8") as f:
            content = f.read()
        content = content.replace("{{ SUPABASE_URL }}",          SUPABASE_URL or "")
        content = content.replace("{{ SUPABASE_ANON_KEY }}",     SUPABASE_ANON_KEY or "")
        content = content.replace("{{ NEXT_PUBLIC_SITE_URL }}",  NEXT_PUBLIC_SITE_URL)
        content = content.replace("{{ RAZORPAY_BTN_DEVELOPER }}", RAZORPAY_BTN_DEVELOPER)
        content = content.replace("{{ RAZORPAY_BTN_PRO }}",       RAZORPAY_BTN_PRO)
        content = content.replace("{{ RAZORPAY_BTN_BUSINESS }}",  RAZORPAY_BTN_BUSINESS)
        return HTMLResponse(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Pricing page template not found.")

@app.get("/login", include_in_schema=False, response_class=HTMLResponse)
async def login_page():
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(base_dir, "login.html"), "r", encoding="utf-8") as f:
            content = f.read()
        content = content.replace("{{ SUPABASE_URL }}", SUPABASE_URL or "")
        content = content.replace("{{ SUPABASE_ANON_KEY }}", SUPABASE_ANON_KEY or "")
        content = content.replace("{{ NEXT_PUBLIC_SITE_URL }}", NEXT_PUBLIC_SITE_URL)
        content = content.replace("{{ GITHUB_CLIENT_ID }}", GITHUB_CLIENT_ID or "")
        return HTMLResponse(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Login template not found.")

@app.get("/dashboard", include_in_schema=False, response_class=HTMLResponse)
async def dashboard_page():
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(base_dir, "dashboard.html"), "r", encoding="utf-8") as f:
            content = f.read()
        content = content.replace("{{ SUPABASE_URL }}", SUPABASE_URL or "")
        content = content.replace("{{ SUPABASE_ANON_KEY }}", SUPABASE_ANON_KEY or "")
        content = content.replace("{{ NEXT_PUBLIC_SITE_URL }}", NEXT_PUBLIC_SITE_URL)
        return HTMLResponse(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Dashboard template not found.")

@app.get("/auth/callback", include_in_schema=False)
async def auth_callback(request: Request):
    """
    Unified auth callback.
    - If ?code= is present: GitHub OAuth — exchange code server-side, then redirect with tokens
    - Otherwise: Supabase magic link / OAuth redirect handler
    """
    import urllib.parse as _urlparse

    code = request.query_params.get("code")
    state = request.query_params.get("state", "")

    if code and state == "github_login":
        # ── GitHub OAuth: exchange code server-side ──────────────────────────
        # We do the full exchange here so the one-time code is only ever used once
        # (avoids double-use caused by any intermediate redirect).

        import urllib.request as _urlreq

        error_html = lambda msg: HTMLResponse(f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<title>Sign-in Error — GST Accelerator</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap" rel="stylesheet">
<style>*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#06090F;color:#F2F4F8;font-family:'Inter',sans-serif;
  display:flex;align-items:center;justify-content:center;min-height:100vh;}}
.card{{text-align:center;padding:2.5rem 3rem;background:#0E141E;
  border:1px solid rgba(107,122,153,0.14);border-radius:16px;max-width:420px;width:100%;}}
h2{{font-size:1.1rem;font-weight:600;margin-bottom:0.75rem;}}
p{{color:#F04545;font-size:0.875rem;margin-bottom:1.25rem;word-break:break-word;}}
a{{color:#E8650A;text-decoration:none;font-weight:600;}}</style></head>
<body><div class="card">
  <h2>Authentication Failed</h2>
  <p>{msg}</p>
  <a href="/login">← Try again</a>
</div></body></html>""", status_code=400)

        if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
            return error_html("GitHub OAuth is not configured on the server.")

        # Step 1 — Exchange code for GitHub access token
        token_payload = _urlparse.urlencode({
            "client_id":     GITHUB_CLIENT_ID,
            "client_secret": GITHUB_CLIENT_SECRET,
            "code":          code,
        }).encode()
        try:
            with _urlreq.urlopen(
                _urlreq.Request(
                    "https://github.com/login/oauth/access_token",
                    data=token_payload,
                    headers={
                        "Accept": "application/json",
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                    method="POST"
                ), timeout=10
            ) as r:
                token_data = json.loads(r.read())
        except Exception as e:
            return error_html(f"GitHub token request failed: {e}")

        github_access_token = token_data.get("access_token")
        if not github_access_token:
            gh_err = token_data.get("error", "unknown")
            gh_desc = token_data.get("error_description", "")
            return error_html(f"GitHub denied the code: {gh_err} — {gh_desc}")

        # Step 2 — Fetch GitHub profile
        def gh_get(url):
            req = _urlreq.Request(url, headers={
                "Authorization": f"Bearer {github_access_token}",
                "Accept":        "application/vnd.github+json",
                "User-Agent":    "GST-Accelerator",
            })
            with _urlreq.urlopen(req, timeout=10) as r:
                return json.loads(r.read())

        try:
            gh_user = gh_get("https://api.github.com/user")
        except Exception as e:
            return error_html(f"Could not fetch GitHub profile: {e}")

        email = gh_user.get("email")
        if not email:
            try:
                emails = gh_get("https://api.github.com/user/emails")
                primary = next(
                    (e for e in emails if e.get("primary") and e.get("verified")), None
                )
                email = primary["email"] if primary else None
            except Exception:
                pass

        if not email:
            return error_html(
                "Your GitHub account has no verified primary email. "
                "Please verify your email on GitHub and try again."
            )

        github_id  = str(gh_user.get("id", ""))
        username   = gh_user.get("login", "")
        avatar_url = gh_user.get("avatar_url", "")
        full_name  = gh_user.get("name") or username

        # Step 3 — Create or update Supabase user
        if not supabase:
            return error_html("Database not configured.")

        try:
            existing = supabase.auth.admin.list_users(page=1, per_page=1000)
            existing_user = next(
                (u for u in existing if u.email and u.email.lower() == email.lower()), None
            )
            if existing_user:
                supabase.auth.admin.update_user_by_id(
                    existing_user.id,
                    {"user_metadata": {
                        "github_id":  github_id,
                        "avatar_url": avatar_url,
                        "full_name":  full_name,
                        "username":   username,
                    }}
                )
                sb_user_id = existing_user.id
            else:
                new_user = supabase.auth.admin.create_user({
                    "email":         email,
                    "email_confirm": True,
                    "user_metadata": {
                        "github_id":  github_id,
                        "avatar_url": avatar_url,
                        "full_name":  full_name,
                        "username":   username,
                    }
                })
                sb_user_id = new_user.user.id
        except Exception as e:
            import traceback
            return error_html(f"Account setup failed: {e} | {traceback.format_exc()}")

        # Step 4 — Generate Supabase session via email OTP
        try:
            link_res = supabase.auth.admin.generate_link({
                "type":  "magiclink",
                "email": email,
            })
            otp_token = link_res.properties.email_otp
            if not otp_token:
                return error_html("Could not generate a session token.")

            session_res = supabase.auth.verify_otp({
                "email": email,
                "token": otp_token,
                "type":  "magiclink"
            })
            session = session_res.session
        except Exception as e:
            import traceback
            return error_html(f"Session creation failed: {e} | {traceback.format_exc()}")

        # Step 5 — Redirect to dashboard; pass tokens via fragment so JS can pick them up
        access_token  = session.access_token
        refresh_token = session.refresh_token
        expires_at    = session.expires_at
        display_name  = full_name or username

        return HTMLResponse(f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<title>Signing you in — GST Accelerator</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap" rel="stylesheet">
<style>*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#06090F;color:#F2F4F8;font-family:'Inter',sans-serif;
  display:flex;align-items:center;justify-content:center;min-height:100vh;}}
.card{{text-align:center;padding:2.5rem 3rem;background:#0E141E;
  border:1px solid rgba(107,122,153,0.14);border-radius:16px;max-width:380px;width:100%;}}
.spinner{{width:40px;height:40px;border:3px solid rgba(232,101,10,0.2);
  border-top-color:#E8650A;border-radius:50%;animation:spin 0.8s linear infinite;margin:0 auto 1.5rem;}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}
h2{{font-size:1.1rem;font-weight:600;margin-bottom:0.5rem;}}
p{{color:#6B7A99;font-size:0.875rem;}}</style></head>
<body><div class="card">
  <div class="spinner"></div>
  <h2>Welcome, {display_name}!</h2>
  <p>Redirecting to your dashboard…</p>
</div>
<script>
  (function() {{
    var session = {{
      access_token: {json.dumps(access_token)},
      refresh_token: {json.dumps(refresh_token)},
      expires_at: {json.dumps(expires_at)},
      user: {{
        id: {json.dumps(sb_user_id)},
        email: {json.dumps(email)},
        username: {json.dumps(username)},
        avatar_url: {json.dumps(avatar_url)},
        full_name: {json.dumps(full_name)}
      }}
    }};
    localStorage.setItem('sb-session', JSON.stringify(session));
    // Also set Supabase's native storage key
    var projectRef = 'apozbgntylczkzhdwfbz';
    localStorage.setItem(
      'sb-' + projectRef + '-auth-token',
      JSON.stringify({{
        access_token: session.access_token,
        refresh_token: session.refresh_token,
        expires_at: session.expires_at,
        token_type: 'bearer',
        user: session.user
      }})
    );
    window.location.href = '/dashboard';
  }})();
</script></body></html>""")

    # Supabase magic link / OAuth redirect — pass through to dashboard
    query = request.url.query
    redirect_url = f"/dashboard?{query}" if query else "/dashboard"
    return RedirectResponse(url=redirect_url, status_code=302)


@app.get("/docs", include_in_schema=False, response_class=HTMLResponse)
async def api_docs_page():
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(base_dir, "docs.html"), "r", encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Docs template not found.")

@app.get("/blog/gst-api-for-developers", include_in_schema=False, response_class=HTMLResponse)
async def gst_api_blog_page():
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(base_dir, "gst-api-for-developers.html"), "r", encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Blog template not found.")

@app.get("/llms.txt", include_in_schema=False)
async def llms_txt():
    """
    llms.txt — machine-readable API description for AI crawlers (LLMs, ChatGPT plugins, etc.)
    See: https://llmstxt.org
    """
    content = """# GST Accelerator API

> India's most accurate GST HSN & SAC rate API. Condition-aware, GST 2.0 compliant, agent-native.

## What this API does

The GST Accelerator API provides structured GST (Goods and Services Tax) rate data for Indian goods (HSN codes) and services (SAC codes). It covers 48,752 HSN codes and 681 SAC codes with CGST, SGST, IGST, and Cess rates as per CBIC Notification 09/2025-CT(Rate), effective 2025-09-22.

## Endpoints

- GET /api/v1/hsn/{code} — Lookup GST rate for an HSN code (goods)
- GET /api/v1/sac/{code} — Lookup GST rate for a SAC code (services)
- POST /api/v1/lookup — Full-text search by product/service description
- GET /api/v1/lookup?q={query} — GET alias for description-based lookup
- POST /api/v1/bulk — Batch lookup (up to 100 items)
- GET /api/v1/autocomplete?q={query} — Autocomplete HSN/SAC descriptions
- GET /api/v1/rates/summary — Coverage statistics and rate slab breakdown
- GET /health — Liveness check with uptime and DB status
- GET /meta — API metadata, total code counts, MCP endpoint

## Authentication

All /api/v1/ endpoints require an `X-API-Key` header. Get a free key (1,000 calls/month) at https://gstaccelerator.in/pricing.

## MCP (Model Context Protocol) endpoint

AI agents and LLMs can connect natively via the MCP SSE endpoint:
- GET /mcp/sse — SSE stream (pass X-API-Key header)
- POST /mcp/messages — Message handler

Tool: `lookup_gst_rate` — accepts a product description query and optional condition flags (branded, b2b, sale_value_inr, end_use, supply_type).

## Rate limits

- Free: 1,000 calls/month
- Developer: 50,000 calls/month
- Pro: 500,000 calls/month
- Business: 5,000,000 calls/month

Response headers: X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset

## Data source

CBIC (Central Board of Indirect Taxes and Customs), Government of India.
Notification: 09/2025-Central Tax (Rate), effective 2025-09-22.

## Useful links

- Homepage: https://gstaccelerator.in/
- Docs: https://gstaccelerator.in/docs
- Pricing: https://gstaccelerator.in/pricing
- Developer guide: https://gstaccelerator.in/blog/gst-api-for-developers
"""
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(content=content, media_type="text/plain; charset=utf-8")


@app.get("/sitemap.xml", include_in_schema=False)
async def sitemap_xml():
    """Sitemap for SEO crawlers."""
    from fastapi.responses import Response as FastAPIResponse
    sitemap = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://gstaccelerator.in/</loc>
    <changefreq>weekly</changefreq>
    <priority>1.0</priority>
    <lastmod>2026-07-02</lastmod>
  </url>
  <url>
    <loc>https://gstaccelerator.in/docs</loc>
    <changefreq>weekly</changefreq>
    <priority>0.9</priority>
    <lastmod>2026-07-02</lastmod>
  </url>
  <url>
    <loc>https://gstaccelerator.in/pricing</loc>
    <changefreq>monthly</changefreq>
    <priority>0.8</priority>
    <lastmod>2026-07-02</lastmod>
  </url>
  <url>
    <loc>https://gstaccelerator.in/blog/gst-api-for-developers</loc>
    <changefreq>monthly</changefreq>
    <priority>0.8</priority>
    <lastmod>2026-06-30</lastmod>
  </url>
  <url>
    <loc>https://gstaccelerator.in/llms.txt</loc>
    <changefreq>monthly</changefreq>
    <priority>0.5</priority>
    <lastmod>2026-07-02</lastmod>
  </url>
  <url>
    <loc>https://gstaccelerator.in/terms</loc>
    <changefreq>yearly</changefreq>
    <priority>0.3</priority>
    <lastmod>2026-07-03</lastmod>
  </url>
  <url>
    <loc>https://gstaccelerator.in/privacy</loc>
    <changefreq>yearly</changefreq>
    <priority>0.3</priority>
    <lastmod>2026-07-03</lastmod>
  </url>
</urlset>"""
    return FastAPIResponse(content=sitemap, media_type="application/xml")



class KeyCreateRequest(BaseModel):
    name: str = "Default Key"

class KeyRenameRequest(BaseModel):
    name: str

@app.get("/api/v1/dashboard/keys", tags=["Dashboard"])
async def get_dashboard_keys(user=Depends(verify_jwt)):
    res = (
        supabase.table("api_keys")
        .select("id, name, key_prefix, is_active, created_at, tier, monthly_limit, calls_this_month")
        .eq("user_id", user.id)
        .eq("is_active", True)
        .execute()
    )
    return res.data

@app.post("/api/v1/dashboard/keys", tags=["Dashboard"])
async def create_dashboard_key(req: KeyCreateRequest, user=Depends(verify_jwt)):
    # Generate a new random key
    raw_key = f"gsta_live_{secrets.token_urlsafe(24)}"
    key_hash = _hash_key(raw_key)
    key_prefix = raw_key[:15]
    
    res = (
        supabase.table("api_keys")
        .insert({
            "user_id": user.id,
            "key_prefix": key_prefix,
            "key_hash": key_hash,
            "name": req.name,
            "is_active": True,
            "tier": "free",
            "monthly_limit": 1000,
            "calls_this_month": 0
        })
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=500, detail="Failed to generate key")
        
    return {"raw_key": raw_key, "key_id": res.data[0]["id"]}

@app.patch("/api/v1/dashboard/keys/{key_id}", tags=["Dashboard"])
async def rename_dashboard_key(key_id: str, req: KeyRenameRequest, user=Depends(verify_jwt)):
    res = (
        supabase.table("api_keys")
        .update({"name": req.name})
        .eq("id", key_id)
        .eq("user_id", user.id)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Key not found or not owned by user.")
    return {"status": "renamed"}

@app.post("/api/v1/dashboard/keys/{key_id}/rotate", tags=["Dashboard"])
async def rotate_dashboard_key(key_id: str, user=Depends(verify_jwt)):
    # Fetch old key details
    old_res = supabase.table("api_keys").select("*").eq("id", key_id).eq("user_id", user.id).execute()
    if not old_res.data:
        raise HTTPException(status_code=404, detail="Key not found")
    old_key = old_res.data[0]

    # Deactivate old key
    supabase.table("api_keys").update({"is_active": False}).eq("id", key_id).execute()

    # Create new key
    raw_key = f"gsta_live_{secrets.token_urlsafe(24)}"
    new_res = (
        supabase.table("api_keys")
        .insert({
            "user_id": user.id,
            "key_prefix": raw_key[:15],
            "key_hash": _hash_key(raw_key),
            "name": old_key["name"],
            "is_active": True,
            "tier": old_key.get("tier", "free"),
            "monthly_limit": old_key.get("monthly_limit", 1000),
            "calls_this_month": 0
        })
        .execute()
    )
    return {"raw_key": raw_key, "key_id": new_res.data[0]["id"]}

@app.delete("/api/v1/dashboard/keys/{key_id}", tags=["Dashboard"])
async def revoke_dashboard_key(key_id: str, user=Depends(verify_jwt)):
    # Instead of deleting, just mark as inactive
    res = (
        supabase.table("api_keys")
        .update({"is_active": False})
        .eq("id", key_id)
        .eq("user_id", user.id)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Key not found or not owned by user.")
    return {"status": "revoked"}


@app.get("/api/v1/dashboard/usage", tags=["Dashboard"])
async def get_dashboard_usage(user=Depends(verify_jwt)):
    """Return aggregated API call usage for the authenticated user this month."""
    res = (
        supabase.table("api_keys")
        .select("tier, monthly_limit, calls_this_month")
        .eq("user_id", user.id)
        .eq("is_active", True)
        .execute()
    )
    keys = res.data or []
    calls_used  = sum(k.get("calls_this_month", 0) or 0 for k in keys)
    calls_limit = max((k.get("monthly_limit", 1000) or 1000 for k in keys), default=1000)
    tier        = keys[0].get("tier", "free") if keys else "free"
    return {
        "calls_used":  calls_used,
        "calls_limit": calls_limit,
        "tier":        tier,
    }


# ---------------------------------------------------------------------------
# MCP Endpoints (SSE)
# ---------------------------------------------------------------------------

mcp_server = Server("gst-accelerator")
sse_transport = SseServerTransport("/mcp/messages")
mcp_api_key_ctx = contextvars.ContextVar("mcp_api_key_ctx", default=None)

@mcp_server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="lookup_gst_rate",
            description="Lookup GST rates based on product description.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The product description, e.g., 'rice', 'software'"},
                    "conditions": {
                        "type": "object",
                        "description": "Optional conditions.",
                        "properties": {
                            "sale_value_inr": {"type": "number"},
                            "branded": {"type": "boolean"},
                            "b2b": {"type": "boolean"},
                            "end_use": {"type": "string"},
                            "supply_type": {"type": "string", "enum": ["domestic", "export", "sez", "works_contract", "with_installation"]}
                        }
                    }
                },
                "required": ["query"]
            }
        )
    ]

@mcp_server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    if name == "lookup_gst_rate":
        api_key_dict = mcp_api_key_ctx.get()
        if not api_key_dict:
            return [types.TextContent(type="text", text="Error: Unauthorized. Missing API key in MCP context.")]
            
        req = LookupRequest(description=arguments.get("query", ""))
        cond_dict = arguments.get("conditions")
        if cond_dict:
            req.conditions = ConditionFlags(**cond_dict)
            
        results = await lookup_rate(req, api_key_dict)
        text_results = [json.loads(r.model_dump_json()) for r in results]
        return [types.TextContent(type="text", text=json.dumps(text_results, indent=2))]
        
    raise ValueError(f"Unknown tool: {name}")

@app.get("/mcp/sse", include_in_schema=False)
async def mcp_sse_route(request: Request):
    api_key_header = request.headers.get("x-api-key")
    if not api_key_header:
        raise HTTPException(status_code=401, detail="Missing X-API-Key")
    
    auth_dict = await verify_api_key(api_key_header)
    
    async with sse_transport.connect_sse(request.scope, request.receive, request._send) as streams:
        await mcp_server.run(streams[0], streams[1], mcp_server.create_initialization_options())

@app.post("/mcp/messages", include_in_schema=False)
async def mcp_messages_route(request: Request):
    api_key_header = request.headers.get("x-api-key")
    if not api_key_header:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header in POST request")
        
    auth_dict = await verify_api_key(api_key_header)
    mcp_api_key_ctx.set(auth_dict)
    
    await sse_transport.handle_post_message(request.scope, request.receive, request._send)

if __name__ == "__main__":
    # pyrefly: ignore [missing-import]
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
