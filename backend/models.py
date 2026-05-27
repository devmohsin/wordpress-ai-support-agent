from pydantic import BaseModel
from typing import Optional, List


class OnboardRequest(BaseModel):
    url: str
    product_name: str
    agent_id: str
    max_pages: Optional[int] = 50


class ChatRequest(BaseModel):
    message: str
    session_id: str
    agent_id: str


class FeedbackRequest(BaseModel):
    session_id: str
    message_index: int
    rating: int  # 1 = helpful, -1 = not helpful


class ChatResponse(BaseModel):
    answer: str
    sources: List[str] = []
    escalate: bool = False
    session_id: str
