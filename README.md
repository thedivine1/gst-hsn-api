# GST Accelerator API
> The only condition-aware GST rate engine with audit-ready CBIC citations. HSN/SAC lookup, GSTIN validation, invoice classifier.

## Why this exists
Indian billing software hardcodes GST rates. Every GST Council meeting breaks them. We built an API so you never hardcode again.

## Quick start (under 60 seconds)

### cURL
```bash
curl -X GET "https://gstaccelerator.in/api/v1/hsn/84151010" \
     -H "X-API-Key: YOUR_API_KEY"
```

### Python
```python
import requests

url = "https://gstaccelerator.in/api/v1/hsn/84151010"
headers = {"X-API-Key": "YOUR_API_KEY"}
response = requests.get(url, headers=headers)
print(response.json())
```

### Node.js
```javascript
const response = await fetch("https://gstaccelerator.in/api/v1/hsn/84151010", {
  headers: { "X-API-Key": "YOUR_API_KEY" }
});
const data = await response.json();
console.log(data);
```

## What makes it different

| Feature | gstaccelerator.in | Flat lookup APIs | Hardcoded tables |
|---------|------------------|-----------------|------------------|
| **Accuracy** | Daily updates via CBIC | Often outdated | Stale |
| **Condition-aware** | Resolves B2B/B2C, price thresholds | No | Hard to map |
| **Citation** | Official CBIC notification reference | No | No |

## API reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/autocomplete` | GET | Search HSN/SAC codes by description |
| `/api/v1/hsn/{code}` | GET | Get GST rates for an HSN code |
| `/api/v1/sac/{code}` | GET | Get GST rates for an SAC code |
| `/api/v1/gst-rate` | GET | Query rates by description and conditions |
| `/api/v1/invoice/classify` | POST | Classify an invoice line item |
| `/api/v1/gstin/{gstin}/validate` | GET | Validate a GSTIN format and checksum |
| `/api/v1/webhooks` | POST | Register for rate-change webhooks |

## Response schema

```json
{
  "hsn_code": "84151010",
  "description": "Air conditioning machines, comprising a motor-driven fan and elements for changing the temperature and humidity",
  "rates": [
    {
      "igst": 28,
      "cgst": 14,
      "sgst": 14,
      "condition": null
    }
  ],
  "notification_ref": "09/2025-CT(Rate)"
}
```

## SDKs
```bash
pip install gstaccelerator
npm install gstaccelerator
```

## Pricing
[View Plans & Pricing](https://gstaccelerator.in/pricing)

## Status
[System Status & Uptime](https://gstaccelerator.instatus.com)

<!--
GitHub topics: gst-api, hsn-codes, india-gst, condition-resolver, mcp-server, fastapi, nextjs, typescript, rest-api, developer-tools, gstin-validation, invoice-classifier, cbic
-->
