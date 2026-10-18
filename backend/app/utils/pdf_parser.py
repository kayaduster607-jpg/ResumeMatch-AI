import io
import fitz  # PyMuPDF
from app.core.exceptions import PDFParseError


def _ocr_from_pixmap(page: fitz.Page) -> str:
    """Render page to image and run Tesseract OCR. Returns empty string on failure."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return ""

    pix = page.get_pixmap(dpi=300)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    try:
        text = pytesseract.image_to_string(img, lang="chi_sim+eng")
    except Exception:
        text = pytesseract.image_to_string(img, lang="eng")
    return text.strip() if text else ""


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from a PDF. Falls back to OCR for image-based pages."""
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception:
        raise PDFParseError("Invalid PDF file, cannot open")

    pages: list[str] = []
    for page in doc:
        text = page.get_text().strip()
        if not text:
            text = _ocr_from_pixmap(page)
        pages.append(text)
    doc.close()

    raw_text = "\n".join(pages).strip()
    return raw_text
