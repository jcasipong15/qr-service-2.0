"""
QR Code Detection API
Routes and app setup only. Business logic lives in processors/ and detection.py.
"""

import asyncio
import base64
import io
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List

import cv2
from dotenv import load_dotenv
load_dotenv()  # Load .env before anything reads os.getenv()

from fastapi import Depends, FastAPI, File, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.models import DetectionResult
from app.libreoffice import find_libreoffice
from app.processors import PROCESSORS
from app.security import IPAllowlistMiddleware, require_api_key

app = FastAPI(
    title="QR Code Detection API",
    description="Security-focused API to detect QR codes in files of various types.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(IPAllowlistMiddleware)

# Thread pool for CPU-bound detection work (keeps async event loop free)
_executor = ThreadPoolExecutor(max_workers=4)

# ---------------------------------------------------------------------------
# File type resolution
# ---------------------------------------------------------------------------

SUPPORTED_TYPES = {
    "image/png": "image", "image/jpeg": "image", "image/jpg": "image",
    "image/bmp": "image", "image/gif": "image", "image/webp": "image", "image/tiff": "image",
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
    "application/zip": "zip",
    "application/x-zip-compressed": "zip",
}

EXT_FALLBACK = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".bmp": "image/bmp", ".gif": "image/gif", ".webp": "image/webp",
    ".tiff": "image/tiff", ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".zip": "application/zip",
}


def resolve_file_type(content_type: str, filename: str) -> str | None:
    file_type = SUPPORTED_TYPES.get(content_type)
    if not file_type:
        ext = Path(filename).suffix.lower()
        guessed_ct = EXT_FALLBACK.get(ext)
        file_type = SUPPORTED_TYPES.get(guessed_ct or "", "")
    return file_type or None


async def run_detection(data: bytes, filename: str, file_type: str) -> DetectionResult:
    """
    Run detection in a thread pool to avoid blocking the async event loop.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, PROCESSORS[file_type], data, filename)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
def root():
    lo = find_libreoffice()
    return {
        "service": "QR Code Detection API",
        "version": "2.0.0",
        "libreoffice": lo or "not found (XLSX/PPTX detection degraded)",
        # "supported_formats": list(EXT_FALLBACK.keys()),
        "endpoints": {
            "POST /detect": "Detect QR codes in a single file",
            "POST /detect/batch": "Detect QR codes in multiple files (max 20, parallel)",
            "GET /health": "Health check",
        },
    }


@app.get("/health")
def health():
    lo = find_libreoffice()
    return {
        "status": "ok",
        "opencv": cv2.__version__,
        "libreoffice": lo or "not found",
    }

 
@app.post("/debug/extract-images", dependencies=[Depends(require_api_key)])
async def debug_extract_images(file: UploadFile = File(...)):
    """Debug: returns base64-encoded images extracted from the file's zip container."""
    data = await file.read()
    results = []
    image_exts = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            media_files = [f for f in zf.namelist()
                           if any(f.lower().endswith(e) for e in image_exts)]
            for entry in media_files:
                try:
                    img_bytes = zf.read(entry)
                    b64 = base64.b64encode(img_bytes).decode()
                    ext = Path(entry).suffix.lower().strip(".")
                    results.append({
                        "path": entry,
                        "size_bytes": len(img_bytes),
                        "data_url": f"data:image/{ext};base64,{b64}",
                    })
                except Exception as e:
                    results.append({"path": entry, "error": str(e)})
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

    return {"file": file.filename, "images_found": len(results), "images": results}


@app.post("/detect", response_model=DetectionResult, dependencies=[Depends(require_api_key)])
async def detect(file: UploadFile = File(...)):
    """Upload any supported file and get QR code detection results."""
    data = await file.read()
    filename = file.filename or "unknown"
    file_type = resolve_file_type(file.content_type or "", filename)

    if not file_type:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type. Supported extensions: {', '.join(EXT_FALLBACK.keys())}",
        )

    return await run_detection(data, filename, file_type)


@app.post("/detect/batch", response_model=List[DetectionResult], dependencies=[Depends(require_api_key)])
async def detect_batch(files: List[UploadFile] = File(...)):
    """Upload multiple files (max 20) — processed in parallel for maximum throughput."""
    if len(files) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 files per batch request.")

    # Read all files first (async I/O)
    file_data = []
    for file in files:
        data = await file.read()
        filename = file.filename or "unknown"
        file_type = resolve_file_type(file.content_type or "", filename)
        file_data.append((data, filename, file_type))

    # Process all files concurrently
    async def process_one(data: bytes, filename: str, file_type: str | None) -> DetectionResult:
        if not file_type:
            return DetectionResult(
                filename=filename, file_type="unknown", qr_codes_found=0,
                qr_codes=[], pages_or_frames_scanned=0, risk_level="LOW",
                message="Unsupported file type skipped.",
            )
        try:
            return await run_detection(data, filename, file_type)
        except HTTPException as e:
            return DetectionResult(
                filename=filename, file_type=file_type, qr_codes_found=0,
                qr_codes=[], pages_or_frames_scanned=0, risk_level="LOW",
                message=f"Error processing file: {e.detail}",
            )

    return list(await asyncio.gather(*[process_one(*fd) for fd in file_data]))