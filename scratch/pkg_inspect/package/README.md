# GST Accelerator JavaScript Client

JavaScript client for the GST Accelerator API — India GST HSN/SAC lookup, GSTIN validation, and condition resolver.

## Installation

```bash
npm install gstaccelerator
```

## Quickstart

### Node.js (CommonJS)

```javascript
const { GSTAccelerator } = require('gstaccelerator');
const gst = new GSTAccelerator({ apiKey: 'your_api_key' });

async function run() {
  const result = await gst.hsn.get('84151010');
  console.log(result);
}
run();
```

### Browser fetch (ESM)

```javascript
import { GSTAccelerator } from 'gstaccelerator';
const gst = new GSTAccelerator({ apiKey: 'your_api_key' });

// Note: Ensure your API keys are not exposed in client-side code in production.
gst.hsn.get('84151010').then(console.log);
```

### MCP Agent Use (Claude/GPT-4o)

```javascript
import { GSTAcceleratorMCPTools } from 'gstaccelerator';

console.log(GSTAcceleratorMCPTools);
```

## API Reference

| Resource | Method | Description |
|---|---|---|
| `gst.hsn` | `get(code: string)` | HSN lookup |
| `gst.sac` | `get(code: string)` | SAC lookup |
| `gst` | `lookup(description: string, options?: LookupOptions)` | Description search |
| `gst` | `autocomplete(query: string)` | Autocomplete |
| `gst` | `bulk(descriptions: string[])` | Bulk lookup |
| `gst.gstin` | `validate(gstin: string)` | GSTIN validation |
| `gst.gstin` | `state(gstin: string)` | State info |
| `gst.gstin` | `pan(gstin: string)` | PAN info |
| `gst` | `health()` | Health check |
| `gst` | `meta()` | Meta data |

## Error Handling

```javascript
import { GSTAccelerator, RateLimitError, AuthenticationError } from 'gstaccelerator';

const gst = new GSTAccelerator({ apiKey: 'your_api_key' });

async function checkRate() {
  try {
    const result = await gst.hsn.get('84151010');
  } catch (error) {
    if (error instanceof AuthenticationError) {
      console.error('Auth failed:', error.message);
    } else if (error instanceof RateLimitError) {
      console.error('Rate limited. Retry after:', error.retryAfter);
    } else {
      console.error('Error:', error.message);
    }
  }
}
```

For full documentation, visit: https://gstaccelerator.in/docs
