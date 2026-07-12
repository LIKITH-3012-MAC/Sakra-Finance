"""
Customer management routes: CRUD with loan summaries, credit scores, and document attachments.
"""
import logging
import re
import io
import asyncio
from datetime import date, datetime
from app.utils.timezone import now_ist_naive
from decimal import Decimal
from typing import Optional
from io import BytesIO
from PIL import Image

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status, File, UploadFile, Form, Response, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload, joinedload

from app.database.session import get_db
from app.middleware.auth import get_current_user, PermissionRequirement
from app.models.user import User
from app.models.customer import Customer
from app.models.customer_document import CustomerDocument
from app.models.loan import Loan
from app.repositories.customer_repo import CustomerRepository
from app.repositories.loan_repo import LoanRepository
from app.repositories.payment_repo import PaymentRepository
from app.schemas.common import APIResponse
from app.schemas.customer import CustomerCreate, CustomerUpdate, CustomerResponse
from app.schemas.loan import LoanResponse
from app.services.audit import log_audit
from app.services.interest import get_loan_balance_summary
from app.services.credit_score import calculate_credit_score
from app.exceptions.handlers import CustomerNotFound, DuplicateAadhaar, ConflictError
from app.services.cache import cache
from app.core.config import settings
from app.utils.timezone import today_ist

logger = logging.getLogger("sakra.customers")

router = APIRouter()

ADMIN_ROLES = ["SUPER_ADMIN", "ADMIN"]
WRITE_ROLES = ["SUPER_ADMIN", "ADMIN", "ASSISTANT_ADMIN"]

def validate_uploaded_file(file: UploadFile, max_size_mb: int, allowed_extensions: list[str], allowed_types: list[str]) -> int:
    filename = file.filename or ""
    ext = filename.split(".")[-1].lower() if "." in filename else ""
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file extension '{ext}'. Allowed: {', '.join(allowed_extensions)}"
        )
    content_type = file.content_type or ""
    if content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported content type '{content_type}'. Allowed: {', '.join(allowed_types)}"
        )
    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)
    max_bytes = max_size_mb * 1024 * 1024
    if size > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File '{filename}' exceeds maximum size of {max_size_mb}MB (actual size: {size / (1024*1024):.2f}MB)"
        )
    return size


def process_profile_photo(file_bytes: bytes) -> bytes:
    try:
        img = Image.open(BytesIO(file_bytes))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.thumbnail((400, 400), Image.Resampling.LANCZOS)
        out_buf = BytesIO()
        img.save(out_buf, format="JPEG", quality=85, optimize=True)
        return out_buf.getvalue()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid profile photo image data: {str(e)}")


