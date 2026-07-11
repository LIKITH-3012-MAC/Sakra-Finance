import logging
import re
from typing import Dict, Any, Optional

logger = logging.getLogger("sakra.ai.security")

# Blacklisted patterns that indicate jailbreak or SQL injection attempts
SECURITY_BLACKLIST = [
    r"select\s+.*\s+from",
    r"union\s+select",
    r"drop\s+table",
    r"delete\s+from",
    r"insert\s+into",
    r"update\s+.*\s+set",
    r"exec\s*\(",
    r"system\s*\(",
    r"eval\s*\(",
    r"subprocess",
    r"__class__",
    r"__subclasses__",
    r"write_to_file",
    r"run_command",
]

def verify_query_safety(query: str) -> bool:
    """Scan query for potential code injection, SQL injection, or execution bypass attempts."""
    for pattern in SECURITY_BLACKLIST:
        if re.search(pattern, query, re.IGNORECASE):
            logger.warning("Security alert: Blocked suspicious query pattern. Match: %s", pattern)
            return False
    return True

def verify_tool_permission(tool_name: str, user_role: str) -> bool:
    """
    Enforce granular Role-Based Access Control (RBAC) on tools before execution.
    - SUPER_ADMIN: Can call any tool.
    - ADMIN: Can call any customer registry tool.
    - ASSISTANT_ADMIN: Restrict to collection records, customer search. No dashboard analytics.
    - VIEWER: Read-only customer information. No edit/write operations.
    """
    role = user_role.upper()
    
    if role == "SUPER_ADMIN":
        return True
        
    if role == "ADMIN":
        # Can view registry and database summaries
        return tool_name in ["get_customers_list", "get_customer_profile", "get_dashboard_analytics"]
        
    if role in ["ASSISTANT_ADMIN", "VIEWER"]:
        # Viewer/Assistant cannot run full dashboard financial summaries
        return tool_name in ["get_customers_list", "get_customer_profile"]
        
    return False
