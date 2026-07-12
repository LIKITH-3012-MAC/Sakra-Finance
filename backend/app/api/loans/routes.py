"""
Loan management routes: CRUD with schedule generation and payment tracking.
"""
import logging
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database.session import get_db
from app.middleware.auth import get_current_user, PermissionRequirement
from app.models.user import User
from app.models.loan_schedule import LoanSchedule
from app.repositories.loan_repo import LoanRepository
from app.repositories.customer_repo import CustomerRepository
from app.repositories.payment_repo import PaymentRepository
from app.schemas.common import APIResponse
from app.schemas.loan import LoanCreate, LoanUpdate, LoanResponse
from app.schemas.payment import PaymentResponse
from app.services.audit import log_audit
from app.services.loan_service import get_loan_status_details
from app.exceptions.handlers import LoanNotFound, ConflictError
from app.services.cache import cache
from app.utils.timezone import today_ist
from app.core.config import settings

logger = logging.getLogger("sakra.loans")

router = APIRouter()

ADMIN_ROLES = ["SUPER_ADMIN", "ADMIN"]


@router.get("/", response_model=APIResponse)
async def list_loans(
    customer_id: int = Query(None, description="Filter by customer ID"),
    status_filter: str = Query(None, alias="status", description="Filter by loan status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),  # Default limit set to 50, ge=1, le=1000
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all loans with optional filtering by customer and status.
    """
    # Enforce maximum allowed limit
    if limit > 1000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum allowed limit is 1000 records per request"
        )

    # Redis Cache retrieval
    cache_key = f"loans:list:{customer_id or 'all'}:{status_filter or 'all'}:{skip}:{limit}"
    if settings.CACHE_ENABLED:
        cached_data = await cache.get(cache_key)
        if cached_data is not None:
            return APIResponse(
                success=True,
                message="Retrieved loans (cached)",
                data=cached_data,
            )

    from app.models.loan import Loan

    stmt = select(Loan)
    count_stmt = select(func.count(Loan.id))

    where_clauses = []
    if customer_id:
        where_clauses.append(Loan.customer_id == customer_id)
    if status_filter:
        where_clauses.append(Loan.status == status_filter.upper())

    if where_clauses:
        stmt = stmt.filter(*where_clauses)
        count_stmt = count_stmt.filter(*where_clauses)

    import asyncio
    res_task = db.execute(stmt.order_by(Loan.created_at.desc()).offset(skip).limit(limit))
    count_task = db.execute(count_stmt)

    res, count_res = await asyncio.gather(res_task, count_task)
    loans = res.scalars().all()
    total = count_res.scalar() or 0

    loans_data = [LoanResponse.model_validate(l).model_dump(mode="json") for l in loans]

    response_data = {
        "loans": loans_data,
        "total": total,
        "skip": skip,
        "limit": limit,
    }

    if settings.CACHE_ENABLED:
        await cache.set(cache_key, response_data, expire_seconds=settings.CACHE_TTL)

    return APIResponse(
        success=True,
        message=f"Retrieved {len(loans_data)} loans",
        data=response_data,
    )


@router.post("/", response_model=APIResponse)
async def create_loan(
    loan_data: LoanCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionRequirement(ADMIN_ROLES)),
):
    """
    Create a new loan with auto-generated installment schedule.
    Requires ADMIN role.
    """
    # Verify customer exists
    customer = await CustomerRepository.get_by_id(db, loan_data.customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    loan = await LoanRepository.create(db, loan_data, current_user.id)

    await log_audit(
        db=db,
        actor_id=current_user.id,
        action="CREATE_LOAN",
        table_name="loans",
        record_id=loan.id,
        new_values={
            "customer_id": loan.customer_id,
            "principal": str(loan.principal_amount),
            "interest_rate": str(loan.interest_rate),
            "formula": loan.interest_formula,
            "duration": loan.duration_days,
        },
        request=request,
    )
    await db.commit()

    # Invalidate caches
    if settings.CACHE_ENABLED:
        await cache.invalidate_pattern("loans:*")
        await cache.invalidate_pattern("customers:*")
        await cache.delete("dashboard_metrics")

    return APIResponse(
        success=True,
        message="Loan created with installment schedule",
        data=LoanResponse.model_validate(loan).model_dump(mode="json"),
    )


@router.get("/{loan_id}", response_model=APIResponse)
async def get_loan(
    loan_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get loan details with schedule, payments, and status summary.
    """
    cache_key = f"loans:detail:{loan_id}"
    if settings.CACHE_ENABLED:
        cached_data = await cache.get(cache_key)
        if cached_data is not None:
            return APIResponse(
                success=True,
                message="Loan details retrieved (cached)",
                data=cached_data,
            )

    loan = await LoanRepository.get_by_id(db, loan_id)
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")

    loan_dict = LoanResponse.model_validate(loan).model_dump(mode="json")

    # Get payments
    payments = await PaymentRepository.list_by_loan(db, loan_id)
    payments_data = [PaymentResponse.model_validate(p).model_dump(mode="json") for p in payments]

    from app.services.loan_service import get_loan_repayment_rows
    repayment_rows = await get_loan_repayment_rows(db, loan)

    schedule_data = [
        {
            "installment_number": idx + 1,
            "due_date": r["payment_date"],
            "expected_amount": str(r["expected_amount"]),
            "paid_amount": str(r["amount_paid"]),
            "remaining_amount": str(r["expected_amount"] - r["amount_paid"] if r["amount_paid"] < r["expected_amount"] else 0.0),
            "status": r["payment_status"],
        }
        for idx, r in enumerate(repayment_rows)
    ]

    # Get status details
    today = today_ist()
    status_details = get_loan_status_details(loan, payments, today)
    status_data = {k: str(v) if isinstance(v, Decimal) else v for k, v in status_details.items()}

    loan_dict["payments"] = payments_data
    loan_dict["schedule"] = schedule_data
    loan_dict["status_details"] = status_data

    if settings.CACHE_ENABLED:
        await cache.set(cache_key, loan_dict, expire_seconds=settings.CACHE_TTL)

    return APIResponse(
        success=True,
        message="Loan details retrieved",
        data=loan_dict,
    )


@router.put("/{loan_id}", response_model=APIResponse)
async def update_loan(
    loan_id: int,
    update_data: LoanUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionRequirement(ADMIN_ROLES)),
):
    """
    Update loan data. Requires ADMIN role.
    Uses optimistic locking via version_id.
    """
    loan = await LoanRepository.get_by_id(db, loan_id)
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")

    old_values = {
        "principal_amount": str(loan.principal_amount),
        "interest_rate": str(loan.interest_rate),
        "interest_formula": loan.interest_formula,
        "duration_days": loan.duration_days,
    }

    try:
        updated = await LoanRepository.update(db, loan, update_data)
    except ConflictError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    new_values = {
        "principal_amount": str(updated.principal_amount),
        "interest_rate": str(updated.interest_rate),
        "interest_formula": updated.interest_formula,
        "duration_days": updated.duration_days,
    }

    await log_audit(
        db=db,
        actor_id=current_user.id,
        action="UPDATE_LOAN",
        table_name="loans",
        record_id=loan_id,
        old_values=old_values,
        new_values=new_values,
        request=request,
    )
    await db.commit()

    # Invalidate caches
    if settings.CACHE_ENABLED:
        await cache.invalidate_pattern("loans:*")
        await cache.invalidate_pattern("customers:*")
        await cache.delete("dashboard_metrics")

    return APIResponse(
        success=True,
        message="Loan updated successfully",
        data=LoanResponse.model_validate(updated).model_dump(mode="json"),
    )


@router.get("/{loan_id}/schedule", response_model=APIResponse)
async def get_loan_schedule(
    loan_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the installment schedule for a specific loan.
    """
    cache_key = f"loans:schedule:{loan_id}"
    if settings.CACHE_ENABLED:
        cached_data = await cache.get(cache_key)
        if cached_data is not None:
            return APIResponse(
                success=True,
                message="Retrieved installments (cached)",
                data=cached_data,
            )

    loan = await LoanRepository.get_by_id(db, loan_id)
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")

    from app.services.loan_service import get_loan_repayment_rows
    repayment_rows = await get_loan_repayment_rows(db, loan)

    schedule_data = [
        {
            "id": r["id"],
            "loan_id": r["loan_id"],
            "installment_number": idx + 1,
            "due_date": r["payment_date"],
            "expected_amount": str(r["expected_amount"]),
            "paid_amount": str(r["amount_paid"]),
            "remaining_amount": str(r["expected_amount"] - r["amount_paid"] if r["amount_paid"] < r["expected_amount"] else 0.0),
            "status": r["payment_status"],
        }
        for idx, r in enumerate(repayment_rows)
    ]

    if settings.CACHE_ENABLED:
        await cache.set(cache_key, schedule_data, expire_seconds=settings.CACHE_TTL)

    return APIResponse(
        success=True,
        message=f"Retrieved {len(schedule_data)} installments for loan #{loan_id}",
        data=schedule_data,
    )
