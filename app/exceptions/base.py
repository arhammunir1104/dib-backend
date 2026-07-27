# app/exceptions/base.py
class DibAIException(Exception):
    """Base exception for the DIB Circular AI system."""
    def __init__(self, message: str, detail: str = None):
        self.message = message
        self.detail = detail
        super().__init__(message)

class ProcessingError(DibAIException):
    """Raised when a processing step fails."""
    pass

class ValidationError(DibAIException):
    """Raised when extracted data fails validation."""
    pass

class ConfigurationError(DibAIException):
    """Raised when system configuration is invalid."""
    pass