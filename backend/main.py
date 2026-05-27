"""
AI Customer Support Agent — FastAPI Backend
Provides endpoints for knowledge base ingestion, chat, and admin analytics.
"""

import os
import uuid
from datetime import datetime
from typing import Dict, List

import uvicorn
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from chat_engine import ChatEngine
from models import ChatRequest, FeedbackRequest, OnboardRequest
from scraper import DocScraper
from vector_store import VectorStore

load_dotenv()

app = FastAPI(
    title="AI Support Agent",
    description="White-label AI customer support agent for WordPress / SaaS products",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared singletons
vector_store = VectorStore()
chat_engine = ChatEngine(vector_store)

# In-memory conversation store (swap for a DB in production)
conversations: Dict[str, Dict] = {}

# Track onboarding job statuses
onboard_jobs: Dict[str, Dict] = {}


# ─── Onboarding ───────────────────────────────────────────────────────────────

@app.post("/api/onboard")
async def onboard(request: OnboardRequest, background_tasks: BackgroundTasks):
    """
    Kick off a background job that crawls the provided docs URL,
    chunks the content, and stores it in the agent's knowledge base.
    """
    job_id = str(uuid.uuid4())
    onboard_jobs[job_id] = {
        "status": "processing",
        "agent_id": request.agent_id,
        "started_at": datetime.now().isoformat(),
    }
    background_tasks.add_task(
        _run_onboarding, job_id, request.url, request.product_name,
        request.agent_id, request.max_pages
    )
    return {"job_id": job_id, "status": "processing"}


@app.get("/api/onboard/status/{job_id}")
async def onboard_status(job_id: str):
    """Poll the status of a running onboarding job."""
    if job_id not in onboard_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return onboard_jobs[job_id]


async def _run_onboarding(job_id: str, url: str, product_name: str, agent_id: str, max_pages: int):
    try:
        scraper = DocScraper()
        docs = await scraper.scrape(url, max_pages=max_pages)
        vector_store.add_documents(docs, agent_id, product_name)
        onboard_jobs[job_id].update({
            "status": "done",
            "pages_indexed": len(docs),
            "finished_at": datetime.now().isoformat(),
        })
    except Exception as e:
        onboard_jobs[job_id].update({
            "status": "error",
            "error": str(e),
            "finished_at": datetime.now().isoformat(),
        })


# ─── Chat ─────────────────────────────────────────────────────────────────────

@app.post("/api/chat")
async def chat(request: ChatRequest):
    """Handle a user message and return an AI-generated answer from the product docs."""
    if request.session_id not in conversations:
        conversations[request.session_id] = {
            "id": request.session_id,
            "agent_id": request.agent_id,
            "messages": [],
            "created_at": datetime.now().isoformat(),
            "escalated": False,
        }

    history = conversations[request.session_id]["messages"]

    response = await chat_engine.get_response(
        message=request.message,
        agent_id=request.agent_id,
        session_id=request.session_id,
        history=history,
    )

    # Persist both turns
    now = datetime.now().isoformat()
    history.append({"role": "user", "content": request.message, "timestamp": now})
    history.append({
        "role": "assistant",
        "content": response["answer"],
        "timestamp": now,
        "escalate": response.get("escalate", False),
        "sources": response.get("sources", []),
    })

    if response.get("escalate"):
        conversations[request.session_id]["escalated"] = True

    return response


# ─── Feedback ─────────────────────────────────────────────────────────────────

@app.post("/api/feedback")
async def submit_feedback(request: FeedbackRequest):
    """Record a thumbs-up / thumbs-down on any assistant message."""
    conv = conversations.get(request.session_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Session not found")

    conv.setdefault("feedback", []).append({
        "message_index": request.message_index,
        "rating": request.rating,
        "timestamp": datetime.now().isoformat(),
    })
    return {"status": "ok"}


# ─── Admin ────────────────────────────────────────────────────────────────────

@app.get("/api/conversations")
async def get_conversations():
    """Admin: list all conversations with summary stats."""
    result = []
    for conv in conversations.values():
        msgs = conv["messages"]
        result.append({
            "id": conv["id"],
            "agent_id": conv["agent_id"],
            "message_count": len(msgs),
            "created_at": conv["created_at"],
            "escalated": conv.get("escalated", False),
            "preview": msgs[0]["content"][:80] if msgs else "",
        })
    return sorted(result, key=lambda x: x["created_at"], reverse=True)


@app.get("/api/conversations/{session_id}")
async def get_conversation(session_id: str):
    """Admin: get full message history for a single conversation."""
    conv = conversations.get(session_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@app.get("/api/stats")
async def get_stats():
    """Admin: return dashboard summary numbers."""
    total = len(conversations)
    escalated = sum(1 for c in conversations.values() if c.get("escalated"))
    total_messages = sum(len(c["messages"]) for c in conversations.values())
    return {
        "total_conversations": total,
        "escalated": escalated,
        "resolved": total - escalated,
        "total_messages": total_messages,
    }


@app.delete("/api/knowledge-base/{agent_id}")
async def clear_knowledge_base(agent_id: str):
    """Admin: wipe and re-index an agent's knowledge base."""
    vector_store.clear(agent_id)
    return {"status": "cleared", "agent_id": agent_id}


# ─── Serve frontend ───────────────────────────────────────────────────────────

frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.isdir(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
