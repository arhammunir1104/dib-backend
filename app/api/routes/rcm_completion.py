from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from pathlib import Path
import openpyxl
from app.core.config import settings
from app.rag.parser import PDFParser
from app.agents.rcm_completion_agent import RCMCompletionAgent
from app.exceptions.rate_limit import RateLimitException
from app.logging.setup import logger

router = APIRouter(prefix="/api", tags=["rcm-completion"])

GENERATED_COLUMNS = [
    "Risk Category", "Risk", "Risk Description",
    "Control Objective", "Control Description", "Control Type",
     "Frequency", "Control Owner", 
    "Recommendation",  "Remarks",
    "Evidence Required", "Risk Level", "Audit Test Steps"
]

# Mapping from LLM JSON keys to Excel column headers.
# Some columns share the same LLM field – we handle those separately.
JSON_KEY_TO_EXCEL = {
    "risk_category": "Risk Category",
    "risk": "Risk",
    "risk_description": "Risk Description",
    "control_objective": "Control Objective",
    "control_description": "Control Description",
    "control_type": "Control Type",
    # "control_nature": "Control Nature",
    "frequency": "Frequency",
    "control_owner": "Control Owner",
    # "key_control": "Key Control",
    # "audit_test_procedure": "Audit Test Procedure",   # also fills "Audit Test Steps" below
    # "expected_evidence": "Expected Evidence",          # also fills "Evidence Required" below
    # "testing_method": "Testing Method",
    "recommendation": "Recommendation",
    # "severity": "Severity",                            # also fills "Risk Level" below
    # "automation_possible": "Automation Possible",
    "remarks": "Remarks",
}

# Columns that share the same LLM value as another column
MIRROR_COLUMNS = {
    "audit_test_procedure": "Audit Test Steps",
    "expected_evidence": "Evidence Required",
    "severity": "Risk Level",
}

@router.post("/complete-rcm")
async def complete_rcm(pdf_file: UploadFile = File(...), excel_file: UploadFile = File(...)):
    # Save uploaded files
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = upload_dir / pdf_file.filename
    xlsx_path = upload_dir / excel_file.filename
    try:
        with open(pdf_path, "wb") as f:
            f.write(await pdf_file.read())
        with open(xlsx_path, "wb") as f:
            f.write(await excel_file.read())
    except Exception as e:
        logger.error(f"Failed to save uploaded files: {e}")
        raise HTTPException(status_code=500, detail="Failed to save uploaded files. Please try again.")

    # Parse the circular PDF
    try:
        parser = PDFParser()
        full_text = await parser.parse(str(pdf_path))
    except Exception as e:
        logger.error(f"Failed to parse PDF: {e}")
        raise HTTPException(status_code=400, detail="Could not read the PDF file. Please ensure it is a valid PDF document.")

    # Load the Excel workbook
    try:
        wb = openpyxl.load_workbook(str(xlsx_path))
        ws = wb.active
    except Exception as e:
        logger.error(f"Failed to load Excel: {e}")
        raise HTTPException(status_code=400, detail="Could not read the Excel file. Please ensure it is a valid .xlsx/.xls file.")

    headers = [cell.value for cell in next(ws.iter_rows(min_row=1, max_row=1))]

    # Find column indices for required inputs
    col_map = {}
    required_inputs = ["Control Requirement", "Clause Ref", "Page No"]
    for col_name in required_inputs:
        if col_name in headers:
            col_map[col_name] = headers.index(col_name)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Required column '{col_name}' not found in the uploaded Excel file."
            )

    # Ensure generated columns exist (add them if missing)
    for gen_col in GENERATED_COLUMNS:
        if gen_col not in headers:
            ws.cell(row=1, column=len(headers)+1, value=gen_col)
            headers.append(gen_col)

    agent = RCMCompletionAgent()
    row_count = 0
    skipped_count = 0

    # Process each data row
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        control_req = row[col_map["Control Requirement"]].value or ""
        clause_ref = row[col_map["Clause Ref"]].value or ""
        page_num = row[col_map["Page No"]].value or ""

        if not control_req.strip():
            continue

        context_text = _extract_context(full_text, clause_ref) or full_text[:3000]

        logger.info(f"Completing row: Clause={clause_ref}, Requirement={control_req[:80]}...")
        try:
            result = await agent.complete_row(clause_ref, control_req, context_text)
        except RateLimitException as e:
            logger.error(f"Rate limit hit – aborting entire job: {e}")
            raise HTTPException(
                status_code=503,
                detail="AI service rate limit reached. Please wait a few minutes and try again."
            )
        except Exception as e:
            logger.error(f"LLM completion failed for clause '{clause_ref}': {e}. Skipping row.")
            skipped_count += 1
            continue   # skip this row, continue with next

        # Fill the generated columns
        for json_key, excel_header in JSON_KEY_TO_EXCEL.items():
            value = result.get(json_key, "")
            if excel_header in headers:
                col_idx = headers.index(excel_header)
                ws.cell(row=row[0].row, column=col_idx+1, value=value)

        # Fill mirrored columns (same value, different header)
        for json_key, mirror_header in MIRROR_COLUMNS.items():
            value = result.get(json_key, "")
            if mirror_header in headers:
                col_idx = headers.index(mirror_header)
                ws.cell(row=row[0].row, column=col_idx+1, value=value)

        row_count += 1

    logger.info(f"Completed {row_count} rows, skipped {skipped_count} rows.")

    # Save completed file
    output_path = upload_dir / f"completed_{xlsx_path.stem}.xlsx"
    try:
        wb.save(str(output_path))
    except Exception as e:
        logger.error(f"Failed to save completed Excel: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate the completed Excel file. Please try again.")

    def iterfile():
        with open(output_path, mode="rb") as f:
            yield from f

    response_headers = {"Content-Disposition": f"attachment; filename={output_path.name}"}
    if skipped_count > 0:
        response_headers["X-Skipped-Rows"] = str(skipped_count)

    return StreamingResponse(
        iterfile(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=response_headers
    )

def _extract_context(full_text: str, clause_ref: str) -> str:
    """Locate the clause reference in the full text and return surrounding context."""
    idx = full_text.lower().find(clause_ref.lower())
    if idx == -1:
        parts = clause_ref.split('.')
        if parts:
            idx = full_text.lower().find(parts[0].lower())
    if idx != -1:
        start = max(0, idx - 500)
        end = min(len(full_text), idx + 2500)
        return full_text[start:end]
    return ""