from typing import Optional, Dict, Any

class GSTAcceleratorError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None, response_body: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_body = response_body or {}

class AuthenticationError(GSTAcceleratorError): pass
class RateLimitError(GSTAcceleratorError): pass
class NotFoundError(GSTAcceleratorError): pass
class ValidationError(GSTAcceleratorError): pass
class ServerError(GSTAcceleratorError): pass
