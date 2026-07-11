"""
Loan lifecycle service: end date calculation, schedule generation, and status tracking.
"""
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from app.services.interest import calculate_interest, get_loan_balance_summary

QUANTIZE_PRECISION = Decimal("0.01")


def calculate_loan_end_date(start_date: date, duration_days: int = 100) -> date:
    """
    Calculate loan end date from start date and duration.

    Args:
        start_date: Loan start date
        duration_days: Number of days for the loan term (default 100)

    Returns:
        The loan end date
    """
    return start_date + timedelta(days=duration_days)


def generate_loan_schedule(
    loan_id: int,
    principal: Decimal,
    interest_rate: Decimal,
    interest_formula: str,
    start_date: date,
    duration_days: int,
) -> list[dict]:
    """
    Generate a daily installment schedule for a loan.

    Creates one installment per day over the loan duration. Each installment
    has an equal expected amount based on the total due (principal + interest)
    divided by duration days.

    Args:
        loan_id: The loan ID
        principal: Loan principal amount
        interest_rate: Interest rate percentage
        interest_formula: Interest formula type
        start_date: Loan start date
        duration_days: Number of days for the loan term

    Returns:
        List of installment dictionaries with keys:
        - loan_id, installment_number, due_date, expected_amount,
          paid_amount (0), remaining_amount, status ('PENDING')
    """
    interest = calculate_interest(principal, interest_rate, interest_formula, duration_days)
    total_due = principal + interest

    # Calculate daily installment amount
    daily_amount = (total_due / Decimal(str(duration_days))).quantize(
        QUANTIZE_PRECISION, rounding=ROUND_HALF_UP
    )

    schedule = []
    cumulative = Decimal("0")

    for i in range(1, duration_days + 1):
        due_date = start_date + timedelta(days=i)

        # Last installment absorbs rounding difference
        if i == duration_days:
            expected_amount = (total_due - cumulative).quantize(
                QUANTIZE_PRECISION, rounding=ROUND_HALF_UP
            )
        else:
            expected_amount = daily_amount
            cumulative += daily_amount

        schedule.append({
            "loan_id": loan_id,
            "installment_number": i,
            "due_date": due_date,
            "expected_amount": expected_amount,
            "paid_amount": Decimal("0"),
            "remaining_amount": expected_amount,
            "status": "PENDING",
        })

    return schedule


def get_loan_status_details(
    loan,
    payments_list: list,
    current_date: date,
) -> dict:
    """
    Calculate comprehensive loan status including payment progress and balance summary.

    Args:
        loan: Loan ORM object with principal_amount, interest_rate, interest_formula,
              loan_start_date, loan_end_date, duration_days
        payments_list: List of payment ORM objects with amount_paid attribute
        current_date: Date to calculate status as of

    Returns:
        Dictionary with:
        - daily_due_amount: Expected daily payment
        - days_elapsed: Days since loan start
        - days_overdue: Days past loan end date (min 0)
        - expected_paid_to_date: Amount that should have been paid by now
        - status: Current loan status string
        - All fields from get_loan_balance_summary
    """
    principal = loan.principal_amount
    rate = loan.interest_rate
    formula = loan.interest_formula
    duration = loan.duration_days

    interest = calculate_interest(principal, rate, formula, duration)
    total_due = principal + interest

    # Daily expected payment
    daily_due_amount = (total_due / Decimal(str(duration))).quantize(
        QUANTIZE_PRECISION, rounding=ROUND_HALF_UP
    )

    # Calculate days elapsed from loan start
    days_elapsed = max((current_date - loan.loan_start_date).days, 0)

    # Days overdue (past loan end date)
    if loan.loan_end_date and current_date > loan.loan_end_date:
        days_overdue = (current_date - loan.loan_end_date).days
    else:
        days_overdue = 0

    # Expected paid amount by today
    expected_days = min(days_elapsed, duration)
    expected_paid_to_date = (daily_due_amount * Decimal(str(expected_days))).quantize(
        QUANTIZE_PRECISION, rounding=ROUND_HALF_UP
    )

    # Total actually paid
    total_paid = sum(
        (p.amount_paid for p in payments_list),
        Decimal("0"),
    ).quantize(QUANTIZE_PRECISION, rounding=ROUND_HALF_UP)

    # Get balance summary
    balance = get_loan_balance_summary(principal, rate, formula, total_paid, duration)

    # Determine status
    if total_paid >= total_due:
        status = "COMPLETED"
    elif days_overdue > 0 and total_paid < total_due:
        status = "OVERDUE"
    else:
        status = "ACTIVE"

    return {
        "daily_due_amount": daily_due_amount,
        "days_elapsed": days_elapsed,
        "days_overdue": days_overdue,
        "expected_paid_to_date": expected_paid_to_date,
        "status": status,
        **balance,
    }


