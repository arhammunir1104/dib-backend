import fitz  # PyMuPDF
from pathlib import Path
from app.logging.setup import logger

class PDFParser:
    async def parse(self, file_path: str) -> str:
        """Extract text from a PDF file. Returns full text."""
        logger.info(f"Parsing PDF: {file_path}")
        doc = fitz.open(file_path)
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        logger.info(f"Parsed {len(text)} characters")
        return text