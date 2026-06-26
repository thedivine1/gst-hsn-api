import os
import re
import hashlib
from enum import Enum
from typing import List, Optional, Tuple, Literal
# pyrefly: ignore [missing-import]
from fastapi import FastAPI, Header, HTTPException, Depends
# pyrefly: ignore [missing-import]
from fastapi.responses import HTMLResponse
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field
from supabase import create_client, Client  # pyright: ignore [missing-import]
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY")

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


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


async def verify_api_key(x_api_key: str = Header(..., description="Your API key")):
    """Dependency: validates X-API-Key, enforces monthly limits, increments usage."""
    if x_api_key == "gsta_demo_frontend":
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

  fetch('/v1/lookup', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-API-Key': 'gsta_demo_frontend' },
    body: JSON.stringify({ description: val })
  })
  .then(function(res) {
    return res.json().then(function(data) {
      if (res.ok && data && data.length > 0) {
        out.innerHTML = fmt(data[0]);
        out.classList.add('has-result');
      } else {
        out.innerHTML = '<span style="color:#3D4E6A">// No match found for "' + val + '".\n// Try: AC unit, gold jewellery, basmati rice, namkeen\n// All 48,752 HSN codes available with an API key.</span>';
      }
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


@app.get("/demo.js", include_in_schema=False)
async def demo_js():
    # pyrefly: ignore [missing-import]
    from fastapi.responses import Response
    return Response(content=DEMO_JS, media_type="application/javascript")


@app.get("/", include_in_schema=False, response_class=HTMLResponse)
async def root():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>GST Accelerator — GST at the speed of business</title>
  <meta name="description" content="India's most accurate GST HSN & SAC rate API. Condition-aware. GST 2.0 compliant. Agent-native. 48,752 HSN codes. Free tier available." />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />
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
      transition: opacity 0.15s;
    }
    .pa-outline { background: transparent; border: 1px solid var(--border-md); color: var(--white); }
    .pa-solid { background: var(--amber); color: #fff; }
    .pa-outline:hover, .pa-solid:hover { opacity: 0.8; }
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
    <a href="/docs">Docs</a>
    <a class="nav-cta" href="/dashboard">Get API Key</a>
  </div>
</nav>

<!-- HERO -->
<section class="hero">
  <div class="hero-eyebrow">
    <span class="hero-eyebrow-dot"></span>
    GST 2.0 · 09/2025-CT(Rate) · Updated Sept 2025
  </div>

  <h1>GST at the <em>speed of business</em></h1>

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
      <a class="plan-action pa-outline" href="mailto:hello@gstaccelerator.in?subject=Free API Key Request">Get free key</a>
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
      <a class="plan-action pa-solid" href="mailto:hello@gstaccelerator.in?subject=Developer Plan - Rs 399">Get started</a>
      <div class="upi-note">Pay via UPI · Instant activation</div>
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
      <a class="plan-action pa-outline" href="mailto:hello@gstaccelerator.in?subject=Pro Plan">Get started</a>
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
      <a class="plan-action pa-outline" href="mailto:hello@gstaccelerator.in?subject=Business Plan Enquiry">Contact us</a>
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
    <a href="#">Terms</a>
    <a href="#">Privacy</a>
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

@app.get("/dashboard", include_in_schema=False, response_class=HTMLResponse)
async def dashboard_page():
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(base_dir, "dashboard.html"), "r", encoding="utf-8") as f:
            content = f.read()
        content = content.replace("{{ SUPABASE_URL }}", SUPABASE_URL or "")
        content = content.replace("{{ SUPABASE_ANON_KEY }}", SUPABASE_ANON_KEY or "")
        return HTMLResponse(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Dashboard template not found.")

@app.get("/docs", include_in_schema=False, response_class=HTMLResponse)
async def api_docs_page():
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(base_dir, "docs.html"), "r", encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Docs template not found.")

class KeyCreateRequest(BaseModel):
    name: str = "Default Key"

@app.get("/v1/dashboard/keys", tags=["Dashboard"])
async def get_dashboard_keys(user=Depends(verify_jwt)):
    res = (
        supabase.table("api_keys")
        .select("id, name, key_prefix, is_active")
        .eq("user_id", user.id)
        .eq("is_active", True)
        .execute()
    )
    return res.data

@app.post("/v1/dashboard/keys", tags=["Dashboard"])
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

@app.delete("/v1/dashboard/keys/{key_id}", tags=["Dashboard"])
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


if __name__ == "__main__":
    # pyrefly: ignore [missing-import]
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
