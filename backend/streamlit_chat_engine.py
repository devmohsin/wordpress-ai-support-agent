"""
Streamlit-compatible chat engine.
Auto-detects the provider from the API key prefix:
  - Groq keys  start with  gsk_   → uses Groq  (free, Llama 3.3)
  - Anthropic keys start with sk-ant- → uses Anthropic (Claude Haiku)
No manual provider selection needed — just paste any key and it works.
"""

import os
from typing import Dict, List

ESCALATION_KEYWORDS = [
    "refund", "billing", "payment", "charge", "invoice",
    "legal", "lawsuit", "account deletion", "data breach",
    "angry", "furious", "unacceptable", "terrible", "worst",
    "critical bug", "all data lost", "urgent", "emergency",
]


class StreamlitChatEngine:
    """Retrieves relevant doc chunks then calls the AI to answer product questions."""

    def __init__(self, vector_store):
        self.vector_store = vector_store

    # ── Main entry point ───────────────────────────────────────────────────────

    def get_response(
        self,
        message:      str,
        agent_id:     str,
        session_id:   str,
        history:      List[Dict],
        product_name: str = "our product",
    ) -> Dict:
        should_escalate = any(kw in message.lower() for kw in ESCALATION_KEYWORDS)

        chunks  = self.vector_store.search(message, agent_id, top_k=5)
        sources = list({c["url"] for c in chunks if c["url"]})
        context = self._format_context(chunks)

        api_key  = os.environ.get("ANTHROPIC_API_KEY", "")
        provider = self._detect_provider(api_key)

        if provider == "groq":
            answer = self._call_groq(api_key, message, history, context, product_name)
        elif provider == "anthropic":
            answer = self._call_anthropic(api_key, message, history, context, product_name)
        else:
            raise ValueError(
                "API key not recognised. "
                "Groq keys start with 'gsk_', Anthropic keys start with 'sk-ant-'."
            )

        return {
            "answer":     answer,
            "sources":    sources,
            "escalate":   should_escalate,
            "session_id": session_id,
        }

    # ── Provider detection ─────────────────────────────────────────────────────

    @staticmethod
    def _detect_provider(api_key: str) -> str:
        if api_key.startswith("gsk_"):
            return "groq"
        if api_key.startswith("sk-ant-"):
            return "anthropic"
        return "unknown"

    # ── Groq call (free — Llama 3.3 70B) ──────────────────────────────────────

    def _call_groq(self, api_key, message, history, context, product_name):
        from groq import Groq

        client = Groq(api_key=api_key)

        # Groq uses OpenAI-style messages with a leading system message
        messages = [{"role": "system", "content": self._system_prompt(context, product_name)}]
        for m in history[-6:]:
            messages.append({"role": m["role"], "content": m["content"]})
        messages.append({"role": "user", "content": message})

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",   # Best free Groq model
            messages=messages,
            max_tokens=1024,
            temperature=0.3,
        )
        return response.choices[0].message.content

    # ── Anthropic call (Claude Haiku) ──────────────────────────────────────────

    def _call_anthropic(self, api_key, message, history, context, product_name):
        import anthropic

        client   = anthropic.Anthropic(api_key=api_key)
        messages = [{"role": m["role"], "content": m["content"]} for m in history[-6:]]
        messages.append({"role": "user", "content": message})

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=self._system_prompt(context, product_name),
            messages=messages,
        )
        return response.content[0].text

    # ── Shared helpers ─────────────────────────────────────────────────────────

    def _system_prompt(self, context: str, product_name: str) -> str:
        return f"""You are a friendly customer support agent for {product_name}.

Rules:
1. Answer ONLY using the documentation context provided below.
2. If the answer is not in the docs, say: "I don't have that information. Let me connect you with our support team."
3. Never guess or invent features, pricing, or settings.
4. Be warm, concise, and helpful.
5. Use numbered steps or bullet points for how-to answers.
6. If the user seems frustrated, acknowledge their feeling before answering.

--- PRODUCT DOCUMENTATION ---
{context}
--- END ---"""

    def _format_context(self, chunks: List[Dict]) -> str:
        if not chunks:
            return "No documentation available yet."
        return "\n\n".join(f"[{c['title']}]\n{c['content']}" for c in chunks)
