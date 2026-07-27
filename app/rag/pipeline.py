from pathlib import Path
from app.rag.parser import PDFParser
from app.rag.ocr import OCRService
from app.rag.chunker import SemanticChunker
from app.rag.embedder import Embedder
from app.rag.vector_store import VectorStore
from app.rag.retriever import Retriever
from app.logging.setup import logger

class RAGPipeline:
    def __init__(self):
        self.parser = PDFParser()
        self.ocr = OCRService()
        self.chunker = SemanticChunker()
        self.embedder = Embedder()
        self.vector_store = VectorStore()
        self.retriever = Retriever(self.embedder, self.vector_store)

    async def index_document(self, file_path: str) -> None:
        # 1. Parse
        text = await self.parser.parse(file_path)
        # 2. OCR fallback
        text = await self.ocr.ocr_pdf_if_needed(file_path, text)
        # 3. Chunk with page metadata (simplified: we don't track pages yet)
        chunks = self.chunker.chunk_text(text, metadata={"source": file_path})
        # 4. Embed
        embeddings = self.embedder.embed([c["text"] for c in chunks])
        # 5. Store
        self.vector_store.add_chunks(chunks, embeddings)
        logger.info(f"Indexed {len(chunks)} chunks from {file_path}")

    def retrieve_context(self, query: str, top_k: int = 5) -> list[dict]:
        return self.retriever.retrieve(query, top_k)