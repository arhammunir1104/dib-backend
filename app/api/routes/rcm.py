# app/api/routes/rcm.py
from fastapi import APIRouter, UploadFile, File
from fastapi.responses import StreamingResponse
from pathlib import Path
import openpyxl
from app.core.config import settings
from app.rag.parser import PDFParser
from app.agents.rcm_agent import RCMAgent
from app.logging.setup import logger

router = APIRouter(prefix="/api", tags=["rcm"])

# Full column headers matching the ideal JSON keys
RCM_COLUMNS = [
    "clause_ref", "section", "sub_section", "sbp_reference", "page_number",
    "process", "sub_process", "risk_category", "risk_description",
    "control_objective", "control_description", "control_type", "control_nature",
    "frequency", "control_owner", "audit_test_procedure",
    "evidence_required", "recommendation", "severity",
    "source_text", "remarks"
]

# Mapping from JSON keys to Excel column headers (same names, so direct mapping)
JSON_TO_EXCEL = {col: col for col in RCM_COLUMNS}

def _convert_json_to_xlsx(controls: list, xlsx_path: str):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(RCM_COLUMNS)
    for ctrl in controls:
        row = [ctrl.get(col, "") for col in RCM_COLUMNS]
        ws.append(row)
    # Auto-adjust column widths
    for col in ws.columns:
        max_length = 0
        col_letter = col[0].column_letter
        for cell in col:
            if cell.value:
                max_length = max(max_length, len(str(cell.value)))
        ws.column_dimensions[col_letter].width = min(max_length + 4, 50)
    wb.save(xlsx_path)

@router.post("/generate-rcm")
async def generate_rcm(pdf_file: UploadFile = File(...)):
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = upload_dir / pdf_file.filename
    with open(pdf_path, "wb") as f:
        f.write(await pdf_file.read())

    parser = PDFParser()
    full_text = await parser.parse(str(pdf_path))

    agent = RCMAgent()
    state = {"document_text": full_text}
    state = await agent.run(state)

    controls = state.get("rcm_controls", [])
    if not controls:
        return {"error": "RCM generation failed or returned empty. Check logs for details."}

    base_name = Path(pdf_file.filename).stem
    excel_path = upload_dir / f"rcm_{base_name}.xlsx"
    _convert_json_to_xlsx(controls, str(excel_path))

    def iterfile():
        with open(excel_path, mode="rb") as f:
            yield from f

    return StreamingResponse(
        iterfile(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={excel_path.name}"}
    )