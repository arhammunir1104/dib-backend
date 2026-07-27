import easyocr
from app.logging.setup import logger

class OCRService:
    _reader = None

    @property
    def reader(self):
        if OCRService._reader is None:
            logger.info("Initializing EasyOCR reader (loading models)...")
            try:
                OCRService._reader = easyocr.Reader(['en'])  # add 'ar' for Arabic if needed
            except Exception as e:
                logger.error(f"Failed to initialize OCR: {e}")
                raise
        return OCRService._reader

    async def extract_text_from_image(self, image_path: str) -> str:
        logger.info(f"Running OCR on {image_path}")
        result = self.reader.readtext(image_path, detail=0)
        return " ".join(result)

    async def ocr_pdf_if_needed(self, file_path: str, full_text: str) -> str:
        """
        If the extracted text is empty or very short, assume scanned PDF and run OCR page by page.
        Returns combined text.
        """
        if full_text.strip() and len(full_text.strip()) > 100:
            return full_text

        logger.info("Text extraction sparse, falling back to OCR")
        import fitz
        from pathlib import Path
        doc = fitz.open(file_path)
        ocr_text = ""
        for page_num, page in enumerate(doc):
            pix = page.get_pixmap(dpi=300)
            img_path = f"{file_path}_page_{page_num}.png"
            pix.save(img_path)
            page_text = await self.extract_text_from_image(img_path)
            ocr_text += page_text + "\n"
            Path(img_path).unlink()  # cleanup temp image
        doc.close()
        return ocr_text