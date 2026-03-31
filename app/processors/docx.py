import io

from fastapi import HTTPException
from PIL import Image

from app.models import DetectionResult
from app.detection import detect_qr_in_image, pil_to_cv2, risk_level

try:
    from docx import Document as DocxDocument
    DOCX_SUPPORT = True
except ImportError:
    DOCX_SUPPORT = False


def process_docx(data: bytes, filename: str) -> DetectionResult:
    if not DOCX_SUPPORT:
        raise HTTPException(status_code=501, detail="python-docx not installed.")

    try:
        doc = DocxDocument(io.BytesIO(data))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot open DOCX: {e}")

    found = []
    img_count = 0

    for rel in doc.part.rels.values():
        if "image" in rel.reltype:
            img_count += 1
            try:
                img_bytes = rel.target_part.blob
                pil_img = Image.open(io.BytesIO(img_bytes))
                img_cv = pil_to_cv2(pil_img)
                found.extend(detect_qr_in_image(img_cv, f"embedded image {img_count}"))
            except Exception:
                continue

    count = len(found)
    return DetectionResult(
        filename=filename,
        file_type="docx",
        qr_codes_found=count,
        qr_codes=found,
        pages_or_frames_scanned=img_count,
        risk_level=risk_level(count),
        message=f"{count} QR code(s) detected in {img_count} embedded image(s)." if count else f"No QR codes found ({img_count} embedded images scanned).",
    )