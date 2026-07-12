"""
Loan repository with schedule generation and optimistic locking.
"""
from typing import Optional
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.loan import Loan
from app.models.loan_schedule import LoanSchedule
from app.schemas.loan import LoanCreate, LoanUpdate
from app.services.loan_service import calculate_loan_end_date, generate_loan_schedule
from app.exceptions.handlers import ConflictError


class LoanRepository:
    """Repository for Loan model database operations."""

    @staticmethod
    async def get_by_id(db: AsyncSession, loan_id: int) -> Optional[Loan]:
        """Get a loan by ID."""
        stmt = select(Loan).filter(Loan.id == loan_id)
        result = await db.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def list_by_customer(db: AsyncSession, customer_id: int) -> list[Loan]:
        """Get all loans for a specific customer."""
        stmt = select(Loan).filter(
            Loan.customer_id == customer_id,
        ).order_by(Loan.created_at.desc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def create(db: AsyncSession, schema: LoanCreate, creator_id: int) -> Loan:
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
        from decimal import Decimal, ROUND_HALF_UP
        from app.services.interest import calculate_interest

        end_date = calculate_loan_end_date(schema.loan_start_date, schema.duration_days)
        interest = calculate_interest(
            schema.principal_amount,
            schema.interest_rate,
            schema.interest_formula,
            schema.duration_days,
        )
        total_repayable = schema.principal_amount + interest
        daily_inst = (total_repayable / Decimal(str(schema.duration_days))).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

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
            interest_amount=interest,
            total_repayable_amount=total_repayable,
            daily_installment=daily_inst,
            remaining_balance=total_repayable,
        )

        db.add(loan)
        await db.flush()  # Get the loan ID

        # Generate and insert schedule records
        schedule_data = generate_loan_schedule(
            loan_id=loan.id,
            principal=schema.principal_amount,
            interest_rate=schema.interest_rate,
            interest_formula=schema.interest_formula,
            start_date=schema.loan_start_date,
            duration_days=schema.duration_days,
        )

        from sqlalchemy import insert
        if schedule_data:
            await db.execute(insert(LoanSchedule), schedule_data)

        await db.flush()
        return loan

    @staticmethod
    async def update(db: AsyncSession, loan: Loan, schema: LoanUpdate) -> Loan:
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

        # Recalculate calculated fields if any configuration changed
        if any(f in update_data for f in ["principal_amount", "interest_rate", "interest_formula", "duration_days"]):
            from decimal import Decimal, ROUND_HALF_UP
            from app.services.interest import calculate_interest
            from app.models.payment import Payment
            
            principal = loan.principal_amount
            rate = loan.interest_rate
            formula = loan.interest_formula
            duration = loan.duration_days
            
            interest = calculate_interest(principal, rate, formula, duration)
            total_repayable = principal + interest
            daily_inst = (total_repayable / Decimal(str(duration))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            
            # Fetch all payments to subtract from total repayable
            stmt = select(Payment).filter(Payment.loan_id == loan.id)
            result = await db.execute(stmt)
            all_payments = result.scalars().all()
            total_paid = sum(p.amount_paid for p in all_payments)
            remaining = max(total_repayable - total_paid, Decimal("0"))
            
            loan.interest_amount = interest
            loan.total_repayable_amount = total_repayable
            loan.daily_installment = daily_inst
            loan.remaining_balance = remaining

        loan.version_id += 1
        await db.flush()
        return loan

    @staticmethod
    async def get_active_loans(db: AsyncSession) -> list[Loan]:
        """Get all loans with ACTIVE status."""
        stmt = select(Loan).filter(Loan.status == "ACTIVE")
        result = await db.execute(stmt)
        return list(result.scalars().all())
