from typing import List

import cv2
import numpy as np
from PIL import Image

from app.models import QRLocation

# ── Singleton detector — initialized once per worker process ──────────────────
_DETECTOR = cv2.QRCodeDetector()


def detect_qr_in_image(img_array: np.ndarray, source_label: str) -> List[QRLocation]:
    """Run OpenCV QR detection on a numpy image array. Tries multi then single QR fallback."""
    detector = _DETECTOR
    results: List[QRLocation] = []

    # Multi-QR detection (OpenCV 4.5.4+)
    try:
        retval, decoded_list, points_list, _ = detector.detectAndDecodeMulti(img_array)
        if retval and decoded_list:
            for data, pts in zip(decoded_list, points_list):
                if data:
                    pts_int = pts.astype(int).reshape(-1, 2)
                    x = int(pts_int[:, 0].min())
                    y = int(pts_int[:, 1].min())
                    w = int(pts_int[:, 0].max() - x)
                    h = int(pts_int[:, 1].max() - y)
                    results.append(QRLocation(
                        source=source_label,
                        bounding_box={"x": x, "y": y, "width": w, "height": h},
                        data=data,
                    ))
        return results
    except Exception:
        pass

    # Fallback: single QR detection
    data, pts, _ = detector.detectAndDecode(img_array)
    if data and pts is not None:
        pts_int = pts.astype(int).reshape(-1, 2)
        x = int(pts_int[:, 0].min())
        y = int(pts_int[:, 1].min())
        w = int(pts_int[:, 0].max() - x)
        h = int(pts_int[:, 1].max() - y)
        results.append(QRLocation(
            source=source_label,
            bounding_box={"x": x, "y": y, "width": w, "height": h},
            data=data,
        ))
    return results


def pil_to_cv2(pil_img: Image.Image) -> np.ndarray:
    """Convert PIL image to OpenCV BGR numpy array, handling RGBA transparency correctly."""
    if pil_img.mode == "RGBA":
        # Composite onto white background — transparency can break QR decoding
        background = Image.new("RGB", pil_img.size, (255, 255, 255))
        background.paste(pil_img, mask=pil_img.split()[3])  # use alpha as mask
        pil_img = background
    else:
        pil_img = pil_img.convert("RGB")
    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)


def risk_level(count: int) -> str:
    if count == 0:
        return "LOW"
    if count <= 2:
        return "MEDIUM"
    return "HIGH"