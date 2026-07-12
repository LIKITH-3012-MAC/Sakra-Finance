"""
Sakra Finance — One-time idempotent migration script to shift all existing
DATETIME values from UTC to IST (+05:30).

This script:
1. Creates a `_timezone_migrations` tracking table if it doesn't exist.
2. Checks if the migration has already run (idempotent guard).
3. Shifts all timestamp columns across 19 tables by +5:30.
4. Records the migration so re-execution is a no-op.

Usage:
    python migrate_utc_to_ist.py

Requirements:
    - MySQL database credentials in .env / app.core.config
"""

import sys
import os
import asyncio
import logging
from datetime import datetime

# Ensure app imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.database.session import SessionLocal

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("sakra.migration.utc_to_ist")

# All tables and their DATETIME columns that need the +5:30 shift
MIGRATION_MAP = {
    "users": ["created_at", "updated_at", "reset_otp_expires_at", "reset_token_expires_at"],
    "customers": ["created_at", "updated_at"],
    "loans": ["created_at", "updated_at"],
    "payments": ["created_at", "updated_at"],
    "notifications": ["sent_at"],
    "audit_logs": ["created_at"],
    "ai_logs": ["timestamp"],
    "copilot_sessions": ["created_at"],
    "copilot_messages": ["timestamp"],
    "login_logs": ["created_at"],
    "mail_logs": ["created_at"],
    "user_sessions": ["last_active_at", "expires_at", "created_at"],
    "user_invitations": ["expires_at", "created_at", "updated_at"],
    "user_password_histories": ["created_at"],
    "customer_documents": ["created_at"],
    "credit_scores": ["created_at"],
    "payment_adjustments": ["created_at"],
    "loan_schedules": ["created_at", "updated_at"],
    "user_permissions": ["created_at"],
}

MIGRATION_ID = "utc_to_ist_v1"


async def run_migration():
    async with SessionLocal() as db:
        try:
            # Step 1: Create tracking table if it doesn't exist
            await db.execute(text("""
                CREATE TABLE IF NOT EXISTS _timezone_migrations (
                    id VARCHAR(100) PRIMARY KEY,
                    executed_at DATETIME NOT NULL,
                    tables_migrated INT NOT NULL DEFAULT 0,
                    columns_migrated INT NOT NULL DEFAULT 0
                )
            """))
            await db.commit()

            # Step 2: Check if this migration has already run
            result = await db.execute(
                text("SELECT id FROM _timezone_migrations WHERE id = :mid"),
                {"mid": MIGRATION_ID}
            )
            if result.fetchone():
                logger.info("✓ Migration '%s' has already been applied. Skipping (idempotent).", MIGRATION_ID)
                return

            logger.info("Starting UTC → IST migration (+05:30 shift)...")
            tables_migrated = 0
            columns_migrated = 0

            # Step 3: Shift all timestamp columns
            for table_name, columns in MIGRATION_MAP.items():
                # Check if table exists
                check = await db.execute(text(
                    "SELECT COUNT(*) FROM information_schema.tables "
                    "WHERE table_schema = DATABASE() AND table_name = :tname"
                ), {"tname": table_name})
                
                if check.scalar() == 0:
                    logger.warning("Table '%s' does not exist. Skipping.", table_name)
                    continue

                for col in columns:
                    # Check if column exists
                    col_check = await db.execute(text(
                        "SELECT COUNT(*) FROM information_schema.columns "
                        "WHERE table_schema = DATABASE() AND table_name = :tname AND column_name = :cname"
                    ), {"tname": table_name, "cname": col})
                    
                    if col_check.scalar() == 0:
                        logger.warning("Column '%s.%s' does not exist. Skipping.", table_name, col)
                        continue

                    # Apply the +5:30 shift only to non-NULL values
                    stmt = text(f"""
                        UPDATE `{table_name}`
                        SET `{col}` = DATE_ADD(`{col}`, INTERVAL '5:30' HOUR_MINUTE)
                        WHERE `{col}` IS NOT NULL
                    """)
                    result = await db.execute(stmt)
                    logger.info(
                        "  ✓ %s.%s — %d rows shifted +05:30",
                        table_name, col, result.rowcount
                    )
                    columns_migrated += 1

                tables_migrated += 1

            # Step 4: Record migration as complete
            await db.execute(text(
                "INSERT INTO _timezone_migrations (id, executed_at, tables_migrated, columns_migrated) "
                "VALUES (:mid, :now, :tables, :cols)"
            ), {
                "mid": MIGRATION_ID,
                "now": datetime.now().isoformat(),
                "tables": tables_migrated,
                "cols": columns_migrated,
            })
            await db.commit()

            logger.info(
                "✅ Migration complete! %d tables, %d columns shifted to IST.",
                tables_migrated, columns_migrated
            )

        except Exception as e:
            await db.rollback()
            logger.error("❌ Migration failed: %s", str(e))
            raise


if __name__ == "__main__":
    asyncio.run(run_migration())
