"""
Customer repository with Aadhaar encryption/hashing and optimistic locking.
"""
from typing import Optional
from sqlalchemy.orm import selectinload
from sqlalchemy import or_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio

from app.models.customer import Customer
from app.schemas.customer import CustomerCreate, CustomerUpdate
from app.utils.crypto import encrypt_aadhaar, decrypt_aadhaar, hash_aadhaar
from app.exceptions.handlers import DuplicateAadhaar, ConflictError, CustomerNotFound


class CustomerRepository:
    """Repository for Customer model database operations."""

    @staticmethod
    async def get_by_id(db: AsyncSession, customer_id: int) -> Optional[Customer]:
        """Get a customer by ID, excluding soft-deleted customers."""
        from app.models.loan import Loan
        stmt = select(Customer).filter(
            Customer.id == customer_id,
            Customer.is_deleted == False,
        ).options(
            selectinload(Customer.documents),
            selectinload(Customer.loans).selectinload(Loan.payments),
            selectinload(Customer.loans).selectinload(Loan.schedules)
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_by_aadhar_hash(db: AsyncSession, aadhar_hash: str) -> Optional[Customer]:
        """Get a customer by their hashed Aadhaar number."""
        stmt = select(Customer).filter(
            Customer.aadhar_hash == aadhar_hash,
            Customer.is_deleted == False,
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def list_customers(
        db: AsyncSession,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[Customer], int]:
        """
        List customers with optional search and pagination.

        Search matches against name and phone_number fields.

        Args:
            db: Database session
            search: Optional search term
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            Tuple of (list of customers, total count)
        """
        from app.models.loan import Loan
        
        where_clauses = [Customer.is_deleted == False]
        
        if search:
            search_term = f"%{search}%"
            try:
                search_id = int(search.strip())
            except ValueError:
                search_id = -1
                
            from app.utils.crypto import hash_aadhaar
            import re
            is_aadhar = bool(re.match(r"^\d{12}$", search.strip()))
            aadhar_h = hash_aadhaar(search.strip()) if is_aadhar else None

            filters = [
                Customer.name.ilike(search_term),
                Customer.phone_number.ilike(search_term)
            ]
            if search_id != -1:
                filters.append(Customer.id == search_id)
            if aadhar_h:
                filters.append(Customer.aadhar_hash == aadhar_h)
            elif len(search.strip()) == 64:
                filters.append(Customer.aadhar_hash == search.strip())

            where_clauses.append(or_(*filters))

        stmt = select(Customer).filter(*where_clauses).options(
            selectinload(Customer.documents),
            selectinload(Customer.loans).selectinload(Loan.payments)
        ).order_by(Customer.created_at.desc()).offset(skip).limit(limit)

        count_stmt = select(func.count()).select_from(Customer).filter(*where_clauses)

        res = await db.execute(stmt)
        count_res = await db.execute(count_stmt)
        customers = list(res.scalars().all())
        total = count_res.scalar() or 0

        return customers, total

    @staticmethod
    async def create(db: AsyncSession, schema: CustomerCreate, creator_id: int) -> Customer:
        """
        Create a new customer with encrypted Aadhaar.

        Hashes the Aadhaar for duplicate detection and encrypts it for storage.
        Creates a masked version (XXXX-XXXX-1234) for display.

        Args:
            db: Database session
            schema: CustomerCreate schema with customer data
            creator_id: ID of the user creating the customer

        Returns:
            The created Customer object

        Raises:
            DuplicateAadhaar: If a customer with the same Aadhaar already exists
        """
        # Hash Aadhaar for duplicate check
        aadhar_hash = hash_aadhaar(schema.aadhar_number)

        # Check for duplicate
        stmt = select(Customer).filter(
            Customer.aadhar_hash == aadhar_hash,
            Customer.is_deleted == False,
        )
        result = await db.execute(stmt)
        existing = result.scalars().first()

        if existing:
            raise DuplicateAadhaar()

        # Encrypt Aadhaar for storage
        aadhar_encrypted = encrypt_aadhaar(schema.aadhar_number)

        # Create masked version for display
        aadhar_masked = f"XXXX-XXXX-{schema.aadhar_number[-4:]}"

        customer = Customer(
            name=schema.name,
            phone_number=schema.phone_number,
            address=schema.address,
            aadhar_encrypted=aadhar_encrypted,
            aadhar_hash=aadhar_hash,
            aadhar_masked=aadhar_masked,
            promissory_note=schema.promissory_note,
            date_of_birth=schema.date_of_birth,
            gender=schema.gender,
            occupation=schema.occupation,
            remarks=schema.remarks,
            created_by=creator_id,
            version_id=1,
        )

        db.add(customer)
        await db.flush()
        return customer

    @staticmethod
    async def update(db: AsyncSession, customer: Customer, schema: CustomerUpdate) -> Customer:
        """
        Update customer fields with optimistic locking.

        Checks that the provided version_id matches the current version
        to prevent concurrent modification conflicts.

        Args:
            db: Database session
            customer: Existing Customer object to update
            schema: CustomerUpdate schema with optional fields

        Returns:
            The updated Customer object

        Raises:
            ConflictError: If version_id doesn't match (optimistic lock failure)
        """
        if customer.version_id != schema.version_id:
            raise ConflictError(
                "Customer record has been modified by another user. "
                f"Expected version {schema.version_id}, current version {customer.version_id}."
            )

        update_data = schema.model_dump(exclude_unset=True, exclude={"version_id"})
        for field, value in update_data.items():
            if value is not None:
                setattr(customer, field, value)

        customer.version_id += 1
        await db.flush()
        return customer

    @staticmethod
    async def soft_delete(db: AsyncSession, customer: Customer) -> Customer:
        """Soft delete a customer by setting is_deleted flag."""
        customer.is_deleted = True
        await db.flush()
        return customer
