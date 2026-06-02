"""
Streamlit-compatible vector store.
Uses scikit-learn TF-IDF (pre-installed on Streamlit Cloud, zero compilation)
instead of ChromaDB. Data is persisted to disk via pickle.
"""

import os
import pickle
from typing import Dict, List

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class StreamlitVectorStore:
    """Per-agent TF-IDF knowledge base with local pickle persistence."""

    CHUNK_SIZE    = 500   # words per chunk
    CHUNK_OVERLAP = 50    # shared words between adjacent chunks

    def __init__(self, persist_path: str = "./vector_data"):
        self.persist_path = persist_path
        os.makedirs(persist_path, exist_ok=True)
        # {agent_id: {vectorizer, matrix, texts, metadata}}
        self._agents: Dict = {}
        self._load_all()

    # ── Public API ─────────────────────────────────────────────────────────────

    def add_documents(self, docs: List[Dict], agent_id: str, product_name: str):
        """Chunk all docs and build a TF-IDF index for this agent."""
        texts, metadata = [], []

        for doc in docs:
            for chunk in self._chunk(doc['content']):
                texts.append(chunk)
                metadata.append({
                    "url":     doc.get('url', ''),
                    "title":   doc.get('title', ''),
                    "product": product_name,
                })

        if not texts:
            return

        vectorizer = TfidfVectorizer(max_features=10_000, stop_words='english', ngram_range=(1, 2))
        matrix     = vectorizer.fit_transform(texts)

        self._agents[agent_id] = {
            "vectorizer": vectorizer,
            "matrix":     matrix,
            "texts":      texts,
            "metadata":   metadata,
        }
        self._save(agent_id)

    def search(self, query: str, agent_id: str, top_k: int = 5) -> List[Dict]:
        """Return the most relevant chunks for the query using cosine similarity."""
        if agent_id not in self._agents:
            return []

        agent     = self._agents[agent_id]
        query_vec = agent["vectorizer"].transform([query])
        scores    = cosine_similarity(query_vec, agent["matrix"])[0]
        top_idx   = np.argsort(scores)[-top_k:][::-1]

        return [
            {
                "content": agent["texts"][i],
                "url":     agent["metadata"][i]["url"],
                "title":   agent["metadata"][i]["title"],
            }
            for i in top_idx
            if scores[i] > 0
        ]

    def get_stats(self, agent_id: str) -> Dict:
        if agent_id in self._agents:
            return {"total_chunks": len(self._agents[agent_id]["texts"])}
        return {"total_chunks": 0}

    def clear(self, agent_id: str):
        self._agents.pop(agent_id, None)
        path = self._pkl_path(agent_id)
        if os.path.exists(path):
            os.remove(path)

    # ── Persistence ────────────────────────────────────────────────────────────

    def _save(self, agent_id: str):
        with open(self._pkl_path(agent_id), 'wb') as f:
            pickle.dump(self._agents[agent_id], f)

    def _load_all(self):
        for fname in os.listdir(self.persist_path):
            if fname.endswith('.pkl'):
                agent_id = fname[:-4]
                with open(self._pkl_path(agent_id), 'rb') as f:
                    self._agents[agent_id] = pickle.load(f)

    def _pkl_path(self, agent_id: str) -> str:
        return os.path.join(self.persist_path, f"{agent_id}.pkl")

    # ── Text chunking ──────────────────────────────────────────────────────────

    def _chunk(self, text: str) -> List[str]:
        words = text.split()
        step  = self.CHUNK_SIZE - self.CHUNK_OVERLAP
        return [
            ' '.join(words[i:i + self.CHUNK_SIZE])
            for i in range(0, len(words), step)
            if words[i:i + self.CHUNK_SIZE]
        ]
