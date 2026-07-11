"""
Customer repository with Aadhaar encryption/hashing and optimistic locking.
"""
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from app.models.customer import Customer
from app.schemas.customer import CustomerCreate, CustomerUpdate
from app.utils.crypto import encrypt_aadhaar, decrypt_aadhaar, hash_aadhaar
from app.exceptions.handlers import DuplicateAadhaar, ConflictError, CustomerNotFound


class CustomerRepository:
    """Repository for Customer model database operations."""

    @staticmethod
    def get_by_id(db: Session, customer_id: int) -> Optional[Customer]:
        """Get a customer by ID, excluding soft-deleted customers."""
        return db.query(Customer).filter(
            Customer.id == customer_id,
            Customer.is_deleted == False,
        ).first()

    @staticmethod
    def get_by_aadhar_hash(db: Session, aadhar_hash: str) -> Optional[Customer]:
        """Get a customer by their hashed Aadhaar number."""
        return db.query(Customer).filter(
            Customer.aadhar_hash == aadhar_hash,
            Customer.is_deleted == False,
        ).first()

    @staticmethod
    def list_customers(
        db: Session,
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
        from sqlalchemy.orm import selectinload
        from app.models.loan import Loan
        from app.models.payment import Payment
        query = db.query(Customer).filter(Customer.is_deleted == False).options(
            selectinload(Customer.documents),
            selectinload(Customer.loans).selectinload(Loan.payments)
        )

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

            query = query.filter(or_(*filters))


        total = query.count()
        customers = query.order_by(Customer.created_at.desc()).offset(skip).limit(limit).all()

        return customers, total

    @staticmethod
    def create(db: Session, schema: CustomerCreate, creator_id: int) -> Customer:
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
        existing = db.query(Customer).filter(
            Customer.aadhar_hash == aadhar_hash,
            Customer.is_deleted == False,
        ).first()

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
        db.flush()
        return customer

    @staticmethod
    def update(db: Session, customer: Customer, schema: CustomerUpdate) -> Customer:
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
        db.flush()
        return customer

    @staticmethod
    def soft_delete(db: Session, customer: Customer) -> Customer:
        """Soft delete a customer by setting is_deleted flag."""
        customer.is_deleted = True
        db.flush()
        return customer
