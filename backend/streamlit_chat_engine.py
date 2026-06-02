"""
Streamlit-compatible chat engine.
Synchronous (no async/await) so it works directly in Streamlit callbacks
without needing asyncio wrappers.
"""

import os
from typing import Dict, List

import anthropic

ESCALATION_KEYWORDS = [
    "refund", "billing", "payment", "charge", "invoice",
    "legal", "lawsuit", "account deletion", "data breach",
    "angry", "furious", "unacceptable", "terrible", "worst",
    "critical bug", "all data lost", "urgent", "emergency",
]


class StreamlitChatEngine:
    """Retrieves relevant doc chunks then calls Claude to answer product questions."""

    def __init__(self, vector_store):
        self.vector_store = vector_store
        self._client      = None   # Lazy-init so API key can be set after import

    @property
    def client(self):
        """Create the Anthropic client on first use (after API key is set)."""
        if self._client is None:
            self._client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        return self._client

    def get_response(
        self,
        message:      str,
        agent_id:     str,
        session_id:   str,
        history:      List[Dict],
        product_name: str = "our product",
    ) -> Dict:
        """Return answer + metadata for the given user message."""
        should_escalate = any(kw in message.lower() for kw in ESCALATION_KEYWORDS)

        # Fetch the top-5 most relevant doc chunks
        chunks  = self.vector_store.search(message, agent_id, top_k=5)
        sources = list({c['url'] for c in chunks if c['url']})
        context = self._format_context(chunks)

        response = self.client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=self._system_prompt(context, product_name),
            messages=self._build_messages(message, history),
        )

        return {
            "answer":     response.content[0].text,
            "sources":    sources,
            "escalate":   should_escalate,
            "session_id": session_id,
        }

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _system_prompt(self, context: str, product_name: str) -> str:
        return f"""You are a friendly customer support agent for {product_name}.

Rules:
1. Answer ONLY using the documentation context provided below.
2. If the answer is not in the docs, say: "I don't have that information. Let me connect you with our support team."
3. Never guess or invent features, pricing, or settings.
4. Be warm, concise, and helpful.
5. Use numbered steps or bullet points for how-to answers.
6. Acknowledge frustration before answering if the user seems upset.

--- PRODUCT DOCUMENTATION ---
{context}
--- END ---"""

    def _format_context(self, chunks: List[Dict]) -> str:
        if not chunks:
            return "No documentation available."
        return "\n\n".join(f"[{c['title']}]\n{c['content']}" for c in chunks)

    def _build_messages(self, message: str, history: List[Dict]) -> List[Dict]:
        messages = [
            {"role": m["role"], "content": m["content"]}
            for m in history[-6:]
        ]
        messages.append({"role": "user", "content": message})
        return messages
