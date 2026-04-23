import io

try:
    import pytesseract
    from PIL import Image
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False


def extract_text_from_image(buffer: bytes) -> str:
    if not OCR_AVAILABLE:
        raise ImportError(
            "pytesseract and/or Pillow not installed.\n"
            "Run: pip install pytesseract pillow\n"
            "Also install Tesseract: brew install tesseract tesseract-lang"
        )
    try:
        image = Image.open(io.BytesIO(buffer))
        text = pytesseract.image_to_string(image, lang="eng+fra")
        return text.strip()
    except pytesseract.TesseractNotFoundError:
        raise RuntimeError(
            "Tesseract binary not found. Install it:\n"
            "  macOS: brew install tesseract tesseract-lang\n"
            "  Ubuntu: sudo apt install tesseract-ocr tesseract-ocr-fra"
        )
