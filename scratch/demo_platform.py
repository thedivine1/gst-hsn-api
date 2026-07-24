"""
GST Accelerator — Live Sales Demo Platform
============================================
A fully interactive Streamlit app that calls the *real* GST Accelerator API.
All endpoints are showcased. API key is session-only (clears on close).
"""

# pyrefly: ignore [missing-import]
import streamlit as st
import requests
import time
import json
import random
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

# ─────────────────────────────────────────────────────────────────────────────
# App Configuration
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="GST Accelerator — Live Demo",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

BASE_URL = "http://127.0.0.1:8000"

# ─────────────────────────────────────────────────────────────────────────────
# Session State Initialization
# ─────────────────────────────────────────────────────────────────────────────
def init_state():
    defaults = {
        "prospect_name": "Khatabook",
        "industry": "Fintech/Ledger",
        "tech_stack": "Python Dominant",
        "demo_initialized": False,
        "api_key": "",           # session-only — never persisted
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

# ─────────────────────────────────────────────────────────────────────────────
# API Helper
# ─────────────────────────────────────────────────────────────────────────────
def api(method: str, path: str, api_key: str = None, **kwargs):
    """Thin wrapper: injects the session API key and measures latency."""
    headers = kwargs.pop("headers", {})
    headers["X-API-Key"] = api_key if api_key is not None else st.session_state.api_key
    url = BASE_URL + path
    t0 = time.perf_counter()
    try:
        r = requests.request(method, url, headers=headers, timeout=15, **kwargs)
        latency = int((time.perf_counter() - t0) * 1000)
        return r, latency
    except requests.exceptions.ConnectionError:
        st.error("❌ Cannot reach the local API server at `http://127.0.0.1:8000`. Is `uvicorn main:app` running?")
        st.stop()

# ─────────────────────────────────────────────────────────────────────────────
# Sidebar — Persona Manager
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Demo Persona Manager")
    st.caption("Customize the live presentation context.")

    with st.form("persona_form"):
        p_name  = st.text_input("Prospect Company", st.session_state.prospect_name)
        p_ind   = st.selectbox("Industry Vertical",
                    ["Fintech/Ledger", "Payments Gateway", "SaaS/Accounting", "E-commerce"],
                    index=["Fintech/Ledger", "Payments Gateway", "SaaS/Accounting", "E-commerce"]
                    .index(st.session_state.industry))
        p_stack = st.radio("Primary Dev Stack",
                    ["Python Dominant", "Node.js Dominant", "Mixed/AI-First"],
                    index=["Python Dominant", "Node.js Dominant", "Mixed/AI-First"]
                    .index(st.session_state.tech_stack))
        submitted = st.form_submit_button("Initialize Demo ▶", use_container_width=True)
        if submitted:
            st.session_state.prospect_name = p_name
            st.session_state.industry = p_ind
            st.session_state.tech_stack = p_stack
            st.session_state.demo_initialized = True
            st.success("Persona loaded!")

    st.divider()
    st.subheader("🔑 Demo API Key")
    st.caption("Session-only. Clears when the app is closed.")
    api_key_input = st.text_input(
        "Paste your demo key here",
        value=st.session_state.api_key,
        type="password",
        placeholder="gsta_demo_..."
    )
    if api_key_input != st.session_state.api_key:
        st.session_state.api_key = api_key_input
        st.rerun()

    if not st.session_state.api_key:
        st.warning("No API key set. Endpoints that require auth will return 401.")

# ─────────────────────────────────────────────────────────────────────────────
# Header
# ─────────────────────────────────────────────────────────────────────────────
pn = st.session_state.prospect_name
st.title(f"⚡ GST Accelerator Live Demo — {pn}")
st.markdown(f"**Industry:** {st.session_state.industry} &nbsp;|&nbsp; **Stack:** {st.session_state.tech_stack}")

if not st.session_state.demo_initialized:
    st.info("👈 Initialize the demo persona from the sidebar to begin.")
    st.stop()

# ─────────────────────────────────────────────────────────────────────────────
# Tabs (all 9 endpoint groups)
# ─────────────────────────────────────────────────────────────────────────────
(
    tab_gstin, tab_hsn, tab_sac, tab_lookup,
    tab_autocomplete, tab_invoice, tab_bulk_lookup,
    tab_bulk_gstin, tab_meta
) = st.tabs([
    "🏷️ GSTIN",
    "📦 HSN Lookup",
    "🔧 SAC Lookup",
    "🔍 Description Lookup",
    "⚡ Autocomplete",
    "🧾 Invoice Classify",
    "📋 Bulk Lookup",
    "📊 Bulk GSTIN Batch",
    "📡 Meta / Health",
])

# ═════════════════════════════════════════════════════════════════════════════
# TAB 1 — GSTIN (Validate / State / PAN)
# ═════════════════════════════════════════════════════════════════════════════
with tab_gstin:
    st.header("GSTIN Endpoints")
    st.markdown("Three sub-endpoints: **validate**, **state**, **pan**.")
    gstin_input = st.text_input("Enter any GSTIN", "27AADCB2230M1Z2", key="gstin_inp")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Validate GSTIN", use_container_width=True):
            r, ms = api("GET", f"/api/v1/gstin/{gstin_input}/validate")
            st.caption(f"HTTP {r.status_code} · {ms}ms")
            data = r.json()
            if r.ok and data.get("valid"):
                st.success(f"✅ Valid GSTIN — State: {data.get('state_name')} ({data.get('state_code')})")
                st.json(data)
            elif r.ok:
                st.error(f"❌ Invalid — {data.get('error_reason')}")
                st.json(data)
            else:
                st.error(data)

    with col2:
        if st.button("Get State from GSTIN", use_container_width=True):
            r, ms = api("GET", f"/api/v1/gstin/{gstin_input}/state")
            st.caption(f"HTTP {r.status_code} · {ms}ms")
            st.json(r.json())

    with col3:
        if st.button("Extract PAN from GSTIN", use_container_width=True):
            r, ms = api("GET", f"/api/v1/gstin/{gstin_input}/pan")
            st.caption(f"HTTP {r.status_code} · {ms}ms")
            d = r.json()
            if r.ok:
                st.success(f"PAN: **{d.get('pan')}** | Entity Code: **{d.get('entity_type_code')}**")
            st.json(d)

    st.divider()
    st.subheader("📋 Python Code Reference")
    st.code(f"""import asyncio
from gstaccelerator import GSTClient

async def gstin_demo():
    client = GSTClient(api_key="sk_prod_...")
    gstin = "{gstin_input}"

    # Validate structure + checksum
    validity = await client.validate_gstin(gstin)
    print(validity.valid, validity.state_name)

    # Extract PAN
    pan_info = await client.get_gstin_pan(gstin)
    print(pan_info.pan)

asyncio.run(gstin_demo())
""", language="python")

# ═════════════════════════════════════════════════════════════════════════════
# TAB 2 — HSN Lookup
# ═════════════════════════════════════════════════════════════════════════════
with tab_hsn:
    st.header("HSN Rate Lookup")
    st.markdown("Returns CGST/SGST/IGST/Cess rates for any HSN code. Falls back 8→6→4 digits automatically.")

    col1, col2 = st.columns([1, 1])
    with col1:
        hsn_code = st.text_input("HSN Code", "10063010", key="hsn_inp")
        supply_type_hsn = st.radio("Supply Type", ["intrastate", "interstate"], horizontal=True, key="st_hsn")

        if st.button("Lookup HSN Rate", use_container_width=True):
            r, ms = api("GET", f"/api/v1/hsn/{hsn_code}", params={"supply_type": supply_type_hsn})
            st.caption(f"HTTP {r.status_code} · {ms}ms")
            if r.ok:
                data = r.json()
                if data:
                    d = data[0]
                    rate = d.get("tax_rates", {})
                    st.success(f"**{d.get('hsn_code')}** — IGST: {rate.get('igst')}% | CGST: {rate.get('cgst')}% | SGST: {rate.get('sgst')}%")
                    st.json(d)
            else:
                st.error(r.json())

    with col2:
        st.subheader("TypeScript Snippet")
        st.code(f"""import {{ GSTClient }} from 'gstaccelerator';

const client = new GSTClient({{ apiKey: process.env.GST_API_KEY }});

const rate = await client.hsn.lookup("{hsn_code}", {{
    supplyType: "{supply_type_hsn}"
}});

console.log(`IGST: ${{rate[0].tax_rates.igst}}%`);
""", language="typescript")

# ═════════════════════════════════════════════════════════════════════════════
# TAB 3 — SAC Lookup
# ═════════════════════════════════════════════════════════════════════════════
with tab_sac:
    st.header("SAC Rate Lookup (Services)")
    st.markdown("Returns GST rates for any SAC code (Services Accounting Code).")

    col1, col2 = st.columns([1, 1])
    with col1:
        sac_code = st.text_input("SAC Code", "9983", key="sac_inp")
        supply_type_sac = st.radio("Supply Type", ["intrastate", "interstate"], horizontal=True, key="st_sac")

        if st.button("Lookup SAC Rate", use_container_width=True):
            r, ms = api("GET", f"/api/v1/sac/{sac_code}", params={"supply_type": supply_type_sac})
            st.caption(f"HTTP {r.status_code} · {ms}ms")
            if r.ok:
                data = r.json()
                if data:
                    d = data[0]
                    rate = d.get("tax_rates", {})
                    st.success(f"**{d.get('sac_code')}** — IGST: {rate.get('igst')}% | {d.get('description','')[:80]}")
                    st.json(d)
            else:
                st.error(r.json())

    with col2:
        st.subheader("Python Snippet")
        st.code(f"""from gstaccelerator import GSTClient

async def sac_demo():
    client = GSTClient(api_key="sk_prod_...")
    rate = await client.sac.lookup("{sac_code}", supply_type="{supply_type_sac}")
    print(rate[0].tax_rates.igst)
""", language="python")

# ═════════════════════════════════════════════════════════════════════════════
# TAB 4 — Description Lookup (GET + POST)
# ═════════════════════════════════════════════════════════════════════════════
with tab_lookup:
    st.header("Description-Based Rate Lookup")
    st.markdown("Full-text search across 48,000+ HSN descriptions. Returns top 3 matches with confidence scores and condition flags.")

    col1, col2 = st.columns([1, 1])
    with col1:
        desc_q      = st.text_input("Product / Service Description", "basmati rice", key="desc_q")
        branded     = st.checkbox("Pre-packaged / Branded product?")
        b2b         = st.checkbox("B2B transaction (registered buyer)?")
        sale_value  = st.number_input("Sale Value (INR, for threshold conditions)", value=0, min_value=0)
        supply_type_lookup = st.radio("Supply Type", ["intrastate", "interstate"], horizontal=True, key="st_lookup")

        if st.button("Search by Description", use_container_width=True):
            payload = {
                "description": desc_q,
                "branded": branded,
                "b2b": b2b,
                "supply_type": supply_type_lookup,
            }
            if sale_value > 0:
                payload["sale_value_inr"] = sale_value

            r, ms = api("POST", "/api/v1/lookup", json=payload)
            st.caption(f"HTTP {r.status_code} · {ms}ms")
            if r.ok:
                results = r.json()
                for match in results:
                    hsn = match.get("hsn_code", "—")
                    desc = match.get("description", "—")[:80]
                    score = match.get("confidence_score", "—")
                    igst = match.get("tax_rates", {}).get("igst", "—")
                    st.success(f"**HSN {hsn}** | IGST {igst}% | Score: {score} | {desc}")
                    if match.get("condition_warning"):
                        st.warning(f"⚠️ Condition: {match['condition_warning']}")
            else:
                st.error(r.json())

    with col2:
        st.subheader("Python Snippet")
        st.code(f"""from gstaccelerator import GSTClient, LookupRequest

async def lookup_demo():
    client = GSTClient(api_key="sk_prod_...")
    results = await client.lookup(LookupRequest(
        description="{desc_q}",
        branded={str(branded)},
        b2b={str(b2b)},
        supply_type="{supply_type_lookup}",
    ))
    for r in results:
        print(r.hsn_code, r.tax_rates.igst)
""", language="python")

# ═════════════════════════════════════════════════════════════════════════════
# TAB 5 — Autocomplete (Live)
# ═════════════════════════════════════════════════════════════════════════════
with tab_autocomplete:
    st.header("HSN Autocomplete — Sub-50ms Live Search")
    st.markdown(f"Shows how {pn}'s onboarding forms can suggest HSN codes instantly as users type.")

    ac_q = st.text_input("Start typing a product description…", "cotton", key="ac_q")

    if st.button("Search Autocomplete", use_container_width=True):
        r, ms = api("GET", "/api/v1/autocomplete", params={"q": ac_q})
        st.caption(f"HTTP {r.status_code} · **{ms}ms** — Two-tier GIN index query")
        if r.ok:
            results = r.json()
            if results:
                df = pd.DataFrame(results)
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("No results found.")
        else:
            st.error(r.json())

    st.code(f"""// Attach to an <input> onChange event in React / Vue / Angular
import {{ GSTClient }} from 'gstaccelerator';

const client = new GSTClient({{ apiKey: process.env.GST_API_KEY }});

const suggestions = await client.autocomplete("{ac_q}");
// Returns up to 10 results in < 50ms
setSuggestions(suggestions);
""", language="typescript")

# ═════════════════════════════════════════════════════════════════════════════
# TAB 6 — Invoice Classify
# ═════════════════════════════════════════════════════════════════════════════
with tab_invoice:
    st.header("Invoice Tax Classifier")
    st.markdown("The flagship endpoint. Pass seller state, buyer state, and line items → get full CGST/SGST/IGST breakdown instantly.")

    col1, col2 = st.columns([1, 1])
    with col1:
        seller_state = st.text_input("Seller State (name / code / 2-digit)", "Maharashtra", key="seller")
        buyer_state  = st.text_input("Buyer State  (name / code / 2-digit)", "Karnataka", key="buyer")

        st.subheader("Line Items")
        num_items = st.number_input("Number of line items", 1, 10, 2)
        items = []
        for i in range(num_items):
            with st.expander(f"Item {i+1}", expanded=(i == 0)):
                hsn = st.text_input(f"HSN/SAC Code", ["10063010", "9983", "72041000", "85171200"][i % 4], key=f"inv_hsn_{i}")
                qty = st.number_input("Quantity", 1.0, key=f"inv_qty_{i}")
                rate = st.number_input("Rate (₹)", 1000.0, key=f"inv_rate_{i}")
                items.append({"hsn_code": hsn, "quantity": qty, "rate": rate})

        if st.button("Classify Invoice", use_container_width=True, type="primary"):
            payload = {"seller_state": seller_state, "buyer_state": buyer_state, "items": items}
            r, ms = api("POST", "/api/v1/invoice/classify", json=payload)
            st.caption(f"HTTP {r.status_code} · {ms}ms")
            if r.ok:
                data = r.json()
                txn_type = data.get("transaction_type", "").upper()
                if txn_type == "INTERSTATE":
                    st.info("↔️ **Interstate transaction** — IGST applies")
                else:
                    st.success("📍 **Intrastate transaction** — CGST + SGST applies")

                rows = []
                for it in data.get("items", []):
                    rows.append({
                        "HSN": it["hsn_code"],
                        "Taxable Value": f"₹{it['taxable_value']:,.2f}",
                        "Tax Rate": it.get("applicable_rate_string", ""),
                        "Tax Amount": f"₹{it['tax_amount']:,.2f}",
                        "Total": f"₹{it['total_amount']:,.2f}",
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                c1, c2, c3 = st.columns(3)
                c1.metric("Base Amount", f"₹{data['total_base_amount']:,.2f}")
                c2.metric("Total Tax", f"₹{data['total_tax_amount']:,.2f}")
                c3.metric("Grand Total", f"₹{data['grand_total']:,.2f}")
            else:
                st.error(r.json())

    with col2:
        st.subheader("Python Snippet")
        st.code(f"""from gstaccelerator import GSTClient, InvoiceRequest, InvoiceItem

async def classify():
    client = GSTClient(api_key="sk_prod_...")
    invoice = await client.invoice.classify(InvoiceRequest(
        seller_state="{seller_state}",
        buyer_state="{buyer_state}",
        items=[
            InvoiceItem(hsn_code="10063010", quantity=1, rate=5000),
            InvoiceItem(hsn_code="9983", quantity=1, rate=2000),
        ]
    ))
    print(f"Grand Total: ₹{{invoice.grand_total}}")
    print(f"Transaction: {{invoice.transaction_type}}")
""", language="python")

# ═════════════════════════════════════════════════════════════════════════════
# TAB 7 — Bulk Description Lookup (up to 100 items)
# ═════════════════════════════════════════════════════════════════════════════
with tab_bulk_lookup:
    st.header("Bulk Description Lookup — Up to 100 Items")
    st.markdown(f"Demonstrate how {pn}'s compliance team can scrub an entire product catalog in a single parallel API call.")

    st.caption("Enter one product description per line:")
    default_bulk = """basmati rice
cotton yarn
steel sheets
software development services
mobile phones
gold jewellery
petroleum products
pharmaceutical tablets
textile garments
construction materials"""
    bulk_text = st.text_area("Descriptions (one per line)", value=default_bulk, height=200)
    branded_bulk = st.checkbox("All items are branded/pre-packaged?", key="branded_bulk")
    b2b_bulk     = st.checkbox("All transactions are B2B?", key="b2b_bulk")
    st_bulk      = st.radio("Supply Type", ["intrastate", "interstate"], horizontal=True, key="st_bulk")

    if st.button(f"Run {pn} Bulk Catalog Scrub", use_container_width=True, type="primary"):
        descriptions = [l.strip() for l in bulk_text.strip().splitlines() if l.strip()]
        if len(descriptions) > 100:
            st.error("Maximum 100 items per request.")
        else:
            payload = [
                {"description": d, "branded": branded_bulk, "b2b": b2b_bulk, "supply_type": st_bulk}
                for d in descriptions
            ]

            progress = st.progress(0, text="Sending bulk request…")
            r, ms = api("POST", "/api/v1/bulk", json=payload)
            progress.progress(100, text=f"Completed in {ms}ms")
            st.caption(f"HTTP {r.status_code} · **{ms}ms** for {len(descriptions)} items in parallel")

            if r.ok:
                results = r.json()
                rows = []
                for desc, matches in zip(descriptions, results):
                    if matches and isinstance(matches, list) and len(matches) > 0:
                        top = matches[0]
                        row = {
                            "Description": desc,
                            "HSN Code": top.get("hsn_code", "—"),
                        }
                        if st_bulk == "intrastate":
                            row["CGST %"] = top.get("tax_rates", {}).get("cgst", "—")
                            row["SGST %"] = top.get("tax_rates", {}).get("sgst", "—")
                        else:
                            row["IGST %"] = top.get("tax_rates", {}).get("igst", "—")
                        
                        row["Confidence"] = top.get("confidence_score", "—")
                        row["Has Condition"] = "⚠️ Yes" if top.get("has_condition") else "✅ No"
                        rows.append(row)
                    else:
                        row = {"Description": desc, "HSN Code": "Not Found"}
                        if st_bulk == "intrastate":
                            row["CGST %"] = "—"
                            row["SGST %"] = "—"
                        else:
                            row["IGST %"] = "—"
                        row["Confidence"] = "—"
                        row["Has Condition"] = "—"
                        rows.append(row)

                df = pd.DataFrame(rows)

                def highlight_not_found(val):
                    return 'background-color: #ff4b4b; color: white' if val == "Not Found" else ''

                st.dataframe(df.style.map(highlight_not_found, subset=["HSN Code"]), use_container_width=True, hide_index=True)
            else:
                st.error(r.json())

# ═════════════════════════════════════════════════════════════════════════════
# TAB 8 — Bulk GSTIN Batch Test
# ═════════════════════════════════════════════════════════════════════════════
with tab_bulk_gstin:
    st.header("Bulk GSTIN Batch Validation")
    st.markdown(f"Paste up to 100 GSTINs to validate in parallel — simulating {pn}'s vendor onboarding or AP reconciliation pipeline.")

    default_gstins = """27AADCB2230M1Z2
29GGGGG1314R9Z6
06BZAHM6385P1Z2
33AAACH7409R1ZZ
24AAACI1681G1ZP
07AABCU9603R1ZX
19AABCT1332L1ZY
09AABCU9603R1ZX
27AAGCM3023P1Z6
32AAACO0512M1ZX
INVALID123456789
27AADCB2230M1Z3
36AABCT1332L1ZK
27AAAPL0442C1ZW
21AABCS1591M1ZA"""

    gstins_text = st.text_area("GSTINs (one per line)", value=default_gstins, height=250)

    if st.button(f"Run {pn} GSTIN Batch Scrub", use_container_width=True, type="primary"):
        gstins = [g.strip() for g in gstins_text.strip().splitlines() if g.strip()]

        if len(gstins) > 100:
            st.error("Maximum 100 GSTINs per batch.")
        else:
            progress = st.progress(0, text="Validating GSTINs in parallel threads…")
            results = []
            start = time.perf_counter()

            session_key = st.session_state.api_key
            def validate_one(gstin, key):
                r, ms = api("GET", f"/api/v1/gstin/{gstin}/validate", api_key=key)
                return gstin, r.json(), ms

            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = {executor.submit(validate_one, g, session_key): g for g in gstins}
                for i, future in enumerate(as_completed(futures), 1):
                    progress.progress(int(i / len(gstins) * 100), text=f"Processed {i}/{len(gstins)}…")
                    gstin, data, ms = future.result()
                    results.append((gstin, data, ms))

            total_ms = int((time.perf_counter() - start) * 1000)
            st.caption(f"**{len(gstins)} GSTINs validated in {total_ms}ms** using parallel connections")

            rows = []
            for gstin, data, ms in results:
                valid = data.get("valid", False)
                rows.append({
                    "GSTIN": gstin,
                    "Valid": "✅ Valid" if valid else "❌ Invalid",
                    "State": data.get("state_name", "—"),
                    "PAN": data.get("pan", "—"),
                    "Error": data.get("error_reason", "") if not valid else "",
                    "Latency (ms)": ms,
                })

            df = pd.DataFrame(rows)

            def highlight_invalid(val):
                return 'background-color: #ff4b4b; color: white' if "Invalid" in str(val) else ''

            valid_count   = sum(1 for r in rows if "Valid" in r["Valid"])
            invalid_count = len(rows) - valid_count

            c1, c2, c3 = st.columns(3)
            c1.metric("Total GSTINs", len(rows))
            c2.metric("✅ Valid", valid_count)
            c3.metric("❌ Invalid / At Risk", invalid_count)

            st.dataframe(df.style.map(highlight_invalid, subset=["Valid"]), use_container_width=True, hide_index=True)

# ═════════════════════════════════════════════════════════════════════════════
# TAB 9 — Meta / Health / Summary
# ═════════════════════════════════════════════════════════════════════════════
with tab_meta:
    st.header("Meta Endpoints — API Health & Coverage")
    st.markdown("Demonstrate API reliability, uptime, and coverage statistics.")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("GET /health", use_container_width=True):
            r, ms = api("GET", "/api/v1/health")
            st.caption(f"HTTP {r.status_code} · {ms}ms")
            data = r.json()
            if r.ok:
                status = data.get("status", "")
                st.success(f"**{status}**") if "healthy" in status.lower() else st.warning(f"**{status}**")
            st.json(data)

    with col2:
        if st.button("GET /meta", use_container_width=True):
            r, ms = api("GET", "/api/v1/meta")
            st.caption(f"HTTP {r.status_code} · {ms}ms")
            st.json(r.json())

    with col3:
        if st.button("GET /rates/summary", use_container_width=True):
            r, ms = api("GET", "/api/v1/rates/summary")
            st.caption(f"HTTP {r.status_code} · {ms}ms")
            if r.ok:
                data = r.json()
                c1, c2 = st.columns(2)
                c1.metric("Total HSN Codes", f"{data.get('total_hsn_codes', 0):,}")
                c2.metric("Total SAC Codes", f"{data.get('total_sac_codes', 0):,}")
                c1.metric("Matched with Rate", f"{data.get('matched_with_rate', 0):,}")
                c2.metric("Has Conditions", f"{data.get('has_conditions', 0):,}")
                st.json(data)
            else:
                st.error(r.json())

    st.divider()
    st.subheader("All Available Endpoints — Reference")
    endpoints = [
        ("GET",  "/api/v1/health",                        "Meta",     "Health check (cached, sub-20ms)"),
        ("GET",  "/api/v1/meta",                          "Meta",     "API metadata and version info"),
        ("GET",  "/api/v1/rates/summary",                 "Meta",     "Coverage stats: HSN/SAC count, schedule breakdown"),
        ("GET",  "/api/v1/gstin/{gstin}/validate",        "GSTIN",    "Full checksum + PAN + state validation"),
        ("GET",  "/api/v1/gstin/{gstin}/state",           "GSTIN",    "Extract state name from GSTIN"),
        ("GET",  "/api/v1/gstin/{gstin}/pan",             "GSTIN",    "Extract PAN + entity type from GSTIN"),
        ("GET",  "/api/v1/hsn/{code}",                    "HSN",      "GST rates for HSN code (8→6→4 fallback)"),
        ("GET",  "/api/v1/gst-rate?hsn=",                 "HSN",      "Alias for HSN lookup"),
        ("GET",  "/api/v1/sac/{code}",                    "SAC",      "GST rates for SAC code (services)"),
        ("GET",  "/api/v1/lookup?q=",                     "Lookup",   "GET alias for description-based lookup"),
        ("POST", "/api/v1/lookup",                        "Lookup",   "Full-text + condition-aware rate lookup"),
        ("POST", "/api/v1/bulk",                          "Lookup",   "Parallel bulk lookup (up to 100 items)"),
        ("GET",  "/api/v1/autocomplete?q=",               "Lookup",   "Live HSN suggestions (sub-50ms, GIN index)"),
        ("POST", "/api/v1/invoice/classify",              "Invoice",  "Full invoice CGST/SGST vs IGST classifier"),
    ]
    df_ep = pd.DataFrame(endpoints, columns=["Method", "Path", "Tag", "Description"])
    st.dataframe(df_ep, use_container_width=True, hide_index=True)