def get_loan_repayment_rows(db, loan) -> list[dict]:
    """
    Build repayment rows dynamically for a loan by merging its schedule and payments.
    """
    from decimal import Decimal
    from datetime import date
    from app.models.payment import Payment
    from app.models.loan_schedule import LoanSchedule
    from app.models.user import User
    from app.services.interest import calculate_interest

    # Get payments for this loan (use preloaded if available)
    if "payments" in loan.__dict__:
        payments = sorted(loan.payments, key=lambda x: x.payment_date)
    else:
        payments = db.query(Payment).filter(Payment.loan_id == loan.id).order_by(Payment.payment_date.asc()).all()
    payments_dict = {p.payment_date: p for p in payments}

    # Get loan schedules (use preloaded if available)
    if "schedules" in loan.__dict__:
        schedules = sorted(loan.schedules, key=lambda x: x.installment_number)
    else:
        schedules = db.query(LoanSchedule).filter(LoanSchedule.loan_id == loan.id).order_by(LoanSchedule.installment_number.asc()).all()

    # Pre-fetch all recorder users in a single query
    recorder_ids = {p.recorded_by for p in payments if p.recorded_by}
    recorders_dict = {}
    if recorder_ids:
        recorders = db.query(User).filter(User.id.in_(list(recorder_ids))).all()
        recorders_dict = {u.id: u.username for u in recorders}

    # Calculate overall loan totals
    total_due = loan.principal_amount + calculate_interest(loan.principal_amount, loan.interest_rate, loan.interest_formula, loan.duration_days)
    total_paid = sum((p.amount_paid for p in payments), Decimal("0"))
    remaining_balance = max(total_due - total_paid, Decimal("0"))

    today = date.today()
    repayment_rows = []

    for s in schedules:
        p = payments_dict.get(s.due_date)
        amount_paid = p.amount_paid if p else Decimal("0")
        
        # Calculate dynamic status
        if remaining_balance == 0:
            status = "COMPLETED"
        elif loan.loan_end_date and today > loan.loan_end_date and remaining_balance > 0:
            status = "OVERDUE"
        elif p:
            if amount_paid >= s.expected_amount:
                status = "PAID"
            elif amount_paid > 0:
                status = "PARTIALLY PAID"
            else:
                if s.due_date == today:
                    status = "PENDING"
                elif s.due_date < today:
                    status = "MISSED"
                else:
                    status = "PENDING"
        else:
            if s.due_date == today:
                status = "PENDING"
            elif s.due_date < today:
                status = "MISSED"
            else:
                status = "PENDING"

        recorded_by_name = "—"
        recorded_time = "—"
        if p:
            recorded_by_name = recorders_dict.get(p.recorded_by, "—")
            recorded_time = p.created_at.strftime("%Y-%m-%d %H:%M:%S")

        repayment_rows.append({
            "id": p.id if p else None,
            "loan_id": loan.id,
            "customer_id": loan.customer_id,
            "payment_date": s.due_date.isoformat(),
            "expected_amount": float(s.expected_amount),
            "amount_paid": float(amount_paid),
            "payment_mode": p.payment_mode if p else "—",
            "payment_status": status,
            "remarks": p.remarks if (p and p.remarks) else "—",
            "recorded_by_name": recorded_by_name,
            "created_at": recorded_time,
        })

    return repayment_rows


