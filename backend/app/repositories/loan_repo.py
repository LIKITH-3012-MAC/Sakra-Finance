"""
Loan repository with schedule generation and optimistic locking.
"""
from typing import Optional
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.loan import Loan
from app.models.loan_schedule import LoanSchedule
from app.schemas.loan import LoanCreate, LoanUpdate
from app.services.loan_service import calculate_loan_end_date, generate_loan_schedule
from app.exceptions.handlers import ConflictError


class LoanRepository:
    """Repository for Loan model database operations."""

    @staticmethod
    def get_by_id(db: Session, loan_id: int) -> Optional[Loan]:
        """Get a loan by ID."""
        return db.query(Loan).filter(Loan.id == loan_id).first()

    @staticmethod
    def list_by_customer(db: Session, customer_id: int) -> list[Loan]:
        """Get all loans for a specific customer."""
        return db.query(Loan).filter(
            Loan.customer_id == customer_id,
        ).order_by(Loan.created_at.desc()).all()

    @staticmethod
    def create(db: Session, schema: LoanCreate, creator_id: int) -> Loan:
        """
        Create a new loan with calculated end date and auto-generated schedule.

        Also bulk-inserts LoanSchedule records for each installment day.

        Args:
            db: Database session
            schema: LoanCreate schema with loan data
            creator_id: ID of the user creating the loan

        Returns:
            The created Loan object (with schedule records committed)
        """
        end_date = calculate_loan_end_date(schema.loan_start_date, schema.duration_days)

        loan = Loan(
            customer_id=schema.customer_id,
            principal_amount=schema.principal_amount,
            interest_formula=schema.interest_formula,
            interest_rate=schema.interest_rate,
            loan_start_date=schema.loan_start_date,
            loan_end_date=end_date,
            duration_days=schema.duration_days,
            status="ACTIVE",
            created_by=creator_id,
            version_id=1,
        )

        db.add(loan)
        db.flush()  # Get the loan ID

        # Generate and insert schedule records
        schedule_data = generate_loan_schedule(
            loan_id=loan.id,
            principal=schema.principal_amount,
            interest_rate=schema.interest_rate,
            interest_formula=schema.interest_formula,
            start_date=schema.loan_start_date,
            duration_days=schema.duration_days,
        )

        for entry in schedule_data:
            schedule_record = LoanSchedule(
                loan_id=entry["loan_id"],
                installment_number=entry["installment_number"],
                due_date=entry["due_date"],
                expected_amount=entry["expected_amount"],
                paid_amount=entry["paid_amount"],
                remaining_amount=entry["remaining_amount"],
                status=entry["status"],
            )
            db.add(schedule_record)

        db.flush()
        return loan

    @staticmethod
    def update(db: Session, loan: Loan, schema: LoanUpdate) -> Loan:
        """
        Update loan fields with optimistic locking.

        Args:
            db: Database session
            loan: Existing Loan object to update
            schema: LoanUpdate schema with optional fields

        Returns:
            The updated Loan object

        Raises:
            ConflictError: If version_id doesn't match
        """
        if loan.version_id != schema.version_id:
            raise ConflictError(
                f"Loan record has been modified. "
                f"Expected version {schema.version_id}, current version {loan.version_id}."
            )

        update_data = schema.model_dump(exclude_unset=True, exclude={"version_id"})

        for field, value in update_data.items():
            if value is not None:
                setattr(loan, field, value)

        # Recalculate end date if start date or duration changed
        if "loan_start_date" in update_data or "duration_days" in update_data:
            start = loan.loan_start_date
            duration = loan.duration_days
            loan.loan_end_date = calculate_loan_end_date(start, duration)

        loan.version_id += 1
        db.flush()
        return loan

    @staticmethod
    def get_active_loans(db: Session) -> list[Loan]:
        """Get all loans with ACTIVE status."""
        return db.query(Loan).filter(Loan.status == "ACTIVE").all()
