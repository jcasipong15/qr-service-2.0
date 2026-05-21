from app.models import DetectionResult
from app.libreoffice import convert_to_pdf
from app.processors.pdf import process_pdf

def process_csv(data: bytes, filename: str) -> DetectionResult:
    pdf_data = convert_to_pdf(data, "csv")
    if pdf_data:
        result = process_pdf(pdf_data, filename)
        result.file_type = "csv"
        return result

    return DetectionResult(
        filename=filename,
        file_type="csv",
        qr_codes_found=0,
        qr_codes=[],
        pages_or_frames_scanned=0,
        risk_level="LOW",
        message="No QR codes found (LibreOffice conversion failed).",
    )
