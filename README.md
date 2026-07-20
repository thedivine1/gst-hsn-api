<div align="center">
  <img src="https://gstaccelerator.in/favicon.ico" width="80" alt="GST Accelerator Logo"/>
  <h1>GST Accelerator</h1>
  <p><strong>The High-Performance India GST API Client & MCP Server</strong></p>

  <p>
    <a href="https://pypi.org/project/gstaccelerator/"><img src="https://img.shields.io/pypi/v/gstaccelerator?style=for-the-badge&color=blue" alt="PyPI version"/></a>
    <a href="https://www.npmjs.com/package/gstaccelerator"><img src="https://img.shields.io/npm/v/gstaccelerator?style=for-the-badge&color=cb3837" alt="NPM version"/></a>
    <a href="https://github.com/thedivine1/gstaccelerator-python/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-success?style=for-the-badge" alt="License"/></a>
    <a href="#"><img src="https://img.shields.io/badge/Build-Passing-success?style=for-the-badge" alt="Build Status"/></a>
  </p>
</div>

> Lightning-fast, async-first HSN/SAC rate lookups and GSTIN validation for enterprise Indian B2B platforms. Features native **Model Context Protocol (MCP)** compliance to instantly connect your AI agents to live Indian tax data.

---

## ⚡ Key Features

Built for the scale and reliability required by modern fintech platforms and high-throughput enterprise systems.

- 🚀 **Lightning-Fast & Async-First:** Non-blocking API requests designed for extreme concurrency and low-latency environments.
- 🛡️ **Enterprise Reliability:** Built-in connection pooling, exponential backoff, and robust error handling for rate limits or inactive/blocked GSTINs.
- 🤖 **Zero-Config MCP Server:** Native integration for AI agents (Claude Desktop, Cursor, Windsurf). Give your LLMs secure access to live tax rate intelligence instantly.
- 🇮🇳 **Fully Compliant:** Always updated with the latest CBIC rate notifications (including GST 2.0).
- 🧩 **Dual SDK:** Available simultaneously for both Python (PyPI) and Node.js/TypeScript (npm).

---

## 📦 Installation

Install the library in your preferred environment:

### Python 3.10+
```bash
pip install gstaccelerator
```

### Node.js (TypeScript Ready)
```bash
npm install gstaccelerator
```

---

## 🚀 Dual-Mode Usage Quickstart

### 1. Standard SDK Usage

Fetch precise tax details or validate business identity via a GSTIN seamlessly in your application.

**Python (asyncio)**
```python
import asyncio
from gstaccelerator import GSTClient

async def check_gstin():
    # Initialize client with your API key
    client = GSTClient(api_key="your_api_key_here")
    
    try:
        # Fetch high-speed GSTIN details
        business = await client.get_gstin_details("27AADCB2230M1Z2")
        print(f"Business Name: {business.legal_name}")
        print(f"Status: {business.status}") # e.g., 'Active'
    finally:
        await client.close()

asyncio.run(check_gstin())
```

**TypeScript / Node.js**
```typescript
import { GSTClient } from 'gstaccelerator';

async function checkGstin() {
    // Initialize client with your API key
    const client = new GSTClient({ apiKey: "your_api_key_here" });
    
    try:
        // Fetch high-speed GSTIN details
        const business = await client.getGstinDetails("27AADCB2230M1Z2");
        console.log(`Business Name: ${business.legalName}`);
        console.log(`Status: ${business.status}`);
    } finally {
        await client.close();
    }
}

checkGstin();
```

### 2. MCP Server Configuration (For AI Agents)

You can mount `gstaccelerator` as a native MCP server to allow AI models to query GST and HSN rates directly during agentic workflows. 

Add the following block to your `claude_desktop_config.json` (or Cursor/Windsurf configuration):

```json
{
  "mcpServers": {
    "gstaccelerator": {
      "command": "npx",
      "args": [
        "-y",
        "gstaccelerator",
        "mcp"
      ],
      "env": {
        "GST_API_KEY": "your_api_key_here"
      }
    }
  }
}
```
*(Python equivalent command: `"command": "gstaccelerator-mcp"`)*

---

## 🛑 Error Handling

Enterprise systems require structured, predictable failures. The SDK bubbles up clean, typed exceptions for edge cases rather than silent failures or raw HTTP dumps.

```python
from gstaccelerator.exceptions import InvalidGSTINError, RateLimitError

try:
    data = await client.get_gstin_details("INVALID123")
except InvalidGSTINError as e:
    print(f"Validation failed: {e.message}") # The GSTIN format is invalid
except RateLimitError as e:
    print(f"Throttled! Retry after {e.retry_after} seconds.")
except Exception as e:
    print("An unexpected network error occurred.")
```

---

## 🔗 Links

- **Website & Dashboard:** [gstaccelerator.in](https://gstaccelerator.in)
- **Documentation:** [docs.gstaccelerator.in](https://docs.gstaccelerator.in)
- **Python Repo:** [github.com/thedivine1/gstaccelerator-python](https://github.com/thedivine1/gstaccelerator-python)
- **Node Repo:** [github.com/thedivine1/gstaccelerator-js](https://github.com/thedivine1/gstaccelerator-js)
