import io

import fitz
from fastapi import HTTPException
from PIL import Image

from app.models import DetectionResult
from app.detection import detect_qr_in_image, pil_to_cv2, risk_level


def process_pdf(data: bytes, filename: str) -> DetectionResult:
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot open PDF: {e}")

    found = []
    pages_scanned = len(doc)

    for page_num, page in enumerate(doc, start=1):
        mat = fitz.Matrix(2, 2)  # 2x zoom for better QR detection
        pix = page.get_pixmap(matrix=mat)
        pil_img = Image.open(io.BytesIO(pix.tobytes("png")))
        img_cv = pil_to_cv2(pil_img)
        page_results = detect_qr_in_image(img_cv, f"page {page_num}")
        for r in page_results:
            r.page_or_frame = page_num
        found.extend(page_results)

    count = len(found)
    return DetectionResult(
        filename=filename,
        file_type="pdf",
        qr_codes_found=count,
        qr_codes=found,
        pages_or_frames_scanned=pages_scanned,
        risk_level=risk_level(count),
        message=f"{count} QR code(s) detected across {pages_scanned} page(s)." if count else f"No QR codes found in {pages_scanned} page(s).",
    )