"""
Loan management routes: CRUD with schedule generation and payment tracking.
"""
import logging
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

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

logger = logging.getLogger("sakra.loans")

router = APIRouter()

ADMIN_ROLES = ["SUPER_ADMIN", "ADMIN"]


@router.get("/", response_model=APIResponse)
async def list_loans(
    customer_id: int = Query(None, description="Filter by customer ID"),
    status_filter: str = Query(None, alias="status", description="Filter by loan status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all loans with optional filtering by customer and status.
    """
    from app.models.loan import Loan

    query = db.query(Loan)

    if customer_id:
        query = query.filter(Loan.customer_id == customer_id)
    if status_filter:
        query = query.filter(Loan.status == status_filter.upper())

    total = query.count()
    loans = query.order_by(Loan.created_at.desc()).offset(skip).limit(limit).all()
    loans_data = [LoanResponse.model_validate(l).model_dump(mode="json") for l in loans]

    return APIResponse(
        success=True,
        message=f"Retrieved {len(loans_data)} loans",
        data={
            "loans": loans_data,
            "total": total,
            "skip": skip,
            "limit": limit,
        },
    )


@router.post("/", response_model=APIResponse)
async def create_loan(
    loan_data: LoanCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionRequirement(ADMIN_ROLES)),
):
    """
    Create a new loan with auto-generated installment schedule.
    Requires ADMIN role.
    """
    # Verify customer exists
    customer = CustomerRepository.get_by_id(db, loan_data.customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    loan = LoanRepository.create(db, loan_data, current_user.id)

    log_audit(
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
    db.commit()

    # Invalidate dashboard metrics cache
    from app.services.cache import cache
    cache.delete("dashboard_metrics")

    return APIResponse(
        success=True,
        message="Loan created with installment schedule",
        data=LoanResponse.model_validate(loan).model_dump(mode="json"),
    )


@router.get("/{loan_id}", response_model=APIResponse)
async def get_loan(
    loan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get loan details with schedule, payments, and status summary.
    """
    loan = LoanRepository.get_by_id(db, loan_id)
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")

    loan_dict = LoanResponse.model_validate(loan).model_dump(mode="json")

    # Get payments
    payments = PaymentRepository.list_by_loan(db, loan_id)
    payments_data = [PaymentResponse.model_validate(p).model_dump(mode="json") for p in payments]

    # Get schedule
    schedule = db.query(LoanSchedule).filter(
        LoanSchedule.loan_id == loan_id
    ).order_by(LoanSchedule.installment_number).all()

    from app.services.loan_service import get_loan_repayment_rows
    repayment_rows = get_loan_repayment_rows(db, loan)

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
    today = date.today()
    status_details = get_loan_status_details(loan, payments, today)
    # Convert Decimals to strings for JSON serialization
    status_data = {k: str(v) if isinstance(v, Decimal) else v for k, v in status_details.items()}

    loan_dict["payments"] = payments_data
    loan_dict["schedule"] = schedule_data
    loan_dict["status_details"] = status_data

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
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionRequirement(ADMIN_ROLES)),
):
    """
    Update loan data. Requires ADMIN role.
    Uses optimistic locking via version_id.
    """
    loan = LoanRepository.get_by_id(db, loan_id)
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")

    old_values = {
        "principal_amount": str(loan.principal_amount),
        "interest_rate": str(loan.interest_rate),
        "interest_formula": loan.interest_formula,
        "duration_days": loan.duration_days,
    }

    try:
        updated = LoanRepository.update(db, loan, update_data)
    except ConflictError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    new_values = {
        "principal_amount": str(updated.principal_amount),
        "interest_rate": str(updated.interest_rate),
        "interest_formula": updated.interest_formula,
        "duration_days": updated.duration_days,
    }

    log_audit(
        db=db,
        actor_id=current_user.id,
        action="UPDATE_LOAN",
        table_name="loans",
        record_id=loan_id,
        old_values=old_values,
        new_values=new_values,
        request=request,
    )
    db.commit()

    return APIResponse(
        success=True,
        message="Loan updated successfully",
        data=LoanResponse.model_validate(updated).model_dump(mode="json"),
    )


@router.get("/{loan_id}/schedule", response_model=APIResponse)
async def get_loan_schedule(
    loan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the installment schedule for a specific loan.
    """
    loan = LoanRepository.get_by_id(db, loan_id)
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")

    schedule = db.query(LoanSchedule).filter(
        LoanSchedule.loan_id == loan_id
    ).order_by(LoanSchedule.installment_number).all()

    from app.services.loan_service import get_loan_repayment_rows
    repayment_rows = get_loan_repayment_rows(db, loan)

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


    return APIResponse(
        success=True,
        message=f"Retrieved {len(schedule_data)} installments for loan #{loan_id}",
        data=schedule_data,
    )
