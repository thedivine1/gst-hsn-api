import json, textwrap

logo_b64 = open(r'C:/Users/chaitanya.patankar/gst-hsn-api/scratch/logo_b64.txt').read().strip()
logo_uri = 'data:image/png;base64,' + logo_b64

html = '''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>GST Accelerator — Internal API Tester</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg:#0B0E14;--surface:#111520;--surface-2:#161B27;--border:#1E2A3A;
      --border-2:#263344;--amber:#E8650A;--amber-dim:rgba(232,101,10,0.12);
      --amber-glow:rgba(232,101,10,0.25);--text:#F0F2F5;--text-2:#B4BFCC;
      --text-muted:#6B7B8D;--success:#10B981;--danger:#F04545;--warning:#F59E0B;
      --blue:#60A5FA;--green:#34D399;
    }
    *{box-sizing:border-box;margin:0;padding:0;}
    body{font-family:"Inter",sans-serif;background:var(--bg);color:var(--text);min-height:100vh;}

    /* NAV */
    .nav{height:62px;padding:0 2rem;background:rgba(11,14,20,0.97);border-bottom:1px solid var(--border);
      display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:200;
      backdrop-filter:blur(16px);}
    .nav-brand{display:flex;align-items:center;gap:0.75rem;}
    .nav-logo{height:34px;width:auto;}
    .nav-title{font-weight:700;font-size:1rem;letter-spacing:-0.01em;}
    .nav-badge{font-size:0.68rem;background:rgba(232,101,10,0.15);color:var(--amber);border:1px solid var(--amber-glow);
      border-radius:4px;padding:2px 7px;font-weight:600;margin-left:0.5rem;}
    .nav-right{display:flex;align-items:center;gap:1rem;}
    .status-dot{width:8px;height:8px;border-radius:50%;background:var(--text-muted);}
    .status-dot.running{background:var(--warning);animation:pulse 1s ease-in-out infinite;}
    .status-dot.done{background:var(--success);}
    @keyframes pulse{0%,100%{opacity:1;}50%{opacity:0.4;}}
    #statusText{font-size:0.8rem;color:var(--text-muted);}

    .container{max-width:1400px;margin:0 auto;padding:2rem;}

    /* CONFIG */
    .config-card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:1.5rem 2rem;margin-bottom:1.5rem;}
    .config-row{display:flex;gap:1rem;flex-wrap:wrap;align-items:flex-end;}
    .field{display:flex;flex-direction:column;gap:0.4rem;flex:1;min-width:200px;}
    .field label{font-size:0.7rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:var(--text-muted);}
    .field input,.field select,.field textarea{background:var(--bg);border:1px solid var(--border-2);border-radius:8px;
      padding:0.6rem 0.85rem;color:var(--text);font-family:"JetBrains Mono",monospace;font-size:0.8rem;transition:border-color 0.2s;width:100%;}
    .field input:focus,.field select:focus,.field textarea:focus{outline:none;border-color:var(--amber);}
    .field textarea{resize:vertical;min-height:80px;}
    .btn{padding:0.65rem 1.4rem;border-radius:8px;border:none;font-family:"Inter",sans-serif;font-weight:600;
      font-size:0.85rem;cursor:pointer;transition:all 0.2s;white-space:nowrap;display:inline-flex;align-items:center;gap:0.4rem;}
    .btn-primary{background:var(--amber);color:#fff;}
    .btn-primary:hover{opacity:0.85;transform:translateY(-1px);}
    .btn-outline{background:transparent;border:1px solid var(--border-2);color:var(--text-2);}
    .btn-outline:hover{border-color:var(--amber);color:var(--amber);}
    .btn-green{background:var(--success);color:#fff;}
    .btn-green:hover{opacity:0.85;}
    .btn-row{display:flex;gap:0.75rem;flex-wrap:wrap;margin-top:1rem;}

    /* SUMMARY */
    .summary-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:1rem;margin-bottom:1.5rem;}
    .summary-card{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:1.2rem 1.5rem;}
    .summary-label{font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:var(--text-muted);margin-bottom:0.4rem;}
    .summary-value{font-size:1.75rem;font-weight:700;letter-spacing:-0.02em;}
    .sv-green{color:var(--green);}.sv-red{color:var(--danger);}.sv-amber{color:var(--amber);}.sv-blue{color:var(--blue);}

    /* PROGRESS */
    .progress-wrap{margin-bottom:1.5rem;display:none;}
    .progress-bar-outer{height:6px;background:var(--border);border-radius:3px;overflow:hidden;}
    .progress-bar-inner{height:100%;background:linear-gradient(90deg,var(--amber),#F59E0B);transition:width 0.3s;border-radius:3px;}
    .progress-text{font-size:0.78rem;color:var(--text-muted);margin-top:0.4rem;}

    /* FILTER */
    .filter-bar{display:flex;gap:0.5rem;margin-bottom:1.5rem;flex-wrap:wrap;}
    .filter-btn{padding:0.35rem 0.9rem;border-radius:6px;border:1px solid var(--border-2);background:transparent;
      color:var(--text-muted);font-size:0.78rem;font-weight:500;cursor:pointer;transition:all 0.15s;font-family:inherit;}
    .filter-btn.active{background:var(--amber-dim);border-color:var(--amber);color:var(--amber);}
    .filter-btn:hover:not(.active){border-color:var(--text-muted);color:var(--text-2);}

    /* TEST GROUPS */
    .group-label{font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;
      color:var(--text-muted);margin-bottom:0.6rem;padding-left:0.2rem;}
    .test-group{margin-bottom:1.5rem;}

    /* TEST CARD */
    .test-card{background:var(--surface);border:1px solid var(--border);border-radius:10px;
      overflow:hidden;margin-bottom:0.6rem;transition:border-color 0.2s;}
    .test-card.pass{border-left:3px solid var(--success);}
    .test-card.fail{border-left:3px solid var(--danger);}
    .test-card.running{border-left:3px solid var(--warning);}
    .test-card.pending{border-left:3px solid var(--border-2);}

    .tc-header{display:flex;align-items:center;gap:0.75rem;padding:0.85rem 1.25rem;cursor:pointer;
      transition:background 0.15s;user-select:none;}
    .tc-header:hover{background:rgba(255,255,255,0.02);}
    .method-pill{font-family:"JetBrains Mono",monospace;font-size:0.62rem;font-weight:700;
      padding:2px 6px;border-radius:4px;flex-shrink:0;}
    .method-pill.GET{background:rgba(96,165,250,0.15);color:var(--blue);}
    .method-pill.POST{background:rgba(232,101,10,0.15);color:var(--amber);}
    .tc-name{font-weight:600;font-size:0.85rem;flex:1;}
    .tc-path{font-family:"JetBrains Mono",monospace;font-size:0.72rem;color:var(--text-muted);}
    .tc-meta{display:flex;align-items:center;gap:0.75rem;margin-left:auto;flex-shrink:0;}
    .http-code{font-family:"JetBrains Mono",monospace;font-size:0.72rem;color:var(--text-muted);min-width:30px;text-align:right;}
    .http-code.ok{color:var(--success);}.http-code.err{color:var(--danger);}
    .resp-ms{font-family:"JetBrains Mono",monospace;font-size:0.72rem;min-width:50px;text-align:right;}
    .resp-ms.fast{color:var(--green);}.resp-ms.medium{color:var(--warning);}.resp-ms.slow{color:var(--danger);}
    .status-badge{font-size:0.68rem;font-weight:700;padding:2px 8px;border-radius:4px;}
    .status-badge.pass{background:rgba(16,185,129,0.15);color:var(--success);}
    .status-badge.fail{background:rgba(240,69,69,0.15);color:var(--danger);}
    .status-badge.running{background:rgba(245,158,11,0.15);color:var(--warning);}
    .status-badge.pending{background:rgba(107,123,141,0.1);color:var(--text-muted);}
    .chevron{font-size:0.65rem;color:var(--text-muted);transition:transform 0.2s;flex-shrink:0;}
    .chevron.open{transform:rotate(90deg);}

    /* EDITOR / BODY */
    .tc-body{display:none;border-top:1px solid var(--border);background:var(--surface-2);}
    .tc-body.open{display:block;}
    .tc-body-grid{display:grid;grid-template-columns:1fr 1fr;min-height:0;}
    .tc-pane{padding:1.25rem 1.5rem;}
    .tc-pane:first-child{border-right:1px solid var(--border);}
    .pane-label{font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;
      color:var(--text-muted);margin-bottom:0.75rem;}
    .param-grid{display:flex;flex-direction:column;gap:0.6rem;}
    .param-row{display:grid;grid-template-columns:140px 1fr;gap:0.5rem;align-items:center;}
    .param-key{font-family:"JetBrains Mono",monospace;font-size:0.72rem;color:var(--text-muted);}
    .param-val{background:var(--bg);border:1px solid var(--border-2);border-radius:6px;
      padding:0.4rem 0.65rem;color:var(--text);font-family:"JetBrains Mono",monospace;
      font-size:0.75rem;transition:border-color 0.2s;width:100%;}
    .param-val:focus{outline:none;border-color:var(--amber);}
    textarea.param-val{resize:vertical;min-height:80px;}
    .run-single-btn{margin-top:1rem;}

    .code-block{background:var(--bg);border-radius:8px;padding:0.85rem;font-family:"JetBrains Mono",monospace;
      font-size:0.72rem;color:var(--text-2);overflow-x:auto;white-space:pre-wrap;word-break:break-all;
      max-height:300px;overflow-y:auto;border:1px solid var(--border);}
    .error-block{background:rgba(240,69,69,0.07);border:1px solid rgba(240,69,69,0.2);border-radius:8px;
      padding:0.85rem;font-family:"JetBrains Mono",monospace;font-size:0.72rem;color:var(--danger);}

    .perf-wrap{margin-top:0.85rem;}
    .perf-row{margin-bottom:0.5rem;}
    .perf-label{display:flex;justify-content:space-between;font-size:0.7rem;color:var(--text-muted);margin-bottom:0.3rem;}
    .perf-bar{height:5px;border-radius:3px;background:var(--border);overflow:hidden;}
    .perf-bar-fill{height:100%;border-radius:3px;transition:width 0.6s ease;}

    /* PRINT / PDF */
    @media print {
      body{background:#fff!important;color:#000!important;}
      .nav,.config-card,.filter-bar,.btn-row,.btn,.summary-grid,.progress-wrap{display:none!important;}
      .container{max-width:100%;padding:0;}
      .print-header{display:flex!important;}
      .test-card{border:1px solid #ddd!important;border-left-width:3px!important;margin-bottom:8px;page-break-inside:avoid;}
      .tc-body{display:block!important;background:#fafafa!important;}
      .tc-pane{padding:0.75rem 1rem;}
      .code-block,.error-block{background:#f5f5f5!important;color:#333!important;border:1px solid #ddd!important;font-size:0.65rem!important;}
      .tc-header{background:#fafafa!important;}
      .tc-name{color:#111!important;}
      .tc-path{color:#555!important;}
      .param-key,.param-val{color:#333!important;}
      .summary-print{display:grid!important;}
      .group-label{color:#555!important;}
      .test-card.pass{border-left-color:#10B981!important;}
      .test-card.fail{border-left-color:#F04545!important;}
      .test-card.pending{border-left-color:#ccc!important;}
    }
    .print-header{display:none;align-items:center;gap:1.5rem;padding:1.5rem 0 1rem;border-bottom:2px solid #E8650A;margin-bottom:1.5rem;}
    .print-logo{height:48px;width:auto;}
    .print-title{font-size:1.4rem;font-weight:700;color:#111;}
    .print-subtitle{font-size:0.85rem;color:#666;margin-top:0.2rem;}
    .print-meta{margin-left:auto;font-size:0.78rem;color:#666;text-align:right;}
    .summary-print{display:none;grid-template-columns:repeat(6,1fr);gap:1rem;margin-bottom:1.5rem;padding:1rem;background:#f9f9f9;border:1px solid #eee;border-radius:8px;}
    .sp-card .sp-label{font-size:0.65rem;text-transform:uppercase;font-weight:700;color:#888;margin-bottom:0.2rem;}
    .sp-card .sp-val{font-size:1.2rem;font-weight:700;}
  </style>
</head>
<body>

<!-- PRINT HEADER (only visible when printing) -->
<div class="print-header" id="printHeader">
  <img src="LOGO_PLACEHOLDER" class="print-logo" alt="GST Accelerator">
  <div>
    <div class="print-title">GST Accelerator — API Test Report</div>
    <div class="print-subtitle">Internal Quality Assurance &amp; Performance Report</div>
  </div>
  <div class="print-meta" id="printMeta"></div>
</div>

<div class="summary-print" id="summaryPrint"></div>

<nav class="nav">
  <div class="nav-brand">
    <img src="LOGO_PLACEHOLDER" class="nav-logo" alt="GST Accelerator">
    <span class="nav-title">API Tester</span>
    <span class="nav-badge">INTERNAL</span>
  </div>
  <div class="nav-right">
    <div class="status-dot" id="statusDot"></div>
    <span id="statusText">Ready</span>
  </div>
</nav>

<div class="container">
  <!-- CONFIG -->
  <div class="config-card">
    <div class="config-row">
      <div class="field">
        <label>Base URL</label>
        <input type="text" id="baseUrl" value="http://localhost:8000">
      </div>
      <div class="field">
        <label>API Key (X-API-Key)</label>
        <input type="text" id="apiKey" placeholder="gsta_live_...">
      </div>
    </div>
    <div class="btn-row">
      <button class="btn btn-primary" onclick="runAll()">&#9654; Run All Tests</button>
      <button class="btn btn-outline" onclick="clearAll()">&#10005; Clear Results</button>
      <button class="btn btn-green" onclick="printReport()">&#128438; Export PDF Report</button>
    </div>
  </div>

  <!-- PROGRESS -->
  <div class="progress-wrap" id="progressWrap">
    <div class="progress-bar-outer"><div class="progress-bar-inner" id="progBar" style="width:0%"></div></div>
    <div class="progress-text" id="progText">0 / 0 tests complete</div>
  </div>

  <!-- SUMMARY -->
  <div class="summary-grid">
    <div class="summary-card"><div class="summary-label">Total</div><div class="summary-value sv-blue" id="sTotal">—</div></div>
    <div class="summary-card"><div class="summary-label">Passed</div><div class="summary-value sv-green" id="sPass">—</div></div>
    <div class="summary-card"><div class="summary-label">Failed</div><div class="summary-value sv-red" id="sFail">—</div></div>
    <div class="summary-card"><div class="summary-label">Avg Time</div><div class="summary-value sv-amber" id="sAvg">—</div></div>
    <div class="summary-card"><div class="summary-label">Fastest</div><div class="summary-value sv-green" id="sFastest">—</div></div>
    <div class="summary-card"><div class="summary-label">Slowest</div><div class="summary-value sv-red" id="sSlowest">—</div></div>
  </div>

  <!-- FILTERS -->
  <div class="filter-bar">
    <button class="filter-btn active" onclick="setFilter(this,'all')">All</button>
    <button class="filter-btn" onclick="setFilter(this,'pass')">&#10003; Passed</button>
    <button class="filter-btn" onclick="setFilter(this,'fail')">&#10007; Failed</button>
    <button class="filter-btn" onclick="setFilter(this,'slow')">&#9889; Slow (&gt;500ms)</button>
  </div>

  <div id="testRoot"></div>
</div>

<script>
// ── LOGO DATA URI ──
const LOGO = 'LOGO_DATA_URI';

// ── TEST DEFINITIONS ──
const TESTS = [
  {id:'health',group:'Health & Meta',name:'Health Check',method:'GET',path:'/api/v1/health',expected:200,params:[]},
  {id:'meta',group:'Health & Meta',name:'API Meta',method:'GET',path:'/api/v1/meta',expected:200,params:[]},
  {id:'rates_summary',group:'Health & Meta',name:'Rate Coverage Summary',method:'GET',path:'/api/v1/rates/summary',expected:200,params:[]},
  {id:'hsn_8d',group:'HSN Lookup',name:'HSN — 8-digit exact match',method:'GET',path:'/api/v1/hsn/{code}',expected:200,
    params:[{key:'code',label:'HSN Code',type:'path',val:'84151010'}]},
  {id:'hsn_4d',group:'HSN Lookup',name:'HSN — 4-digit chapter fallback',method:'GET',path:'/api/v1/hsn/{code}',expected:200,
    params:[{key:'code',label:'HSN Code',type:'path',val:'8415'}]},
  {id:'hsn_intra',group:'HSN Lookup',name:'HSN — supply_type=intrastate',method:'GET',path:'/api/v1/hsn/{code}?supply_type={supply_type}',expected:200,
    params:[{key:'code',label:'HSN Code',type:'path',val:'84151010'},{key:'supply_type',label:'Supply Type',type:'path',val:'intrastate'}]},
  {id:'hsn_inter',group:'HSN Lookup',name:'HSN — supply_type=interstate',method:'GET',path:'/api/v1/hsn/{code}?supply_type={supply_type}',expected:200,
    params:[{key:'code',label:'HSN Code',type:'path',val:'84151010'},{key:'supply_type',label:'Supply Type',type:'path',val:'interstate'}]},
  {id:'hsn_404',group:'HSN Lookup',name:'HSN — invalid code (expect 404)',method:'GET',path:'/api/v1/hsn/{code}',expected:404,
    params:[{key:'code',label:'HSN Code',type:'path',val:'99999999'}]},
  {id:'gst_rate',group:'GST Rate',name:'GST Rate by HSN',method:'GET',path:'/api/v1/gst-rate?hsn={hsn}',expected:200,
    params:[{key:'hsn',label:'HSN Code',type:'path',val:'8517'}]},
  {id:'sac_exact',group:'SAC Lookup',name:'SAC — exact match',method:'GET',path:'/api/v1/sac/{code}',expected:200,
    params:[{key:'code',label:'SAC Code',type:'path',val:'9983'}]},
  {id:'sac_intra',group:'SAC Lookup',name:'SAC — with supply_type=intrastate',method:'GET',path:'/api/v1/sac/{code}?supply_type={supply_type}',expected:200,
    params:[{key:'code',label:'SAC Code',type:'path',val:'9983'},{key:'supply_type',label:'Supply Type',type:'path',val:'intrastate'}]},
  {id:'sac_404',group:'SAC Lookup',name:'SAC — invalid code (expect 404)',method:'GET',path:'/api/v1/sac/{code}',expected:404,
    params:[{key:'code',label:'SAC Code',type:'path',val:'9999'}]},
  {id:'lookup_get',group:'Lookup & Search',name:'GET Lookup — keyword search',method:'GET',path:'/api/v1/lookup?q={q}',expected:200,
    params:[{key:'q',label:'Search Query',type:'path',val:'mobile phone'}]},
  {id:'lookup_post',group:'Lookup & Search',name:'POST Lookup — with conditions',method:'POST',path:'/api/v1/lookup',expected:200,
    params:[],body:'{ "description": "cotton t-shirt", "supply_type": "intrastate", "branded": true }'},
  {id:'lookup_threshold',group:'Lookup & Search',name:'POST Lookup — price threshold',method:'POST',path:'/api/v1/lookup',expected:200,
    params:[],body:'{ "description": "footwear", "supply_type": "intrastate", "sale_value_inr": 800 }'},
  {id:'autocomplete',group:'Lookup & Search',name:'Autocomplete suggestions',method:'GET',path:'/api/v1/autocomplete?q={q}',expected:200,
    params:[{key:'q',label:'Query',type:'path',val:'mobile'}]},
  {id:'bulk',group:'Lookup & Search',name:'Bulk Lookup (3 items)',method:'POST',path:'/api/v1/bulk',expected:200,
    params:[],body:'[ { "description": "laptop" }, { "description": "rice" }, { "description": "consulting services" } ]'},
  {id:'gstin_valid',group:'GSTIN Validation',name:'Validate GSTIN — valid',method:'GET',path:'/api/v1/gstin/{gstin}/validate',expected:200,
    params:[{key:'gstin',label:'GSTIN',type:'path',val:'27AAPFU0939F1ZV'}]},
  {id:'gstin_invalid',group:'GSTIN Validation',name:'Validate GSTIN — invalid',method:'GET',path:'/api/v1/gstin/{gstin}/validate',expected:200,
    params:[{key:'gstin',label:'GSTIN',type:'path',val:'INVALIDGSTIN123'}]},
  {id:'gstin_state',group:'GSTIN Validation',name:'GSTIN State info',method:'GET',path:'/api/v1/gstin/{gstin}/state',expected:200,
    params:[{key:'gstin',label:'GSTIN',type:'path',val:'27AAPFU0939F1ZV'}]},
  {id:'gstin_pan',group:'GSTIN Validation',name:'GSTIN PAN extraction',method:'GET',path:'/api/v1/gstin/{gstin}/pan',expected:200,
    params:[{key:'gstin',label:'GSTIN',type:'path',val:'27AAPFU0939F1ZV'}]},
  {id:'inv_intra',group:'Invoice Classifier',name:'Invoice — Intrastate (CGST+SGST)',method:'POST',path:'/api/v1/invoice/classify',expected:200,
    params:[],body:'{ "seller_state": "Maharashtra", "buyer_state": "27", "items": [{ "hsn_code": "8415", "quantity": 2, "rate": 10000 }] }'},
  {id:'inv_inter',group:'Invoice Classifier',name:'Invoice — Interstate (IGST)',method:'POST',path:'/api/v1/invoice/classify',expected:200,
    params:[],body:'{ "seller_state": "Maharashtra", "buyer_state": "Karnataka", "items": [{ "hsn_code": "8415", "quantity": 1, "rate": 15000 }, { "hsn_code": "9983", "quantity": 1, "rate": 5000 }] }'},
  {id:'inv_alias',group:'Invoice Classifier',name:'Invoice — State aliases (mh, tn)',method:'POST',path:'/api/v1/invoice/classify',expected:200,
    params:[],body:'{ "seller_state": "mh", "buyer_state": "tn", "items": [{ "hsn_code": "6101", "quantity": 10, "rate": 500 }] }'},
  {id:'inv_bad_state',group:'Invoice Classifier',name:'Invoice — Bad state (expect 400)',method:'POST',path:'/api/v1/invoice/classify',expected:400,
    params:[],body:'{ "seller_state": "InvalidState", "buyer_state": "Maharashtra", "items": [{ "hsn_code": "8415", "quantity": 1, "rate": 1000 }] }'},
  {id:'inv_bad_hsn',group:'Invoice Classifier',name:'Invoice — Bad HSN (expect 404)',method:'POST',path:'/api/v1/invoice/classify',expected:404,
    params:[],body:'{ "seller_state": "Maharashtra", "buyer_state": "Gujarat", "items": [{ "hsn_code": "99999999", "quantity": 1, "rate": 1000 }] }'},
];

let results = {};
let curFilter = 'all';
let testParams = {};  // id -> {key: value}
let testBodies = {};  // id -> string

// Init defaults
TESTS.forEach(t => {
  testParams[t.id] = {};
  (t.params||[]).forEach(p => { testParams[t.id][p.key] = p.val; });
  if (t.body) testBodies[t.id] = t.body;
});

function resolveUrl(base, t) {
  const params = testParams[t.id] || {};
  let path = t.path;
  Object.entries(params).forEach(([k,v]) => { path = path.replace('{'+k+'}', encodeURIComponent(v)); });
  return base.replace(/\/$/, '') + path;
}

function resolveBody(t) {
  const bodyStr = testBodies[t.id];
  if (!bodyStr) return undefined;
  try { return JSON.parse(bodyStr); } catch(e) { return bodyStr; }
}

function msClass(ms) {
  if (ms == null) return '';
  return ms < 200 ? 'fast' : ms < 500 ? 'medium' : 'slow';
}

function escHtml(s) {
  return String(s||'')
    .replace(/&/g,'&amp;')
    .replace(/</g,'&lt;')
    .replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;');
}

function render() {
  const done = Object.values(results).filter(r=>r.status!=='pending'&&r.status!=='running');
  const passed = done.filter(r=>r.status==='pass').length;
  const failed = done.filter(r=>r.status==='fail').length;
  const times = done.filter(r=>r.ms!=null).map(r=>r.ms);
  const avg = times.length ? Math.round(times.reduce((a,b)=>a+b,0)/times.length) : null;
  const fastest = times.length ? Math.min(...times) : null;
  const slowest = times.length ? Math.max(...times) : null;

  document.getElementById('sTotal').textContent = TESTS.length;
  document.getElementById('sPass').textContent = done.length ? passed : '—';
  document.getElementById('sFail').textContent = done.length ? failed : '—';
  document.getElementById('sAvg').textContent = avg!=null?avg+'ms':'—';
  document.getElementById('sFastest').textContent = fastest!=null?fastest+'ms':'—';
  document.getElementById('sSlowest').textContent = slowest!=null?slowest+'ms':'—';

  const groups = {};
  TESTS.forEach(t => { if(!groups[t.group]) groups[t.group]=[]; groups[t.group].push(t); });

  let html = '';
  Object.entries(groups).forEach(([gName, tests]) => {
    const visible = tests.filter(t => {
      const r = results[t.id]||{status:'pending'};
      if (curFilter==='pass') return r.status==='pass';
      if (curFilter==='fail') return r.status==='fail';
      if (curFilter==='slow') return r.ms!=null&&r.ms>500;
      return true;
    });
    if (!visible.length) return;
    html += `<div class="test-group"><div class="group-label">${gName}</div>`;
    visible.forEach(t => {
      const r = results[t.id]||{status:'pending'};
      const sClass = r.status||'pending';
      const sLabel = {pass:'&#10003; PASS',fail:'&#10007; FAIL',running:'&#9884; Running',pending:'PENDING'}[sClass]||'';
      const ms = r.ms;
      const isOpen = r._open;
      const httpOk = r.httpCode&&(r.httpCode===t.expected);

      // Build param inputs
      let paramRows = '';
      (t.params||[]).forEach(p => {
        const val = testParams[t.id][p.key]||'';
        paramRows += `<div class="param-row">
          <div class="param-key">${p.label}</div>
          <input class="param-val" value="${escHtml(val)}" 
            oninput="testParams['${t.id}']['${p.key}']=this.value">
        </div>`;
      });
      if (t.body !== undefined || testBodies[t.id]) {
        const bodyVal = testBodies[t.id]||'';
        paramRows += `<div style="margin-top:0.5rem;">
          <div class="param-key" style="margin-bottom:0.3rem;">Request Body (JSON)</div>
          <textarea class="param-val" rows="6" 
            oninput="testBodies['${t.id}']=this.value">${escHtml(bodyVal)}</textarea>
        </div>`;
      }

      // Response display
      let resBlock = '';
      if (r.status && r.status !== 'pending') {
        const res = r.error || (r.json ? JSON.stringify(r.json, null, 2) : r.rawText) || '(empty)';
        const cls = r.status==='fail'&&!r.json ? 'error-block' : 'code-block';
        const barW = ms ? Math.min(100, ms/20) : 0;
        const barC = ms<200?'var(--success)':(ms<500?'var(--warning)':'var(--danger)');
        resBlock = `
          <div class="${cls}">${escHtml(res)}</div>
          <div class="perf-wrap">
            <div class="perf-row">
              <div class="perf-label"><span>Response Time</span><span>${ms!=null?ms+'ms':'—'}</span></div>
              <div class="perf-bar"><div class="perf-bar-fill" style="width:${barW}%;background:${barC};"></div></div>
            </div>
          </div>`;
      }

      html += `
        <div class="test-card ${sClass}" id="card-${t.id}">
          <div class="tc-header" onclick="toggleCard('${t.id}')">
            <span class="method-pill ${t.method}">${t.method}</span>
            <div><div class="tc-name">${t.name}</div><div class="tc-path">${t.path}</div></div>
            <div class="tc-meta">
              ${r.httpCode!=null?`<span class="http-code ${httpOk?'ok':'err'}">${r.httpCode}</span>`:''}
              <span class="resp-ms ${msClass(ms)}">${ms!=null?ms+'ms':'' }</span>
              <span class="status-badge ${sClass}">${sLabel}</span>
              <button class="btn btn-primary" style="padding:3px 10px;font-size:0.72rem;" 
                onclick="event.stopPropagation();runOne('${t.id}');">Run</button>
              <span class="chevron ${isOpen?'open':''}" >&#9654;</span>
            </div>
          </div>
          <div class="tc-body ${isOpen?'open':''}" id="body-${t.id}">
            <div class="tc-body-grid">
              <div class="tc-pane">
                <div class="pane-label">Parameters &amp; Request</div>
                <div class="param-grid">${paramRows||('<div style="color:var(--text-muted);font-size:0.78rem">No parameters for this endpoint.</div>')}</div>
              </div>
              <div class="tc-pane">
                <div class="pane-label">Response ${r.httpCode?`(HTTP ${r.httpCode})`:r.status==='pending'?'':'—'}</div>
                ${resBlock||'<div style="color:var(--text-muted);font-size:0.78rem;">Run this test to see the response.</div>'}
              </div>
            </div>
          </div>
        </div>`;
    });
    html += '</div>';
  });
  document.getElementById('testRoot').innerHTML = html;
}

function toggleCard(id) {
  if (!results[id]) results[id] = {status:'pending'};
  results[id]._open = !results[id]._open;
  render();
}

async function runOne(id) {
  const base = document.getElementById('baseUrl').value.trim();
  const key = document.getElementById('apiKey').value.trim();
  const t = TESTS.find(x=>x.id===id);
  if (!t) return;
  await executeTest(t, base, key);
  results[id]._open = true;
  updateSummary();
  render();
}

async function executeTest(t, base, key) {
  const url = resolveUrl(base, t);
  const headers = {'X-API-Key': key, 'Content-Type':'application/json'};
  const body = resolveBody(t);
  const opts = {method:t.method, headers};
  if (body) opts.body = typeof body==='string' ? body : JSON.stringify(body);
  results[t.id] = {status:'running',ms:null};
  render();
  const t0 = performance.now();
  try {
    const resp = await fetch(url, opts);
    const ms = Math.round(performance.now()-t0);
    let json = null, rawText = '';
    try { rawText = await resp.text(); json = JSON.parse(rawText); } catch {}
    const pass = resp.status === t.expected;
    results[t.id] = {status:pass?'pass':'fail',ms,httpCode:resp.status,json,rawText,_open:results[t.id]?results[t.id]._open:false};
  } catch(e) {
    const ms = Math.round(performance.now()-t0);
    results[t.id] = {status:'fail',ms,error:'Network Error: '+e.message,_open:true};
  }
}

async function runAll() {
  const base = document.getElementById('baseUrl').value.trim();
  const key = document.getElementById('apiKey').value.trim();
  TESTS.forEach(t => results[t.id] = {status:'pending'});
  render();
  document.getElementById('progressWrap').style.display = 'block';
  document.getElementById('statusDot').className = 'status-dot running';
  document.getElementById('statusText').textContent = 'Running tests…';
  for (let i=0; i<TESTS.length; i++) {
    document.getElementById('progBar').style.width = (i/TESTS.length*100)+'%';
    document.getElementById('progText').textContent = i+' / '+TESTS.length+' complete';
    await executeTest(TESTS[i], base, key);
    updateSummary(); render();
    await new Promise(r=>setTimeout(r,120));
  }
  document.getElementById('progBar').style.width = '100%';
  document.getElementById('progText').textContent = TESTS.length+' / '+TESTS.length+' complete';
  const failed = Object.values(results).filter(r=>r.status==='fail').length;
  document.getElementById('statusDot').className = 'status-dot done';
  document.getElementById('statusText').textContent = failed ? `Done — ${failed} test(s) failed` : 'All tests passed ✓';
}

function updateSummary() {
  const done = Object.values(results).filter(r=>r.status!=='pending'&&r.status!=='running');
  const passed = done.filter(r=>r.status==='pass').length;
  const failed = done.filter(r=>r.status==='fail').length;
  const times = done.filter(r=>r.ms!=null).map(r=>r.ms);
  document.getElementById('sTotal').textContent = TESTS.length;
  document.getElementById('sPass').textContent = done.length?passed:'—';
  document.getElementById('sFail').textContent = done.length?failed:'—';
  const avg = times.length?Math.round(times.reduce((a,b)=>a+b,0)/times.length):null;
  document.getElementById('sAvg').textContent = avg!=null?avg+'ms':'—';
  document.getElementById('sFastest').textContent = times.length?Math.min(...times)+'ms':'—';
  document.getElementById('sSlowest').textContent = times.length?Math.max(...times)+'ms':'—';
}

function clearAll() {
  results = {};
  document.getElementById('progressWrap').style.display = 'none';
  document.getElementById('statusDot').className = 'status-dot';
  document.getElementById('statusText').textContent = 'Ready';
  document.getElementById('progBar').style.width = '0%';
  updateSummary(); render();
}

function setFilter(btn, type) {
  curFilter = type;
  document.querySelectorAll('.filter-btn').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  render();
}

function printReport() {
  // Populate print header
  const now = new Date();
  const key = document.getElementById('apiKey').value;
  document.getElementById('printMeta').innerHTML =
    '<div>Base URL: '+document.getElementById('baseUrl').value+'</div>'+
    '<div>Generated: '+now.toLocaleString()+'</div>'+
    '<div>API Key: '+(key ? key.slice(0,12)+'…' : 'None')+'</div>';

  // Populate print summary
  const done = Object.values(results).filter(r=>r.status!=='pending'&&r.status!=='running');
  const passed = done.filter(r=>r.status==='pass').length;
  const failed = done.filter(r=>r.status==='fail').length;
  const times = done.filter(r=>r.ms!=null).map(r=>r.ms);
  const avg = times.length?Math.round(times.reduce((a,b)=>a+b,0)/times.length):null;
  document.getElementById('summaryPrint').innerHTML = `
    <div class="sp-card"><div class="sp-label">Total Tests</div><div class="sp-val">${TESTS.length}</div></div>
    <div class="sp-card"><div class="sp-label">Passed</div><div class="sp-val" style="color:#10B981">${passed}</div></div>
    <div class="sp-card"><div class="sp-label">Failed</div><div class="sp-val" style="color:#F04545">${failed}</div></div>
    <div class="sp-card"><div class="sp-label">Avg Time</div><div class="sp-val">${avg!=null?avg+'ms':'—'}</div></div>
    <div class="sp-card"><div class="sp-label">Fastest</div><div class="sp-val" style="color:#10B981">${times.length?Math.min(...times)+'ms':'—'}</div></div>
    <div class="sp-card"><div class="sp-label">Slowest</div><div class="sp-val" style="color:#F04545">${times.length?Math.max(...times)+'ms':'—'}</div></div>`;

  // Open all cards for print
  Object.keys(results).forEach(id => { if (results[id]) results[id]._open = true; });
  render();
  setTimeout(() => window.print(), 400);
}

// Init
render();
</script>
</body>
</html>'''

# Replace placeholders
html = html.replace('LOGO_PLACEHOLDER', logo_uri).replace('LOGO_DATA_URI', logo_uri)

open(r'C:/Users/chaitanya.patankar/gst-hsn-api/api_tester.html', 'w', encoding='utf-8').write(html)
print('Written:', len(html), 'chars')
