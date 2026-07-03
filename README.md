# GST Accelerator API

> India's most accurate GST HSN & SAC lookup API — condition-aware, GST 2.0 compliant, agent-native.

[![Live](https://img.shields.io/badge/live-gstaccelerator.in-E8650A?style=flat-square)](https://gstaccelerator.in)
[![License](https://img.shields.io/badge/license-proprietary-gray?style=flat-square)]()
[![CBIC](https://img.shields.io/badge/source-CBIC%2009%2F2025--CT(Rate)-blue?style=flat-square)](https://cbic-gst.gov.in)

**48,752 HSN codes · 681 SAC codes · CGST / SGST / IGST / Cess · Condition-aware · MCP-ready**

---

## Quickstart

```bash
curl -X GET "https://gstaccelerator.in/api/v1/hsn/8415" \
     -H "X-API-Key: gsta_live_YOUR_KEY"
```

**Response:**

```json
{
  "hsn_code": "8415",
  "description": "Air conditioning machines",
  "cgst": 9.0,
  "sgst": 9.0,
  "igst": 18.0,
  "cess": 0.0,
  "total_intrastate": 18.0,
  "applicable_rate": "CGST 9% + SGST 9% = 18%",
  "notification_ref": "09/2025-CT(Rate), Schedule II",
  "effective_date": "2025-09-22"
}
```

Get your free API key (100 calls/month, no card required) → **[gstaccelerator.in/dashboard](https://gstaccelerator.in/dashboard)**

---

## Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/hsn/{code}` | GST rate for a specific HSN code (goods) |
| `GET` | `/api/v1/sac/{code}` | GST rate for a specific SAC code (services) |
| `GET` | `/api/v1/lookup?q={query}` | Full-text search by product/service description |
| `POST` | `/api/v1/lookup` | Same as GET lookup, body: `{"q": "laptop"}` |
| `POST` | `/api/v1/bulk` | Batch lookup — up to 100 items per request |
| `GET` | `/api/v1/autocomplete?q={query}` | Autocomplete HSN/SAC descriptions |
| `GET` | `/api/v1/rates/summary` | Coverage stats and rate slab breakdown |
| `GET` | `/health` | Liveness check with uptime and DB status |
| `GET` | `/meta` | API metadata, code counts, MCP endpoint |

Full interactive docs → **[gstaccelerator.in/docs](https://gstaccelerator.in/docs)**

---

## Authentication

All `/api/v1/` endpoints require an `X-API-Key` header:

```bash
-H "X-API-Key: gsta_live_YOUR_KEY"
```

Generate a key for free at **[gstaccelerator.in/dashboard](https://gstaccelerator.in/dashboard)**.

---

## SAC Code Example

```bash
curl -X GET "https://gstaccelerator.in/api/v1/sac/998314" \
     -H "X-API-Key: gsta_live_YOUR_KEY"
```

```json
{
  "sac_code": "998314",
  "description": "Legal advisory and representation services",
  "cgst": 9.0,
  "sgst": 9.0,
  "igst": 18.0,
  "total_intrastate": 18.0,
  "notification_ref": "09/2025-CT(Rate)"
}
```

## Bulk Lookup Example

```bash
curl -X POST "https://gstaccelerator.in/api/v1/bulk" \
     -H "X-API-Key: gsta_live_YOUR_KEY" \
     -H "Content-Type: application/json" \
     -d '[{"q": "laptop"}, {"q": "cement"}, {"hsn": "0101"}]'
```

---

## MCP (Model Context Protocol)

The API exposes an MCP endpoint for use with AI agents (Claude, GPT, etc.):

```
https://gstaccelerator.in/mcp/sse
```

Add it to your MCP client config and query GST rates from any AI workflow.

---

## Pricing

| Plan | Price | Calls | Notes |
|------|-------|-------|-------|
| **Free** | ₹0 | 100/month | No card required |
| **Developer** | ₹399 | 5,000 + ₹0.10/extra | 30 days access |
| **Pro** | ₹1,499 | 50,000 + ₹0.08/extra | 30 days access |
| **Business** | ₹5,999 | Unlimited | 30 days access, GST invoice |

→ **[View pricing & pay via Razorpay](https://gstaccelerator.in/pricing)**

---

## Data Source

All rates are sourced from:
- **CBIC Notification 09/2025-CT(Rate)** — effective 22 September 2025
- **CBIC Notification 10/2025-CT(Rate)** — Compensation Cess (03/2025)

Data is condition-aware — the API resolves conditional GST rates (e.g. price thresholds, end-use, supply nature) automatically.

---

## Stack

- **FastAPI** (Python) — REST API
- **Supabase** (PostgreSQL) — rate database
- **Vercel** — deployment
- **Razorpay** — payments

---

## Topics

`gst-api` `hsn` `sac` `india` `mcp-server` `cgst` `sgst` `igst` `tax-api` `fastapi` `supabase` `gst-2-0`

---

## Contact

- Docs: [gstaccelerator.in/docs](https://gstaccelerator.in/docs)
- Email: [hello@gstaccelerator.in](mailto:hello@gstaccelerator.in)
- Privacy: [gstaccelerator.in/privacy](https://gstaccelerator.in/privacy)
- Terms: [gstaccelerator.in/terms](https://gstaccelerator.in/terms)
