import logging
import random
from datetime import datetime, date
from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.core.config import settings
from app.database.session import get_db
from app.middleware.auth import get_current_user
from app.models.audit_log import AuditLog
from app.models.credit_score import CreditScore
from app.models.customer import Customer
from app.models.loan import Loan
from app.models.loan_closure import LoanClosure
from app.models.notification import Notification
from app.models.payment import Payment
from app.models.user import User
from app.repositories.payment_repo import PaymentRepository
from app.schemas.common import APIResponse
from app.schemas.payment import PaymentCreate
from app.services.audit import log_audit
from app.services.credit_score import calculate_credit_score
from app.services.interest import calculate_interest
from app.services.notification_service import create_system_notification, push_realtime_notifications
from app.utils.timezone import today_ist, now_ist_naive

logger = logging.getLogger("sakra.loan_closure")
router = APIRouter()


class VerifyAuthRequest(BaseModel):
    passkey: str


class CloseLoanRequest(BaseModel):
    passkey: str
    final_amount_received: Decimal
    remarks: Optional[str] = None


@router.get("/{loan_id}/summary", response_model=APIResponse)
async def get_closure_summary(
    loan_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the summary of the loan details for Step 1 of the settlement wizard.
    """
    stmt = select(Loan).filter(Loan.id == loan_id).options(
        selectinload(Loan.customer),
        selectinload(Loan.payments),
        selectinload(Loan.schedules)
    )
    result = await db.execute(stmt)
    loan = result.scalars().first()
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")

    customer = loan.customer
    payments = list(loan.payments)
    today = today_ist()

    total_paid = sum((p.amount_paid for p in payments), Decimal("0"))
    principal = loan.principal_amount
    interest = loan.interest_amount if loan.interest_amount is not None else calculate_interest(principal, loan.interest_rate, loan.interest_formula, loan.duration_days)
    total_repayable = loan.total_repayable_amount if loan.total_repayable_amount is not None else (principal + interest)
    remaining_balance = max(total_repayable - total_paid, Decimal("0"))
    daily_installment = loan.daily_installment if loan.daily_installment is not None else (total_repayable / Decimal(str(loan.duration_days)))

    days_elapsed = max((today - loan.loan_start_date).days, 0)
    expected_days = min(days_elapsed, loan.duration_days)
    expected_collection = (daily_installment * Decimal(str(expected_days)))

    equivalent_paid_days = float(total_paid / daily_installment) if daily_installment > 0 else 0.0
    days_behind = days_elapsed - equivalent_paid_days

    credit_score = calculate_credit_score(loan, payments, today)
    if credit_score >= 750:
        risk_level = "LOW RISK"
    elif credit_score < 650:
        risk_level = "HIGH RISK"
    else:
        risk_level = "MEDIUM RISK"

    summary_data = {
        "customer_name": customer.name,
        "customer_id": customer.id,
        "loan_id": loan.id,
        "principal": float(principal),
        "interest": float(interest),
        "total_repayable": float(total_repayable),
        "collected_till_now": float(total_paid),
        "remaining_balance": float(remaining_balance),
        "expected_daily_installment": float(daily_installment),
        "equivalent_paid_days": round(equivalent_paid_days, 2),
        "days_behind_ahead": round(days_behind, 2),
        "risk_score": risk_level,
        "credit_score": credit_score,
        "status": loan.status,
    }

    return APIResponse(
        success=True,
        message="Loan closure summary retrieved successfully",
        data=summary_data,
    )


@router.post("/{loan_id}/verify-auth", response_model=APIResponse)
async def verify_auth_passkey(
    loan_id: int,
    payload: VerifyAuthRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Verify the manager authorization passkey server-side.
    """
    configured_secret = settings.LOAN_CLOSURE_SECRET or "shiva"
    
    if payload.passkey != configured_secret:
        # Record a failed authorization audit event
        await log_audit(
            db=db,
            actor_id=current_user.id,
            action="LOAN_CLOSURE_AUTH_FAILED",
            table_name="loans",
            record_id=loan_id,
            old_values={"message": "Failed manager authorization passkey entry"},
            request=request,
        )
        await db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization passkey."
        )

    return APIResponse(
        success=True,
        message="Manager authorization verified successfully."
    )


