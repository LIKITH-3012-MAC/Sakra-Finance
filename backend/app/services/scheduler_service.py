"""
Scheduler service for automated daily overdue loan checks.
"""
import logging
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from app.models.loan import Loan
from app.models.payment import Payment
from app.models.notification import Notification
from app.models.user import User
from app.services.interest import calculate_interest
from app.services.email_service import send_email

logger = logging.getLogger("sakra.scheduler")


def run_daily_overdue_check(db: Session, today_date: date) -> dict:
    """
    Check all active loans for overdue status and send notifications.

    For each active loan:
    1. Sum all payments for the loan
    2. If today is past the loan end date and remaining balance > 0, flag as overdue
    3. Update loan status to 'OVERDUE'
    4. Create notifications for all admin users
    5. Send a consolidated email to admins

    Args:
        db: Database session
        today_date: The date to check against (typically today)

    Returns:
        Dictionary with:
        - total_audited: Number of active loans checked
        - total_overdue: Number of newly flagged overdue loans
        - overdue_details: List of overdue loan details
    """
    # Get all active loans
    active_loans = db.query(Loan).filter(Loan.status == "ACTIVE").all()
    total_audited = len(active_loans)
    overdue_details = []

    for loan in active_loans:
        # Sum all payments for this loan
        payments = db.query(Payment).filter(
            Payment.loan_id == loan.id,
        ).all()

        total_paid = sum(
            (p.amount_paid for p in payments),
            Decimal("0"),
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # Calculate total due
        interest = calculate_interest(
            loan.principal_amount,
            loan.interest_rate,
            loan.interest_formula,
            loan.duration_days,
        )
        total_due = loan.principal_amount + interest
        remaining = (total_due - total_paid).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # Check if overdue
        if loan.loan_end_date and today_date > loan.loan_end_date and remaining > 0:
            days_overdue = (today_date - loan.loan_end_date).days

            # Update loan status
            loan.status = "OVERDUE"

            overdue_info = {
                "loan_id": loan.id,
                "customer_id": loan.customer_id,
                "principal": str(loan.principal_amount),
                "total_due": str(total_due),
                "total_paid": str(total_paid),
                "remaining": str(remaining),
                "days_overdue": days_overdue,
                "loan_end_date": str(loan.loan_end_date),
            }
            overdue_details.append(overdue_info)

            # Create notifications for admin users
            admin_users = db.query(User).filter(
                User.role.in_(["SUPER_ADMIN", "ADMIN"]),
                User.is_deleted == False,
                User.status == "active",
            ).all()

            for admin in admin_users:
                notification = Notification(
                    user_id=admin.id,
                    title="Loan Overdue Alert",
                    message=(
                        f"Loan #{loan.id} (Customer #{loan.customer_id}) is overdue by "
                        f"{days_overdue} day(s). Remaining balance: ₹{remaining}"
                    ),
                    type="OVERDUE",
                    is_read=False,
                    reference_id=loan.id,
                    reference_type="LOAN",
                )
                db.add(notification)

    # Commit all status updates and notifications
    if overdue_details:
        db.commit()

        # Send consolidated email to admins
        admin_users = db.query(User).filter(
            User.role.in_(["SUPER_ADMIN", "ADMIN"]),
            User.is_deleted == False,
            User.status == "active",
        ).all()

        if admin_users:
            overdue_rows = ""
            for detail in overdue_details:
                overdue_rows += (
                    f"<tr style='border-bottom: 1px solid #f1f5f9;'>"
                    f"<td style='padding: 12px 8px; font-weight: 600;'>#{detail['loan_id']}</td>"
                    f"<td style='padding: 12px 8px; color: #64748b;'>#{detail['customer_id']}</td>"
                    f"<td style='padding: 12px 8px; text-align: right; font-weight: 600;'>₹{detail['remaining']}</td>"
                    f"<td style='padding: 12px 8px; text-align: right; color: #ef4444; font-weight: 600;'>{detail['days_overdue']} days</td>"
                    f"</tr>"
                )

            email_html = f"""
            <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; background-color: #ffffff;">
                <div style="background-color: #050816; padding: 24px; text-align: center;">
                    <img src="http://localhost:5173/logo.png" alt="SAKRA FINANCE" style="height: 40px; width: auto; display: inline-block;" />
                </div>
                <div style="padding: 32px; color: #0f172a; line-height: 1.6;">
                    <h2 style="margin-top: 0; font-size: 18px; font-weight: 700; color: #ef4444; display: flex; align-items: center; gap: 8px;">
                        🚨 Daily Overdue Loan Report - {today_date.isoformat()}
                    </h2>
                    <p style="font-size: 14px; color: #475569;">The system has flags for <strong>{len(overdue_details)}</strong> loan account(s) that are currently overdue:</p>
                    <table border="0" cellpadding="10" cellspacing="0" style="width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 13px;">
                        <thead>
                            <tr style="background-color: #f8fafc; border-bottom: 2px solid #e2e8f0; color: #475569; font-weight: 700; text-align: left;">
                                <th style="padding: 12px 8px;">Loan ID</th>
                                <th style="padding: 12px 8px;">Customer ID</th>
                                <th style="padding: 12px 8px; text-align: right;">Remaining Balance</th>
                                <th style="padding: 12px 8px; text-align: right;">Days Overdue</th>
                            </tr>
                        </thead>
                        <tbody style="color: #0f172a;">
                            {overdue_rows}
                        </tbody>
                    </table>
                    <p style="font-size: 13px; color: #64748b; margin-top: 24px; border-top: 1px solid #f1f5f9; pt-16;">
                        This is an automated system audit report from SAKRA FINANCE. No action is required unless account remediation steps have been requested.
                    </p>
                </div>
                <div style="background-color: #f8fafc; border-t: 1px solid #e2e8f0; padding: 16px; text-align: center; font-size: 10px; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em;">
                    Sakra Automated Compliance System · Server Mumbai Gateway
                </div>
            </div>
            """

            for admin in admin_users:
                send_email(
                    to_email=admin.email,
                    subject=f"🚨 Overdue Loan Report - {today_date.isoformat()} ({len(overdue_details)} loans)",
                    body_html=email_html,
                )

    result = {
        "total_audited": total_audited,
        "total_overdue": len(overdue_details),
        "overdue_details": overdue_details,
    }

    logger.info(
        "Daily overdue check completed: audited=%d, overdue=%d",
        total_audited,
        len(overdue_details),
    )

    return result
