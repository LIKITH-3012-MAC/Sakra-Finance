"""
Analytics routes: dashboard summary metrics and AI copilot services.
"""
import logging
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database.session import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.customer import Customer
from app.models.loan import Loan
from app.models.payment import Payment
from app.schemas.common import APIResponse
from app.services.interest import calculate_interest
from app.services.copilot_service import CopilotService

logger = logging.getLogger("sakra.analytics")

router = APIRouter()


@router.get("/dashboard", response_model=APIResponse)
async def get_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get dashboard summary metrics from live database calculations.
    """
    from app.services.cache import cache
    
    cached_metrics = cache.get("dashboard_metrics")
    if cached_metrics:
        return APIResponse(
            success=True,
            message="Dashboard data retrieved (cached)",
            data=cached_metrics,
        )

    from app.services.loan_service import get_dashboard_metrics_details
    metrics = get_dashboard_metrics_details(db)
    
    cache.set("dashboard_metrics", metrics, expire_seconds=300)
    
    return APIResponse(
        success=True,
        message="Dashboard data retrieved",
        data=metrics,
    )



# ── AI Copilot Chat Gateway ──────────────────────────────────
from pydantic import BaseModel
from app.ai.agent import SakraCopilotAgent

class AIChatRequest(BaseModel):
    query: str
    session_id: Optional[str] = "default"

copilot_agent = SakraCopilotAgent()


@router.post("/chat", response_model=APIResponse)
async def chat_with_copilot(
    payload: AIChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Gateway endpoint to chat with SAKRA AI COPILOT.
    Enforces role verification and executes safe query analysis.
    """
    logger.info("User '%s' (role: %s) requested copilot execution", current_user.username, current_user.role)
    
    session_id = payload.session_id or f"session_{current_user.id}"
    
    # 1. Register session in DB
    CopilotService.get_or_create_session(db, current_user.id, session_id)
    
    # 2. Get AI Response
    response_content = await copilot_agent.execute(
        query=payload.query,
        user_role=current_user.role,
        session_id=session_id,
        db=db,
    )
    
    # 3. Log interaction to copilot_messages
    CopilotService.add_message(db, session_id, "user", payload.query, response_content)
    
    # Invalidate cache
    from app.services.cache import cache
    cache.delete(f"user_chat_history:{current_user.id}")
    
    return APIResponse(
        success=True,
        message="Copilot query completed",
        data={"response": response_content},
    )


@router.get("/chat/history", response_model=APIResponse)
async def get_copilot_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Load past message log history for the authenticated user session.
    """
    from app.services.cache import cache
    cache_key = f"user_chat_history:{current_user.id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return APIResponse(
            success=True,
            message="Chat history loaded successfully (cached)",
            data={"messages": cached},
        )

    history = CopilotService.get_session_history(db, current_user.id)
    formatted = []
    for msg in history:
        formatted.append({"role": "user", "content": msg.message})
        if msg.response:
            formatted.append({"role": "assistant", "content": msg.response})
            
    cache.set(cache_key, formatted, expire_seconds=300)
            
    return APIResponse(
        success=True,
        message="Chat history loaded successfully",
        data={"messages": formatted},
    )


@router.delete("/chat/history", response_model=APIResponse)
async def clear_copilot_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Permanently delete all session histories and messages for the user.
    """
    CopilotService.clear_history(db, current_user.id)
    
    from app.services.cache import cache
    cache.delete(f"user_chat_history:{current_user.id}")
    
    return APIResponse(
        success=True,
        message="Chat history successfully cleared",
    )
