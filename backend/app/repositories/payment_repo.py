"""
Payment repository with duplicate detection, optimistic locking, and adjustment tracking.
"""
from typing import Optional, Any
from datetime import date
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.payment import Payment
from app.models.payment_adjustment import PaymentAdjustment
from app.schemas.payment import PaymentCreate, PaymentUpdate
from app.exceptions.handlers import PaymentError, ConflictError


class PaymentRepository:
    """Repository for Payment model database operations."""

    @staticmethod
    async def get_by_id(db: AsyncSession, payment_id: int) -> Optional[Payment]:
        """Get a payment by ID."""
        stmt = select(Payment).filter(Payment.id == payment_id).options(joinedload(Payment.loan))
        result = await db.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_by_loan_and_date(db: AsyncSession, loan_id: int, payment_date: date) -> Optional[Payment]:
        """Get a payment for a specific loan on a specific date."""
        stmt = select(Payment).filter(
            Payment.loan_id == loan_id,
            Payment.payment_date == payment_date,
        ).options(joinedload(Payment.loan))
        result = await db.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def list_by_loan(db: AsyncSession, loan_id: int) -> list[Payment]:
        """Get all payments for a specific loan, ordered by date."""
        stmt = select(Payment).filter(
            Payment.loan_id == loan_id,
        ).order_by(Payment.payment_date.asc()).options(joinedload(Payment.loan))
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def list_by_customer(db: AsyncSession, customer_id: int) -> list[Payment]:
        """Get all payments for a specific customer, ordered by date descending."""
        stmt = select(Payment).filter(
            Payment.customer_id == customer_id,
        ).order_by(Payment.payment_date.desc()).options(joinedload(Payment.loan))
        result = await db.execute(stmt)
        return list(result.scalars().all())
    @staticmethod
    async def create(
        db: AsyncSession,
        schema: PaymentCreate,
        customer_id: int,
        recorder_id: int,
        loan: Any,
    ) -> Payment:
        """
        Create a new payment with duplicate detection using unique constraints.
        """
        from decimal import Decimal
        from sqlalchemy.exc import IntegrityError

        amount_paid_decimal = Decimal(str(schema.amount_paid))
        remaining = max(loan.remaining_balance - amount_paid_decimal, Decimal("0"))

        payment_status = "PAID"
        loan.remaining_balance = remaining
        if remaining <= 0:
            loan.status = "COMPLETED"
        else:
            loan.status = "ACTIVE"

        payment = Payment(
            loan_id=schema.loan_id,
            customer_id=customer_id,
            payment_date=schema.payment_date,
            expected_amount=schema.amount_paid,
            amount_paid=schema.amount_paid,
            remaining_amount=remaining,
            payment_mode=schema.payment_mode,
            payment_status=payment_status,
            remarks=schema.remarks,
            recorded_by=recorder_id,
            version_id=1,
        )

        try:
            db.add(payment)
            await db.flush()
        except IntegrityError:
            raise PaymentError(
                f"A payment for loan #{schema.loan_id} on {schema.payment_date} already exists."
            )

        return payment
    async def update(db: AsyncSession, payment: Payment, schema: PaymentUpdate) -> Payment:
        """
        Update a payment with optimistic locking and adjustment tracking.

        Creates a PaymentAdjustment record to track the modification.

        Args:
            db: Database session
            payment: Existing Payment object to update
            schema: PaymentUpdate schema with new amount

        Returns:
            The updated Payment object

        Raises:
            ConflictError: If version_id doesn't match
        """
        if payment.version_id != schema.version_id:
            raise ConflictError(
                f"Payment record has been modified. "
                f"Expected version {schema.version_id}, current version {payment.version_id}."
            )

        old_amount = payment.amount_paid

        # Create adjustment record for audit trail
        adjustment = PaymentAdjustment(
            payment_id=payment.id,
            old_amount=old_amount,
            new_amount=schema.amount_paid,
            reason=f"Payment modified from ₹{old_amount} to ₹{schema.amount_paid}",
        )
        db.add(adjustment)

        # Update payment
        payment.amount_paid = schema.amount_paid
        payment.version_id += 1
        await db.flush()

        # Update loan remaining balance and status
        from app.models.loan import Loan
        stmt = select(Loan).filter(Loan.id == payment.loan_id)
        result = await db.execute(stmt)
        loan = result.scalars().first()
        if loan:
            # sum all payments
            stmt = select(Payment.amount_paid).filter(
                Payment.loan_id == loan.id
            )
            result = await db.execute(stmt)
            all_payments_sum = result.all()
            total_paid = sum(p[0] for p in all_payments_sum)

            if loan.total_repayable_amount is not None:
                total_due = loan.total_repayable_amount
            else:
                from app.services.interest import calculate_interest
                total_due = loan.principal_amount + calculate_interest(loan.principal_amount, loan.interest_rate, loan.interest_formula, loan.duration_days)

            remaining = max(total_due - total_paid, Decimal("0"))
            loan.remaining_balance = remaining
            if remaining <= 0:
                loan.status = "COMPLETED"
            else:
                loan.status = "ACTIVE"

        return payment

    @staticmethod
    async def list_today(db: AsyncSession, today: date) -> list[Payment]:
        """Get all payments recorded for today."""
        stmt = select(Payment).filter(
            Payment.payment_date == today,
        ).order_by(Payment.created_at.desc()).options(joinedload(Payment.loan))
        result = await db.execute(stmt)
        return list(result.scalars().all())
