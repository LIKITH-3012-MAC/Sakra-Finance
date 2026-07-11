import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from app.repositories.customer_repo import CustomerRepository
from app.repositories.loan_repo import LoanRepository
from app.repositories.payment_repo import PaymentRepository
from app.services.interest import get_loan_balance_summary
from app.services.credit_score import calculate_credit_score

logger = logging.getLogger("sakra.ai.tools")

def get_customers_list(db: Session, search: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetch matching customer registry summaries."""
    try:
        customers, _ = CustomerRepository.list_customers(db, search=search, skip=0, limit=20)
        return [
            {
                "id": c.id,
                "name": c.name,
                "phone_number": c.phone_number,
                "address": c.address,
                "version_id": c.version_id,
            }
            for c in customers
        ]
    except Exception as e:
        logger.error("AI tool failed to list customers: %s", str(e))
        return []

def get_customer_profile(db: Session, customer_id: int) -> Dict[str, Any]:
    """Retrieve full customer profile including active loans and credit score."""
    try:
        customer = CustomerRepository.get_by_id(db, customer_id)
        if not customer:
            return {"error": "Customer not found"}
        
        loans = LoanRepository.list_by_customer(db, customer_id)
        payments = PaymentRepository.list_by_customer(db, customer_id)
        
        # Calculate active credit score
        active_score = 700.0
        if loans:
            active_score = calculate_credit_score(loans[0], payments, date.today() if hasattr(date, 'today') else None)

        return {
            "customer": {
                "id": customer.id,
                "name": customer.name,
                "phone_number": customer.phone_number,
                "address": customer.address,
                "aadhar_masked": getattr(customer, "aadhar_masked", "XXXX-XXXX-XXXX"),
                "promissory_note": customer.promissory_note,
            },
            "loans": [
                {
                    "id": l.id,
                    "principal_amount": float(l.principal_amount),
                    "interest_rate": float(l.interest_rate),
                    "interest_formula": l.interest_formula,
                    "status": l.status,
                    "loan_start_date": str(l.loan_start_date),
                    "loan_end_date": str(l.loan_end_date),
                }
                for l in loans
            ],
            "credit_score": active_score,
            "payments_count": len(payments),
        }
    except Exception as e:
        logger.error("AI tool failed to fetch customer profile: %s", str(e))
        return {"error": str(e)}

def get_dashboard_analytics(db: Session) -> Dict[str, Any]:
    """Retrieve aggregate collections and outstanding metrics."""
    try:
        # Import inside tool to avoid circular dependencies
        from app.models.customer import Customer
        from app.models.loan import Loan
        from app.models.payment import Payment
        from decimal import Decimal
        from app.services.interest import calculate_interest

        total_customers = db.query(Customer).filter(Customer.is_deleted == False).count()
        loans = db.query(Loan).filter(Loan.is_deleted == False).all()
        payments = db.query(Payment).all()

        total_disbursed = sum((l.principal_amount for l in loans), Decimal("0"))
        total_collected = sum((p.amount_paid for p in payments), Decimal("0"))
        
        # Calculate total due (repayable) across all loans
        total_due = Decimal("0")
        for l in loans:
            if l.total_repayable_amount is not None:
                total_due += l.total_repayable_amount
            else:
                interest = calculate_interest(l.principal_amount, l.interest_rate, l.interest_formula, l.duration_days)
                total_due += l.principal_amount + interest

        outstanding = max(Decimal("0"), total_due - total_collected)
        overdue_count = sum((1 for l in loans if l.status == "OVERDUE"), 0)

        return {
            "total_customers": total_customers,
            "total_loans": len(loans),
            "disbursed_principal": float(total_disbursed),
            "total_collected": float(total_collected),
            "outstanding_balance": float(outstanding),
            "overdue_count": overdue_count,
        }
    except Exception as e:
        logger.error("AI tool failed to compile dashboard analytics: %s", str(e))
        return {"error": str(e)}

# Define tools metadata schema for LLM function calling
AI_TOOLS_METADATA = [
    {
        "type": "function",
        "function": {
            "name": "get_customers_list",
            "description": "Fetch list of customers with search parameters like name or phone.",
            "parameters": {
                "type": "object",
                "properties": {
                    "search": {"type": "string", "description": "Search term matching name or phone."}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_customer_profile",
            "description": "Get complete customer financial profile, credit score and loans history by customer ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "integer", "description": "Unique numeric customer ID."}
                },
                "required": ["customer_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_dashboard_analytics",
            "description": "Get high-level dashboard aggregate collections, total disbursed, collected, outstanding amounts and default counts."
        }
    }
]
