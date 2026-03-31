from typing import List
from pydantic import BaseModel


class QRLocation(BaseModel):
    page_or_frame: int | None = None
    source: str
    bounding_box: dict | None = None
    data: str


class DetectionResult(BaseModel):
    filename: str
    file_type: str
    qr_codes_found: int
    qr_codes: List[QRLocation]
    pages_or_frames_scanned: int
    risk_level: str  # LOW / MEDIUM / HIGH
    message: str