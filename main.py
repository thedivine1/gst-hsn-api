import os
import re
import hashlib
from enum import Enum
from typing import List, Optional, Tuple, Literal
# pyrefly: ignore [missing-import]
from fastapi import FastAPI, Header, HTTPException, Depends
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field
from supabase import create_client, Client  # pyright: ignore [missing-import]
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "SUPABASE_URL and SUPABASE_KEY must be set in environment variables."
    )

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = FastAPI(
    title="gstaccelerator.in API",
    version="1.0.0",
    description="Lookup GST CGST/IGST/SGST/Cess rates for Indian goods (HSN) and services (SAC) codes. Powered by gstaccelerator.in.",
)


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


async def verify_api_key(x_api_key: str = Header(..., description="Your API key")):
    """Dependency: validates X-API-Key, enforces monthly limits, increments usage."""
    key_hash = _hash_key(x_api_key)

    res = (
        supabase.table("api_keys")
        .select("*")
        .eq("key_hash", key_hash)
        .eq("is_active", True)
        .single()
        .execute()
    )
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

    return record


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
    schedule: Optional[str] = None
    condition_text: Optional[str] = None
    condition_type: Optional[str] = "none"
    has_condition: Optional[bool] = False
    notification_ref: Optional[str] = None
    effective_date: Optional[str] = None
    needs_review: Optional[bool] = False
    tax_rates: TaxRates
    applicable_rate: ApplicableRate


class SacRate(BaseModel):
    id: Optional[int] = None
    sac_code: str
    sac_description: str
    condition_text: Optional[str] = None
    condition_type: Optional[str] = "none"
    has_condition: Optional[bool] = False
    notification_ref: Optional[str] = None
    effective_date: Optional[str] = None
    needs_review: Optional[bool] = False
    tax_rates: TaxRates
    applicable_rate: ApplicableRate


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
    results = []
    for i, row in enumerate(rows):
        passes, condition_note, condition_warning = _evaluate_condition(row, req)
        if not passes:
            continue

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
            )
        )

    return results[:3]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/", include_in_schema=False)
async def root():
    return {"message": "gstaccelerator.in Rate Lookup API v1. See /docs for usage."}


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
    )


@app.get(
    "/v1/hsn/{code}",
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
    code = code.strip().zfill(8) if len(code) <= 8 else code.strip()

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
    "/v1/sac/{code}",
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
    code = code.strip().zfill(6) if len(code) <= 6 else code.strip()

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


@app.post(
    "/v1/lookup",
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

    # Build a tsquery: tokenise and OR-join terms
    terms = [t.strip() for t in req.description.split() if t.strip()]
    tsquery = " | ".join(terms)

    res = (
        supabase.table("hsn_rates")
        .select("*")
        .text_search("hsn_description", tsquery, config="english")
        .execute()
    )

    if not res.data:
        return []

    return _build_lookup_results(res.data, req)


@app.post(
    "/v1/bulk",
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
        terms = [t.strip() for t in req.description.split() if t.strip()]
        tsquery = " | ".join(terms)
        res = (
            supabase.table("hsn_rates")
            .select("*")
            .text_search("hsn_description", tsquery, config="english")
            .execute()
        )
        all_results.append(_build_lookup_results(res.data or [], req))

    return all_results


@app.get(
    "/v1/rates/summary",
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
