import json
import logging
import time
from datetime import datetime, date
from decimal import Decimal
from typing import Any, Dict, List, Optional
from sqlalchemy import or_, func, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.utils.timezone import today_ist, now_ist

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
        """Classify user intent and extract search entities using Groq reasoning, supporting multilingual inputs."""
        classification_prompt = f"""
        Analyze the following query from a banking portal admin. The query can be in English, Telugu, or mixed Telugu-English (Romanized Telugu, e.g., 'entha kattali', 'balance entha', 'details ivvu', or Telugu script: 'ఎవరు డబ్బు కట్టారు', 'ఎవరి EMI మిస్ అయింది'):
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
        - CREATE_PAYMENT_REQUEST (adding/recording new daily payments, e.g., 'record payment of 500 for customer 2')
        - UNKNOWN (general conversation)

        Extract entities if present (do not guess, output null if not specified):
        - customer_name (e.g. Likith Naidu, Priya, or Telugu equivalent name strings)
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
        db: AsyncSession,
    ) -> str:
        """Central execution pipeline for SAKRA AI COPILOT."""
        start_time = time.time()
        
        # 1. Input Security Scan
        if not verify_query_safety(query):
            return "❌ SECURITY WARNING: The query contains expressions flagged as potentially unsafe by the database protection shield."

        # Find current user ID for auditing
        stmt = select(User).filter(User.role == user_role, User.is_deleted == False)
        res = await db.execute(stmt)
        user = res.scalars().first()
        user_id = user.id if user else 1

        # Check transaction confirmation
        clean_query = query.lower().strip()
        if clean_query in ["confirm", "yes", "confirm payment"] and session_id in self.pending_transactions:
            if user_role not in ["SUPER_ADMIN", "ADMIN", "ASSISTANT_ADMIN", "DATA_ENTRY", "COLLECTION_OFFICER", "FINANCE_MANAGER"]:
                return f"❌ ACCESS DENIED: Role '{user_role}' is unauthorized to record transactions."
            
            tx = self.pending_transactions.pop(session_id)
            try:
                # Find customer
                stmt_cust = select(Customer).filter(Customer.name.ilike(f"%{tx['customer_name']}%"), Customer.is_deleted == False)
                res_cust = await db.execute(stmt_cust)
                customer = res_cust.scalars().first()
                if not customer:
                    return f"Could not complete transaction. Customer '{tx['customer_name']}' not found."
                
                # Find active loan
                stmt_loans = select(Loan).filter(Loan.customer_id == customer.id, Loan.is_deleted == False)
                res_loans = await db.execute(stmt_loans)
                loans = res_loans.scalars().all()
                active_loan = next((l for l in loans if l.status in ["ACTIVE", "OVERDUE"]), None)
                if not active_loan:
                    return f"No active loan found for customer '{customer.name}'."

                # Create Payment
                payment_date = tx.get("date") or today_ist().isoformat()
                payment = await PaymentRepository.create(
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
                await db.commit()
                
                response_text = f"✅ **Transaction Completed:** Recorded payment of **₹{tx['amount']:,}** for **{customer.name}** on **{payment_date}**."
                await self._log_ai_interaction(db, user_id, session_id, query, "CREATE_PAYMENT_REQUEST", "PaymentRepository.create", response_text, start_time)
                return response_text
            except Exception as err:
                logger.error("Failed to commit AI payment: %s", str(err))
                await db.rollback()
                return f"❌ Transaction failed: {str(err)}"

        # 2. Intent Classification & Entity Extraction
        intent_info = await self._understand_intent(query)
        intent = intent_info.get("intent", "UNKNOWN")
        entities = intent_info.get("entities", {})
        
        logger.info("Classified Intent: %s | Entities: %s", intent, entities)

        # Stage payment request
        if intent == "CREATE_PAYMENT_REQUEST" and entities.get("customer_name") and entities.get("amount"):
            if user_role not in ["SUPER_ADMIN", "ADMIN", "ASSISTANT_ADMIN", "DATA_ENTRY", "COLLECTION_OFFICER", "FINANCE_MANAGER"]:
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
        target_search_val = None

        try:
            # Check DB Connection
            await db.execute(select(func.now()))
        except Exception:
            return "Unable to retrieve customer information because the database connection is unavailable. Do NOT fabricate answers."

        # Search Customer by Aadhaar
        if entities.get("aadhaar"):
            target_search_val = entities["aadhaar"]
            searched_entities.append(f"Aadhaar Hash/Number: {entities['aadhaar']}")
            hashed = hash_aadhaar(entities["aadhaar"])
            stmt_cust = select(Customer).options(selectinload(Customer.documents)).filter(Customer.aadhar_hash == hashed, Customer.is_deleted == False)
            res_cust = await db.execute(stmt_cust)
            customer = res_cust.scalars().first()
            if customer:
                context_data += await self._build_customer_context(db, customer, user_role)
                database_hit = True

        # Search Customer by ID
        elif entities.get("customer_id"):
            target_search_val = str(entities["customer_id"])
            searched_entities.append(f"Customer ID: {entities['customer_id']}")
            stmt_cust = select(Customer).options(selectinload(Customer.documents)).filter(Customer.id == entities["customer_id"], Customer.is_deleted == False)
            res_cust = await db.execute(stmt_cust)
            customer = res_cust.scalars().first()
            if customer:
                context_data += await self._build_customer_context(db, customer, user_role)
                database_hit = True

        # Search Customer by Phone
        elif entities.get("phone_number"):
            target_search_val = entities["phone_number"]
            searched_entities.append(f"Phone: {entities['phone_number']}")
            stmt_cust = select(Customer).options(selectinload(Customer.documents)).filter(Customer.phone_number.ilike(f"%{entities['phone_number']}%"), Customer.is_deleted == False)
            res_cust = await db.execute(stmt_cust)
            customer = res_cust.scalars().first()
            if customer:
                context_data += await self._build_customer_context(db, customer, user_role)
                database_hit = True

        # Search Customer by Name
        elif entities.get("customer_name"):
            target_search_val = entities["customer_name"]
            searched_entities.append(f"Customer Name: {entities['customer_name']}")
            cleaned_name = entities["customer_name"].strip()
            stmt_custs = select(Customer).options(selectinload(Customer.documents)).filter(Customer.name.ilike(f"%{cleaned_name}%"), Customer.is_deleted == False)
            res_custs = await db.execute(stmt_custs)
            customers = res_custs.scalars().all()
            if customers:
                for customer in customers:
                    context_data += await self._build_customer_context(db, customer, user_role)
                database_hit = True

        # Search Customer by Address
        elif entities.get("address"):
            target_search_val = entities["address"]
            searched_entities.append(f"Address: {entities['address']}")
            stmt_custs = select(Customer).options(selectinload(Customer.documents)).filter(Customer.address.ilike(f"%{entities['address']}%"), Customer.is_deleted == False)
            res_custs = await db.execute(stmt_custs)
            customers = res_custs.scalars().all()
            if customers:
                for customer in customers:
                    context_data += await self._build_customer_context(db, customer, user_role)
                database_hit = True

        # Search by Loan ID
        elif entities.get("loan_id"):
            target_search_val = str(entities["loan_id"])
            searched_entities.append(f"Loan ID: {entities['loan_id']}")
            stmt_loan = select(Loan).filter(Loan.id == entities["loan_id"], Loan.is_deleted == False)
            res_loan = await db.execute(stmt_loan)
            loan = res_loan.scalars().first()
            if loan:
                stmt_cust = select(Customer).options(selectinload(Customer.documents)).filter(Customer.id == loan.customer_id, Customer.is_deleted == False)
                res_cust = await db.execute(stmt_cust)
                customer = res_cust.scalars().first()
                if customer:
                    context_data += await self._build_customer_context(db, customer, user_role)
                    database_hit = True

        # Search by Payment ID
        elif entities.get("payment_id"):
            target_search_val = str(entities["payment_id"])
            searched_entities.append(f"Payment ID: {entities['payment_id']}")
            stmt_pay = select(Payment).filter(Payment.id == entities["payment_id"])
            res_pay = await db.execute(stmt_pay)
            payment = res_pay.scalars().first()
            if payment:
                stmt_cust = select(Customer).options(selectinload(Customer.documents)).filter(Customer.id == payment.customer_id, Customer.is_deleted == False)
                res_cust = await db.execute(stmt_cust)
                customer = res_cust.scalars().first()
                if customer:
                    context_data += await self._build_customer_context(db, customer, user_role)
                    database_hit = True

        # General/Portfolio Dashboard intents
        if not database_hit:
            if intent in ["DASHBOARD_ANALYTICS", "TODAYS_COLLECTION", "OVERDUE_CUSTOMERS", "COMPLETED_LOANS", "RISK_ANALYSIS", "RECOVERY_SUGGESTIONS"]:
                context_data += await self._build_portfolio_context(db, intent, user_role)
                database_hit = True

        # If a search was performed but zero matches were found, return the requested specific format
        if len(searched_entities) > 0 and not database_hit:
            val = target_search_val or query
            return f"No customer matching \"{val}\" was found.\n\nSuggestions:\n• Customer ID\n• Phone Number\n• Full Name"

        # 4. Groq Reasoning Layer
        ist_now = now_ist()
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
        await self._log_ai_interaction(db, user_id, session_id, query, intent, "SQLAlchemy DB Search", final_content, start_time)
        
        return final_content

    async def _build_customer_context(self, db: AsyncSession, customer: Customer, role: str) -> str:
        """Fetch all customer details, calculate business metrics and format into context."""
        from app.models.customer_document import CustomerDocument
        from app.models.payment_adjustment import PaymentAdjustment
        from app.models.audit_log import AuditLog
        from app.models.notification import Notification

        # Fetch customer's loans
        stmt_loans = select(Loan).filter(Loan.customer_id == customer.id, Loan.is_deleted == False)
        res_loans = await db.execute(stmt_loans)
        loans = res_loans.scalars().all()

        today = today_ist()

        context = f"\n### Customer Profile: {customer.name} (ID: {customer.id})\n"
        context += f"- Phone Number: {customer.phone_number}\n"
        
        # Obey RBAC security masking
        if role in ["SUPER_ADMIN", "ADMIN"]:
            context += f"- Aadhaar Masked: {customer.aadhar_masked}\n"
            context += f"- Hashed Aadhaar: {customer.aadhar_hash}\n"
        else:
            context += f"- Aadhaar Masked: XXXX-XXXX-XXXX (REDACTED for {role})\n"

        context += f"- Address: {customer.address or '—'}\n"
        context += f"- Occupation: {customer.occupation or '—'}\n"
        context += f"- Created Date: {customer.created_at.strftime('%Y-%m-%d %I:%M %p IST') if customer.created_at else '—'}\n"
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
        context += f"- Remarks: {customer.remarks or '—'}\n"

        # Calculate collection intelligence delinquency metadata
        from app.services.loan_service import compute_pending_installments_metadata
        delinquency = compute_pending_installments_metadata(loans, today)
        context += f"- Pending Installments Count: {delinquency['pending_installments_count']}\n"
        context += f"- Oldest Pending Date: {delinquency['oldest_pending_date'] or '—'}\n"
        context += f"- Latest Pending Date: {delinquency['latest_pending_date'] or '—'}\n"
        context += f"- Total Overdue Pending Amount: ₹{delinquency['pending_amount']:,}\n"
        if delinquency["pending_dates"]:
            context += f"- Detailed Missed Installments:\n"
            for d in delinquency["pending_dates"]:
                context += f"  * {d['date']}: Expected ₹{d['expected_amount']:,} - Status: {d['status']}\n"

        # Fetch notifications for this customer
        stmt_notif = select(Notification).filter(Notification.customer_id == customer.id).order_by(Notification.sent_at.desc()).limit(5)
        res_notif = await db.execute(stmt_notif)
        notifications = res_notif.scalars().all()

        # Fetch audit logs related to this customer
        stmt_audit = select(AuditLog).filter(AuditLog.record_id == customer.id, AuditLog.table_name == "customers").order_by(AuditLog.created_at.desc()).limit(5)
        res_audit = await db.execute(stmt_audit)
        audits = res_audit.scalars().all()

        for idx, loan in enumerate(loans, 1):
            stmt_pay = select(Payment).filter(Payment.loan_id == loan.id)
            res_pay = await db.execute(stmt_pay)
            payments = res_pay.scalars().all()
            total_paid = sum((p.amount_paid for p in payments), Decimal("0"))
            
            # Dynamic calculations
            interest = loan.interest_amount if loan.interest_amount is not None else calculate_interest(loan.principal_amount, loan.interest_rate, loan.interest_formula, loan.duration_days)
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
            
            # Fetch schedules to count paid, pending, missed installments
            stmt_sched = select(LoanSchedule).filter(LoanSchedule.loan_id == loan.id).order_by(LoanSchedule.installment_number.asc())
            res_sched = await db.execute(stmt_sched)
            schedules = res_sched.scalars().all()

            paid_scheds = sum(1 for s in schedules if s.remaining_amount == 0)
            pending_scheds = sum(1 for s in schedules if s.remaining_amount > 0 and s.due_date >= today)
            missed_scheds = sum(1 for s in schedules if s.remaining_amount > 0 and s.due_date < today)
            next_due_sched = next((s for s in schedules if s.remaining_amount > 0 and s.due_date >= today), None)

            context += f"\n  * Loan #{idx} (Loan ID: {loan.id})\n"
            context += f"    - Principal Amount: ₹{loan.principal_amount:,}\n"
            context += f"    - Interest rate: {loan.interest_rate}% ({loan.interest_formula})\n"
            context += f"    - Total Interest: ₹{interest:,}\n"
            context += f"    - Total Due (Repayable): ₹{total_due:,}\n"
            context += f"    - Collected / Paid: ₹{total_paid:,}\n"
            context += f"    - Outstanding Balance: ₹{remaining_balance:,}\n"
            context += f"    - Completion Percentage: {completion_percent:.2f}%\n"
            context += f"    - Credit Score: {credit_score}\n"
            context += f"    - Risk Level / Category: {risk_level}\n"
            context += f"    - Daily Installment: ₹{daily_due:.2f}\n"
            context += f"    - Loan Status: {loan.status}\n"
            context += f"    - Remaining Days: {remaining_days}\n"
            context += f"    - Overdue Days: {overdue_days}\n"
            context += f"    - Next Due Date: {next_due_sched.due_date if next_due_sched else 'Fully Paid'}\n"
            context += f"    - Schedule Summary: {paid_scheds} Paid, {pending_scheds} Pending, {missed_scheds} Missed\n"
            
            # Check for adjustments on these payments
            pay_ids = [p.id for p in payments]
            adjustments = []
            if pay_ids:
                stmt_adj = select(PaymentAdjustment).filter(PaymentAdjustment.payment_id.in_(pay_ids))
                res_adj = await db.execute(stmt_adj)
                adjustments = res_adj.scalars().all()

            context += "    - Recent Payments:\n"
            for p in payments[-5:]:
                context += f"      * {p.payment_date}: ₹{p.amount_paid:,} ({p.payment_mode}) - Status: PAID\n"

            if adjustments:
                context += "    - Payment Adjustments:\n"
                for adj in adjustments:
                    context += f"      * Payment ID {adj.payment_id}: shifted from ₹{adj.old_amount:,} to ₹{adj.new_amount:,} due to: {adj.reason} (Approved on: {adj.created_at.strftime('%Y-%m-%d') if adj.created_at else '—'})\n"

        if notifications:
            context += "  - Recent Notifications:\n"
            for n in notifications:
                context += f"    * [{n.sent_at.strftime('%Y-%m-%d %I:%M %p') if n.sent_at else '—'}] Type: {n.notification_type} - {n.message} (Read: {n.is_read})\n"

        if audits:
            context += "  - Audit Log Activity:\n"
            for a in audits:
                context += f"    * [{a.created_at.strftime('%Y-%m-%d %I:%M %p') if a.created_at else '—'}] Action: {a.action} - Details: {a.new_values}\n"

        return context

    async def _build_portfolio_context(self, db: AsyncSession, intent: str, role: str) -> str:
        """Fetch general dashboard, collections, and overdue list context from DB."""
        from app.services.loan_service import get_dashboard_metrics_details
        today = today_ist()
        
        metrics = await get_dashboard_metrics_details(db)
        
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

        # Fetch payments recorded today
        stmt_today_pay = select(Payment).filter(Payment.payment_date == today)
        res_today_pay = await db.execute(stmt_today_pay)
        today_payments = res_today_pay.scalars().all()
        
        context += "\n#### Payments Recorded Today:\n"
        if today_payments:
            for idx, p in enumerate(today_payments, 1):
                # get customer name
                stmt_c = select(Customer).filter(Customer.id == p.customer_id)
                res_c = await db.execute(stmt_c)
                c = res_c.scalars().first()
                c_name = c.name if c else f"Customer #{p.customer_id}"
                context += f"{idx}. **{c_name}** (ID: {p.customer_id}) - Paid: ₹{p.amount_paid:,} ({p.payment_mode})\n"
        else:
            context += "No payments recorded yet today.\n"

        # Overdue customers list details
        if intent in ["OVERDUE_CUSTOMERS", "RECOVERY_SUGGESTIONS", "RISK_ANALYSIS"]:
            context += "\n#### Overdue Customer Dockets:\n"
            stmt_overdue = select(Loan).filter(Loan.loan_end_date < today, Loan.is_deleted == False)
            res_overdue = await db.execute(stmt_overdue)
            overdue_loans = res_overdue.scalars().all()
            
            count = 0
            for o_loan in overdue_loans:
                stmt_pay = select(Payment).filter(Payment.loan_id == o_loan.id)
                res_pay = await db.execute(stmt_pay)
                payments = res_pay.scalars().all()
                total_paid = sum((p.amount_paid for p in payments), Decimal("0"))
                interest = calculate_interest(o_loan.principal_amount, o_loan.interest_rate, o_loan.interest_formula, o_loan.duration_days)
                total_due = o_loan.principal_amount + interest
                remaining = max(total_due - total_paid, Decimal("0"))

                if remaining > 0:
                    stmt_cust = select(Customer).filter(Customer.id == o_loan.customer_id)
                    res_cust = await db.execute(stmt_cust)
                    cust = res_cust.scalars().first()
                    if cust:
                        count += 1
                        overdue_days = (today - o_loan.loan_end_date).days
                        context += f"{count}. **{cust.name}** (ID: {cust.id}, Phone: {cust.phone_number}) " \
                                   f"- Outstanding: ₹{remaining:,}, Overdue Days: {overdue_days} days (Loan closed: {o_loan.loan_end_date})\n"
            if count == 0:
                context += "No customer accounts are currently overdue.\n"

        # Top outstanding borrowers
        stmt_all_loans = select(Loan).filter(Loan.is_deleted == False)
        res_all_loans = await db.execute(stmt_all_loans)
        all_loans = res_all_loans.scalars().all()
        
        borrower_outstanding = {}
        for l in all_loans:
            stmt_pay = select(Payment).filter(Payment.loan_id == l.id)
            res_pay = await db.execute(stmt_pay)
            payments = res_pay.scalars().all()
            total_paid = sum((p.amount_paid for p in payments), Decimal("0"))
            interest = calculate_interest(l.principal_amount, l.interest_rate, l.interest_formula, l.duration_days)
            total_due = l.principal_amount + interest
            remaining = max(total_due - total_paid, Decimal("0"))
            
            if remaining > 0:
                borrower_outstanding[l.customer_id] = borrower_outstanding.get(l.customer_id, Decimal("0")) + remaining
        
        sorted_borrowers = sorted(borrower_outstanding.items(), key=lambda x: x[1], reverse=True)[:5]
        context += "\n#### Top Outstanding Balances:\n"
        if sorted_borrowers:
            for rank, (cust_id, outstanding) in enumerate(sorted_borrowers, 1):
                stmt_c = select(Customer).filter(Customer.id == cust_id)
                res_c = await db.execute(stmt_c)
                c = res_c.scalars().first()
                c_name = c.name if c else f"Customer #{cust_id}"
                context += f"{rank}. **{c_name}** (ID: {cust_id}) - Total Outstanding: ₹{outstanding:,}\n"
        else:
            context += "No outstanding balances.\n"

        # Completed loans list
        if intent == "COMPLETED_LOANS":
            context += "\n#### Completed Loan Accounts:\n"
            count = 0
            for c_loan in all_loans:
                stmt_pay = select(Payment).filter(Payment.loan_id == c_loan.id)
                res_pay = await db.execute(stmt_pay)
                payments = res_pay.scalars().all()
                total_paid = sum((p.amount_paid for p in payments), Decimal("0"))
                interest = calculate_interest(c_loan.principal_amount, c_loan.interest_rate, c_loan.interest_formula, c_loan.duration_days)
                total_due = c_loan.principal_amount + interest
                remaining = max(total_due - total_paid, Decimal("0"))

                if remaining == 0:
                    stmt_cust = select(Customer).filter(Customer.id == c_loan.customer_id)
                    res_cust = await db.execute(stmt_cust)
                    cust = res_cust.scalars().first()
                    if cust:
                        count += 1
                        context += f"{count}. **{cust.name}** (ID: {cust.id}) - Loan ID: {c_loan.id}, Disbursed: ₹{c_loan.principal_amount:,}, Fully Settled.\n"
            if count == 0:
                context += "No completed loans found in record.\n"

        # Pending Installment Analytics context for AI Copilot
        # Compile a list of all active customers and their pending installments
        from app.services.loan_service import compute_pending_installments_metadata
        
        stmt_active_custs = select(Customer).filter(Customer.is_deleted == False).options(
            selectinload(Customer.loans).selectinload(Loan.payments),
            selectinload(Customer.loans).selectinload(Loan.schedules)
        )
        res_active_custs = await db.execute(stmt_active_custs)
        active_custs = res_active_custs.scalars().all()
        
        context += "\n#### SAKRA CUSTOMERS COLLECTION INTELLIGENCE (PENDING INSTALLMENTS):\n"
        context += "| Rank | Customer Name | ID | Pending Installments | Oldest Missed Date | Latest Missed Date | Total Overdue Amount | Missed Installments Dates |\n"
        context += "|---|---|---|---|---|---|---|---|\n"
        
        cust_delinquencies = []
        for cust in active_custs:
            meta = compute_pending_installments_metadata(cust.loans, today)
            if meta["pending_installments_count"] > 0:
                cust_delinquencies.append((cust, meta))
        
        # Sort by pending_installments_count descending
        cust_delinquencies.sort(key=lambda x: x[1]["pending_installments_count"], reverse=True)
        
        if cust_delinquencies:
            for rank, (cust, meta) in enumerate(cust_delinquencies, 1):
                missed_dates_str = ", ".join(d["date"] for d in meta["pending_dates"])
                context += f"| {rank} | {cust.name} | {cust.id} | {meta['pending_installments_count']} | {meta['oldest_pending_date'] or '—'} | {meta['latest_pending_date'] or '—'} | ₹{meta['pending_amount']:,} | {missed_dates_str} |\n"
        else:
            context += "No customers have any pending or missed installments.\n"

        return context

    async def _log_ai_interaction(
        self,
        db: AsyncSession,
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
            await db.commit()
        except Exception as e:
            logger.error("Failed to commit AI interaction log: %s", str(e))
            await db.rollback()
