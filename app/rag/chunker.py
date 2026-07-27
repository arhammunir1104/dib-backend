from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.logging.setup import logger

class SemanticChunker:
    def __init__(self, chunk_size=1000, chunk_overlap=200):
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ".", " ", ""],
        )

    def chunk_text(self, text: str, metadata: dict = None) -> list[dict]:
        """
        Returns list of dicts: {"text": chunk, "metadata": {...}}
        """
        chunks = self.splitter.create_documents([text], metadatas=[metadata or {}])
        return [{"text": c.page_content, "metadata": c.metadata} for c in chunks]