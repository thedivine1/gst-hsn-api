# GST Accelerator API

> India's most accurate GST HSN/SAC lookup and GSTIN validation API. Condition-aware, GST 2.0 compliant, and agent-native.

[![PyPI version](https://img.shields.io/pypi/v/gstaccelerator)](https://pypi.org/project/gstaccelerator/)
[![npm version](https://img.shields.io/npm/v/gstaccelerator)](https://www.npmjs.com/package/gstaccelerator)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Base URL:** `https://gstaccelerator.in/api/v1`  
**Docs:** [gstaccelerator.in/docs](https://gstaccelerator.in/docs)  
**Dashboard / Free Key:** [gstaccelerator.in/dashboard](https://gstaccelerator.in/dashboard)

---

## What this API does

- **HSN Lookup** — Get IGST, CGST, SGST, CESS, and notification references for any 4, 6, or 8-digit HSN code
- **SAC Lookup** — Same for service codes (681 SAC codes, codes starting with `99` are automatically routed to the SAC database)
- **Intelligent Product Search** — Natural language search maps product descriptions to the correct HSN code with condition-aware rate resolution
- **Condition-Aware Rates** — Resolves GST notification conditions automatically: branded vs unbranded, B2B vs B2C, sale value thresholds, supply type (intrastate/interstate/export/SEZ)
- **GSTIN Validation** — Validates GSTIN checksum, extracts PAN and state jurisdiction
- **Bulk Lookup** — Process up to 100 items in a single request
- **Invoice Classifier** — Pass seller/buyer state + line items; get full CGST+SGST or IGST tax breakdown per item and document totals
- **Autocomplete** — Fast trigram-indexed partial-text search on HSN/SAC descriptions (GIN index, <10ms)

**Data source:** CBIC Notification 09/2025-CT(Rate), effective 22 September 2025  
**Coverage:** 48,752 HSN codes · 681 SAC codes · 8 GST rate slabs

---

## Quick Start

### Authentication

All endpoints require an `X-API-Key` header. Get a free key (100 calls/month, no card) at [gstaccelerator.in/dashboard](https://gstaccelerator.in/dashboard).

```bash
# HSN lookup
curl https://gstaccelerator.in/api/v1/hsn/84151010 \
  -H "X-API-Key: YOUR_KEY"

# Natural language search
curl "https://gstaccelerator.in/api/v1/lookup?q=cotton+shirt" \
  -H "X-API-Key: YOUR_KEY"

# GSTIN validation
curl https://gstaccelerator.in/api/v1/gstin/27AAPFU0939F1ZV/validate \
  -H "X-API-Key: YOUR_KEY"

# Invoice classifier (mixed HSN goods + SAC services)
curl -X POST https://gstaccelerator.in/api/v1/invoice/classify \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "seller_state": "Maharashtra",
    "buyer_state": "Karnataka",
    "items": [
      {"hsn_code": "84151010", "quantity": 1, "rate": 50000},
      {"hsn_code": "9983",     "quantity": 1, "rate": 5000}
    ]
  }'
```

---

## Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/api/v1/hsn/{code}` | HSN lookup by code (4, 6, or 8-digit) |
| `GET`  | `/api/v1/sac/{code}` | SAC lookup for services |
| `GET`  | `/api/v1/lookup?q={description}` | Natural language product search |
| `POST` | `/api/v1/lookup` | Advanced lookup with condition flags |
| `GET`  | `/api/v1/autocomplete?q={term}` | Fast trigram partial-text search on descriptions |
| `POST` | `/api/v1/bulk` | Batch lookup (up to 100 items) |
| `POST` | `/api/v1/invoice/classify` | Invoice tax classifier — CGST/SGST or IGST breakdown |
| `GET`  | `/api/v1/gstin/{gstin}/validate` | Full GSTIN validation |
| `GET`  | `/api/v1/gstin/{gstin}/state` | Extract state from GSTIN |
| `GET`  | `/api/v1/gstin/{gstin}/pan` | Extract PAN from GSTIN |
| `GET`  | `/api/v1/rates/summary` | Aggregate stats — total codes, rate slabs, schedule breakdown |
| `GET`  | `/api/v1/health` | API health check |
| `GET`  | `/api/v1/meta` | Database stats and version info |

---

## Sample Responses

```json
// GET /api/v1/hsn/84151010
{
  "hsn_code": "84151010",
  "hsn_description": "Split system air conditioners of a kind used for buildings",
  "tax_rates": {
    "igst": 28.0,
    "cgst": 14.0,
    "sgst": 14.0,
    "cess": 0.0,
    "total_intrastate": 28.0,
    "total_interstate": 28.0
  },
  "applicable_rate": {
    "intrastate": "CGST 14% + SGST 14% = 28%",
    "interstate": "IGST 28%"
  },
  "notification_ref": "09/2025-CT(Rate)",
  "effective_date": "2025-09-22",
  "has_condition": false,
  "source": "GST Council Notification 09/2025-CT(Rate)"
}
```

```json
// POST /api/v1/invoice/classify
// Request: seller Maharashtra, buyer Karnataka (interstate), 1 HSN + 1 SAC item
{
  "transaction_type": "interstate",
  "items": [
    {
      "hsn_code": "84151010",
      "description": "Split system air conditioners...",
      "supply_type": "interstate",
      "tax_rates": { "igst": 28.0, "cgst": 0, "sgst": 0, "cess": 0.0 },
      "taxable_value": 50000.0,
      "tax_amount": 14000.0,
      "total_amount": 64000.0,
      "applicable_rate_string": "IGST 28.0%"
    },
    {
      "hsn_code": "9983",
      "description": "Other professional, technical and business services",
      "supply_type": "interstate",
      "tax_rates": { "igst": 18.0, "cgst": 0, "sgst": 0, "cess": 0.0 },
      "taxable_value": 5000.0,
      "tax_amount": 900.0,
      "total_amount": 5900.0,
      "applicable_rate_string": "IGST 18.0%"
    }
  ],
  "total_base_amount": 55000.0,
  "total_igst_amount": 14900.0,
  "total_tax_amount": 14900.0,
  "grand_total": 69900.0
}
```

---

## SDK — Python

```bash
pip install gstaccelerator
```

```python
from gstaccelerator import GSTAccelerator

gst = GSTAccelerator(api_key="YOUR_KEY")

# HSN lookup
result = gst.hsn.get("84151010")
print(result["tax_rates"]["igst"])   # 28.0

# SAC lookup (services — codes starting with 99)
sac = gst.sac.get("9983")

# Natural language search
results = gst.lookup("cotton shirt", branded=False, supply_type="intrastate")

# Autocomplete
suggestions = gst.autocomplete("mobile")  # returns ranked HSN/SAC matches

# Invoice classifier — accepts HSN and SAC codes mixed
invoice = gst.invoice.classify(
    seller_state="Maharashtra",
    buyer_state="Karnataka",
    items=[
        {"hsn_code": "84151010", "quantity": 1, "rate": 50000},
        {"hsn_code": "9983",     "quantity": 1, "rate": 5000},
    ]
)
print(invoice["transaction_type"])  # "interstate"
print(invoice["grand_total"])       # 69900.0

# Bulk lookup — pass list of LookupRequest dicts
results = gst.bulk([
    {"description": "smartphone"},
    {"description": "laptop"},
])

# GSTIN validation
info = gst.gstin.validate("27AAPFU0939F1ZV")
print(info["valid"], info["state_name"])   # True, Maharashtra
```

> **Authentication note:** Pass your key as `api_key=` in the constructor.  
> The SDK sends it as `X-API-Key` header automatically.

**PyPI:** [pypi.org/project/gstaccelerator](https://pypi.org/project/gstaccelerator/)  
**Repo:** [github.com/thedivine1/gstaccelerator-python](https://github.com/thedivine1/gstaccelerator-python)

---

## SDK — JavaScript / TypeScript

```bash
npm install gstaccelerator
```

```typescript
import GSTAccelerator from 'gstaccelerator';

const gst = new GSTAccelerator({ apiKey: 'YOUR_KEY' });

// HSN lookup
const rate = await gst.hsn.get('84151010');
console.log(rate.tax_rates.igst);   // 28

// SAC lookup (services)
const sac = await gst.sac.get('9983');

// Natural language search
const results = await gst.lookup('air conditioner', { supplyType: 'intrastate' });

// Autocomplete
const suggestions = await gst.autocomplete('mobile');

// Invoice classifier — HSN and SAC codes accepted together
const invoice = await gst.invoice.classify(
  'Maharashtra',
  'Karnataka',
  [
    { hsn_code: '84151010', quantity: 1, rate: 50000 },
    { hsn_code: '9983',     quantity: 1, rate: 5000  },
  ]
);
console.log(invoice.transaction_type);  // 'interstate'
console.log(invoice.grand_total);       // 69900

// GSTIN validation
const info = await gst.gstin.validate('27AAPFU0939F1ZV');
console.log(info.valid, info.state_name);   // true, Maharashtra
```

> **Authentication note:** Pass your key as `apiKey:` in the constructor options.  
> The SDK sends it as `X-API-Key` header automatically.

**npm:** [npmjs.com/package/gstaccelerator](https://www.npmjs.com/package/gstaccelerator)  
**Repo:** [github.com/thedivine1/gstaccelerator-js](https://github.com/thedivine1/gstaccelerator-js)

---

## MCP Server — AI Agents (Claude, GPT, etc.)

The package includes a native **Model Context Protocol (MCP)** server. Any LLM agent can query live GST data directly.

```bash
# Run via npx (Node.js)
GST_API_KEY=your_key npx gstaccelerator-mcp

# Run via Python
GST_API_KEY=your_key gstaccelerator-mcp
```

### Claude Desktop configuration

Add this to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "gstaccelerator": {
      "command": "npx",
      "args": ["-y", "-p", "gstaccelerator", "gstaccelerator-mcp"],
      "env": {
        "GST_API_KEY": "YOUR_API_KEY"
      }
    }
  }
}
```

### Available MCP Tools

| Tool | Description |
|------|-------------|
| `hsn_lookup` | Get GST rate for a specific HSN code |
| `sac_lookup` | Get GST rate for a specific SAC code (services) |
| `gst_search` | Search by product description |
| `invoice_classify` | Classify invoice items and compute tax breakdown |
| `gstin_validate` | Validate a GSTIN and extract components |

---

## Pricing

| Plan | Price | Calls/month |
|------|-------|-------------|
| **Free** | ₹0 | 100 |
| **Developer** | ₹399 | 5,000 |
| **Pro** | ₹1,499 | 50,000 |
| **Business** | ₹5,999 | Unlimited |

No credit card required for the free tier. [See full pricing →](https://gstaccelerator.in/pricing)

---

## Tech Stack

- **Backend:** Python (FastAPI + Uvicorn) with async PostgreSQL (asyncpg)
- **Database:** Supabase (PostgreSQL) — 48,752 HSN records, 681 SAC records
- **Auth:** SHA-256 hashed API keys with in-memory TTL cache (60s) — eliminates per-request DB lookups
- **Rate Limiting:** Per-IP (100 req/min) + per-key monthly quota with buffered write-back
- **Caching:**
  - In-process LRU cache (2,000 entries, 1-hour TTL) for lookup/search queries
  - 24-hour in-memory TTL cache for `/rates/summary` (avoids repeated full-table aggregates)
- **Search Index:** GIN trigram indexes (`pg_trgm`) on `hsn_description` and `sac_description` — reduces autocomplete latency from ~200ms to <10ms
- **MCP:** Official `@modelcontextprotocol/sdk` (Node.js) and `mcp` (Python)

---

## License

MIT — see [LICENSE](LICENSE)

---

*Data source: CBIC Notification 09/2025-CT(Rate), effective 22 September 2025. Not legal or tax advice.*
