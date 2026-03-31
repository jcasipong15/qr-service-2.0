import io
import zipfile
from pathlib import Path

from fastapi import HTTPException
from PIL import Image

from app.models import DetectionResult
from app.detection import detect_qr_in_image, pil_to_cv2, risk_level
from app.libreoffice import convert_to_pdf
from app.processors.pdf import process_pdf


def process_pptx(data: bytes, filename: str) -> DetectionResult:
    """
    Strategy 1: Convert PPTX -> PDF via LibreOffice (catches vectors, EMF, all image types).
    Strategy 2: Direct media extraction from PPTX ZIP (raster images only).
    """
    # Strategy 1: LibreOffice render
    pdf_data = convert_to_pdf(data, "pptx")
    if pdf_data:
        result = process_pdf(pdf_data, filename)
        result.file_type = "pptx"
        return result

    # Strategy 2: ZIP media extraction fallback
    found = []
    img_count = 0
    image_exts = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tiff"}

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            media_entries = [
                e for e in zf.namelist()
                if e.startswith("ppt/media/") and Path(e).suffix.lower() in image_exts
            ]
            img_count = len(media_entries)
            for entry in media_entries:
                try:
                    pil_img = Image.open(io.BytesIO(zf.read(entry)))
                    img_cv = pil_to_cv2(pil_img)
                    found.extend(detect_qr_in_image(img_cv, f"media: {Path(entry).name}"))
                except Exception:
                    continue
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Invalid PPTX file.")

    count = len(found)
    return DetectionResult(
        filename=filename,
        file_type="pptx",
        qr_codes_found=count,
        qr_codes=found,
        pages_or_frames_scanned=img_count,
        risk_level=risk_level(count),
        message=f"{count} QR code(s) detected in {img_count} embedded image(s)." if count else f"No QR codes found ({img_count} embedded images scanned).",
    )