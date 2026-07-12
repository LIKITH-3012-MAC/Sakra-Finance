import logging
import sys
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

# Setup system path to import app modules
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.utils.timezone import now_ist_naive
from app.database.session import SessionLocal
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


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sakra.seed")

def seed_database():
    db: Session = SessionLocal()
    try:
        logger.info("Starting database seeding...")
        
        # 1. Fetch or create super admin user
        admin = db.query(User).filter(User.role == "SUPER_ADMIN").first()
        if not admin:
            logger.error("No SUPER_ADMIN found. Run app.main to seed admin user first.")
            return

        # 2. Add Customers
        customer_data = [
            {"name": "Rajesh Kumar", "phone_number": "9876543210", "address": "12, MG Road, Bengaluru", "note": "Priority account with backing security."},
            {"name": "Priya Sharma", "phone_number": "9123456789", "address": "45, Jubilee Hills, Hyderabad", "note": "Aadhaar verified via portal verification."},
            {"name": "Likith Naidu", "phone_number": "9988776655", "address": "78, T-Nagar, Chennai", "note": "Enterprise-grade portfolio collateral."},
            {"name": "Amit Patel", "phone_number": "9445566778", "address": "101, Bandra West, Mumbai", "note": "Regular daily repayments scheduled."},
            {"name": "Sneha Reddy", "phone_number": "9665544332", "address": "202, Gachibowli, Hyderabad", "note": "Verification check cleared successfully."}
        ]

        customers = []
        for idx, c_info in enumerate(customer_data):
            existing = db.query(Customer).filter(Customer.phone_number == c_info["phone_number"]).first()
            if not existing:
                cust = Customer(
                    name=c_info["name"],
                    phone_number=c_info["phone_number"],
                    address=c_info["address"],
                    aadhar_hash=f"hashed_identifier_salt_{idx}",
                    aadhar_encrypted=f"enc_aadhaar_bytes_{idx}",
                    promissory_note=c_info["note"],
                    created_by=admin.id,
                    is_deleted=False,
                    version_id=1
                )
                db.add(cust)
                customers.append(cust)
            else:
                customers.append(existing)

        
        db.commit()
        logger.info(f"✓ Seeded {len(customers)} customers.")

        # 3. Add Loans
        loan_configs = [
            {"cust_idx": 0, "principal": 50000.0, "rate": 12.0, "status": "ACTIVE", "days_ago": 10},
            {"cust_idx": 1, "principal": 75000.0, "rate": 15.0, "status": "OVERDUE", "days_ago": 110},  # Crossed 100 days limit!
            {"cust_idx": 2, "principal": 120000.0, "rate": 10.0, "status": "ACTIVE", "days_ago": 5},
            {"cust_idx": 3, "principal": 30000.0, "rate": 8.0, "status": "ACTIVE", "days_ago": 15},
            {"cust_idx": 4, "principal": 90000.0, "rate": 14.0, "status": "OVERDUE", "days_ago": 125}   # Crossed 100 days limit!
        ]

        for config in loan_configs:
            cust = customers[config["cust_idx"]]
            
            # Check if customer already has a loan
            existing_loan = db.query(Loan).filter(Loan.customer_id == cust.id).first()
            if existing_loan:
                continue

            start_date = now_ist_naive().date() - timedelta(days=config["days_ago"])
            end_date = start_date + timedelta(days=100) # Sakra 100 days default duration
            
            loan = Loan(
                customer_id=cust.id,
                principal_amount=config["principal"],
                interest_formula="FLAT",
                interest_rate=config["rate"],
                loan_start_date=start_date,
                loan_end_date=end_date,
                duration_days=100,
                status=config["status"],
                created_by=admin.id,
                version_id=1,
                is_deleted=False
            )
            db.add(loan)
            db.flush() # Populate loan.id

            # 4. Generate daily Loan Schedules (repayments expected daily from day 1 to day 100)
            daily_principal = config["principal"] / 100.0
            daily_interest = (config["principal"] * (config["rate"] / 100.0)) / 100.0
            daily_due = daily_principal + daily_interest
            
            for day in range(1, 101):
                due_date = start_date + timedelta(days=day)
                schedule_status = "PENDING"
                if due_date < now_ist_naive().date():
                    schedule_status = "PAID" if config["status"] == "ACTIVE" else "UNPAID"

                schedule = LoanSchedule(
                    loan_id=loan.id,
                    installment_number=day,
                    due_date=due_date,
                    expected_amount=daily_due,
                    paid_amount=daily_due if schedule_status == "PAID" else 0.0,
                    remaining_amount=0.0 if schedule_status == "PAID" else daily_due,
                    status=schedule_status
                )
                db.add(schedule)


            # 5. Add Payments / Repayments
            if config["status"] == "ACTIVE":
                # Let's say Rajesh or Likith have made 80% payments
                paid_installments = int(config["days_ago"] * 0.9) # 90% collection efficiency
                for p_day in range(1, paid_installments + 1):
                    pay_date = start_date + timedelta(days=p_day)
                    payment = Payment(
                        loan_id=loan.id,
                        customer_id=cust.id,
                        payment_date=pay_date,
                        expected_amount=daily_due,
                        amount_paid=daily_due,
                        remaining_amount=0.0,
                        payment_mode="UPI",
                        payment_status="PAID",
                        recorded_by=admin.id,
                        version_id=1
                    )
                    db.add(payment)
            elif config["status"] == "OVERDUE":
                # Priya or Sneha only made payments for first 20 days and then stopped
                for p_day in range(1, 21):
                    pay_date = start_date + timedelta(days=p_day)
                    payment = Payment(
                        loan_id=loan.id,
                        customer_id=cust.id,
                        payment_date=pay_date,
                        expected_amount=daily_due,
                        amount_paid=daily_due,
                        remaining_amount=0.0,
                        payment_mode="CASH",
                        payment_status="PAID",
                        recorded_by=admin.id,
                        version_id=1
                    )
                    db.add(payment)


                # Add Overdue Alert notification
                notification = Notification(
                    user_id=admin.id,
                    customer_id=cust.id,
                    notification_type="OVERDUE_ALERT",
                    message=f"Customer {cust.name} loan #{loan.id} is OVERDUE. Days crossed: {config['days_ago'] - 100} days.",
                    is_read=False,
                    sent_at=now_ist_naive()
                )
                db.add(notification)

            # 6. Add Audit Log
            audit_log = AuditLog(
                actor_id=admin.id,
                action="LOAN_CREATE",
                table_name="loans",
                record_id=loan.id,
                new_values={"principal": config["principal"], "status": config["status"]},
                ip_address="127.0.0.1",
                user_agent="CLI Seeder V3.0",
                created_at=now_ist_naive()
            )
            db.add(audit_log)

        db.commit()
        logger.info("✓ Seeding database tables completed successfully!")
    except Exception as e:
        db.rollback()
        logger.error(f"Seeding failure: {str(e)}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
