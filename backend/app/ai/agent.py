import json
import logging
import time
from datetime import datetime, date
from decimal import Decimal
from typing import Any, Dict, List, Optional
from sqlalchemy import or_, func
from sqlalchemy.orm import Session

from app.ai.groq_client import GroqClient
from app.ai.prompts import SYSTEM_PROMPT
from app.ai.security import verify_query_safety
from app.models.ai_log import AIAuditLog
from app.models.user import User
from app.models.customer import Customer
from app.models.loan import Loan
from app.models.payment import Payment
from app.models.loan_schedule import LoanSchedule
from app.models.notification import Notification
from app.repositories.payment_repo import PaymentRepository
from app.schemas.payment import PaymentCreate
from app.services.interest import calculate_interest, get_loan_balance_summary
from app.services.credit_score import calculate_credit_score
from app.utils.crypto import hash_aadhaar

logger = logging.getLogger("sakra.ai.agent")

class SakraCopilotAgent:
    """
    Enterprise-grade SAKRA AI COPILOT Agent.
    Implements dynamic MySQL query generation via SQLAlchemy, calculates metrics
    using backend rules, enforces security RBAC roles, and uses Groq solely
    to explain live database records.
    """
    
    def __init__(self):
        self.client = GroqClient()
        # In-memory transaction staging to support confirmation workflow
        self.pending_transactions: Dict[str, Dict[str, Any]] = {}

    async def _understand_intent(self, query: str) -> Dict[str, Any]:
        """Classify user intent and extract search entities using Groq reasoning."""
        classification_prompt = f"""
        Analyze the following query from a banking portal admin:
        Query: "{query}"

        Classify the intent into one of these:
        - CUSTOMER_STATUS (questions about customer status, details, profile, search by name/phone/aadhaar/ID/address)
        - DASHBOARD_ANALYTICS (high level overview, collection metrics, realization, portfolios summary)
        - OVERDUE_CUSTOMERS (repayment period crossed / overdue customers search)
        - COMPLETED_LOANS (loans completed/fully paid)
        - TODAYS_COLLECTION (today's, yesterday's, or monthly collection amounts)
        - PAYMENT_HISTORY (payment history / transaction ledger for customer or loan)
        - RISK_ANALYSIS (highest risk, lowest credit score)
        - RECOVERY_SUGGESTIONS (recovery suggestions, portfolio summary report)
        - CREATE_PAYMENT_REQUEST (adding/recording new daily payments)
        - UNKNOWN (general conversation)

        Extract entities if present (do not guess, output null if not specified):
        - customer_name (e.g. Likith Naidu, Priya)
        - customer_id (integer ID)
        - phone_number (phone number digit string)
        - aadhaar (12-digit Aadhaar number string)
        - loan_id (integer loan ID)
        - payment_id (integer payment ID)
        - address (address matching search string)
        - amount (numeric payment amount if recording)
        - date (date if recording, format YYYY-MM-DD or relative terms)

        Return ONLY a raw JSON block in this format:
        {{
            "intent": "INTENT_TYPE",
            "entities": {{
                "customer_name": "extracted_name" or null,
                "customer_id": customer_id_int or null,
                "phone_number": "extracted_phone" or null,
                "aadhaar": "extracted_aadhaar" or null,
                "loan_id": loan_id_int or null,
                "payment_id": payment_id_int or null,
                "address": "extracted_address" or null,
                "amount": numeric_amount or null,
                "date": "extracted_date" or null
            }}
        }}
        """
        try:
            res = await self.client.get_response(
                messages=[{"role": "user", "content": classification_prompt}],
                temperature=0.0,
                max_tokens=250
            )
            raw_text = res.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:-3].strip()
            elif raw_text.startswith("```"):
                raw_text = raw_text[3:-3].strip()
            return json.loads(raw_text)
        except Exception as e:
            logger.error("Intent extraction failed: %s", str(e))
            return {"intent": "UNKNOWN", "entities": {}}

    async def execute(
        self,
        query: str,
        user_role: str,
        session_id: str,
        db: Session,
    ) -> str:
        """Central execution pipeline for SAKRA AI COPILOT."""
        start_time = time.time()
        
        # 1. Input Security Scan
        if not verify_query_safety(query):
            return "❌ SECURITY WARNING: The query contains expressions flagged as potentially unsafe by the database protection shield."

        # Find current user ID for auditing
        user = db.query(User).filter(User.role == user_role, User.is_deleted == False).first()
        user_id = user.id if user else 1

        # Check transaction confirmation
        clean_query = query.lower().strip()
        if clean_query in ["confirm", "yes", "confirm payment"] and session_id in self.pending_transactions:
            if user_role not in ["SUPER_ADMIN", "ADMIN", "ASSISTANT_ADMIN"]:
                return f"❌ ACCESS DENIED: Role '{user_role}' is unauthorized to record transactions."
            
            tx = self.pending_transactions.pop(session_id)
            try:
                # Find customer
                customer = db.query(Customer).filter(Customer.name.ilike(f"%{tx['customer_name']}%"), Customer.is_deleted == False).first()
                if not customer:
                    return f"Could not complete transaction. Customer '{tx['customer_name']}' not found."
                
                # Find active loan
                loans = db.query(Loan).filter(Loan.customer_id == customer.id, Loan.is_deleted == False).all()
                active_loan = next((l for l in loans if l.status in ["ACTIVE", "OVERDUE"]), None)
                if not active_loan:
                    return f"No active loan found for customer '{customer.name}'."

                # Create Payment
                payment_date = tx.get("date") or date.today().isoformat()
                payment = PaymentRepository.create(
                    db=db,
                    schema=PaymentCreate(
                        loan_id=active_loan.id,
                        payment_date=payment_date,
                        amount_paid=tx["amount"],
                        payment_mode="CASH"
                    ),
                    customer_id=customer.id,
                    recorder_id=user_id
                )
                db.commit()
                
                response_text = f"✅ **Transaction Completed:** Recorded payment of **₹{tx['amount']:,}** for **{customer.name}** on **{payment_date}**."
                self._log_ai_interaction(db, user_id, session_id, query, "CREATE_PAYMENT_REQUEST", "PaymentRepository.create", response_text, start_time)
                return response_text
            except Exception as err:
                logger.error("Failed to commit AI payment: %s", str(err))
                db.rollback()
                return f"❌ Transaction failed: {str(err)}"

        # 2. Intent Classification & Entity Extraction
        intent_info = await self._understand_intent(query)
        intent = intent_info.get("intent", "UNKNOWN")
        entities = intent_info.get("entities", {})
        
        logger.info("Classified Intent: %s | Entities: %s", intent, entities)

        # Stage payment request
        if intent == "CREATE_PAYMENT_REQUEST" and entities.get("customer_name") and entities.get("amount"):
            if user_role not in ["SUPER_ADMIN", "ADMIN", "ASSISTANT_ADMIN"]:
                return f"❌ ACCESS DENIED: Role '{user_role}' is unauthorized to record transactions."
            
            self.pending_transactions[session_id] = {
                "customer_name": entities["customer_name"],
                "amount": entities["amount"],
                "date": entities.get("date")
            }
            return f"🤖 **I have prepared the following payment entry:**\n" \
                   f"- **Customer**: {entities['customer_name']}\n" \
                   f"- **Amount**: ₹{entities['amount']:,}\n" \
                   f"- **Date**: {entities.get('date') or 'Today'}\n\n" \
                   f"Please type **'confirm'** to execute this transaction."

        # 3. Database Search Layer (MySQL via SQLAlchemy)
        context_data = ""
        database_hit = False
        searched_entities = []

        try:
            # Check DB Connection
            db.execute(func.now())
        except Exception:
            return "Unable to retrieve customer information because the database connection is unavailable. Do NOT fabricate answers."

        # Search Customer by Aadhaar
        if entities.get("aadhaar"):
            searched_entities.append(f"Aadhaar Hash: {entities['aadhaar']}")
            hashed = hash_aadhaar(entities["aadhaar"])
            customer = db.query(Customer).filter(Customer.aadhar_hash == hashed, Customer.is_deleted == False).first()
            if customer:
                context_data += self._build_customer_context(db, customer, user_role)
                database_hit = True

        # Search Customer by ID
        elif entities.get("customer_id"):
            searched_entities.append(f"Customer ID: {entities['customer_id']}")
            customer = db.query(Customer).filter(Customer.id == entities["customer_id"], Customer.is_deleted == False).first()
            if customer:
                context_data += self._build_customer_context(db, customer, user_role)
                database_hit = True

        # Search Customer by Phone
        elif entities.get("phone_number"):
            searched_entities.append(f"Phone: {entities['phone_number']}")
            customer = db.query(Customer).filter(Customer.phone_number.ilike(f"%{entities['phone_number']}%"), Customer.is_deleted == False).first()
            if customer:
                context_data += self._build_customer_context(db, customer, user_role)
                database_hit = True

        # Search Customer by Name
        elif entities.get("customer_name"):
            searched_entities.append(f"Customer Name: {entities['customer_name']}")
            # Support fuzzy/typo search and spaces
            cleaned_name = entities["customer_name"].strip()
            customers = db.query(Customer).filter(Customer.name.ilike(f"%{cleaned_name}%"), Customer.is_deleted == False).all()
            if customers:
                for customer in customers:
                    context_data += self._build_customer_context(db, customer, user_role)
                database_hit = True

        # Search Customer by Address
        elif entities.get("address"):
            searched_entities.append(f"Address: {entities['address']}")
            customers = db.query(Customer).filter(Customer.address.ilike(f"%{entities['address']}%"), Customer.is_deleted == False).all()
            if customers:
                for customer in customers:
                    context_data += self._build_customer_context(db, customer, user_role)
                database_hit = True

        # Search by Loan ID
        elif entities.get("loan_id"):
            searched_entities.append(f"Loan ID: {entities['loan_id']}")
            loan = db.query(Loan).filter(Loan.id == entities["loan_id"], Loan.is_deleted == False).first()
            if loan:
                customer = db.query(Customer).filter(Customer.id == loan.customer_id, Customer.is_deleted == False).first()
                if customer:
                    context_data += self._build_customer_context(db, customer, user_role)
                    database_hit = True

        # Search by Payment ID
        elif entities.get("payment_id"):
            searched_entities.append(f"Payment ID: {entities['payment_id']}")
            payment = db.query(Payment).filter(Payment.id == entities["payment_id"]).first()
            if payment:
                customer = db.query(Customer).filter(Customer.id == payment.customer_id, Customer.is_deleted == False).first()
                if customer:
                    context_data += self._build_customer_context(db, customer, user_role)
                    database_hit = True

        # General/Portfolio Dashboard intents
        if not database_hit:
            # Check if this is a general dashboard or metrics search query
            if intent in ["DASHBOARD_ANALYTICS", "TODAYS_COLLECTION", "OVERDUE_CUSTOMERS", "COMPLETED_LOANS", "RISK_ANALYSIS", "RECOVERY_SUGGESTIONS"]:
                context_data += self._build_portfolio_context(db, intent, user_role)
                database_hit = True

        # If a search was performed but zero matches were found, NEVER hallucinate
        if len(searched_entities) > 0 and not database_hit:
            search_str = ", ".join(searched_entities)
            return f"Customer not found. Search performed using: {search_str}. No matching records were found."

        # 4. Groq Reasoning Layer
        from zoneinfo import ZoneInfo
        ist_now = datetime.now(ZoneInfo("Asia/Kolkata"))
        today_str = ist_now.date().isoformat()
        current_time = ist_now.strftime("%A, %d %B %Y %I:%M %p IST")
        
        system_prompt = SYSTEM_PROMPT.format(user_role=user_role, current_time=current_time)
        
        messages = [
            {"role": "system", "content": f"{system_prompt}\n\nDATABASE CONTEXT:\n{context_data}\nToday's Date: {today_str}"},
            {"role": "user", "content": query}
        ]

        try:
            res = await self.client.get_response(
                messages=messages,
                temperature=0.2
            )
            final_content = res.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        except Exception as groq_err:
            logger.error("Groq call failed: %s", str(groq_err))
            final_content = "Failed to compile AI response. Live database data is secured but Groq service is temporarily unreachable."

        # 5. Save interaction audit trail
        self._log_ai_interaction(db, user_id, session_id, query, intent, "SQLAlchemy DB Search", final_content, start_time)
        
        return final_content

    def _build_customer_context(self, db: Session, customer: Customer, role: str) -> str:
        """Fetch all customer details, calculate business metrics and format into context."""
        from app.services.interest import calculate_interest
        
        loans = db.query(Loan).filter(Loan.customer_id == customer.id, Loan.is_deleted == False).all()
        today = date.today()

        context = f"\n### Customer Profile: {customer.name} (ID: {customer.id})\n"
        context += f"- Phone Number: {customer.phone_number}\n"
        
        # Obey RBAC security masking
        if role in ["SUPER_ADMIN", "ADMIN"]:
            context += f"- Aadhaar Masked: {customer.aadhar_masked}\n"
            context += f"- Hashed Aadhaar: {customer.aadhar_hash}\n"
        else:
            context += f"- Aadhaar Masked: XXXX-XXXX-XXXX (REDACTED for {role})\n"

        context += f"- Address: {customer.address or '—'}\n"
        context += f"- Promissory Note Remarks: {customer.promissory_note or '—'}\n"
        
        # Document uploads presence indicators
        has_photo = any(d.document_type == "PROFILE_PHOTO" for d in customer.documents)
        has_aadhaar = any(d.document_type == "AADHAAR" for d in customer.documents)
        has_promissory = any(d.document_type == "PROMISSORY_NOTE" for d in customer.documents)

        context += f"- Profile Photo Uploaded: {'Yes' if has_photo else 'No'}\n"
        context += f"- Aadhaar Document Uploaded: {'Yes' if has_aadhaar else 'No'}\n"
        context += f"- Promissory Note Document Uploaded: {'Yes' if has_promissory else 'No'}\n"

        context += f"- Date of Birth: {customer.date_of_birth or '—'}\n"
        context += f"- Gender: {customer.gender or '—'}\n"
        context += f"- Occupation: {customer.occupation or '—'}\n"
        context += f"- Remarks: {customer.remarks or '—'}\n"


        for idx, loan in enumerate(loans, 1):
            payments = db.query(Payment).filter(Payment.loan_id == loan.id).all()
            total_paid = sum((p.amount_paid for p in payments), Decimal("0"))
            
            # Dynamic calculations
            interest = calculate_interest(loan.principal_amount, loan.interest_rate, loan.interest_formula)
            total_due = loan.principal_amount + interest
            remaining_balance = max(total_due - total_paid, Decimal("0"))
            
            days_elapsed = max((today - loan.loan_start_date).days, 0)
            remaining_days = max((loan.loan_end_date - today).days, 0) if loan.loan_end_date else 0
            
            overdue_days = 0
            if loan.loan_end_date and today > loan.loan_end_date and remaining_balance > 0:
                overdue_days = (today - loan.loan_end_date).days

            credit_score = calculate_credit_score(loan, payments, today)
            
            # Risk Level
            if credit_score >= 750:
                risk_level = "LOW"
            elif credit_score < 650:
                risk_level = "HIGH"
            else:
                risk_level = "MEDIUM"

            completion_percent = float((total_paid / total_due) * 100) if total_due > 0 else 100.0
            daily_due = total_due / Decimal(str(loan.duration_days))

            # Expected daily dues and last payment
            expected_days = min(days_elapsed, loan.duration_days)
            expected_paid = daily_due * Decimal(str(expected_days))
            today_due = daily_due

            last_payment_desc = "None"
            if payments:
                sorted_payments = sorted(payments, key=lambda x: x.payment_date, reverse=True)
                last_payment = sorted_payments[0]
                last_payment_desc = f"₹{last_payment.amount_paid:,} on {last_payment.payment_date} ({last_payment.payment_mode})"

            context += f"\n  * Loan #{idx} (Loan ID: {loan.id})\n"
            context += f"    - Principal Amount: ₹{loan.principal_amount:,}\n"
            context += f"    - Interest rate: {loan.interest_rate}% ({loan.interest_formula})\n"
            context += f"    - Total Interest: ₹{interest:,}\n"
            context += f"    - Total Due: ₹{total_due:,}\n"
            context += f"    - Collected / Paid: ₹{total_paid:,}\n"
            context += f"    - Outstanding Balance: ₹{remaining_balance:,}\n"
            context += f"    - Completion Percentage: {completion_percent:.2f}%\n"
            context += f"    - Credit Score: {credit_score}\n"
            context += f"    - Risk Level: {risk_level}\n"
            context += f"    - Expected Daily Installment: ₹{daily_due:.2f}\n"
            context += f"    - Today's Due Amount: ₹{today_due:.2f}\n"
            context += f"    - Expected Paid To Date: ₹{expected_paid:.2f}\n"
            context += f"    - Days Elapsed: {days_elapsed}\n"
            context += f"    - Remaining Days: {remaining_days}\n"
            context += f"    - Overdue Days: {overdue_days}\n"
            context += f"    - Loan Period: {loan.loan_start_date} to {loan.loan_end_date}\n"
            context += f"    - Status: {loan.status}\n"
            context += f"    - Last Payment: {last_payment_desc}\n"

            # Payment history limit to last 5
            context += "    - Recent Payments:\n"
            for p in payments[-5:]:
                context += f"      * {p.payment_date}: ₹{p.amount_paid:,} ({p.payment_mode}) - Status: PAID\n"

        return context

    def _build_portfolio_context(self, db: Session, intent: str, role: str) -> str:
        """Fetch general dashboard, collections, and overdue list context from DB."""
        from app.services.loan_service import get_dashboard_metrics_details
        today = date.today()
        
        metrics = get_dashboard_metrics_details(db)
        
        context = "### SAKRA FINANCE Portfolio Analytics Summary (Live MySQL Data)\n"
        context += f"- Total Registered Customers: {metrics['total_customers']}\n"
        context += f"- Total Active Loans: {metrics['total_loans']}\n"
        context += f"- Total Disbursed Principal: ₹{metrics['disbursed_principal']:,}\n"
        context += f"- Total Collected Dues: ₹{metrics['total_collected']:,}\n"
        context += f"- Total Outstanding Portfolio (with Interest): ₹{metrics['outstanding_balance']:,}\n"
        context += f"- Active Principal Outstanding: ₹{metrics['active_principal']:,}\n"
        context += f"- Realization / Collection Efficiency: {metrics['collection_efficiency']}%\n"
        context += f"- Today's Collections: ₹{metrics['today_collection']:,}\n"
        context += f"- Completed Loans Count: {metrics['completed_loans_count']}\n"
        context += f"- Today's Pending Payments Count: {metrics['pending_payments_count']}\n"
        context += f"- Overdue Customer Count: {metrics['overdue_customers_count']}\n"

        # Overdue customers list details
        if intent in ["OVERDUE_CUSTOMERS", "RECOVERY_SUGGESTIONS", "RISK_ANALYSIS"]:
            context += "\n#### Overdue Customer Dockets:\n"
            from app.models.loan import Loan
            overdue_loans = db.query(Loan).filter(Loan.loan_end_date < today, Loan.is_deleted == False).all()
            
            count = 0
            for idx, o_loan in enumerate(overdue_loans, 1):
                # Calculate remaining balance
                payments = db.query(Payment).filter(Payment.loan_id == o_loan.id).all()
                total_paid = sum((p.amount_paid for p in payments), Decimal("0"))
                interest = calculate_interest(o_loan.principal_amount, o_loan.interest_rate, o_loan.interest_formula)
                total_due = o_loan.principal_amount + interest
                remaining = max(total_due - total_paid, Decimal("0"))

                if remaining > 0:
                    cust = db.query(Customer).filter(Customer.id == o_loan.customer_id).first()
                    if cust:
                        count += 1
                        overdue_days = (today - o_loan.loan_end_date).days
                        context += f"{count}. **{cust.name}** (ID: {cust.id}, Phone: {cust.phone_number}) " \
                                   f"- Outstanding: ₹{remaining:,}, Overdue Days: {overdue_days} days (Loan closed: {o_loan.loan_end_date})\n"
            if count == 0:
                context += "No customer accounts are currently overdue.\n"

        # Completed loans list
        if intent == "COMPLETED_LOANS":
            context += "\n#### Completed Loan Accounts:\n"
            from app.models.loan import Loan
            completed_loans = db.query(Loan).filter(Loan.is_deleted == False).all()
            count = 0
            for idx, c_loan in enumerate(completed_loans, 1):
                payments = db.query(Payment).filter(Payment.loan_id == c_loan.id).all()
                total_paid = sum((p.amount_paid for p in payments), Decimal("0"))
                interest = calculate_interest(c_loan.principal_amount, c_loan.interest_rate, c_loan.interest_formula)
                total_due = c_loan.principal_amount + interest
                remaining = max(total_due - total_paid, Decimal("0"))

                if remaining == 0:
                    cust = db.query(Customer).filter(Customer.id == c_loan.customer_id).first()
                    if cust:
                        count += 1
                        context += f"{count}. **{cust.name}** (ID: {cust.id}) - Loan ID: {c_loan.id}, Disbursed: ₹{c_loan.principal_amount:,}, Fully Settled.\n"
            if count == 0:
                context += "No completed loans found in record.\n"

        return context

    def _log_ai_interaction(
        self,
        db: Session,
        user_id: int,
        session_id: str,
        query: str,
        intent: str,
        tools: str,
        response: str,
        start_time: float
    ):
        """Save AI interaction log data including execution times."""
        try:
            exec_time_ms = int((time.time() - start_time) * 1000)
            log_entry = AIAuditLog(
                user_id=user_id,
                conversation_id=session_id,
                question=query,
                intent=intent,
                tools_used=tools,
                response_summary=response[:500] + ("..." if len(response) > 500 else ""),
                tokens_used=len(query.split()) + len(response.split())  # rough word estimate fallback
            )
            db.add(log_entry)
            db.commit()
        except Exception as e:
            logger.error("Failed to commit AI interaction log: %s", str(e))
            db.rollback()
