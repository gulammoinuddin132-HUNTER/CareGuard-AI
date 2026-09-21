"""
src/api/routes/assistant.py
---------------------------
CareGuard Assistant conversational supervisor interface backed by
real-time SQLite warehouse telemetry and explainable domain models.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter
from src.api.state import CareGuardBackendState
from src.core.warehouse_safety_copilot import WarehouseSafetyCopilot

router = APIRouter(prefix="/api/assistant", tags=["Assistant"])


class ConversationMessage(BaseModel):
    sender: str
    text: str


class ChatRequest(BaseModel):
    message: str
    conversation_history: Optional[List[ConversationMessage]] = None


class ChatResponse(BaseModel):
    reply: str
    structured_data: Dict[str, Any] = Field(default_factory=dict)
    suggested_actions: List[str] = Field(default_factory=list)
    source_context: Optional[str] = "Grounded in CareGuard Telemetry (careguard.db)"


@router.post("/chat", response_model=ChatResponse)
def assistant_chat(req: ChatRequest):
    """
    CareGuard Safety Copilot: Answers warehouse supervisor operational inquiries
    strictly grounded in actual database telemetry (careguard.db) and warehouse safety policy.
    """
    backend = CareGuardBackendState.get_instance()
    copilot = WarehouseSafetyCopilot(backend_state=backend)

    history_dicts = (
        [m.dict() for m in req.conversation_history]
        if req.conversation_history
        else []
    )

    result = copilot.ask(
        message=req.message,
        conversation_history=history_dicts,
    )

    return ChatResponse(
        reply=result.get("reply", ""),
        structured_data=result.get("structured_data", {}),
        suggested_actions=result.get("suggested_actions", []),
        source_context=result.get("source_context", "Grounded in CareGuard Telemetry (careguard.db)"),
    )
