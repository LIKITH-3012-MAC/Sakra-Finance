"""
Custom exception classes for Sakra Finance application.
Provides domain-specific exceptions that map to HTTP status codes.
"""


class SakraException(Exception):
    """Base exception for all Sakra Finance application errors."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(self.message)


class CustomerNotFound(SakraException):
    """Raised when a customer record is not found."""

    def __init__(self, message: str = "Customer not found"):
        super().__init__(status_code=404, message=message)


class LoanNotFound(SakraException):
    """Raised when a loan record is not found."""

    def __init__(self, message: str = "Loan not found"):
        super().__init__(status_code=404, message=message)


class DuplicateCustomer(SakraException):
    """Raised when attempting to create a customer that already exists."""

    def __init__(self, message: str = "Customer already exists"):
        super().__init__(status_code=409, message=message)


class DuplicateAadhaar(SakraException):
    """Raised when a duplicate Aadhaar number is detected."""

    def __init__(self, message: str = "A customer with this Aadhaar number already exists"):
        super().__init__(status_code=409, message=message)


class PermissionDenied(SakraException):
    """Raised when a user lacks required permissions."""

    def __init__(self, message: str = "You do not have permission to perform this action"):
        super().__init__(status_code=403, message=message)


class TokenExpired(SakraException):
    """Raised when a JWT token has expired."""

    def __init__(self, message: str = "Token has expired"):
        super().__init__(status_code=401, message=message)


class PaymentError(SakraException):
    """Raised for payment processing errors."""

    def __init__(self, message: str = "Payment processing error"):
        super().__init__(status_code=400, message=message)


class ExportError(SakraException):
    """Raised when data export fails."""

    def __init__(self, message: str = "Export failed"):
        super().__init__(status_code=500, message=message)


class ConflictError(SakraException):
    """Raised on optimistic locking failures when data has been modified concurrently."""

    def __init__(self, message: str = "Record has been modified by another user. Please refresh and try again."):
        super().__init__(status_code=409, message=message)