@router.get("/", response_model=APIResponse)
async def list_customers(
    search: str = Query(None, description="Search by name, phone, customer ID, or Aadhaar Hash"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=1000),  # Enforce pagination max 1000 limit
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List customers with pagination and optional search.
    Includes loan details, dynamic document flags, and aggregate stats for each customer.
    """
    # Enforce maximum limit check
    if limit > 1000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum allowed limit is 1000 records per request"
        )

    # Redis Cache lookup
    cache_key = f"customers:list:{search or 'none'}:{skip}:{limit}"
    if settings.CACHE_ENABLED:
        cached_data = await cache.get(cache_key)
        if cached_data is not None:
            return APIResponse(
                success=True,
                message="Retrieved customers (cached)",
                data=cached_data,
            )

    customers, total = await CustomerRepository.list_customers(db, search, skip, limit)

    from app.services.loan_service import compute_pending_installments_metadata
    customers_data = []
    for customer in customers:
        customer_dict = CustomerResponse.model_validate(customer).model_dump(mode="json")
        
        # Calculate collection intelligence delinquency metadata
        today = today_ist()
        delinquency = compute_pending_installments_metadata(customer.loans, today)
        customer_dict.update(delinquency)

        # Check document presence
        customer_dict["has_profile_photo"] = any(d.document_type == "PROFILE_PHOTO" for d in customer.documents)
        customer_dict["has_aadhaar"] = any(d.document_type == "AADHAAR" for d in customer.documents)
        customer_dict["has_promissory_note"] = any(d.document_type == "PROMISSORY_NOTE" for d in customer.documents)

        # Get all loans with balance summaries and credit scores
        loans = [l for l in customer.loans if not l.is_deleted]
        loans_data = []
        total_paid_all = Decimal("0")
        total_principal = Decimal("0")
        active_loans = 0
        today = today_ist()

        for loan in loans:
            loan_dict = LoanResponse.model_validate(loan).model_dump(mode="json")
            payments = [p for p in loan.payments]
            loan_total_paid = sum((p.amount_paid for p in payments), Decimal("0"))
            total_paid_all += loan_total_paid
            total_principal += loan.principal_amount
            if loan.status == "ACTIVE":
                active_loans += 1

            balance = get_loan_balance_summary(
                loan.principal_amount, loan.interest_rate, loan.interest_formula, loan_total_paid, loan.duration_days
            )
            loan_dict["balance_summary"] = {k: str(v) for k, v in balance.items()}
            loan_dict["payments_count"] = len(payments)

            # Credit score per loan
            credit_score = calculate_credit_score(loan, payments, today)
            loan_dict["credit_score"] = credit_score

            loans_data.append(loan_dict)

        if loans_data:
            avg_credit_score = round(
                sum(ld["credit_score"] for ld in loans_data) / len(loans_data), 2
            )
        else:
            avg_credit_score = 700.0

        customer_dict["loans"] = loans_data
        customer_dict["aggregate"] = {
            "total_loans": len(loans_data),
            "total_paid": str(total_paid_all),
            "credit_score": avg_credit_score,
        }

        customer_dict["loan_summary"] = {
            "total_loans": len(loans),
            "active_loans": active_loans,
            "total_principal": str(total_principal),
            "total_paid": str(total_paid_all),
        }

        customers_data.append(customer_dict)

    response_data = {
        "customers": customers_data,
        "total": total,
        "skip": skip,
        "limit": limit,
    }

    if settings.CACHE_ENABLED:
        await cache.set(cache_key, response_data, expire_seconds=settings.CACHE_TTL)

    return APIResponse(
        success=True,
        message=f"Retrieved {len(customers_data)} customers",
        data=response_data,
    )


@router.post("/", response_model=APIResponse)
async def create_customer(
    request: Request,
    background_tasks: BackgroundTasks,
    name: str = Form(...),
    phone_number: str = Form(...),
    address: Optional[str] = Form(None),
    aadhar_number: str = Form(...),
    promissory_note: Optional[str] = Form(None),
    date_of_birth: Optional[str] = Form(None),
    gender: Optional[str] = Form(None),
    occupation: Optional[str] = Form(None),
    remarks: Optional[str] = Form(None),
    profile_photo: Optional[UploadFile] = File(None),
    aadhaar: UploadFile = File(...),
    promissory_file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionRequirement(ADMIN_ROLES)),
):
    """
    Onboard a new customer with identity fields and binary document uploads.
    Saves document blobs to the database LONGBLOB column in the background.
    """
    # 1. Validate Form Fields using Pydantic schema
    try:
        schema_data = CustomerCreate(
            name=name,
            phone_number=phone_number,
            address=address,
            aadhar_number=aadhar_number,
            promissory_note=promissory_note,
            date_of_birth=date_of_birth,
            gender=gender,
            occupation=occupation,
            remarks=remarks
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

    # 2. Validate Document Uploads (Fast check on content typings and size metadata)
    aadhaar_size = validate_uploaded_file(
        aadhaar, 10, ["pdf", "png", "jpeg", "jpg"], ["application/pdf", "image/jpeg", "image/png"]
    )
    promissory_size = validate_uploaded_file(
        promissory_file, 20, ["pdf", "png", "jpeg", "jpg"], ["application/pdf", "image/jpeg", "image/png"]
    )
    photo_size = 0
    if profile_photo and profile_photo.filename:
        photo_size = validate_uploaded_file(
            profile_photo, 5, ["jpg", "jpeg", "png", "webp"], ["image/jpeg", "image/png", "image/webp"]
        )

    # 3. Create Customer Record & Defer Documents/Audits to Background
    try:
        try:
            customer = await CustomerRepository.create(db, schema_data, current_user.id)
        except DuplicateAadhaar as e:
            raise HTTPException(status_code=e.status_code, detail=e.message)

        # Save immediately to lock the customer record and acquire customer ID
        await db.flush()

        # Read files into memory to safely pass bytes to background thread
        aadhaar_bytes = await aadhaar.read()
        promissory_bytes = await promissory_file.read()
        
        photo_bytes = None
        if profile_photo and profile_photo.filename:
            photo_bytes = await profile_photo.read()

        # Commit customer record in primary database transaction
        await db.commit()

        # Extract client IP and user agent safely for audit log
        ip_address = None
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            ip_address = forwarded_for.split(",")[0].strip()
        elif request.client:
            ip_address = request.client.host
        user_agent = request.headers.get("user-agent")

        # Defer files processing, documents saving, and audit logs to background tasks
        from app.services.background_tasks import (
            process_customer_registration_documents,
            log_audit_background,
            invalidate_cache_background
        )
        import asyncio

        asyncio.create_task(
            process_customer_registration_documents(
                customer_id=customer.id,
                creator_id=current_user.id,
                aadhaar_filename=aadhaar.filename or "aadhaar.pdf",
                aadhaar_content_type=aadhaar.content_type or "application/pdf",
                aadhaar_bytes=aadhaar_bytes,
                aadhaar_size=aadhaar_size,
                promissory_filename=promissory_file.filename or "promissory.pdf",
                promissory_content_type=promissory_file.content_type or "application/pdf",
                promissory_bytes=promissory_bytes,
                promissory_size=promissory_size,
                profile_photo_filename=profile_photo.filename if profile_photo else None,
                profile_photo_content_type=profile_photo.content_type if profile_photo else None,
                profile_photo_bytes=photo_bytes,
                ip_address=ip_address,
                user_agent=user_agent
            )
        )

        # Main Customer Create Audit Log in background
        asyncio.create_task(
            log_audit_background(
                actor_id=current_user.id,
                action="CREATE_CUSTOMER",
                table_name="customers",
                record_id=customer.id,
                new_values={"name": customer.name, "phone": customer.phone_number},
                ip_address=ip_address,
                user_agent=user_agent
            )
        )

        # Invalidate caches in background
        asyncio.create_task(
            invalidate_cache_background(
                patterns=["customers:*"],
                keys=[]
            )
        )

    except HTTPException as http_err:
        await db.rollback()
        raise http_err
    except Exception as err:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Onboarding transaction failed: " + str(err))

    # Build response schema instantly
    response_dict = CustomerResponse.model_validate(customer).model_dump(mode="json")
    response_dict["has_profile_photo"] = (profile_photo is not None and profile_photo.filename is not None)
    response_dict["has_aadhaar"] = True
    response_dict["has_promissory_note"] = True

    return APIResponse(
        success=True,
        message="Customer onboarding completed successfully",
        data=response_dict,
    )


@router.get("/{customer_id}", response_model=APIResponse)
async def get_customer(
    customer_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get full customer profile with loans, aggregate payments, document presence, and metadata.
    """
    cache_key = f"customers:detail:{customer_id}"
    if settings.CACHE_ENABLED:
        cached_data = await cache.get(cache_key)
        if cached_data is not None:
            return APIResponse(
                success=True,
                message="Customer profile retrieved (cached)",
                data=cached_data,
            )

    stmt = select(Customer).filter(
        Customer.id == customer_id,
        Customer.is_deleted == False
    ).options(
        selectinload(Customer.documents).joinedload(CustomerDocument.uploader),
        selectinload(Customer.loans).selectinload(Loan.payments),
        selectinload(Customer.loans).selectinload(Loan.schedules)
    )
    result = await db.execute(stmt)
    customer = result.scalars().first()

    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    customer_dict = CustomerResponse.model_validate(customer).model_dump(mode="json")

    # Calculate collection intelligence delinquency metadata
    from app.services.loan_service import compute_pending_installments_metadata
    today = today_ist()
    delinquency = compute_pending_installments_metadata(customer.loans, today)
    customer_dict.update(delinquency)

    # Check document presence
    customer_dict["has_profile_photo"] = any(d.document_type == "PROFILE_PHOTO" for d in customer.documents)
    customer_dict["has_aadhaar"] = any(d.document_type == "AADHAAR" for d in customer.documents)
    customer_dict["has_promissory_note"] = any(d.document_type == "PROMISSORY_NOTE" for d in customer.documents)

    # Expose document metadata safely
    docs_meta = {}
    for d in customer.documents:
        uploader_name = d.uploader.username if d.uploader else "System"
        docs_meta[d.document_type] = {
            "id": d.id,
            "filename": d.filename,
            "content_type": d.content_type,
            "file_size": d.file_size,
            "uploaded_at": d.created_at.isoformat(),
            "uploaded_by_name": uploader_name
        }
    customer_dict["documents_metadata"] = docs_meta

    # Get all loans (using eager relationship)
    loans = [l for l in customer.loans if not l.is_deleted]
    loans_data = []
    today = today_ist()

    for loan in loans:
        loan_dict = LoanResponse.model_validate(loan).model_dump(mode="json")
        payments = [p for p in loan.payments]
        loan_total_paid = sum((p.amount_paid for p in payments), Decimal("0"))

        balance = get_loan_balance_summary(
            loan.principal_amount, loan.interest_rate, loan.interest_formula, loan_total_paid, loan.duration_days
        )
        loan_dict["balance_summary"] = {k: str(v) for k, v in balance.items()}
        loan_dict["payments_count"] = len(payments)

        # Credit score per loan
        credit_score = calculate_credit_score(loan, payments, today)
        loan_dict["credit_score"] = credit_score

        loans_data.append(loan_dict)

    # Aggregate credit score (average across loans)
    if loans_data:
        avg_credit_score = round(
            sum(ld["credit_score"] for ld in loans_data) / len(loans_data), 2
        )
    else:
        avg_credit_score = 700.0

    # Fetch dynamic aggregate repayment rows for all loans
    from app.services.loan_service import get_loan_repayment_rows
    from app.models.user import User

    # Pre-fetch all recorder users in a single query across all payments
    all_recorder_ids = set()
    for loan in loans:
        for p in loan.payments:
            if p.recorded_by:
                all_recorder_ids.add(p.recorded_by)

    recorders_dict = {}
    if all_recorder_ids:
        stmt_rec = select(User).filter(User.id.in_(list(all_recorder_ids)))
        res_rec = await db.execute(stmt_rec)
        for u in res_rec.scalars().all():
            recorders_dict[u.id] = u.username

    aggregate_payments = []
    for loan in loans:
        repayment_rows = await get_loan_repayment_rows(db, loan, recorders_dict=recorders_dict)
        aggregate_payments.extend(repayment_rows)

    # Sort payments by date descending
    aggregate_payments.sort(key=lambda x: x["payment_date"], reverse=True)

    # Fetch backend summary details to prevent frontend JavaScript calculations
    from app.services.loan_service import get_customer_summary_details
    summary_details = await get_customer_summary_details(db, customer_id, loans=loans)

    response_payload = {
        "customer": customer_dict,
        "loans": loans_data,
        "aggregate_payments": aggregate_payments,
        "credit_score": avg_credit_score,
        "summary": summary_details
    }

    if settings.CACHE_ENABLED:
        await cache.set(cache_key, response_payload, expire_seconds=settings.CACHE_TTL)

    return APIResponse(
        success=True,
        message="Customer profile retrieved",
        data=response_payload,
    )


@router.put("/{customer_id}", response_model=APIResponse)
async def update_customer(
    customer_id: int,
    update_data: CustomerUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionRequirement(WRITE_ROLES)),
):
    """
    Update customer data. Requires ASSISTANT_ADMIN or higher.
    Uses optimistic locking via version_id.
    """
    customer = await CustomerRepository.get_by_id(db, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    old_values = {
        "name": customer.name,
        "phone_number": customer.phone_number,
        "address": customer.address,
    }

    try:
        updated = await CustomerRepository.update(db, customer, update_data)
    except ConflictError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    new_values = {
        "name": updated.name,
        "phone_number": updated.phone_number,
        "address": updated.address,
    }

    await log_audit(
        db=db,
        actor_id=current_user.id,
        action="UPDATE_CUSTOMER",
        table_name="customers",
        record_id=customer_id,
        old_values=old_values,
        new_values=new_values,
        request=request,
    )
    await db.commit()
    
    # Invalidate caches
    if settings.CACHE_ENABLED:
        await cache.invalidate_pattern("customers:*")
        await cache.delete("dashboard_metrics")

    return APIResponse(
        success=True,
        message="Customer updated successfully",
        data=CustomerResponse.model_validate(updated).model_dump(mode="json"),
    )


@router.delete("/{customer_id}", response_model=APIResponse)
async def delete_customer(
    customer_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionRequirement(ADMIN_ROLES)),
):
    """
    Soft delete a customer. Requires ADMIN role.
    """
    customer = await CustomerRepository.get_by_id(db, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    await CustomerRepository.soft_delete(db, customer)

    await log_audit(
        db=db,
        actor_id=current_user.id,
        action="DELETE_CUSTOMER",
        table_name="customers",
        record_id=customer_id,
        old_values={"name": customer.name},
        request=request,
    )
    await db.commit()
    
    # Invalidate caches
    if settings.CACHE_ENABLED:
        await cache.invalidate_pattern("customers:*")
        await cache.delete("dashboard_metrics")

    return APIResponse(
        success=True,
        message="Customer deleted successfully",
    )


# ── SECURE FILE API ENDPOINTS ──────────────────────────────────

@router.get("/{customer_id}/photo")
async def get_customer_photo(
    customer_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Serve customer profile photo blob or default vector avatar."""
    stmt = select(CustomerDocument).filter(
        CustomerDocument.customer_id == customer_id,
        CustomerDocument.document_type == "PROFILE_PHOTO"
    )
    res = await db.execute(stmt)
    doc = res.scalars().first()

    if not doc:
        default_avatar_svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" style="width:100%;height:100%;color:#cbd5e1;background:#f1f5f9;"><path fill-rule="evenodd" d="M7.5 6a4.5 4.5 0 119 0 4.5 4.5 0 01-9 0zM3.751 20.105a8.25 8.25 0 0116.498 0 .75.75 0 01-.437.695A9.75 9.75 0 0112 22.5c-2.786 0-5.433-.608-7.812-1.7a.75.75 0 01-.437-.695z" clip-rule="evenodd" /></svg>"""
        return Response(content=default_avatar_svg, media_type="image/svg+xml")
        
    return Response(
        content=doc.file_blob,
        media_type=doc.content_type,
        headers={"Content-Disposition": f"inline; filename={doc.filename}"}
    )


@router.get("/{customer_id}/aadhaar")
async def get_customer_aadhaar(
    customer_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Serve Aadhaar PDF or image, restricting VIEWER role access."""
    if current_user.role == "VIEWER":
        raise HTTPException(status_code=403, detail="Access Denied: VIEWER role is not authorized to retrieve sensitive documents")
        
    stmt = select(CustomerDocument).filter(
        CustomerDocument.customer_id == customer_id,
        CustomerDocument.document_type == "AADHAAR"
    )
    res = await db.execute(stmt)
    doc = res.scalars().first()

    if not doc:
        raise HTTPException(status_code=404, detail="Aadhaar document not found")
        
    return Response(
        content=doc.file_blob,
        media_type=doc.content_type,
        headers={"Content-Disposition": f"inline; filename={doc.filename}"}
    )


@router.get("/{customer_id}/promissory")
async def get_customer_promissory(
    customer_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Serve Promissory Note blob, restricting VIEWER role access."""
    if current_user.role == "VIEWER":
        raise HTTPException(status_code=403, detail="Access Denied: VIEWER role is not authorized to retrieve sensitive documents")
        
    stmt = select(CustomerDocument).filter(
        CustomerDocument.customer_id == customer_id,
        CustomerDocument.document_type == "PROMISSORY_NOTE"
    )
    res = await db.execute(stmt)
    doc = res.scalars().first()

    if not doc:
        raise HTTPException(status_code=404, detail="Promissory note document not found")
        
    return Response(
        content=doc.file_blob,
        media_type=doc.content_type,
        headers={"Content-Disposition": f"inline; filename={doc.filename}"}
    )


@router.post("/{customer_id}/documents/{document_type}")
async def upload_document_replacement(
    customer_id: int,
    document_type: str,
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionRequirement(WRITE_ROLES)),
):
    """Replace an existing KYC document or upload a missing one."""
    document_type = document_type.upper()
    if document_type not in ["PROFILE_PHOTO", "AADHAAR", "PROMISSORY_NOTE"]:
        raise HTTPException(status_code=400, detail="Invalid document type")

    # Validate file size & type
    if document_type == "PROFILE_PHOTO":
        size = validate_uploaded_file(file, 5, ["jpg", "jpeg", "png", "webp"], ["image/jpeg", "image/png", "image/webp"])
        bytes_data = await file.read()
        final_bytes = process_profile_photo(bytes_data)
        content_type = "image/jpeg"
    elif document_type == "AADHAAR":
        size = validate_uploaded_file(file, 10, ["pdf", "png", "jpeg", "jpg"], ["application/pdf", "image/jpeg", "image/png"])
        final_bytes = await file.read()
        content_type = file.content_type
    else:
        size = validate_uploaded_file(file, 20, ["pdf", "png", "jpeg", "jpg"], ["application/pdf", "image/jpeg", "image/png"])
        final_bytes = await file.read()
        content_type = file.content_type

    # Check for existing document
    stmt = select(CustomerDocument).filter(
        CustomerDocument.customer_id == customer_id,
        CustomerDocument.document_type == document_type
    )
    res = await db.execute(stmt)
    doc = res.scalars().first()

    if doc:
        doc.file_blob = final_bytes
        doc.filename = file.filename
        doc.content_type = content_type
        doc.file_size = len(final_bytes) if document_type == "PROFILE_PHOTO" else size
        doc.uploaded_by = current_user.id
        doc.created_at = now_ist_naive()
        action = "DOCUMENT_REPLACED" if document_type != "PROFILE_PHOTO" else "PHOTO_UPDATED"
    else:
        doc = CustomerDocument(
            customer_id=customer_id,
            document_type=document_type,
            file_blob=final_bytes,
            filename=file.filename,
            content_type=content_type,
            file_size=len(final_bytes) if document_type == "PROFILE_PHOTO" else size,
            uploaded_by=current_user.id
        )
        db.add(doc)
        action = "PHOTO_UPLOADED" if document_type == "PROFILE_PHOTO" else f"{document_type}_UPLOADED"

    await log_audit(
        db=db,
        actor_id=current_user.id,
        action=action,
        table_name="customer_documents",
        record_id=customer_id,
        new_values={"filename": file.filename, "size": len(final_bytes)},
        request=request
    )
    await db.commit()

    # Invalidate caches
    if settings.CACHE_ENABLED:
        await cache.invalidate_pattern("customers:*")

    return APIResponse(success=True, message=f"Document {document_type} successfully updated")


@router.delete("/{customer_id}/documents/{document_type}")
async def delete_customer_document(
    customer_id: int,
    document_type: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionRequirement(ADMIN_ROLES)),
):
    """Delete a document by type. Requires ADMIN or higher."""
    document_type = document_type.upper()
    stmt = select(CustomerDocument).filter(
        CustomerDocument.customer_id == customer_id,
        CustomerDocument.document_type == document_type
    )
    res = await db.execute(stmt)
    doc = res.scalars().first()
    
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {document_type} not found")

    await db.delete(doc)
    await log_audit(
        db=db,
        actor_id=current_user.id,
        action="PHOTO_DELETED" if document_type == "PROFILE_PHOTO" else "DOCUMENT_DELETED",
        table_name="customer_documents",
        record_id=customer_id,
        old_values={"filename": doc.filename},
        request=request
    )
    await db.commit()

    # Invalidate caches
    if settings.CACHE_ENABLED:
        await cache.invalidate_pattern("customers:*")

    return APIResponse(success=True, message=f"Document {document_type} successfully deleted")
