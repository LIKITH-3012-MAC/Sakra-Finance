import os
import time
import logging
from typing import Any

# Enforce India Standard Time (IST) process-wide (configurable via env)
timezone = os.environ.get("TIMEZONE") or os.environ.get("TZ") or "Asia/Kolkata"
os.environ["TZ"] = timezone
if hasattr(time, "tzset"):
    time.tzset()
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.rate_limit import limiter
from app.database.connection import engine, Base
from app.middleware.request_logging import RequestLoggingMiddleware
from app.schemas.common import APIResponse

# Import all models to ensure they are registered with SQLAlchemy Base
from app.models.user import User
from app.models.customer import Customer
from app.models.customer_document import CustomerDocument
from app.models.loan import Loan
from app.models.loan_schedule import LoanSchedule
from app.models.payment import Payment
from app.models.payment_adjustment import PaymentAdjustment
from app.models.credit_score import CreditScore
from app.models.notification import Notification
from app.models.audit_log import AuditLog
from app.models.ai_log import AIAuditLog
from app.models.copilot_session import CopilotSession
from app.models.copilot_message import CopilotMessage
from app.models.loan_closure import LoanClosure



# Import routers
from app.api.auth.routes import router as auth_router
from app.api.users.routes import router as users_router
from app.api.customers.routes import router as customers_router
from app.api.loans.routes import router as loans_router
from app.api.payments.routes import router as payments_router
from app.api.notifications.routes import router as notifications_router
from app.api.analytics.routes import router as analytics_router
from app.api.audit.routes import router as audit_router
from app.api.copilot.routes import router as copilot_router
from app.api.admin_control.routes import router as admin_router
from app.api.loan_closure.routes import router as loan_closure_router



logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sakra.main")

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Sakra Finance Enterprise Banking Platform Backend API",
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
)

# Attach SlowAPI limiter state
app.state.limiter = limiter

from fastapi.middleware.gzip import GZipMiddleware

# Security Headers Middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'; object-src 'none';"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    return response

