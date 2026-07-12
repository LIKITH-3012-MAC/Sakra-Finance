"""
AI Copilot routes: conversational database assistant with auth and RBAC security.
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.schemas.common import APIResponse
from app.services.copilot_service import CopilotService
from app.ai.agent import SakraCopilotAgent
from app.services.cache import cache
from app.core.config import settings

logger = logging.getLogger("sakra.copilot")

router = APIRouter()

class AIChatRequest(BaseModel):
    query: str
    session_id: Optional[str] = "default"

copilot_agent = SakraCopilotAgent()

@router.post("/chat", response_model=APIResponse)
async def chat_with_copilot(
    payload: AIChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Enterprise Chat Gateway for SAKRA AI COPILOT.
    Verifies user authentication, role, and invokes database search before LLM generation.
    """
    logger.info("Copilot request by user '%s' (role: %s)", current_user.username, current_user.role)
    
    session_id = payload.session_id or f"session_{current_user.id}"
    
    # Register/fetch session in MySQL
    await CopilotService.get_or_create_session(db, current_user.id, session_id)
    
    # Execute AI reasoning pipeline
    response_content = await copilot_agent.execute(
        query=payload.query,
        user_role=current_user.role,
        session_id=session_id,
        db=db,
    )
    
    # Save user message and bot response
    await CopilotService.add_message(db, session_id, "user", payload.query, response_content)

    # Trigger notifications based on query contents
    query_lower = payload.query.lower()
    notif_type = None
    notif_msg = None
    if "report" in query_lower:
        notif_type = "AI_REPORT_GENERATED"
        notif_msg = f"AI Copilot generated a custom operations report for {current_user.username}"
    elif "risk" in query_lower:
        notif_type = "AI_RISK_ANALYSIS"
        notif_msg = f"AI Risk Analysis completed for query by {current_user.username}"
    elif "pattern" in query_lower or "abnormal" in query_lower:
        notif_type = "AI_ABNORMAL_PATTERN"
        notif_msg = f"AI Agent flagged abnormal repayment pattern warnings"
    elif "default" in query_lower or "predict" in query_lower:
        notif_type = "AI_DEFAULT_PREDICTION"
        notif_msg = f"AI Default Prediction model evaluated default risk alerts"
        
    if notif_type:
        from app.services.notification_service import create_system_notification, push_realtime_notifications
        notifs = await create_system_notification(db, notif_type, notif_msg)
        await db.commit()
        push_realtime_notifications(notifs)
    
    # Invalidate chat history cache
    if settings.CACHE_ENABLED:
        await cache.delete(f"user_chat_history:{current_user.id}")

    return APIResponse(
        success=True,
        message="Copilot query completed",
        data={"response": response_content},
    )

@router.get("/chat/history", response_model=APIResponse)
async def get_copilot_history(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Load past message log history for the authenticated user session.
    """
    cache_key = f"user_chat_history:{current_user.id}"
    if settings.CACHE_ENABLED:
        cached = await cache.get(cache_key)
        if cached is not None:
            return APIResponse(
                success=True,
                message="Chat history loaded successfully (cached)",
                data={"messages": cached},
            )

    history = await CopilotService.get_session_history(db, current_user.id)
    formatted = []
    for msg in history:
        formatted.append({"role": "user", "content": msg.message})
        if msg.response:
            formatted.append({"role": "assistant", "content": msg.response})
            
    if settings.CACHE_ENABLED:
        await cache.set(cache_key, formatted, expire_seconds=settings.CACHE_TTL)

    return APIResponse(
        success=True,
        message="Chat history loaded successfully",
        data={"messages": formatted},
    )

@router.delete("/chat/history", response_model=APIResponse)
async def clear_copilot_history(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Permanently delete all session histories and messages for the user.
    """
    await CopilotService.clear_history(db, current_user.id)
    
    if settings.CACHE_ENABLED:
        await cache.delete(f"user_chat_history:{current_user.id}")

    return APIResponse(
        success=True,
        message="Chat history successfully cleared",
    )