@router.post("/{loan_id}/close", response_model=APIResponse)
async def execute_loan_closure(
    loan_id: int,
    payload: CloseLoanRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Securely settle and close a loan, creating archival entries and audit trails.
    """
    # 1. Verify passkey
    configured_secret = settings.LOAN_CLOSURE_SECRET or "shiva"
    if payload.passkey != configured_secret:
        await log_audit(
            db=db,
            actor_id=current_user.id,
            action="LOAN_CLOSURE_AUTH_FAILED",
            table_name="loans",
            record_id=loan_id,
            old_values={"message": "Failed manager authorization passkey entry during execution"},
            request=request,
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization passkey. Loan closure cancelled."
        )

    # 2. Fetch loan
    stmt = select(Loan).filter(Loan.id == loan_id).options(
        selectinload(Loan.customer),
        selectinload(Loan.payments),
        selectinload(Loan.schedules)
    )
    result = await db.execute(stmt)
    loan = result.scalars().first()
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")

    if loan.status == "CLOSED":
        raise HTTPException(status_code=400, detail="Loan is already closed.")

    customer = loan.customer
    payments = list(loan.payments)
    today = today_ist()

    # Calculations before closure
    total_paid_before = sum((p.amount_paid for p in payments), Decimal("0"))
    principal = loan.principal_amount
    interest = loan.interest_amount if loan.interest_amount is not None else calculate_interest(principal, loan.interest_rate, loan.interest_formula, loan.duration_days)
    total_repayable = loan.total_repayable_amount if loan.total_repayable_amount is not None else (principal + interest)
    remaining_before = max(total_repayable - total_paid_before, Decimal("0"))

    # Validation check for partial settlement
    is_partial = payload.final_amount_received != remaining_before
    if is_partial and current_user.role not in ["SUPER_ADMIN", "ADMIN"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can force close a loan with a non-matching settlement amount."
        )

    # Record the final settlement payment if received amount > 0
    final_payment_id = None
    if payload.final_amount_received > 0:
        payment_schema = PaymentCreate(
            loan_id=loan_id,
            payment_date=today,
            amount_paid=payload.final_amount_received,
            payment_mode="CASH",
            remarks=payload.remarks or "Final Settlement Payment"
        )
        final_payment = await PaymentRepository.create(
            db=db,
            schema=payment_schema,
            customer_id=customer.id,
            recorder_id=current_user.id,
            loan=loan
        )
        await db.flush()
        final_payment_id = final_payment.id

    # Recalculate total collected
    updated_payments = list(loan.payments)
    total_collected = sum((p.amount_paid for p in updated_payments), Decimal("0"))

    # Enforce status = CLOSED and remaining_balance = 0.00
    loan.status = "CLOSED"
    loan.remaining_balance = Decimal("0.00")
    loan.version_id += 1

    # Get credit score/risk
    credit_score = calculate_credit_score(loan, updated_payments, today)
    if credit_score >= 750:
        risk_level = "LOW RISK"
    elif credit_score < 650:
        risk_level = "HIGH RISK"
    else:
        risk_level = "MEDIUM RISK"

    # Create reference
    ref_num = f"LC-{today.strftime('%Y%m%d')}-{random.randint(100000, 999999)}"

    # Client metadata
    ip_address = None
    user_agent = None
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        ip_address = forwarded_for.split(",")[0].strip()
    elif request.client:
        ip_address = request.client.host
    user_agent = request.headers.get("user-agent")

    # Create immutable LoanClosure archive record
    loan_closure_record = LoanClosure(
        loan_id=loan_id,
        customer_id=customer.id,
        settlement_amount=payload.final_amount_received,
        remaining_before=remaining_before,
        remaining_after=Decimal("0.00"),
        principal_amount=principal,
        interest_amount=interest,
        total_repayable=total_repayable,
        total_collected=total_collected,
        daily_installment=loan.daily_installment or Decimal("0.00"),
        equivalent_days=Decimal(str(loan.duration_days)),
        completion_percent=Decimal("100.00"),
        credit_score=Decimal(str(credit_score)),
        risk_level=risk_level,
        settlement_reference=ref_num,
        closed_by=current_user.id,
        closed_by_username=current_user.username,
        closed_by_role=current_user.role,
        authorization_verified=True,
        is_partial_settlement=is_partial,
        remarks=payload.remarks,
        ip_address=ip_address,
        user_agent=user_agent
    )
    db.add(loan_closure_record)
    await db.flush()

    # Log audit event
    await log_audit(
        db=db,
        actor_id=current_user.id,
        action="LOAN_CLOSED",
        table_name="loan_closures",
        record_id=loan_closure_record.id,
        new_values={
            "customer_id": customer.id,
            "loan_id": loan_id,
            "settlement_amount": str(payload.final_amount_received),
            "remaining_before": str(remaining_before),
            "remaining_after": "0.00",
            "settlement_reference": ref_num,
            "closed_by": current_user.username,
            "is_partial_settlement": is_partial
        },
        request=request,
    )

    # Generate Notification
    notif_msg = (
        f"Loan Successfully Closed | Customer: {customer.name} | "
        f"Settlement Amount: ₹{payload.final_amount_received:,.2f} | "
        f"Closed By: {current_user.username} | Reference: {ref_num}"
    )
    notifs = await create_system_notification(
        db=db,
        notification_type="LOAN_CLOSED",
        message=notif_msg,
        customer_id=customer.id
    )

    await db.commit()

    # Push notifications & invalidate cache
    push_realtime_notifications(notifs)

    if settings.CACHE_ENABLED:
        from app.services.cache import cache
        await cache.invalidate_pattern("loans:*")
        await cache.invalidate_pattern("customers:*")
        await cache.delete("dashboard_metrics")

    return APIResponse(
        success=True,
        message="Loan closed successfully",
        data={
            "closure_id": loan_closure_record.id,
            "settlement_reference": ref_num,
            "settlement_amount": float(payload.final_amount_received),
            "remaining_before": float(remaining_before),
            "closed_at": loan_closure_record.closed_at.isoformat(),
        }
    )


@router.get("/{loan_id}/certificate", response_model=APIResponse)
async def get_closure_certificate(
    loan_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve closure settlement certificate details.
    """
    stmt = select(LoanClosure).filter(LoanClosure.loan_id == loan_id).options(
        joinedload(LoanClosure.loan),
        joinedload(LoanClosure.customer),
        joinedload(LoanClosure.closer)
    )
    result = await db.execute(stmt)
    closure = result.scalars().first()
    if not closure:
        raise HTTPException(status_code=404, detail="Settlement certificate not found for this loan.")

    cert_data = {
        "customer_name": closure.customer.name,
        "customer_phone": closure.customer.phone_number,
        "customer_id": closure.customer.id,
        "loan_id": closure.loan_id,
        "principal": float(closure.principal_amount),
        "interest": float(closure.interest_amount),
        "total_paid": float(closure.total_collected),
        "settlement_amount": float(closure.settlement_amount),
        "settlement_date": closure.closed_at.date().isoformat(),
        "settlement_time": closure.closed_at.strftime("%H:%M:%S"),
        "closed_by": closure.closed_by_username,
        "completion_percent": float(closure.completion_percent),
        "company_name": "SAKRA FINANCE",
        "digital_verification_id": f"VERIFY-LC-{closure.id}-{random.randint(100000, 999999)}",
        "settlement_reference": closure.settlement_reference,
    }

    return APIResponse(
        success=True,
        message="Closure certificate retrieved successfully",
        data=cert_data,
    )


@router.get("/customers/{customer_id}/timeline", response_model=APIResponse)
async def get_customer_timeline(
    customer_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get full activity history of a customer to show in the Activity Center.
    """
    # 1. Fetch all related Loans
    stmt_loans = select(Loan.id).filter(Loan.customer_id == customer_id)
    res_loans = await db.execute(stmt_loans)
    loan_ids = [row[0] for row in res_loans.all()]

    # 2. Fetch Payments
    stmt_payments = select(Payment).filter(Payment.customer_id == customer_id)
    res_payments = await db.execute(stmt_payments)
    payments = res_payments.scalars().all()

    # 3. Fetch Notifications
    stmt_notifs = select(Notification).filter(Notification.customer_id == customer_id)
    res_notifs = await db.execute(stmt_notifs)
    notifications = res_notifs.scalars().all()

    # 4. Fetch Credit Score Updates
    stmt_scores = select(CreditScore).filter(CreditScore.customer_id == customer_id)
    res_scores = await db.execute(stmt_scores)
    scores = res_scores.scalars().all()

    # 5. Fetch closures
    stmt_closures = select(LoanClosure).filter(LoanClosure.customer_id == customer_id)
    res_closures = await db.execute(stmt_closures)
    closures = res_closures.scalars().all()

    # 6. Fetch Audit logs for loans, payments, customer documents
    audit_conditions = [
        (AuditLog.table_name == "customers") & (AuditLog.record_id == customer_id),
        (AuditLog.table_name == "customer_documents") & (AuditLog.record_id == customer_id)
    ]
    if loan_ids:
        audit_conditions.append((AuditLog.table_name == "loans") & (AuditLog.record_id.in_(loan_ids)))
        payment_ids = [p.id for p in payments]
        if payment_ids:
            audit_conditions.append((AuditLog.table_name == "payments") & (AuditLog.record_id.in_(payment_ids)))

    stmt_audit = select(AuditLog, User.username).outerjoin(User, AuditLog.actor_id == User.id).filter(or_(*audit_conditions))
    res_audit = await db.execute(stmt_audit)
    audit_rows = res_audit.all()

    # Merge into a single chronological timeline list
    events = []

    for closure in closures:
        events.append({
            "type": "LOAN_CLOSURE",
            "title": "Loan Fully Settled & Closed",
            "description": f"Loan #{closure.loan_id} successfully closed. Reference ID: {closure.settlement_reference}. Settlement Amount: ₹{closure.settlement_amount:,.2f}.",
            "timestamp": closure.closed_at.isoformat(),
            "actor": closure.closed_by_username,
            "metadata": {
                "reference": closure.settlement_reference,
                "amount": float(closure.settlement_amount),
                "is_partial": closure.is_partial_settlement
            }
        })

    for p in payments:
        events.append({
            "type": "PAYMENT",
            "title": "Payment Recorded",
            "description": f"Payment of ₹{p.amount_paid:,.2f} recorded using mode {p.payment_mode or 'CASH'}.",
            "timestamp": p.created_at.isoformat(),
            "actor": f"User ID #{p.recorded_by}" if p.recorded_by else "System",
            "metadata": {
                "amount": float(p.amount_paid),
                "payment_mode": p.payment_mode,
                "remarks": p.remarks
            }
        })

    for n in notifications:
        events.append({
            "type": "NOTIFICATION",
            "title": f"Notification: {n.notification_type}",
            "description": n.message,
            "timestamp": n.sent_at.isoformat(),
            "actor": "System",
            "metadata": {
                "type": n.notification_type
            }
        })

    for cs in scores:
        events.append({
            "type": "CREDIT_SCORE",
            "title": "Credit Score Analysis",
            "description": f"Credit score computed at {cs.score:.1f} (Previous: {cs.previous_score or '—'}). Reason: {cs.reason or 'Regular recalculation'}.",
            "timestamp": cs.created_at.isoformat(),
            "actor": "AI engine",
            "metadata": {
                "score": float(cs.score),
                "reason": cs.reason
            }
        })

    for audit, actor_username in audit_rows:
        # Avoid duplicate rendering of loan closure since we have direct loan closure event
        if audit.action == "LOAN_CLOSED":
            continue
            
        title = audit.action.replace("_", " ").title()
        desc = f"Action performed on database table '{audit.table_name}'."
        if audit.new_values:
            import json
            try:
                new_vals = json.loads(audit.new_values) if isinstance(audit.new_values, str) else audit.new_values
                if "name" in new_vals:
                    desc = f"Record name: {new_vals['name']}"
                elif "principal" in new_vals:
                    desc = f"Loan amount: ₹{new_vals['principal']}"
            except Exception:
                pass

        events.append({
            "type": "AUDIT_LOG",
            "title": title,
            "description": desc,
            "timestamp": audit.created_at.isoformat(),
            "actor": actor_username or "SYSTEM",
            "metadata": {
                "action": audit.action,
                "table": audit.table_name,
                "record_id": audit.record_id,
                "ip": audit.ip_address
            }
        })

    # Sort descending (newest first)
    events.sort(key=lambda x: x["timestamp"], reverse=True)

    return APIResponse(
        success=True,
        message="Customer Activity timeline loaded",
        data={"events": events}
    )
