from app.rag.embedder import Embedder
from app.rag.vector_store import VectorStore
from app.logging.setup import logger

class Retriever:
    def __init__(self, embedder: Embedder, vector_store: VectorStore):
        self.embedder = embedder
        self.vector_store = vector_store

    def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
         try:
            query_embedding = self.embedder.embed([query])[0]
            return self.vector_store.query(query_embedding, n_results=top_k)
         except Exception as e:
            logger.error(f"Retrieval failed: {e}")
            return []