# Middleware
app.add_middleware(RequestLoggingMiddleware)
if settings.ENABLE_GZIP:
    app.add_middleware(GZipMiddleware, minimum_size=1000)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception Handlers to match APIResponse envelope
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    response_content = APIResponse(
        success=False,
        message=str(exc.detail),
        errors={"detail": exc.detail},
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=response_content.model_dump(),
        headers=getattr(exc, "headers", None),
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    response_content = APIResponse(
        success=False,
        message="Validation failed",
        errors=errors,
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=response_content.model_dump(),
    )

@app.exception_handler(RateLimitExceeded)
async def ratelimit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    response_content = APIResponse(
        success=False,
        message="Too many requests. Please try again later.",
        errors={"detail": str(exc)},
    )
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content=response_content.model_dump(),
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled Exception: %s", str(exc), exc_info=True)
    response_content = APIResponse(
        success=False,
        message="Internal server error",
        errors={"detail": str(exc) if settings.DEBUG else "Please contact support"},
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=response_content.model_dump(),
    )

# Include Routers
app.include_router(auth_router, prefix=f"{settings.API_V1_STR}/auth")
app.include_router(users_router, prefix=f"{settings.API_V1_STR}/users")
app.include_router(customers_router, prefix=f"{settings.API_V1_STR}/customers")
app.include_router(loans_router, prefix=f"{settings.API_V1_STR}/loans")
app.include_router(payments_router, prefix=f"{settings.API_V1_STR}/payments")
app.include_router(notifications_router, prefix=f"{settings.API_V1_STR}/notifications")
app.include_router(analytics_router, prefix=f"{settings.API_V1_STR}/analytics")
app.include_router(audit_router, prefix=f"{settings.API_V1_STR}/audit")
app.include_router(copilot_router, prefix=f"{settings.API_V1_STR}/copilot")
app.include_router(admin_router, prefix=f"{settings.API_V1_STR}/admin")
app.include_router(loan_closure_router, prefix=f"{settings.API_V1_STR}/loan-closure")
app.include_router(admin_router, prefix=settings.API_V1_STR)



@app.on_event("startup")
async def on_startup():
    logger.info("Verifying system configurations and security keys...")
    
    # 1. Check Security Keys
    if not settings.JWT_SECRET_KEY or len(settings.JWT_SECRET_KEY) < 32:
        raise RuntimeError("CONFIGURATION ERROR: JWT_SECRET_KEY is missing or too short.")
    if not settings.JWT_REFRESH_SECRET_KEY or len(settings.JWT_REFRESH_SECRET_KEY) < 32:
        raise RuntimeError("CONFIGURATION ERROR: JWT_REFRESH_SECRET_KEY is missing or too short.")
    if not settings.AES_ENCRYPTION_KEY:
        raise RuntimeError("CONFIGURATION ERROR: AES_ENCRYPTION_KEY is missing.")

    # 2. Check AI & Resend Service Keys
    if not settings.LOAN_CLOSURE_SECRET:
        raise RuntimeError("CONFIGURATION ERROR: LOAN_CLOSURE_SECRET environment variable is not configured.")
    if not settings.GROQ_API_KEY:
        raise RuntimeError("CONFIGURATION ERROR: GROQ_API_KEY environment variable is not configured.")
    if not settings.RESEND_API_KEY:
        raise RuntimeError("CONFIGURATION ERROR: RESEND_API_KEY environment variable is not configured.")
    if not settings.SENDER_EMAIL:
        raise RuntimeError("CONFIGURATION ERROR: SENDER_EMAIL environment variable is not configured.")

    # 3. Check Database connection
    from sqlalchemy.sql import text
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("✓ Database connection verified successfully.")
    except Exception as e:
        raise RuntimeError(f"CONFIGURATION ERROR: Failed to connect to MySQL database: {str(e)}")

    logger.info("Initializing database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Helper function to run sync migrations on connection
    def check_and_run_migrations(connection):
        from sqlalchemy import inspect
        inspector = inspect(connection)
        
        # Automatically check and add preferred_language column if it is missing
        columns = [col["name"] for col in inspector.get_columns("users")]
        if "preferred_language" not in columns:
            logger.info("Column preferred_language not found in users table. Migrating schema...")
            connection.execute(text("ALTER TABLE users ADD COLUMN preferred_language VARCHAR(5) NOT NULL DEFAULT 'en'"))
            logger.info("✓ Column preferred_language successfully added to users table.")

        # Automatically alter interest_rate column in loans table to DECIMAL(8,4) if its precision/scale is different
        loans_columns = {col["name"]: col for col in inspector.get_columns("loans")}
        if "interest_rate" in loans_columns:
            col_type = loans_columns["interest_rate"]["type"]
            if getattr(col_type, "scale", None) != 4 or getattr(col_type, "precision", None) != 8:
                logger.info("Column interest_rate in loans table does not have DECIMAL(8,4) precision. Migrating schema...")
                connection.execute(text("ALTER TABLE loans MODIFY COLUMN interest_rate DECIMAL(8,4) NOT NULL"))
                logger.info("✓ Column interest_rate successfully migrated to DECIMAL(8,4).")

        # Automatically add new columns to loans table if they are missing
        new_cols = {
            "interest_amount": "DECIMAL(15,2) NULL",
            "total_repayable_amount": "DECIMAL(15,2) NULL",
            "daily_installment": "DECIMAL(15,2) NULL",
            "remaining_balance": "DECIMAL(15,2) NULL"
        }
        for col_name, col_type in new_cols.items():
            if col_name not in loans_columns:
                logger.info(f"Column {col_name} not found in loans table. Migrating schema...")
                connection.execute(text(f"ALTER TABLE loans ADD COLUMN {col_name} {col_type}"))
                logger.info(f"✓ Column {col_name} successfully added to loans table.")

        # Create new indexes if they do not exist
        indexes_to_create = [
            ("users", "idx_users_email_status", "(email, status)"),
            ("users", "idx_users_role_status", "(role, status)"),
            ("users", "idx_users_created_at", "(created_at)"),
            ("users", "idx_users_updated_at", "(updated_at)"),
            ("customers", "idx_customers_created_at", "(created_at)"),
            ("customers", "idx_customers_updated_at", "(updated_at)"),
            ("customers", "idx_customers_is_deleted_created_at", "(is_deleted, created_at)"),
            ("loans", "idx_loans_created_at", "(created_at)"),
            ("loans", "idx_loans_is_deleted", "(is_deleted)"),
            ("loans", "idx_loans_customer_status", "(customer_id, status)"),
            ("loans", "idx_loans_status_created_at", "(status, created_at)"),
            ("loans", "idx_loans_customer_created_at", "(customer_id, created_at)"),
            ("payments", "idx_payments_created_at", "(created_at)"),
            ("payments", "idx_payments_customer_payment_date", "(customer_id, payment_date)"),
            ("payments", "idx_payments_loan_created_at", "(loan_id, created_at)"),
            ("payments", "idx_payments_customer_created_at", "(customer_id, created_at)"),
            ("user_sessions", "idx_sessions_created_at", "(created_at)"),
            ("user_sessions", "idx_sessions_is_active", "(is_active)"),
            ("user_sessions", "idx_sessions_user_created_at", "(user_id, created_at)"),
            ("notifications", "idx_notifications_sent_at", "(sent_at)"),
            ("notifications", "idx_notifications_user_is_read_sent_at", "(user_id, is_read, sent_at)"),
            ("audit_logs", "idx_audit_logs_created_at", "(created_at)"),
            ("audit_logs", "idx_audit_logs_actor_id", "(actor_id)"),
            ("audit_logs", "idx_audit_logs_actor_created_at", "(actor_id, created_at)"),
            ("mail_logs", "idx_mail_logs_created_at", "(created_at)"),
            ("mail_logs", "idx_mail_logs_recipient_created_at", "(recipient, created_at)")
        ]
        
        for table, index_name, cols in indexes_to_create:
            existing_indexes = [idx["name"] for idx in inspector.get_indexes(table)]
            if index_name not in existing_indexes:
                logger.info(f"Creating index {index_name} on table {table}...")
                connection.execute(text(f"CREATE INDEX {index_name} ON {table} {cols}"))
                logger.info(f"✓ Index {index_name} created successfully.")

    try:
        async with engine.begin() as conn:
            await conn.run_sync(check_and_run_migrations)
    except Exception as migrate_err:
        logger.error("Failed to run dynamic schema migrations: %s", str(migrate_err))

    # Seed default SUPER_ADMIN if none exists
    from sqlalchemy import select
    from app.database.session import SessionLocal
    from app.core.security import hash_password
    from app.ai.rag.vector_store import vector_store
    
    async with SessionLocal() as db:
        try:
            stmt = select(User).filter(User.role == "SUPER_ADMIN")
            result = await db.execute(stmt)
            super_admin_exists = result.scalars().first()
            if not super_admin_exists:
                logger.info("No SUPER_ADMIN found. Seeding default admin user...")
                admin_user = User(
                    username="admin",
                    email="admin@sakra.finance",
                    password_hash=hash_password("SuperAdmin@2026"),
                    role="SUPER_ADMIN",
                    status="active",
                    is_deleted=False,
                    version_id=1,
                )
                db.add(admin_user)
                await db.commit()
                logger.info("Default administrator seeded (admin / SuperAdmin@2026).")
                
            # Seed local RAG vector database with domain rules
            logger.info("Seeding local RAG vector store database...")
            vector_store.add_document(
                doc_id="rule_1",
                text="Sakra Finance loans default to a duration of 100 days. Daily repayments are expected every single day from day 1 to day 100.",
                metadata={"category": "loan_terms"}
            )
            vector_store.add_document(
                doc_id="rule_2",
                text="Interest formulas: Simple Interest (Included) increases the core principal immediately. Simple Interest (Excluded) tracks interest separately in a secondary ledger. Fixed percentage applies a flat % over the total loan amount.",
                metadata={"category": "interest_formulas"}
            )
            vector_store.add_document(
                doc_id="rule_3",
                text="Overdue tracking: A loan is marked OVERDUE if the current date is past the loan end date and the outstanding balance is greater than zero.",
                metadata={"category": "overdue_policy"}
            )
            vector_store.add_document(
                doc_id="rule_4",
                text="Credit scoring rules: Calculated from 300 to 850. Weights: 40% payment regularity (unique days of payment), 40% compliance (ratio of paid to expected amount), and 20% timeliness (deductions for overdue days).",
                metadata={"category": "credit_score"}
            )
            logger.info("RAG vector database seeding completed.")
            
            # Warm up dashboard metrics cache on application startup asynchronously
            from app.services.background_tasks import warm_dashboard_cache_background
            logger.info("Warming up dashboard metrics cache on startup...")
            import asyncio
            asyncio.create_task(warm_dashboard_cache_background())
        except Exception as e:
            logger.error("Error during startup seed: %s", str(e))
            await db.rollback()

@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "healthy", "timestamp": time.time()}

