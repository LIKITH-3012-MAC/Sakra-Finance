"""
Central model registry for Alembic and metadata operations.

Import Base and ALL models here so that Alembic's `target_metadata = Base.metadata`
can discover every table. This module should be imported in Alembic's env.py.
"""

from app.database.connection import Base  # noqa: F401

# Import all models so they register with Base.metadata
from app.models.user import User  # noqa: F401
from app.models.customer import Customer  # noqa: F401
from app.models.customer_document import CustomerDocument  # noqa: F401
from app.models.loan import Loan  # noqa: F401
from app.models.loan_schedule import LoanSchedule  # noqa: F401
from app.models.payment import Payment  # noqa: F401
from app.models.payment_adjustment import PaymentAdjustment  # noqa: F401
from app.models.credit_score import CreditScore  # noqa: F401
from app.models.notification import Notification  # noqa: F401
from app.models.audit_log import AuditLog  # noqa: F401
from app.models.ai_log import AIAuditLog  # noqa: F401

