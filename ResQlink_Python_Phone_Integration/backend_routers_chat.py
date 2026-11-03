from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from ai.chatbot import generate_reply, get_history, clear_session

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    user_name: Optional[str] = None
    user_pos: Optional[List[float]] = None
    centers: Optional[List[Dict[str, Any]]] = None


class ChatResponse(BaseModel):
    reply: str
    intent: str


@router.post("/message", response_model=ChatResponse)
def chat_message(payload: ChatRequest):
    user_pos = tuple(payload.user_pos) if payload.user_pos else None
    result = generate_reply(
        message=payload.message,
        session_id=payload.session_id,
        user_name=payload.user_name,
        user_pos=user_pos,
        centers=payload.centers or [],
    )
    return result


@router.get("/history/{session_id}")
def history(session_id: str):
    """Return the stored conversation for a session."""
    return {"session_id": session_id, "messages": get_history(session_id)}


@router.delete("/session/{session_id}")
def reset_session(session_id: str):
    """Clear memory for a session (e.g., when user closes chatbot)."""
    clear_session(session_id)
    return {"ok": True}