def get_customer_summary_details(db, customer_id: int) -> dict:
    """
    Compute customer summary details (Total Paid, Remaining Balance, Expected Till Today,
    Pending Amount, Credit Score, Risk Level, Completion %, Next Due Date).
    """
    from decimal import Decimal
    from datetime import date
    from app.models.loan import Loan
    from app.models.payment import Payment
    from app.services.interest import calculate_interest
    from app.services.credit_score import calculate_credit_score

    from sqlalchemy.orm import selectinload
    from app.models.loan_schedule import LoanSchedule
    loans = db.query(Loan).filter(
        Loan.customer_id == customer_id, 
        Loan.is_deleted == False
    ).options(
        selectinload(Loan.payments),
        selectinload(Loan.schedules)
    ).all()
    today = date.today()

    total_principal_all = Decimal("0")
    total_interest_all = Decimal("0")
    total_paid_all = Decimal("0")
    total_due_all = Decimal("0")
    expected_till_today_all = Decimal("0")
    credit_scores = []
    next_due_date_candidate = None

    for loan in loans:
        payments = list(loan.payments)
        loan_total_paid = sum((p.amount_paid for p in payments), Decimal("0"))
        total_paid_all += loan_total_paid

        principal = loan.principal_amount
        total_principal_all += principal

        interest = loan.interest_amount if loan.interest_amount is not None else calculate_interest(loan.principal_amount, loan.interest_rate, loan.interest_formula, loan.duration_days)
        total_interest_all += interest

        loan_total_due = loan.total_repayable_amount if loan.total_repayable_amount is not None else (principal + interest)
        total_due_all += loan_total_due

        duration = loan.duration_days
        daily_due_amount = loan_total_due / Decimal(str(duration))
        days_elapsed = max((today - loan.loan_start_date).days, 0)
        expected_days = min(days_elapsed, duration)
        expected_paid_to_date = daily_due_amount * Decimal(str(expected_days))
        expected_till_today_all += expected_paid_to_date

        loan_score = calculate_credit_score(loan, payments, today)
        credit_scores.append(loan_score)

        # Retrieve next due installment in memory
        unpaid_installments = [s for s in loan.schedules if s.remaining_amount > 0 and s.due_date >= today]
        if unpaid_installments:
            unpaid_installments.sort(key=lambda x: x.installment_number)
            unpaid_installment = unpaid_installments[0]
            if not next_due_date_candidate or unpaid_installment.due_date < next_due_date_candidate:
                next_due_date_candidate = unpaid_installment.due_date

    remaining_balance_all = max(total_due_all - total_paid_all, Decimal("0"))
    pending_amount_all = max(expected_till_today_all - total_paid_all, Decimal("0"))
    avg_score = round(sum(credit_scores) / len(credit_scores), 2) if credit_scores else 700.0

    if avg_score >= 750:
        risk_level = "LOW RISK"
    elif avg_score < 650:
        risk_level = "HIGH RISK"
    else:
        risk_level = "MEDIUM RISK"

    completion_percent = float((total_paid_all / total_due_all) * 100) if total_due_all > 0 else 100.0

    return {
        "total_principal": float(total_principal_all),
        "total_interest": float(total_interest_all),
        "total_repayable": float(total_due_all),
        "total_paid": float(total_paid_all),
        "remaining_balance": float(remaining_balance_all),
        "expected_till_today": float(expected_till_today_all),
        "pending_amount": float(pending_amount_all),
        "credit_score": avg_score,
        "risk_level": risk_level,
        "completion_percent": round(completion_percent, 2),
        "next_due_date": next_due_date_candidate.isoformat() if next_due_date_candidate else None,
    }


