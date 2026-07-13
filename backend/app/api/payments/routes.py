"""
Payment routes: recording, modifying, listing, and CSV export.
"""
import io
import logging
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database.session import get_db
from app.middleware.auth import get_current_user, PermissionRequirement
from app.models.user import User
from app.models.loan_schedule import LoanSchedule
from app.repositories.loan_repo import LoanRepository
from app.repositories.payment_repo import PaymentRepository
from app.schemas.common import APIResponse
from app.schemas.payment import PaymentCreate, PaymentUpdate, PaymentResponse
from app.services.audit import log_audit
from app.exceptions.handlers import PaymentError, ConflictError, ExportError
from app.services.cache import cache
from app.core.config import settings
from app.utils.timezone import today_ist

logger = logging.getLogger("sakra.payments")

router = APIRouter()

ADMIN_ROLES = ["SUPER_ADMIN", "ADMIN"]


@router.post("/", response_model=APIResponse)
async def record_payment(
    payment_data: PaymentCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Record a new payment for a loan. Pre-loads schedules and payments in one select
    query to optimize database roundtrips, and runs cache updates incrementally.
    """
    from sqlalchemy.orm import selectinload
    from app.models.loan import Loan

    # 1. Fetch loan along with schedules and payments in a single database roundtrip
    stmt = select(Loan).filter(Loan.id == payment_data.loan_id).options(
        selectinload(Loan.schedules),
        selectinload(Loan.payments)
    )
    result = await db.execute(stmt)
    loan = result.scalars().first()
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")
    if loan.status == "CLOSED":
        raise HTTPException(status_code=400, detail="Cannot record payments for a closed loan.")
    # 2. Record the payment (updates loan.remaining_balance in-memory & database)
    try:
        payment = await PaymentRepository.create(
            db=db,
            schema=payment_data,
            customer_id=loan.customer_id,
            recorder_id=current_user.id,
            loan=loan,
        )
        payment.loan = loan
    except PaymentError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    # 3. Locate and update matching loan schedule installment in memory
    schedule_entry = next((s for s in loan.schedules if s.due_date == payment_data.payment_date), None)

    repayment_status = "PAID"
    if schedule_entry:
        schedule_entry.paid_amount = payment_data.amount_paid
        schedule_entry.remaining_amount = max(
            schedule_entry.expected_amount - payment_data.amount_paid,
            Decimal("0"),
        )
        if schedule_entry.remaining_amount == 0:
            schedule_entry.status = "PAID"
        else:
            schedule_entry.status = "PARTIAL"
            repayment_status = "PARTIAL"

    # Create notifications
    from app.services.notification_service import create_system_notification, push_realtime_notifications
    from app.models.customer import Customer
    stmt_cust = select(Customer.name).filter(Customer.id == loan.customer_id)
    res_cust = await db.execute(stmt_cust)
    cust_name = res_cust.scalar() or f"ID #{loan.customer_id}"

    notifs = []
    amount_paid_float = float(payment_data.amount_paid)
    if amount_paid_float >= 50000:
        notifs.extend(await create_system_notification(
            db,
            "PAYMENT_LARGE_RECEIVED",
            f"Large payment received: ₹{amount_paid_float:,.2f} from customer: {cust_name} (Loan ID #{loan.id}) by {current_user.username}",
            customer_id=loan.customer_id
        ))
    
    if loan.status == "COMPLETED":
        notifs.extend(await create_system_notification(
            db,
            "LOAN_COMPLETED",
            f"Loan fully repaid / completed for customer: {cust_name} (Loan ID #{loan.id})",
            customer_id=loan.customer_id
        ))
    else:
        is_partial = False
        if schedule_entry and payment_data.amount_paid < schedule_entry.expected_amount:
            is_partial = True
            
        notif_type = "PAYMENT_RECORDED"
        if is_partial:
            notif_msg = f"Partial payment of ₹{amount_paid_float:,.2f} received from customer: {cust_name} (Loan ID #{loan.id}) by {current_user.username}"
        else:
            notif_msg = f"Payment of ₹{amount_paid_float:,.2f} recorded for customer: {cust_name} (Loan ID #{loan.id}) by {current_user.username}"
            
        notifs.extend(await create_system_notification(db, notif_type, notif_msg, customer_id=loan.customer_id))

    # Commit the transaction immediately (1 roundtrip)
    await db.commit()

    # Push real-time notifications
    push_realtime_notifications(notifs)

    # Extract client IP and user agent safely for audit log
    ip_address = None
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        ip_address = forwarded_for.split(",")[0].strip()
    elif request.client:
        ip_address = request.client.host
    user_agent = request.headers.get("user-agent")

    # Defer audit logging and simple cache invalidation (0 DB queries)
    from app.services.background_tasks import (
        log_audit_background,
        invalidate_cache_background
    )
    import asyncio

    asyncio.create_task(
        log_audit_background(
            actor_id=current_user.id,
            action="RECORD_PAYMENT",
            table_name="payments",
            record_id=payment.id,
            new_values={
                "loan_id": payment.loan_id,
                "amount": str(payment.amount_paid),
                "date": str(payment.payment_date),
                "mode": payment.payment_mode,
            },
            ip_address=ip_address,
            user_agent=user_agent
        )
    )

    asyncio.create_task(
        invalidate_cache_background(
            patterns=["payments:*", "loans:*", f"customers:summary:{loan.customer_id}"],
            keys=[]
        )
    )

    # Read dashboard metrics from cache or fall back to DB calculation
    dashboard_metrics = None
    if settings.CACHE_ENABLED:
        dashboard_metrics = await cache.get("dashboard_metrics")
    
    if not dashboard_metrics:
        from app.services.loan_service import get_dashboard_metrics_details
        dashboard_metrics = await get_dashboard_metrics_details(db)
    else:
        # Perform incremental update to cached dashboard metrics in memory (takes <1ms)
        dashboard_metrics["total_collected"] = float(Decimal(str(dashboard_metrics["total_collected"])) + Decimal(str(payment_data.amount_paid)))
        dashboard_metrics["today_collection"] = float(Decimal(str(dashboard_metrics["today_collection"])) + Decimal(str(payment_data.amount_paid)))
        dashboard_metrics["outstanding_balance"] = float(max(Decimal(str(dashboard_metrics["outstanding_balance"])) - Decimal(str(payment_data.amount_paid)), Decimal("0")))
        
        # Recalculate efficiency: total_collected / total_repayable
        total_due = Decimal(str(dashboard_metrics["total_repayable"]))
        if total_due > 0:
            eff = float((Decimal(str(dashboard_metrics["total_collected"])) / total_due) * 100)
            dashboard_metrics["collection_efficiency"] = round(eff, 2)
            
        # Overwrite cached metrics in Redis asynchronously
        asyncio.create_task(cache.set("dashboard_metrics", dashboard_metrics, expire_seconds=settings.CACHE_TTL))

    # Read customer summaries from cache or fall back to DB calculation
    customer_summary = None
    if settings.CACHE_ENABLED:
        customer_summary = await cache.get(f"customers:summary:{loan.customer_id}")
    if not customer_summary:
        from app.services.loan_service import get_customer_summary_details
        customer_summary = await get_customer_summary_details(db, loan.customer_id)

    remaining_balance_val = float(loan.remaining_balance)

    payment_dict = PaymentResponse.model_validate(payment).model_dump(mode="json")
    payment_dict["payment_status"] = repayment_status

    # Compute equivalent daily coverage for the recorded payment
    equiv_coverage = None
    if loan.daily_installment and float(loan.daily_installment) > 0:
        equiv_coverage = round(float(payment_data.amount_paid) / float(loan.daily_installment), 2)
    payment_dict["equivalent_coverage"] = equiv_coverage

    return APIResponse(
        success=True,
        message="Payment recorded successfully",
        data={
            "payment": payment_dict,
            "customer_summary": customer_summary,
            "remaining_balance": remaining_balance_val,
            "repayment_status": repayment_status,
            "dashboard_metrics": dashboard_metrics
        },
    )
@router.put("/{payment_id}", response_model=APIResponse)
async def modify_payment(
    payment_id: int,
    update_data: PaymentUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionRequirement(ADMIN_ROLES)),
):
    """
    Modify an existing payment. Creates a PaymentAdjustment record.
    Requires ADMIN role. Uses optimistic locking.
    """
    payment = await PaymentRepository.get_by_id(db, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    old_amount = str(payment.amount_paid)

    try:
        updated = await PaymentRepository.update(db, payment, update_data)
    except ConflictError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    await log_audit(
        db=db,
        actor_id=current_user.id,
        action="MODIFY_PAYMENT",
        table_name="payments",
        record_id=payment_id,
        old_values={"amount_paid": old_amount},
        new_values={"amount_paid": str(updated.amount_paid)},
        request=request,
    )
    # Create notifications
    from app.services.notification_service import create_system_notification, push_realtime_notifications
    from app.models.customer import Customer
    stmt_cust = select(Customer.name).filter(Customer.id == payment.customer_id)
    res_cust = await db.execute(stmt_cust)
    cust_name = res_cust.scalar() or f"ID #{payment.customer_id}"

    notifs = await create_system_notification(
        db,
        "PAYMENT_RECORDED",
        f"Payment updated: amount modified from ₹{float(old_amount):,.2f} to ₹{float(updated.amount_paid):,.2f} for customer: {cust_name} (Loan ID #{payment.loan_id}) by {current_user.username}",
        customer_id=payment.customer_id
    )

    await db.commit()

    # Push real-time notifications
    push_realtime_notifications(notifs)
    
    # Invalidate caches
    if settings.CACHE_ENABLED:
        await cache.invalidate_pattern("payments:*")
        await cache.invalidate_pattern("loans:*")
        await cache.invalidate_pattern("customers:*")
        await cache.delete("dashboard_metrics")

    return APIResponse(
        success=True,
        message="Payment modified successfully",
        data=PaymentResponse.model_validate(updated).model_dump(mode="json"),
    )


@router.get("/customer/{customer_id}", response_model=APIResponse)
async def get_payments_by_customer(
    customer_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all payments for a specific customer.
    """
    cache_key = f"payments:customer:{customer_id}"
    if settings.CACHE_ENABLED:
        cached_data = await cache.get(cache_key)
        if cached_data is not None:
            return APIResponse(
                success=True,
                message=f"Retrieved payments for customer #{customer_id} (cached)",
                data=cached_data,
            )

    payments = await PaymentRepository.list_by_customer(db, customer_id)
    payments_data = [PaymentResponse.model_validate(p).model_dump(mode="json") for p in payments]

    if settings.CACHE_ENABLED:
        await cache.set(cache_key, payments_data, expire_seconds=settings.CACHE_TTL)

    return APIResponse(
        success=True,
        message=f"Retrieved {len(payments_data)} payments for customer #{customer_id}",
        data=payments_data,
    )


@router.get("/loan/{loan_id}", response_model=APIResponse)
async def get_payments_by_loan(
    loan_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all repayment rows (installments + payments) for a specific loan.
    """
    cache_key = f"payments:loan:{loan_id}"
    if settings.CACHE_ENABLED:
        cached_data = await cache.get(cache_key)
        if cached_data is not None:
            return APIResponse(
                success=True,
                message=f"Retrieved repayment rows for loan #{loan_id} (cached)",
                data=cached_data,
            )

    loan = await LoanRepository.get_by_id(db, loan_id)
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")

    from app.services.loan_service import get_loan_repayment_rows
    repayment_rows = await get_loan_repayment_rows(db, loan)

    if settings.CACHE_ENABLED:
        await cache.set(cache_key, repayment_rows, expire_seconds=settings.CACHE_TTL)

    return APIResponse(
        success=True,
        message=f"Retrieved {len(repayment_rows)} repayment rows for loan #{loan_id}",
        data=repayment_rows,
    )


@router.get("/today", response_model=APIResponse)
async def get_today_payments(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all payments recorded for today.
    """
    today = today_ist()
    cache_key = f"payments:today:{today.isoformat()}"
    if settings.CACHE_ENABLED:
        cached_data = await cache.get(cache_key)
        if cached_data is not None:
            return APIResponse(
                success=True,
                message=f"Retrieved today's payments (cached)",
                data=cached_data,
            )

    payments = await PaymentRepository.list_today(db, today)
    payments_data = [PaymentResponse.model_validate(p).model_dump(mode="json") for p in payments]

    total_amount = sum((p.amount_paid for p in payments), Decimal("0"))
    response_data = {
        "date": today.isoformat(),
        "payments": payments_data,
        "total_amount": str(total_amount),
        "count": len(payments_data),
    }

    if settings.CACHE_ENABLED:
        await cache.set(cache_key, response_data, expire_seconds=settings.CACHE_TTL)

    return APIResponse(
        success=True,
        message=f"Retrieved {len(payments_data)} payments for {today.isoformat()}",
        data=response_data,
    )


@router.get("/export/csv")
async def export_payments_csv(
    loan_id: int = Query(None, description="Filter by loan ID"),
    customer_id: int = Query(None, description="Filter by customer ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Export payments as CSV file via streaming response.
    Optionally filter by loan_id or customer_id.
    """
    try:
        import pandas as pd
        from app.models.payment import Payment

        stmt = select(Payment)
        if loan_id:
            stmt = stmt.filter(Payment.loan_id == loan_id)
        if customer_id:
            stmt = stmt.filter(Payment.customer_id == customer_id)

        res = await db.execute(stmt.order_by(Payment.payment_date.desc()))
        payments = res.scalars().all()

        # Build dataframe
        data = []
        for p in payments:
            data.append({
                "Payment ID": p.id,
                "Loan ID": p.loan_id,
                "Customer ID": p.customer_id,
                "Payment Date": str(p.payment_date),
                "Amount Paid": str(p.amount_paid),
                "Payment Mode": p.payment_mode,
                "Remarks": p.remarks or "",
                "Recorded By": p.recorded_by,
                "Created At": str(p.created_at),
            })

        df = pd.DataFrame(data)

        # Write to CSV buffer with secure metadata header
        buffer = io.StringIO()
        buffer.write("# SAKRA FINANCE — SECURE WORKSPACE DATA DESK\n")
        buffer.write(f"# Export Date: {today_ist().isoformat()}\n")
        buffer.write("# Classification: RESTRICTED FINANCIAL RECORD\n")
        buffer.write("# Verified Official Branding Asset ID: sakra-logo-v5\n")
        buffer.write("# ------------------------------------------------\n")
        df.to_csv(buffer, index=False)
        buffer.seek(0)

        filename = f"payments_export_{today_ist().isoformat()}.csv"

        return StreamingResponse(
            iter([buffer.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="pandas library is required for CSV export",
        )
    except Exception as e:
        logger.error("CSV export failed: %s", str(e))
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.delete("/{payment_id}", response_model=APIResponse)
async def delete_payment(
    payment_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionRequirement(ADMIN_ROLES)),
):
    """
    Delete a payment record and revert its balance and schedule effects.
    """
    from sqlalchemy.orm import selectinload
    from app.models.loan import Loan
    from app.models.payment import Payment
    from app.models.loan_schedule import LoanSchedule

    # 1. Fetch payment
    payment = await PaymentRepository.get_by_id(db, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    loan_id = payment.loan_id
    amount_paid = payment.amount_paid
    payment_date = payment.payment_date

    # 2. Fetch loan along with schedules and payments in a single DB query
    stmt = select(Loan).filter(Loan.id == loan_id).options(
        selectinload(Loan.schedules),
        selectinload(Loan.payments)
    )
    result = await db.execute(stmt)
    loan = result.scalars().first()
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")

    # 3. Update loan remaining balance and status
    loan.remaining_balance = Decimal(str(loan.remaining_balance)) + Decimal(str(amount_paid))
    loan.status = "ACTIVE"

    # 4. Locate and revert matching loan schedule installment
    schedule_entry = next((s for s in loan.schedules if s.due_date == payment_date), None)
    if schedule_entry:
        schedule_entry.paid_amount = Decimal("0")
        schedule_entry.remaining_amount = schedule_entry.expected_amount
        if payment_date < today_ist():
            schedule_entry.status = "MISSED"
        else:
            schedule_entry.status = "PENDING"

    # 5. Delete the payment record
    await db.delete(payment)
    # Create notifications
    from app.services.notification_service import create_system_notification, push_realtime_notifications
    from app.models.customer import Customer
    stmt_cust = select(Customer.name).filter(Customer.id == loan.customer_id)
    res_cust = await db.execute(stmt_cust)
    cust_name = res_cust.scalar() or f"ID #{loan.customer_id}"

    notifs = await create_system_notification(
        db,
        "PAYMENT_RECORDED",
        f"Payment of ₹{float(amount_paid):,.2f} deleted/reverted for customer: {cust_name} (Loan ID #{loan.id}) by {current_user.username}",
        customer_id=loan.customer_id
    )

    await db.commit()

    # Push real-time notifications
    push_realtime_notifications(notifs)

    # Invalidate cache
    if settings.CACHE_ENABLED:
        import asyncio
        from app.services.background_tasks import invalidate_cache_background
        asyncio.create_task(
            invalidate_cache_background(
                patterns=["payments:*", "loans:*", f"customers:summary:{loan.customer_id}"],
                keys=[f"customers:detail:{loan.customer_id}"]
            )
        )

    # Log audit
    ip_address = None
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        ip_address = forwarded_for.split(",")[0].strip()
    elif request.client:
        ip_address = request.client.host
    user_agent = request.headers.get("user-agent")

    from app.services.background_tasks import log_audit_background
    import asyncio
    asyncio.create_task(
        log_audit_background(
            actor_id=current_user.id,
            action="DELETE_PAYMENT",
            table_name="payments",
            record_id=payment_id,
            new_values={},
            ip_address=ip_address,
            user_agent=user_agent
        )
    )

    return APIResponse(
        success=True,
        message="Payment deleted successfully",
    )

