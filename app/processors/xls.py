from app.models import DetectionResult
from app.detection import risk_level
from app.libreoffice import convert_to_pdf
from app.processors.pdf import process_pdf


def process_xls(data: bytes, filename: str) -> DetectionResult:
    found = []
    scanned_count = 0

    pdf_data = convert_to_pdf(data, "xls")
    if pdf_data:
        try:
            pdf_result = process_pdf(pdf_data, filename)
            scanned_count = pdf_result.pages_or_frames_scanned
            found = pdf_result.qr_codes
        except Exception:
            pass

    count = len(found)
    return DetectionResult(
        filename=filename,
        file_type="xls",
        qr_codes_found=count,
        qr_codes=found,
        pages_or_frames_scanned=scanned_count,
        risk_level=risk_level(count),
        message=f"{count} QR code(s) detected (scanned {scanned_count} page(s))." if count else f"No QR codes found (scanned {scanned_count} page(s)).",
    )