def get_dashboard_metrics_details(db) -> dict:
    """
    Calculate comprehensive dashboard metrics dynamically from live DB.
    Optimized to load all payments in a single query and perform loop calculations in memory.
    """
    from decimal import Decimal
    from datetime import date
    from collections import defaultdict
    from sqlalchemy import func
    from app.models.customer import Customer
    from app.models.loan import Loan
    from app.models.payment import Payment
    from app.models.loan_schedule import LoanSchedule
    from app.services.interest import calculate_interest, get_loan_balance_summary

    today = date.today()

    total_customers = db.query(Customer).filter(Customer.is_deleted == False).count()
    total_loans = db.query(Loan).filter(Loan.is_deleted == False).count()

    disbursed_result = db.query(func.sum(Loan.principal_amount)).filter(Loan.is_deleted == False).scalar()
    disbursed_principal = Decimal(str(disbursed_result)) if disbursed_result else Decimal("0")

    collected_result = db.query(func.sum(Payment.amount_paid)).scalar()
    total_collected = Decimal(str(collected_result)) if collected_result else Decimal("0")

    today_collected_result = db.query(func.sum(Payment.amount_paid)).filter(Payment.payment_date == today).scalar()
    today_collection = Decimal(str(today_collected_result)) if today_collected_result else Decimal("0")

    # Fetch all active loans
    all_loans = db.query(Loan).filter(Loan.is_deleted == False).all()
    loan_ids = [loan.id for loan in all_loans]

    # Batch fetch all payments for these loans in a single query!
    payments_by_loan = defaultdict(list)
    if loan_ids:
        all_payments = db.query(Payment).filter(Payment.loan_id.in_(loan_ids)).all()
        for p in all_payments:
            payments_by_loan[p.loan_id].append(p)

    total_due = Decimal("0")
    active_principal = Decimal("0")
    completed_loans_count = 0
    overdue_count = 0
    overdue_customers_set = set()

    for loan in all_loans:
        # Calculate due
        interest = calculate_interest(loan.principal_amount, loan.interest_rate, loan.interest_formula, loan.duration_days)
        loan_total_due = loan.principal_amount + interest
        total_due += loan_total_due

        # Process payments in memory
        loan_payments = payments_by_loan[loan.id]
        loan_total_paid = sum((p.amount_paid for p in loan_payments), Decimal("0"))
        loan_remaining = max(loan_total_due - loan_total_paid, Decimal("0"))

        # Remaining principal balance calculation
        bal_sum = get_loan_balance_summary(loan.principal_amount, loan.interest_rate, loan.interest_formula, loan_total_paid, loan.duration_days)
        active_principal += bal_sum["remaining_balance"]

        # Loan counts
        if loan_remaining == 0:
            completed_loans_count += 1
        elif loan.loan_end_date and today > loan.loan_end_date and loan_remaining > 0:
            overdue_count += 1
            overdue_customers_set.add(loan.customer_id)

    outstanding_balance = max(total_due - total_collected, Decimal("0"))

    pending_payments_count = db.query(LoanSchedule).filter(
        LoanSchedule.due_date == today,
        LoanSchedule.remaining_amount > 0
    ).count()

    collection_efficiency = float((total_collected / total_due) * 100) if total_due > 0 else 100.0

    return {
        "total_customers": total_customers,
        "total_loans": total_loans,
        "disbursed_principal": float(disbursed_principal),
        "total_collected": float(total_collected),
        "total_repayable": float(total_due),
        "outstanding_balance": float(outstanding_balance),
        "active_principal": float(active_principal),
        "overdue_count": overdue_count,
        "today_collection": float(today_collection),
        "completed_loans_count": completed_loans_count,
        "pending_payments_count": pending_payments_count,
        "overdue_customers_count": len(overdue_customers_set),
        "collection_efficiency": round(collection_efficiency, 2),
    }


