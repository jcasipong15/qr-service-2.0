import io
import zipfile
from pathlib import Path

from fastapi import HTTPException
from PIL import Image

from app.models import DetectionResult
from app.detection import detect_qr_in_image, pil_to_cv2, risk_level

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tiff"}
OFFICE_EXTS = {".pdf", ".docx", ".xlsx", ".pptx"}


def _process_entry(zf: zipfile.ZipFile, entry: str) -> list:
    """
    Recursively process a single zip entry.
    - Images: scan directly.
    - Office files: delegate to the appropriate processor.
    - Nested ZIPs: recurse into them.
    Returns a list of QRLocation objects.
    """
    from app.processors import PROCESSORS  # late import to avoid circular

    ext = Path(entry).suffix.lower()
    found = []

    try:
        data = zf.read(entry)
    except Exception:
        return found

    if ext in IMAGE_EXTS:
        try:
            pil_img = Image.open(io.BytesIO(data))
            img_cv = pil_to_cv2(pil_img)
            found.extend(detect_qr_in_image(img_cv, f"zip entry: {Path(entry).name}"))
        except Exception:
            pass
    elif ext in OFFICE_EXTS:
        file_type = ext.lstrip(".")
        if file_type in PROCESSORS:
            try:
                result = PROCESSORS[file_type](data, Path(entry).name)
                # Re-label source to show it came from inside a zip
                for qr in result.qr_codes:
                    qr.source = f"{Path(entry).name} → {qr.source}"
                found.extend(result.qr_codes)
            except Exception:
                pass
    elif ext == ".zip":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as nested_zf:
                for nested_entry in nested_zf.namelist():
                    found.extend(_process_entry(nested_zf, nested_entry))
        except Exception:
            pass

    return found


def process_zip(data: bytes, filename: str) -> DetectionResult:
    """
    Scan a ZIP archive for QR codes.
    Handles images, nested Office files (.pdf/.docx/.xlsx/.pptx), and nested ZIPs.
    """
    found = []
    entries_scanned = 0

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            scannable_exts = IMAGE_EXTS | OFFICE_EXTS | {".zip"}
            entries = [
                e for e in zf.namelist()
                if Path(e).suffix.lower() in scannable_exts
            ]
            entries_scanned = len(entries)
            for entry in entries:
                found.extend(_process_entry(zf, entry))
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Invalid ZIP file.")

    count = len(found)
    return DetectionResult(
        filename=filename,
        file_type="zip",
        qr_codes_found=count,
        qr_codes=found,
        pages_or_frames_scanned=entries_scanned,
        risk_level=risk_level(count),
        message=f"{count} QR code(s) detected across {entries_scanned} entry/entries inside ZIP."
            if count else f"No QR codes found ({entries_scanned} entries scanned inside ZIP).",
    )