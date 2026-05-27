import os
import anthropic
from typing import List, Dict
from vector_store import VectorStore


# Keywords that indicate a conversation should be handed off to a human agent
ESCALATION_KEYWORDS = [
    "refund", "billing", "payment", "charge", "invoice",
    "legal", "lawsuit", "account deletion", "data breach",
    "angry", "furious", "unacceptable", "terrible", "worst",
    "critical bug", "all data lost", "urgent", "emergency",
]


class ChatEngine:
    """Combines RAG retrieval with Claude to answer product-specific support questions."""

    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store
        self.client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    async def get_response(
        self,
        message: str,
        agent_id: str,
        session_id: str,
        history: List[Dict],
        product_name: str = "our product",
    ) -> Dict:
        """
        Retrieve relevant docs, call Claude with that context,
        and return the answer plus metadata.
        """
        should_escalate = any(kw in message.lower() for kw in ESCALATION_KEYWORDS)

        # Pull top-5 most relevant doc chunks for this question
        context_chunks = self.vector_store.search(message, agent_id, top_k=5)
        sources = list({chunk['url'] for chunk in context_chunks if chunk['url']})

        context = self._format_context(context_chunks)
        messages = self._build_messages(message, history)
        system_prompt = self._build_system_prompt(context, product_name)

        response = self.client.messages.create(
            model="claude-haiku-4-5-20251001",  # Fast and cost-efficient for support volume
            max_tokens=1024,
            system=system_prompt,
            messages=messages,
        )

        answer = response.content[0].text

        return {
            "answer": answer,
            "sources": sources,
            "escalate": should_escalate,
            "session_id": session_id,
        }

    # ─── Private helpers ──────────────────────────────────────────────────────

    def _build_system_prompt(self, context: str, product_name: str) -> str:
        return f"""You are a friendly and knowledgeable customer support agent for {product_name}.

Your rules:
1. Answer ONLY using the documentation context provided below.
2. If the answer is not in the docs, respond: "I don't have that information right now. Let me connect you with our support team who can help further."
3. Never guess or invent features, settings, or prices.
4. Be warm, concise, and clear. Avoid jargon.
5. If the user is frustrated, acknowledge their feeling before answering.
6. Format answers with bullet points or numbered steps when explaining how-to tasks.

--- PRODUCT DOCUMENTATION ---
{context}
--- END OF DOCUMENTATION ---"""

    def _format_context(self, chunks: List[Dict]) -> str:
        if not chunks:
            return "No documentation available."
        return "\n\n".join(
            f"[{chunk['title']}]\n{chunk['content']}" for chunk in chunks
        )

    def _build_messages(self, message: str, history: List[Dict]) -> List[Dict]:
        # Keep only the last 6 turns to stay within context limits
        messages = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in history[-6:]
        ]
        messages.append({"role": "user", "content": message})
        return messages
