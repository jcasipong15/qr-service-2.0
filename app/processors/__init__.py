from app.processors.image import process_image
from app.processors.pdf import process_pdf
from app.processors.docx import process_docx
from app.processors.xlsx import process_xlsx
from app.processors.pptx import process_pptx
from app.processors.zip import process_zip

PROCESSORS = {
    "image": process_image,
    "pdf": process_pdf,
    "docx": process_docx,
    "xlsx": process_xlsx,
    "pptx": process_pptx,
    "zip": process_zip,
}
