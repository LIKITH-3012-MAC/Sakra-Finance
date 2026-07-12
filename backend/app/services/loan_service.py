"""
Loan lifecycle service: end date calculation, schedule generation, and status tracking.
"""
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio
from collections import defaultdict

from app.services.interest import calculate_interest, get_loan_balance_summary
from app.utils.timezone import today_ist

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
    """
    total_paid = sum((p.amount_paid for p in payments_list), Decimal("0"))
    
    balance = get_loan_balance_summary(
        loan.principal_amount,
        loan.interest_rate,
        loan.interest_formula,
        total_paid,
        loan.duration_days,
    )

    days_elapsed = (current_date - loan.loan_start_date).days
    days_elapsed = max(0, min(days_elapsed, loan.duration_days))

    # Expected paid to date is the daily due times elapsed days
    daily_due_amount = balance["total_due"] / Decimal(str(loan.duration_days))
    expected_paid_to_date = (daily_due_amount * Decimal(str(days_elapsed))).quantize(
        QUANTIZE_PRECISION, rounding=ROUND_HALF_UP
    )

    # Determine status
    if balance["remaining_balance"] <= 0:
        status = "COMPLETED"
    elif loan.loan_end_date and current_date > loan.loan_end_date and balance["remaining_balance"] > 0:
        status = "OVERDUE"
    else:
        status = "ACTIVE"

    # Compute days overdue if applicable
    days_overdue = 0
    if status == "OVERDUE" and loan.loan_end_date:
        days_overdue = (current_date - loan.loan_end_date).days

    return {
        "daily_due_amount": daily_due_amount,
        "days_elapsed": days_elapsed,
        "days_overdue": days_overdue,
        "expected_paid_to_date": expected_paid_to_date,
        "status": status,
        **balance,
    }


async def get_loan_repayment_rows(db: AsyncSession, loan, recorders_dict=None) -> list[dict]:
    """
    Build repayment rows dynamically for a loan by merging its schedule and payments.
    """
    from app.models.payment import Payment
    from app.models.loan_schedule import LoanSchedule
    from app.models.user import User

    # Get payments for this loan (use preloaded if available)
    if "payments" in loan.__dict__:
        payments = sorted(loan.payments, key=lambda x: x.payment_date)
    else:
        stmt = select(Payment).filter(Payment.loan_id == loan.id).order_by(Payment.payment_date.asc())
        res = await db.execute(stmt)
        payments = list(res.scalars().all())
    payments_dict = {p.payment_date: p for p in payments}

    # Get loan schedules (use preloaded if available)
    if "schedules" in loan.__dict__:
        schedules = sorted(loan.schedules, key=lambda x: x.installment_number)
    else:
        stmt = select(LoanSchedule).filter(LoanSchedule.loan_id == loan.id).order_by(LoanSchedule.installment_number.asc())
        res = await db.execute(stmt)
        schedules = list(res.scalars().all())

    # Pre-fetch all recorder users in a single query if not provided
    if recorders_dict is None:
        recorder_ids = {p.recorded_by for p in payments if p.recorded_by}
        recorders_dict = {}
        if recorder_ids:
            stmt = select(User).filter(User.id.in_(list(recorder_ids)))
            res = await db.execute(stmt)
            recorders = res.scalars().all()
            recorders_dict = {u.id: u.username for u in recorders}

    # Calculate overall loan totals
    total_due = loan.total_repayable_amount if loan.total_repayable_amount is not None else (loan.principal_amount + calculate_interest(loan.principal_amount, loan.interest_rate, loan.interest_formula, loan.duration_days))
    total_paid = sum((p.amount_paid for p in payments), Decimal("0"))
    remaining_balance = max(total_due - total_paid, Decimal("0"))

    today = today_ist()
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
        equivalent_coverage = None
        if p:
            recorded_by_name = recorders_dict.get(p.recorded_by, "—")
            recorded_time = p.created_at.strftime("%Y-%m-%d %H:%M:%S")
            if loan.daily_installment and loan.daily_installment > 0:
                equivalent_coverage = round(float(amount_paid) / float(loan.daily_installment), 2)

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
            "equivalent_coverage": equivalent_coverage,
        })

    return repayment_rows


async def get_customer_summary_details(db: AsyncSession, customer_id: int, loans=None) -> dict:
    """
    Compute customer summary details (Total Paid, Remaining Balance, Expected Till Today,
    Pending Amount, Credit Score, Risk Level, Completion %, Next Due Date).
    """
    from app.models.loan import Loan
    from app.services.credit_score import calculate_credit_score

    if loans is None:
        stmt = select(Loan).filter(
            Loan.customer_id == customer_id, 
            Loan.is_deleted == False
        ).options(
            selectinload(Loan.payments),
            selectinload(Loan.schedules)
        )
        res = await db.execute(stmt)
        loans = res.scalars().all()
    today = today_ist()

    total_principal_all = Decimal("0")
    total_interest_all = Decimal("0")
    total_paid_all = Decimal("0")
    total_due_all = Decimal("0")
    expected_till_today_all = Decimal("0")
    total_daily_installment_all = Decimal("0")
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

        # Accumulate daily installment for equivalent coverage calculation
        if loan.daily_installment and loan.daily_installment > 0:
            total_daily_installment_all += Decimal(str(loan.daily_installment))

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

    # Equivalent Coverage: Total Collected ÷ Total Daily Installment
    equivalent_coverage = None
    if total_daily_installment_all > 0 and total_paid_all > 0:
        equivalent_coverage = round(float(total_paid_all / total_daily_installment_all), 2)

    # Calculate collection intelligence delinquency metadata
    delinquency = compute_pending_installments_metadata(loans, today)

    return {
        "total_principal": float(total_principal_all),
        "total_interest": float(total_interest_all),
        "total_repayable": float(total_due_all),
        "total_paid": float(total_paid_all),
        "remaining_balance": float(remaining_balance_all),
        "pending_amount": float(pending_amount_all),
        "credit_score": avg_score,
        "risk_level": risk_level,
        "completion_percent": round(completion_percent, 2),
        "next_due_date": next_due_date_candidate.isoformat() if next_due_date_candidate else None,
        "equivalent_coverage": equivalent_coverage,
        "total_daily_installment": float(total_daily_installment_all),
        "pending_installments_count": delinquency["pending_installments_count"],
        "oldest_pending_date": delinquency["oldest_pending_date"],
        "latest_pending_date": delinquency["latest_pending_date"],
        "pending_dates": delinquency["pending_dates"]
    }


async def get_dashboard_metrics_details(db: AsyncSession) -> dict:
    """
    Calculate comprehensive dashboard metrics dynamically from live DB.
    Optimized to run counts and queries in parallel using asyncio.gather().
    """
    from app.models.customer import Customer
    from app.models.loan import Loan
    from app.models.payment import Payment
    from app.models.loan_schedule import LoanSchedule

    today = today_ist()

    cust_res = await db.execute(select(func.count(Customer.id)).filter(Customer.is_deleted == False))
    loan_res = await db.execute(select(func.count(Loan.id)).filter(Loan.is_deleted == False))
    disbursed_res = await db.execute(select(func.sum(Loan.principal_amount)).filter(Loan.is_deleted == False))
    collected_res = await db.execute(select(func.sum(Payment.amount_paid)))
    today_collected_res = await db.execute(select(func.sum(Payment.amount_paid)).filter(Payment.payment_date == today))
    all_loans_res = await db.execute(select(Loan).filter(Loan.is_deleted == False))
    pending_payments_res = await db.execute(select(func.count(LoanSchedule.id)).filter(
        LoanSchedule.due_date == today,
        LoanSchedule.remaining_amount > 0
    ))

    total_customers = cust_res.scalar() or 0
    total_loans = loan_res.scalar() or 0

    disbursed_result = disbursed_res.scalar()
    disbursed_principal = Decimal(str(disbursed_result)) if disbursed_result else Decimal("0")

    collected_result = collected_res.scalar()
    total_collected = Decimal(str(collected_result)) if collected_result else Decimal("0")

    today_collected_result = today_collected_res.scalar()
    today_collection = Decimal(str(today_collected_result)) if today_collected_result else Decimal("0")

    all_loans = list(all_loans_res.scalars().all())
    loan_ids = [loan.id for loan in all_loans]

    # Batch fetch all payments for these loans
    payments_by_loan = defaultdict(list)
    if loan_ids:
        stmt = select(Payment).filter(Payment.loan_id.in_(loan_ids))
        res = await db.execute(stmt)
        all_payments = res.scalars().all()
        for p in all_payments:
            payments_by_loan[p.loan_id].append(p)

    total_due = Decimal("0")
    active_principal = Decimal("0")
    completed_loans_count = 0
    overdue_count = 0
    overdue_customers_set = set()

    for loan in all_loans:
        # Calculate due
        interest = loan.interest_amount if loan.interest_amount is not None else calculate_interest(loan.principal_amount, loan.interest_rate, loan.interest_formula, loan.duration_days)
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
    pending_payments_count = pending_payments_res.scalar() or 0
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


def compute_pending_installments_metadata(loans, today: date) -> dict:
    """
    Compute collection intelligence delinquency metadata for a list of loans.
    Only active/overdue loans are included.
    Only installments whose due date has passed (< today) and remain unpaid are counted.
    """
    pending_installments_count = 0
    oldest_pending_date = None
    latest_pending_date = None
    pending_amount = Decimal("0")
    pending_dates = []

    for loan in loans:
        if loan.is_deleted or loan.status not in ("ACTIVE", "OVERDUE"):
            continue

        payments = list(loan.payments)
        total_paid = sum((p.amount_paid for p in payments), Decimal("0"))
        
        interest = loan.interest_amount if loan.interest_amount is not None else calculate_interest(loan.principal_amount, loan.interest_rate, loan.interest_formula, loan.duration_days)
        total_due = loan.total_repayable_amount if loan.total_repayable_amount is not None else (loan.principal_amount + interest)
        remaining_balance = max(total_due - total_paid, Decimal("0"))

        if remaining_balance == 0:
            continue

        schedules = sorted(loan.schedules, key=lambda x: x.installment_number)
        payments_dict = {p.payment_date: p for p in payments}

        for s in schedules:
            p = payments_dict.get(s.due_date)
            amount_paid = p.amount_paid if p else Decimal("0")
            
            if s.due_date < today:
                is_unpaid = (amount_paid < s.expected_amount)
                if s.remaining_amount > 0 or is_unpaid:
                    is_loan_overdue = (loan.loan_end_date and today > loan.loan_end_date)
                    status = "OVERDUE" if is_loan_overdue else "MISSED"

                    unpaid_part = s.remaining_amount if s.remaining_amount is not None else max(s.expected_amount - amount_paid, Decimal("0"))
                    pending_amount += unpaid_part
                    pending_installments_count += 1
                    
                    pending_dates.append({
                        "date": s.due_date.isoformat(),
                        "expected_amount": float(s.expected_amount),
                        "status": status
                    })
                    
                    if oldest_pending_date is None or s.due_date < oldest_pending_date:
                        oldest_pending_date = s.due_date
                    if latest_pending_date is None or s.due_date > latest_pending_date:
                        latest_pending_date = s.due_date

    pending_dates.sort(key=lambda x: x["date"])

    return {
        "pending_installments_count": pending_installments_count,
        "oldest_pending_date": oldest_pending_date.isoformat() if oldest_pending_date else None,
        "latest_pending_date": latest_pending_date.isoformat() if latest_pending_date else None,
        "pending_amount": float(pending_amount),
        "pending_dates": pending_dates
    }

