# app/api/routes/processing.py
from fastapi import APIRouter, UploadFile, File, Depends, Form, HTTPException
from fastapi.responses import StreamingResponse
from pathlib import Path
from app.core.orchestrator import Orchestrator
from app.api.deps import get_orchestrator
from app.logging.setup import logger

router = APIRouter()

def validate_file(file: UploadFile, allowed_extensions: list[str]):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext}' not allowed. Allowed extensions: {', '.join(allowed_extensions)}"
        )

MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB

@router.post("/process")
async def process_circular(
    pdf_file: UploadFile = File(...),
    template_file: UploadFile = File(None),
    report_issue_date: str = Form(""),
    orchestrator: Orchestrator = Depends(get_orchestrator),
):
    # Validate uploaded files
    validate_file(pdf_file, [".pdf", ".ppt", ".pptx"])
    if template_file:
        validate_file(template_file, [".xlsx", ".xls", ".xlsm", ".xltx", ".xltm", ".csv"])

    # Check file sizes
    if pdf_file.size > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail="PDF file is too large. Maximum size is 50 MB.")
    if template_file and template_file.size > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail="Template file is too large. Maximum size is 50 MB.")

    # Process the circular
    try:
        output_path = await orchestrator.run(pdf_file, template_file, report_issue_date)
    except Exception as e:
        logger.error(f"Processing failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An error occurred while processing the circular. Please try again later.")

    # Return the generated Excel file
    excel_file = Path(output_path)
    if not excel_file.exists():
        raise HTTPException(status_code=500, detail="The processed file could not be found. Please try again.")

    def iterfile():
        with open(excel_file, mode="rb") as f:
            yield from f

    return StreamingResponse(
        iterfile(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={excel_file.name}"}
    )