from .image import process_image
from .pdf import process_pdf
from .docx import process_docx
from .xlsx import process_xlsx
from .pptx import process_pptx
from .zip import process_zip

PROCESSORS = {
    "image": process_image,
    "pdf": process_pdf,
    "docx": process_docx,
    "xlsx": process_xlsx,
    "pptx": process_pptx,
    "zip": process_zip,
}
