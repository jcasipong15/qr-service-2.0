import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


def find_libreoffice() -> str | None:
    """Find LibreOffice binary across PATH and common install locations."""
    lo_bin = shutil.which("libreoffice") or shutil.which("soffice")
    if lo_bin:
        return lo_bin

    candidates = [
        # Windows
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        # Mac
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
        # Linux
        "/usr/bin/libreoffice",
        "/usr/bin/soffice",
        "/usr/local/bin/libreoffice",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    return None


def convert_to_pdf(data: bytes, input_ext: str) -> bytes | None:
    """
    Convert any LibreOffice-supported file to PDF bytes.
    Returns None if LibreOffice is not available or conversion fails.

    Notes:
    - Uses --user-installation to avoid profile lock issues on Windows
    - Logs stderr/stdout on failure so you can diagnose issues
    """
    lo_bin = find_libreoffice()
    if not lo_bin:
        logger.warning("LibreOffice not found — skipping conversion.")
        return None

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        input_path = tmpdir_path / f"input.{input_ext}"
        profile_dir = tmpdir_path / "lo-profile"
        profile_dir.mkdir()
        input_path.write_bytes(data)

        cmd = [
            lo_bin,
            "--headless",
            # Isolate the user profile per call — fixes silent failures on Windows
            # where a shared profile gets locked by another process
            f"-env:UserInstallation=file:///{profile_dir.as_posix()}",
            "--convert-to", "pdf",
            "--outdir", str(tmpdir_path),
            str(input_path),
        ]

        logger.debug("Running LibreOffice: %s", " ".join(cmd))

        try:
            result = subprocess.run(cmd, capture_output=True, timeout=60)

            if result.returncode != 0:
                logger.warning(
                    "LibreOffice conversion failed for .%s\n  returncode: %s\n  stdout: %s\n  stderr: %s",
                    input_ext,
                    result.returncode,
                    result.stdout.decode(errors="replace").strip(),
                    result.stderr.decode(errors="replace").strip(),
                )

            pdf_path = tmpdir_path / "input.pdf"
            if pdf_path.exists():
                logger.debug("Conversion successful: %s -> input.pdf", input_ext)
                return pdf_path.read_bytes()
            else:
                # Log stderr here since the PDF wasn't produced — that's the real failure.
                logger.warning(
                    "PDF not produced for .%s\n  returncode: %s\n  stdout: %s\n  stderr: %s\n  files: %s",
                    input_ext,
                    result.returncode,
                    result.stdout.decode(errors="replace").strip(),
                    result.stderr.decode(errors="replace").strip(),
                    list(tmpdir_path.iterdir()),
                )

        except subprocess.TimeoutExpired:
            logger.error("LibreOffice conversion timed out for .%s", input_ext)
        except Exception as e:
            logger.error("LibreOffice conversion failed: %s", e)

    return None