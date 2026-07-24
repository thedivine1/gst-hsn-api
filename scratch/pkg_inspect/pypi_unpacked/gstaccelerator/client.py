import httpx
import time
from typing import List, Dict, Optional, Any
from .exceptions import (
    GSTAcceleratorError, AuthenticationError, RateLimitError,
    NotFoundError, ValidationError, ServerError
)

class _BaseClient:
    def __init__(self, client: httpx.Client):
        self._client = client

    def _request(self, method: str, path: str, **kwargs) -> Any:
        max_retries = self._client._gsta_max_retries
        retry_delay = self._client._gsta_retry_delay
        
        for attempt in range(max_retries + 1):
            try:
                response = self._client.request(method, path, **kwargs)
                
                if response.status_code < 400:
                    return response.json() if response.content else {}
                    
                resp_json = response.json() if response.content else {}
                
                if response.status_code == 401:
                    raise AuthenticationError("Authentication failed", 401, resp_json)
                elif response.status_code == 404:
                    raise NotFoundError("Resource not found", 404, resp_json)
                elif response.status_code in (400, 422):
                    raise ValidationError("Validation error", response.status_code, resp_json)
                elif response.status_code == 429:
                    if attempt < max_retries:
                        retry_after = response.headers.get("Retry-After")
                        sleep_time = float(retry_after) if retry_after else retry_delay * (2 ** attempt)
                        time.sleep(sleep_time)
                        continue
                    raise RateLimitError("Rate limit exceeded", 429, resp_json)
                elif response.status_code >= 500:
                    if attempt < max_retries:
                        time.sleep(retry_delay * (2 ** attempt))
                        continue
                    raise ServerError(f"Server error: {response.status_code}", response.status_code, resp_json)
                
                response.raise_for_status()
                
            except httpx.RequestError as e:
                if attempt < max_retries:
                    time.sleep(retry_delay * (2 ** attempt))
                    continue
                raise GSTAcceleratorError(f"Request failed: {str(e)}")
        
        return {}

class HSNClient(_BaseClient):
    def get(self, code: str) -> dict:
        return self._request("GET", f"/api/v1/hsn/{code}")

class SACClient(_BaseClient):
    def get(self, code: str) -> dict:
        return self._request("GET", f"/api/v1/sac/{code}")

class GSTINClient(_BaseClient):
    def validate(self, gstin: str) -> dict:
        return self._request("GET", f"/api/v1/gstin/{gstin}/validate")
        
    def state(self, gstin: str) -> dict:
        return self._request("GET", f"/api/v1/gstin/{gstin}/state")
        
    def pan(self, gstin: str) -> dict:
        return self._request("GET", f"/api/v1/gstin/{gstin}/pan")


class InvoiceClient(_BaseClient):
    def classify(
        self,
        seller_state: str,
        buyer_state: str,
        items: List[Dict],
    ) -> dict:
        """
        Classify invoice line items as CGST+SGST (intrastate) or IGST (interstate)
        and return a complete tax breakdown per item and for the full document.

        Args:
            seller_state: Seller's state — full name ("Maharashtra"), abbreviation
                          ("MH"), or 2-digit GST code ("27").
            buyer_state:  Buyer's state — same format as seller_state.
            items:        List of dicts, each with keys:
                            - hsn_code  (str)   e.g. "61099090"
                            - quantity   (float) e.g. 10
                            - rate       (float) unit price in INR e.g. 500.0

        Returns:
            dict with keys:
                transaction_type    "intrastate" | "interstate"
                items               list of per-line breakdowns
                total_base_amount   float
                total_cgst_amount   float
                total_sgst_amount   float
                total_igst_amount   float
                total_cess_amount   float
                total_tax_amount    float
                grand_total         float

        Example::

            result = gst.invoice.classify(
                seller_state="Maharashtra",
                buyer_state="Karnataka",
                items=[
                    {"hsn_code": "61099090", "quantity": 10, "rate": 500},
                    {"hsn_code": "84713010", "quantity": 2,  "rate": 45000},
                ]
            )
            print(result["transaction_type"])  # "interstate"
            print(result["grand_total"])        # e.g. 112400.0
        """
        payload = {
            "seller_state": seller_state,
            "buyer_state":  buyer_state,
            "items":        items,
        }
        return self._request("POST", "/api/v1/invoice/classify", json=payload)

class GSTAccelerator:
    def __init__(
        self,
        api_key: str = "",
        base_url: str = "https://gstaccelerator.in",
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        from importlib.metadata import version, PackageNotFoundError
        try:
            pkg_version = version("gstaccelerator")
        except PackageNotFoundError:
            pkg_version = "0.1.0"
            
        headers = {
            "User-Agent": f"gstaccelerator-python/{pkg_version}",
            "Content-Type": "application/json"
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
            
        self._client = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            headers=headers
        )
        self._client._gsta_max_retries = max_retries
        self._client._gsta_retry_delay = retry_delay
        
        self.hsn    = HSNClient(self._client)
        self.sac    = SACClient(self._client)
        self.gstin  = GSTINClient(self._client)
        self.invoice = InvoiceClient(self._client)

    def lookup(
        self,
        description: str,
        supply_type: Optional[str] = None,
        branded: Optional[bool] = None,
        sale_value_inr: Optional[float] = None,
        state_of_supply: Optional[str] = None
    ) -> List[Dict]:
        payload = {"description": description}
        if supply_type is not None: payload["supply_type"] = supply_type
        if branded is not None: payload["branded"] = branded
        if sale_value_inr is not None: payload["sale_value_inr"] = sale_value_inr
        if state_of_supply is not None: payload["state_of_supply"] = state_of_supply
        
        base = _BaseClient(self._client)
        return base._request("POST", "/api/v1/lookup", json=payload)

    def autocomplete(self, query: str) -> List[str]:
        base = _BaseClient(self._client)
        return base._request("GET", "/api/v1/autocomplete", params={"q": query})

    def bulk(self, descriptions: List[str]) -> List[List[Dict]]:
        base = _BaseClient(self._client)
        return base._request("POST", "/api/v1/bulk", json={"descriptions": descriptions})
        
    def health(self) -> dict:
        base = _BaseClient(self._client)
        return base._request("GET", "/api/v1/health")
        
    def meta(self) -> dict:
        base = _BaseClient(self._client)
        return base._request("GET", "/api/v1/meta")
        
    def close(self):
        self._client.close()
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
