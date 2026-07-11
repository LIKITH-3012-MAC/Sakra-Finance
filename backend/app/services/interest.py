"""
Interest calculation service supporting multiple interest formulas.
"""
from decimal import Decimal, ROUND_HALF_UP

QUANTIZE_PRECISION = Decimal("0.01")


def calculate_interest(
    principal: Decimal,
    rate: Decimal,
    formula: str,
    duration_days: int = 100,
) -> Decimal:
    """
    Calculate total interest for a loan based on the interest formula.

    Args:
        principal: The loan principal amount
        rate: Interest rate as a percentage (e.g., 2.75 for 2.75%)
        formula: Interest formula type ('FLAT', 'REDUCING', 'MONTHLY', 'DAILY', 'COMPOUND')
        duration_days: Term of the loan in days (default 100)

    Returns:
        Total interest amount, quantized to 2 decimal places
    """
    formula = formula.upper()
    rate_decimal = rate / Decimal("100")

    if formula == "FLAT":
        # Simple flat interest: principal * rate / 100
        interest = principal * rate_decimal
    elif formula == "REDUCING":
        # Reducing balance: interest on average outstanding (approximation)
        interest = principal * rate / Decimal("200")
    elif formula == "MONTHLY":
        # Monthly interest: rate is monthly percentage. Number of months is duration_days / 30.
        months = Decimal(str(duration_days)) / Decimal("30")
        interest = principal * rate_decimal * months
    elif formula == "DAILY":
        # Daily interest: rate is daily percentage. Number of days is duration_days.
        interest = principal * rate_decimal * Decimal(str(duration_days))
    elif formula == "COMPOUND":
        # Compound interest over the term placeholder (rate applied as percentage)
        interest = principal * rate_decimal
    else:
        # Default to flat if formula is unrecognized
        interest = principal * rate_decimal

    return interest.quantize(QUANTIZE_PRECISION, rounding=ROUND_HALF_UP)


def get_loan_balance_summary(
    principal: Decimal,
    rate: Decimal,
    formula: str,
    total_paid: Decimal,
    duration_days: int = 100,
) -> dict:
    """
    Calculate comprehensive loan balance summary.

    Args:
        principal: Loan principal amount
        rate: Interest rate percentage
        formula: Interest formula type
        total_paid: Total amount already paid
        duration_days: Term of the loan in days (default 100)

    Returns:
        Dictionary with:
        - principal: Original principal amount
        - interest: Total calculated interest
        - total_due: principal + interest
        - total_paid: Amount paid so far
        - remaining_balance: Remaining principal balance (principal - total_paid, min 0)
        - interest_outstanding: Outstanding interest amount
        - total_outstanding_with_interest: Total remaining including interest
    """
    interest = calculate_interest(principal, rate, formula, duration_days)
    total_due = (principal + interest).quantize(QUANTIZE_PRECISION, rounding=ROUND_HALF_UP)

    # Remaining balance must always be calculated from total due (repayable), not principal
    remaining_balance = max(total_due - total_paid, Decimal("0")).quantize(
        QUANTIZE_PRECISION, rounding=ROUND_HALF_UP
    )

    # Interest outstanding calculation (for compatibility/analytics)
    if total_paid >= principal:
        interest_paid = total_paid - principal
        interest_outstanding = max(interest - interest_paid, Decimal("0"))
    else:
        interest_outstanding = interest

    interest_outstanding = interest_outstanding.quantize(QUANTIZE_PRECISION, rounding=ROUND_HALF_UP)

    # Total outstanding with interest is exactly the remaining balance
    total_outstanding_with_interest = remaining_balance

    completion_percent = float((total_paid / total_due) * 100) if total_due > 0 else 100.0

    return {
        "principal": principal.quantize(QUANTIZE_PRECISION, rounding=ROUND_HALF_UP),
        "interest": interest,
        "total_due": total_due,
        "total_paid": total_paid.quantize(QUANTIZE_PRECISION, rounding=ROUND_HALF_UP),
        "remaining_balance": remaining_balance,
        "interest_outstanding": interest_outstanding,
        "total_outstanding_with_interest": total_outstanding_with_interest,
        "completion_percent": round(completion_percent, 2),
    }
