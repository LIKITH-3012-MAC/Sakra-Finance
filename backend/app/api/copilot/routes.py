"""
AI Copilot routes: conversational database assistant with auth and RBAC security.
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.schemas.common import APIResponse
from app.services.copilot_service import CopilotService
from app.ai.agent import SakraCopilotAgent

logger = logging.getLogger("sakra.copilot")

router = APIRouter()

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
    Enterprise Chat Gateway for SAKRA AI COPILOT.
    Verifies user authentication, role, and invokes database search before LLM generation.
    """
    logger.info("Copilot request by user '%s' (role: %s)", current_user.username, current_user.role)
    
    session_id = payload.session_id or f"session_{current_user.id}"
    
    # Register/fetch session in MySQL
    CopilotService.get_or_create_session(db, current_user.id, session_id)
    
    # Execute AI reasoning pipeline
    response_content = await copilot_agent.execute(
        query=payload.query,
        user_role=current_user.role,
        session_id=session_id,
        db=db,
    )
    
    # Save user message and bot response
    CopilotService.add_message(db, session_id, "user", payload.query, response_content)
    
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
    history = CopilotService.get_session_history(db, current_user.id)
    formatted = []
    for msg in history:
        formatted.append({"role": "user", "content": msg.message})
        if msg.response:
            formatted.append({"role": "assistant", "content": msg.response})
            
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
    return APIResponse(
        success=True,
        message="Chat history successfully cleared",
    )
