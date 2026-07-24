from dataclasses import dataclass
from typing import Optional

@dataclass
class TaxRates:
    igst: float
    cgst: float
    sgst: float
    cess: float

@dataclass
class ApplicableRate:
    intrastate: str
    interstate: str

@dataclass
class HSNResult:
    hsn_code: str
    description: str
    tax_rates: TaxRates
    applicable_rate: ApplicableRate
    notification_ref: str
    confidence: float
    needs_review: bool
    condition_applied: Optional[str] = None
    condition_warning: Optional[str] = None
    last_updated: Optional[str] = None

@dataclass
class GSTINResult:
    valid: bool
    gstin: str
    state_code: Optional[str] = None
    state_name: Optional[str] = None
    pan: Optional[str] = None
    entity_type_code: Optional[str] = None
    error_reason: Optional[str] = None
