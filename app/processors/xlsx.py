import io
import zipfile
from pathlib import Path

from fastapi import HTTPException
from PIL import Image

from app.models import DetectionResult
from app.detection import detect_qr_in_image, pil_to_cv2, risk_level
from app.libreoffice import convert_to_pdf
from app.processors.pdf import process_pdf


def process_xlsx(data: bytes, filename: str) -> DetectionResult:
    found = []
    seen_data = set()
    scanned_count = 0

    pdf_data = convert_to_pdf(data, "xlsx")
    if pdf_data:
        try:
            pdf_result = process_pdf(pdf_data, filename)
            scanned_count += pdf_result.pages_or_frames_scanned
            for qr in pdf_result.qr_codes:
                if qr.data not in seen_data:
                    found.append(qr)
                    seen_data.add(qr.data)
        except Exception:
            pass

    image_exts = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tiff"}
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            media_entries = [
                e for e in zf.namelist()
                if e.startswith("xl/media/") and Path(e).suffix.lower() in image_exts
            ]
            scanned_count += len(media_entries)
            for entry in media_entries:
                try:
                    pil_img = Image.open(io.BytesIO(zf.read(entry)))
                    img_cv = pil_to_cv2(pil_img)
                    for qr in detect_qr_in_image(img_cv, f"media: {Path(entry).name}"):
                        if qr.data not in seen_data:
                            found.append(qr)
                            seen_data.add(qr.data)
                except Exception:
                    continue
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Invalid XLSX file.")

    count = len(found)
    return DetectionResult(
        filename=filename,
        file_type="xlsx",
        qr_codes_found=count,
        qr_codes=found,
        pages_or_frames_scanned=scanned_count,
        risk_level=risk_level(count),
        message=f"{count} QR code(s) detected (scanned {scanned_count} pages/embedded images)." if count else f"No QR codes found (scanned {scanned_count} pages/embedded images).",
    )