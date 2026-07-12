import logging
import json
from io import BytesIO
from typing import Optional, Any
from PIL import Image

from app.database.session import SessionLocal
from app.models.audit_log import AuditLog
from app.models.customer_document import CustomerDocument
from app.services.cache import cache
from app.core.config import settings

logger = logging.getLogger("sakra.background")


async def log_audit_background(
    actor_id: int,
    action: str,
    table_name: str,
    record_id: Optional[int] = None,
    old_values: Optional[dict[str, Any]] = None,
    new_values: Optional[dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
):
    """Save an audit log entry in the background using a fresh database session."""
    try:
        old_values_str = json.dumps(old_values, default=str) if old_values else None
        new_values_str = json.dumps(new_values, default=str) if new_values else None

        async with SessionLocal() as db:
            audit_entry = AuditLog(
                actor_id=actor_id,
                action=action,
                table_name=table_name,
                record_id=record_id,
                old_values=old_values_str,
                new_values=new_values_str,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            db.add(audit_entry)
            await db.commit()
            logger.info("Background audit log created: action=%s table=%s record=%s", action, table_name, record_id)
    except Exception as e:
        logger.error("Failed to create background audit log: %s", str(e), exc_info=True)


def _compress_profile_photo(file_bytes: bytes) -> bytes:
    """Helper to compress profile photo to JPEG thumbnail."""
    img = Image.open(BytesIO(file_bytes))
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    img.thumbnail((400, 400), Image.Resampling.LANCZOS)
    out_buf = BytesIO()
    img.save(out_buf, format="JPEG", quality=85, optimize=True)
    return out_buf.getvalue()


async def process_customer_registration_documents(
    customer_id: int,
    creator_id: int,
    aadhaar_filename: str,
    aadhaar_content_type: str,
    aadhaar_bytes: bytes,
    aadhaar_size: int,
    promissory_filename: str,
    promissory_content_type: str,
    promissory_bytes: bytes,
    promissory_size: int,
    profile_photo_filename: Optional[str],
    profile_photo_content_type: Optional[str],
    profile_photo_bytes: Optional[bytes],
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
):
    """Processes document uploads and writes audit entries asynchronously in the background."""
    try:
        async with SessionLocal() as db:
            # 1. Save Aadhaar
            aadhaar_doc = CustomerDocument(
                customer_id=customer_id,
                document_type="AADHAAR",
                file_blob=aadhaar_bytes,
                filename=aadhaar_filename,
                content_type=aadhaar_content_type,
                file_size=aadhaar_size,
                uploaded_by=creator_id,
            )
            db.add(aadhaar_doc)

            # 2. Save Promissory Note
            promissory_doc = CustomerDocument(
                customer_id=customer_id,
                document_type="PROMISSORY_NOTE",
                file_blob=promissory_bytes,
                filename=promissory_filename,
                content_type=promissory_content_type,
                file_size=promissory_size,
                uploaded_by=creator_id,
            )
            db.add(promissory_doc)

            # 3. Compress & Save Profile Photo if present
            photo_len = 0
            if profile_photo_bytes and profile_photo_filename:
                compressed_photo = _compress_profile_photo(profile_photo_bytes)
                photo_len = len(compressed_photo)
                photo_doc = CustomerDocument(
                    customer_id=customer_id,
                    document_type="PROFILE_PHOTO",
                    file_blob=compressed_photo,
                    filename=profile_photo_filename,
                    content_type="image/jpeg",
                    file_size=photo_len,
                    uploaded_by=creator_id,
                )
                db.add(photo_doc)

            await db.commit()
            logger.info("Documents saved for Customer ID: %d", customer_id)

            # 4. Generate audits in background (separately to ensure clean audits database entries)
            await log_audit_background(
                actor_id=creator_id,
                action="AADHAAR_UPLOADED",
                table_name="customer_documents",
                record_id=customer_id,
                new_values={"filename": aadhaar_filename, "size": aadhaar_size},
                ip_address=ip_address,
                user_agent=user_agent
            )

            await log_audit_background(
                actor_id=creator_id,
                action="PROMISSORY_UPLOADED",
                table_name="customer_documents",
                record_id=customer_id,
                new_values={"filename": promissory_filename, "size": promissory_size},
                ip_address=ip_address,
                user_agent=user_agent
            )

            if photo_len > 0:
                await log_audit_background(
                    actor_id=creator_id,
                    action="PHOTO_UPLOADED",
                    table_name="customer_documents",
                    record_id=customer_id,
                    new_values={"filename": profile_photo_filename, "size": photo_len},
                    ip_address=ip_address,
                    user_agent=user_agent
                )
    except Exception as e:
        logger.error("Failed to process customer registration documents in background: %s", str(e), exc_info=True)


async def warm_dashboard_cache_background():
    """Recalculate dynamic dashboard metrics and set to Redis cache."""
    try:
        from app.services.loan_service import get_dashboard_metrics_details
        async with SessionLocal() as db:
            metrics = await get_dashboard_metrics_details(db)
            if settings.CACHE_ENABLED:
                await cache.set("dashboard_metrics", metrics, expire_seconds=settings.CACHE_TTL)
                logger.info("Dashboard metrics cache warmed successfully.")
    except Exception as e:
        logger.error("Failed to warm dashboard metrics cache: %s", str(e), exc_info=True)


async def warm_customer_summary_cache_background(customer_id: int):
    """Recalculate customer summary details and set to Redis cache."""
    try:
        from app.services.loan_service import get_customer_summary_details
        async with SessionLocal() as db:
            summary = await get_customer_summary_details(db, customer_id)
            if settings.CACHE_ENABLED:
                cache_key = f"customers:summary:{customer_id}"
                await cache.set(cache_key, summary, expire_seconds=settings.CACHE_TTL)
                logger.info("Customer %d summary cache warmed successfully.", customer_id)
    except Exception as e:
        logger.error("Failed to warm customer summary cache: %s", str(e), exc_info=True)


async def invalidate_cache_background(patterns: list[str], keys: list[str]):
    """Invalidates multiple cache keys or pattern keys in the background."""
    try:
        if settings.CACHE_ENABLED:
            for p in patterns:
                await cache.invalidate_pattern(p)
            for k in keys:
                await cache.delete(k)
            logger.info("Background cache invalidation completed.")
    except Exception as e:
        logger.error("Failed to invalidate cache in background: %s", str(e), exc_info=True)
