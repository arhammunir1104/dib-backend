import chromadb
from app.logging.setup import logger

class VectorStore:
    def __init__(self, collection_name: str = "circular_chunks"):
        self.client = chromadb.Client()  # in-memory
        # For persistent: chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
        self.collection = self.client.get_or_create_collection(collection_name)

    def add_chunks(self, chunks: list[dict], embeddings: list[list[float]]):
     try:
        ids = [f"chunk_{i}" for i in range(len(chunks))]
        documents = [c["text"] for c in chunks]
        metadatas = [c["metadata"] for c in chunks]
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )
        logger.info(f"Added {len(chunks)} chunks to vector store")
     except Exception as e:
        logger.error(f"Failed to add chunks to vector store: {e}")

def query(self, query_embedding: list[float], n_results: int = 5) -> list[dict]:
    try:
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
        )
        return [
            {"text": doc, "metadata": meta}
            for doc, meta in zip(results["documents"][0], results["metadatas"][0])
        ]
    except Exception as e:
        logger.error(f"Vector store query failed: {e}")
        return []