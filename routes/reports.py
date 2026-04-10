from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from services.pipeline import process_report
from db.crud_reports import create_report

router = APIRouter()


@router.post("/reports")
async def create(
    modality: str = Form(...),
    raw_text: str = Form(None),
    source: str = Form("text"),
    file: UploadFile = File(None)
):

    # Validation
    if modality not in ["text", "voice", "image"]:
        raise HTTPException(status_code=400, detail="Invalid modality")

    if modality == "text" and not raw_text:
        raise HTTPException(status_code=400, detail="raw_text required")

    if modality in ["voice", "image"] and not file:
        raise HTTPException(status_code=400, detail="file required")

    # Create report first
    report_data = {
        "text": raw_text or "",
        "source": modality,
        "filename": file.filename if file else None
    }
    report = create_report(report_data)

    # Build payload for pipeline
    payload = {
        "report_id": report["id"],
        "text": raw_text or "",
        "source": modality,
        "file": file.file if file else None,
        "filename": file.filename if file else None
    }

    # Call pipeline
    result = await process_report(payload)

    return result