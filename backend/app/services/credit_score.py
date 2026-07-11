"""
Credit score calculation service based on payment behavior analysis.
"""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from app.services.interest import calculate_interest

QUANTIZE_PRECISION = Decimal("0.01")

# Score range
MIN_SCORE = 300.0
MAX_SCORE = 850.0
DEFAULT_SCORE = 700.0

# Weight allocation (must sum to 1.0)
WEIGHT_REGULARITY = 0.40
WEIGHT_COMPLIANCE = 0.40
WEIGHT_TIMELINESS = 0.20


def calculate_credit_score(
    loan,
    payments_list: list,
    current_date: date,
) -> float:
    """
    Calculate a credit score (300-850) based on payment behavior.

    The score is computed using three weighted factors:
    - 40% Regularity: Ratio of unique payment days to elapsed days
    - 40% Compliance: Ratio of total paid to expected paid amount
    - 20% Timeliness: Penalty for overdue days (1.0 - days_overdue * 0.02)

    Args:
        loan: Loan ORM object with principal_amount, interest_rate, interest_formula,
              loan_start_date, loan_end_date, duration_days
        payments_list: List of payment ORM objects with payment_date and amount_paid
        current_date: Date to calculate score as of

    Returns:
        Credit score as a float between 300 and 850. Returns 700 if no days have elapsed.
    """
    days_elapsed = max((current_date - loan.loan_start_date).days, 0)

    # Default score if loan just started
    if days_elapsed == 0:
        return DEFAULT_SCORE

    principal = loan.principal_amount
    rate = loan.interest_rate
    formula = loan.interest_formula
    duration = loan.duration_days

    interest = calculate_interest(principal, rate, formula)
    total_due = principal + interest

    # Daily expected payment
    daily_due = total_due / Decimal(str(duration))

    # --- Factor 1: Regularity (40%) ---
    # How consistently the borrower makes payments (unique days with payments)
    unique_payment_days = len(set(p.payment_date for p in payments_list))
    regularity = min(unique_payment_days / days_elapsed, 1.0)

    # --- Factor 2: Compliance (40%) ---
    # How much of the expected amount has been paid
    expected_days = min(days_elapsed, duration)
    expected_paid = (daily_due * Decimal(str(expected_days))).quantize(
        QUANTIZE_PRECISION, rounding=ROUND_HALF_UP
    )

    total_paid = sum(
        (p.amount_paid for p in payments_list),
        Decimal("0"),
    ).quantize(QUANTIZE_PRECISION, rounding=ROUND_HALF_UP)

    if expected_paid > 0:
        compliance = min(float(total_paid / expected_paid), 1.0)
    else:
        compliance = 1.0

    # --- Factor 3: Timeliness (20%) ---
    # Penalty for being overdue
    if loan.loan_end_date and current_date > loan.loan_end_date:
        days_overdue = (current_date - loan.loan_end_date).days
    else:
        days_overdue = 0

    timeliness = max(1.0 - days_overdue * 0.02, 0.0)

    # --- Weighted Score ---
    raw_score = (
        WEIGHT_REGULARITY * regularity
        + WEIGHT_COMPLIANCE * compliance
        + WEIGHT_TIMELINESS * timeliness
    )

    # Scale to 300-850 range
    score = MIN_SCORE + raw_score * (MAX_SCORE - MIN_SCORE)

    # Clamp to valid range
    score = max(MIN_SCORE, min(MAX_SCORE, score))

    return round(score, 2)
