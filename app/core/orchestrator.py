import tempfile
from pathlib import Path
from fastapi import UploadFile
import json
from app.core.config import settings
from app.logging.setup import logger
from app.rag.pipeline import RAGPipeline
from app.rag.parser import PDFParser
from app.agents.document_understanding import DocumentUnderstandingAgent
from app.agents.extraction import ExtractionAgent
from app.agents.evidence import EvidenceAgent
from app.agents.verification import VerificationAgent
from app.excel_engine.template_loader import TemplateLoader
from app.excel_engine.writer import ExcelWriter
from app.exceptions.base import ProcessingError

class Orchestrator:
    def __init__(self):
        self.rag = RAGPipeline()
        self.doc_agent = DocumentUnderstandingAgent()
        self.extraction_agent = ExtractionAgent(self.rag)
        self.evidence_agent = EvidenceAgent(self.rag)
        self.verification_agent = VerificationAgent()
        self.template_loader = TemplateLoader()
        self.excel_writer = ExcelWriter()

    async def run(self, pdf_file: UploadFile, template_file: UploadFile = None, report_issue_date: str = ""):
        # Save PDF
        upload_dir = Path(settings.UPLOAD_DIR)
        upload_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = upload_dir / pdf_file.filename
        with open(pdf_path, "wb") as f:
            f.write(await pdf_file.read())

        # Template
        if template_file:
            template_dir = Path(settings.TEMP_DIR)
            template_dir.mkdir(parents=True, exist_ok=True)
            template_path = template_dir / template_file.filename
            with open(template_path, "wb") as f:
                f.write(await template_file.read())
        else:
            template_path = Path(settings.TEMPLATE_DIR) / "default_template.xlsx"
            if not template_path.exists():
                raise FileNotFoundError("No template uploaded and default template not found.")

        # Load template schema (list of field definitions)
        schema = self.template_loader.load_schema(str(template_path))
        key_to_header = {
            "S.No.": "S.No.",
            "Authority": "Authority",
            "Group Head": "Group Head",
            "Cycle": "Cycle",
            "Unique Observation No.": "Unique Observation No",
            "Sub Department / Area": "Sub Department / Area",
            "Observation Insertion Date": "Observation Insertion Date",
            "Report Date": "Report Date",
            "Reporting Status": "Reporting Status",
            "Closure Date": "Closure Date",
            "observation_number": "Observation number",
            "observation_summary": "Observation Summary",
            "action_plan_summary": "Action Plan Summary",
            "action_owner": "Responsible Owner (C-1)",
            "department": "Department",
            "current_target_date": "Current Target Date",
            "original_target_date": "Original Target Date",
            "rating": "Rating",
            "section_title": "Section Title",
            "section_subtitle": "Section Subtitle",
            "report_code": "Report Code",
            "report_name": "Report Name",
            "audit_representative": "Audit Representative",
            "observation_insert_date": "Observation Insert Date",
            "report_date": "Report Date",
            "closure_date": "Closure Date",
        }

        # RAG indexing
        await self.rag.index_document(str(pdf_path))

        # Full text
        parser = PDFParser()
        full_text = await parser.parse(str(pdf_path))

        state = {
            "document_text": full_text,
            "schema": schema,
            "report_issue_date": report_issue_date
        }

        # Document Understanding (optional)
        state = await self.doc_agent.run(state)
        logger.info("=== DOCUMENT UNDERSTANDING RESULT ===")
        logger.info(json.dumps(state.get("document_understanding", {}), indent=2, default=str))

        # Extraction
        state = await self.extraction_agent.run(state)
        observations = state.get("extracted_observations", [])
        logger.info(f"Extraction returned {len(observations)} observations")
       

        if not observations:
            raise ProcessingError("No observations extracted.")

        # Translate observation keys to template headers
        mapped_observations = []
        for obs in observations:
            mapped = {}
            for key, value in obs.items():
                header = key_to_header.get(key, key)  # if no mapping, keep original
                mapped[header] = value
            mapped_observations.append(mapped)

        # Write Excel
        output_dir = Path(settings.GENERATED_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_filename = f"filled_{Path(pdf_file.filename).stem}.xlsx"
        output_path = output_dir / output_filename
        self.excel_writer.write_multiple(str(template_path), mapped_observations, str(output_path))

        logger.info(f"Excel generated: {output_path}")
        return str(output_path)