"""
Interest calculation service supporting multiple interest formulas.
"""
from decimal import Decimal, ROUND_HALF_UP

QUANTIZE_PRECISION = Decimal("0.01")


def calculate_interest(principal: Decimal, rate: Decimal, formula: str) -> Decimal:
    """
    Calculate total interest for a loan based on the interest formula.

    The rate is treated as a flat percentage over the loan term (not annualized).

    Args:
        principal: The loan principal amount
        rate: Interest rate as a percentage (e.g., 10 for 10%)
        formula: Interest formula type ('FLAT', 'REDUCING', 'COMPOUND')

    Returns:
        Total interest amount, quantized to 2 decimal places
    """
    formula = formula.upper()

    if formula == "FLAT":
        # Simple flat interest: principal * rate / 100
        interest = principal * rate / Decimal("100")
    elif formula == "REDUCING":
        # Reducing balance: interest on average outstanding (approximation)
        # For a reducing balance over the term, interest ≈ principal * rate / 200
        interest = principal * rate / Decimal("200")
    elif formula == "COMPOUND":
        # Compound interest over the term (rate applied as percentage)
        rate_decimal = rate / Decimal("100")
        interest = principal * ((Decimal("1") + rate_decimal) - Decimal("1"))
        # This simplifies to same as flat for single period
        # For multi-period compound, this would need periods parameter
        interest = principal * rate_decimal
    else:
        # Default to flat if formula is unrecognized
        interest = principal * rate / Decimal("100")

    return interest.quantize(QUANTIZE_PRECISION, rounding=ROUND_HALF_UP)


def get_loan_balance_summary(
    principal: Decimal,
    rate: Decimal,
    formula: str,
    total_paid: Decimal,
) -> dict:
    """
    Calculate comprehensive loan balance summary.

    Args:
        principal: Loan principal amount
        rate: Interest rate percentage
        formula: Interest formula type
        total_paid: Total amount already paid

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
    interest = calculate_interest(principal, rate, formula)
    total_due = (principal + interest).quantize(QUANTIZE_PRECISION, rounding=ROUND_HALF_UP)

    # Payments applied to principal first
    remaining_balance = max(principal - total_paid, Decimal("0")).quantize(
        QUANTIZE_PRECISION, rounding=ROUND_HALF_UP
    )

    # Interest outstanding: if total_paid < principal, full interest remains;
    # if total_paid >= principal, reduce interest by overage
    if total_paid >= principal:
        interest_paid = total_paid - principal
        interest_outstanding = max(interest - interest_paid, Decimal("0"))
    else:
        interest_outstanding = interest

    interest_outstanding = interest_outstanding.quantize(QUANTIZE_PRECISION, rounding=ROUND_HALF_UP)

    total_outstanding_with_interest = (remaining_balance + interest_outstanding).quantize(
        QUANTIZE_PRECISION, rounding=ROUND_HALF_UP
    )

    return {
        "principal": principal.quantize(QUANTIZE_PRECISION, rounding=ROUND_HALF_UP),
        "interest": interest,
        "total_due": total_due,
        "total_paid": total_paid.quantize(QUANTIZE_PRECISION, rounding=ROUND_HALF_UP),
        "remaining_balance": remaining_balance,
        "interest_outstanding": interest_outstanding,
        "total_outstanding_with_interest": total_outstanding_with_interest,
    }
