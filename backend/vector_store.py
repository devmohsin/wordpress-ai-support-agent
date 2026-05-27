import chromadb
from chromadb.utils import embedding_functions
from typing import List, Dict
import hashlib


class VectorStore:
    """Manages the per-agent knowledge base using ChromaDB with local persistence."""

    CHUNK_SIZE = 500    # words per chunk
    CHUNK_OVERLAP = 50  # words shared between adjacent chunks

    def __init__(self, persist_path: str = "./chroma_db"):
        self.client = chromadb.PersistentClient(path=persist_path)
        # Sentence-transformers model runs locally — no external API calls needed
        self.ef = embedding_functions.DefaultEmbeddingFunction()

    # ─── Public API ───────────────────────────────────────────────────────────

    def add_documents(self, docs: List[Dict], agent_id: str, product_name: str):
        """Chunk all scraped documents and upsert them into this agent's collection."""
        collection = self._get_collection(agent_id)
        chunks, ids, metadatas = [], [], []

        for doc in docs:
            for i, chunk in enumerate(self._chunk_text(doc['content'])):
                chunk_id = hashlib.md5(f"{doc['url']}_{i}".encode()).hexdigest()
                chunks.append(chunk)
                ids.append(chunk_id)
                metadatas.append({
                    "url": doc['url'],
                    "title": doc.get('title', ''),
                    "product": product_name,
                })

        if chunks:
            collection.upsert(documents=chunks, ids=ids, metadatas=metadatas)

    def search(self, query: str, agent_id: str, top_k: int = 5) -> List[Dict]:
        """Return the most semantically relevant chunks for a user query."""
        collection = self._get_collection(agent_id)
        count = collection.count()

        if count == 0:
            return []

        results = collection.query(
            query_texts=[query],
            n_results=min(top_k, count),
        )

        chunks = []
        if results['documents'] and results['documents'][0]:
            for doc, meta in zip(results['documents'][0], results['metadatas'][0]):
                chunks.append({
                    "content": doc,
                    "url": meta.get('url', ''),
                    "title": meta.get('title', ''),
                })

        return chunks

    def clear(self, agent_id: str):
        """Wipe an agent's knowledge base so it can be re-indexed."""
        try:
            self.client.delete_collection(f"agent_{agent_id}")
        except Exception:
            pass

    def get_stats(self, agent_id: str) -> Dict:
        """Return chunk count for the agent's knowledge base."""
        try:
            return {"total_chunks": self._get_collection(agent_id).count()}
        except Exception:
            return {"total_chunks": 0}

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _get_collection(self, agent_id: str):
        return self.client.get_or_create_collection(
            name=f"agent_{agent_id}",
            embedding_function=self.ef,
        )

    def _chunk_text(self, text: str) -> List[str]:
        """Split text into overlapping word-level chunks."""
        words = text.split()
        step = self.CHUNK_SIZE - self.CHUNK_OVERLAP
        return [
            ' '.join(words[i:i + self.CHUNK_SIZE])
            for i in range(0, len(words), step)
            if words[i:i + self.CHUNK_SIZE]
        ]
