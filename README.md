# QR Code Detection Service 2.0

A security-focused FastAPI service that detects QR codes in files of various formats. Powered by OpenCV with per-file caching, parallel batch scanning, API key authentication, rate limiting, and IP allowlist support.

## Supported File Types

| Format     | Extension                                        | Detection Strategy                                 |
| ---------- | ------------------------------------------------ | -------------------------------------------------- |
| Images     | `.png`, `.jpg`, `.bmp`, `.gif`, `.webp`, `.tiff` | Direct OpenCV scan                                 |
| PDF        | `.pdf`                                           | Page-by-page render at 2× zoom                     |
| Word       | `.docx`                                          | Embedded image extraction                          |
| Excel      | `.xlsx`                                          | `xl/media/` extraction → LibreOffice PDF render    |
| PowerPoint | `.pptx`                                          | LibreOffice PDF render → media extraction fallback |
| Archive    | `.zip`                                           | Recursive image scan                               |

## Prerequisites

- Python 3.10+
- _(Optional)_ LibreOffice installed for best PPTX/XLSX detection

## Setup

### 1. Clone / Navigate

```bash
cd qr_service_2.0
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
venv\Scripts\activate      # Windows
# source venv/bin/activate  # Mac/Linux
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

Copy the example env file and edit it:

```bash
copy .env.example .env     # Windows
# cp .env.example .env       # Mac/Linux
```

Edit `.env`:

```env
# Comma-separated API keys (leave empty to disable auth in dev)
API_KEYS=your-secret-key-here

# Comma-separated allowed IPs (leave empty to allow all)
ALLOWED_IPS=

# Rate limiting
RATE_LIMIT_REQUESTS=60
RATE_LIMIT_WINDOW_SECONDS=60
```

> **⚠️ Change the default API key before deploying!**

### 5. Run the Server

```bash
uvicorn app.main:app --reload --port 8000
```

The API will be available at **http://localhost:8000**.  
Interactive docs: **http://localhost:8000/docs**

---

## API Reference

All `/detect` endpoints require an `X-API-Key` header (if `API_KEYS` is set in `.env`).

### `POST /detect`

Scan a single file for QR codes.

```bash
curl -X POST http://localhost:8000/detect \
  -H "X-API-Key: your-secret-key-here" \
  -F "file=@path/to/file.pdf"
```

**Response:**

```json
{
  "filename": "file.pdf",
  "file_type": "pdf",
  "qr_codes_found": 1,
  "qr_codes": [
    { "source": "page 1", "data": "https://example.com", "bounding_box": {...} }
  ],
  "pages_or_frames_scanned": 3,
  "risk_level": "MEDIUM",
  "message": "1 QR code(s) detected across 3 page(s)."
}
```

### `POST /detect/batch`

Scan up to **20 files** in parallel.

```bash
curl -X POST http://localhost:8000/detect/batch \
  -H "X-API-Key: your-secret-key-here" \
  -F "files=@file1.xlsx" \
  -F "files=@file2.pdf"
```

Returns an array of `DetectionResult` objects (one per file).

### `GET /health`

```bash
curl http://localhost:8000/health
```

Returns OpenCV version, LibreOffice status, and cache statistics.

---

## Security

| Feature       | Configuration                                       |
| ------------- | --------------------------------------------------- |
| API Key Auth  | `API_KEYS` in `.env`                                |
| IP Allowlist  | `ALLOWED_IPS` in `.env`                             |
| Rate Limiting | `RATE_LIMIT_REQUESTS` / `RATE_LIMIT_WINDOW_SECONDS` |

- `/` and `/health` are **public** (no auth required).
- All `/detect*` endpoints require a valid `X-API-Key`.

---

## Project Structure

```
qr_service_2.0/
├── app/
│   ├── main.py          # FastAPI routes & app setup
│   ├── models.py        # Pydantic schemas
│   ├── detection.py     # OpenCV QR detection core
│   ├── security.py      # Auth, rate limiting, IP allowlist
│   ├── libreoffice.py   # LibreOffice conversion helper
│   └── processors/      # Per-format processors
│       ├── image.py
│       ├── pdf.py
│       ├── docx.py
│       ├── xlsx.py
│       ├── pptx.py
│       └── zip.py
├── requirements.txt
├── .env                 # Your config (not committed)
└── .env.example         # Config template
```
