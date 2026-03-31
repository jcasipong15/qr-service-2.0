import io

from fastapi import HTTPException
from PIL import Image

from app.models import DetectionResult
from app.detection import detect_qr_in_image, pil_to_cv2, risk_level


def process_image(data: bytes, filename: str) -> DetectionResult:
    try:
        pil_img = Image.open(io.BytesIO(data))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot open image: {e}")

    img_cv = pil_to_cv2(pil_img)
    found = detect_qr_in_image(img_cv, "image")
    count = len(found)

    return DetectionResult(
        filename=filename,
        file_type="image",
        qr_codes_found=count,
        qr_codes=found,
        pages_or_frames_scanned=1,
        risk_level=risk_level(count),
        message=f"{count} QR code(s) detected in image." if count else "No QR codes found.",
    )