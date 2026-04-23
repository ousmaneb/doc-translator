import io

try:
    import pytesseract
    from PIL import Image, ImageEnhance, ImageStat, ImageOps
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False


def _open_enhanced(buffer: bytes) -> "Image.Image":
    """
    Enhance contrast and invert dark-background images so Tesseract
    (which expects black text on white) reads them reliably.
    """
    img = Image.open(io.BytesIO(buffer)).convert("RGB")
    gray = img.convert("L")
    enhanced = ImageEnhance.Contrast(gray).enhance(1.8)
    # Invert images that have a predominantly dark background
    mean_brightness = ImageStat.Stat(enhanced).mean[0]
    if mean_brightness < 110:
        enhanced = ImageOps.invert(enhanced)
    return enhanced.convert("RGB")


def extract_text_from_image(buffer: bytes) -> str:
    if not OCR_AVAILABLE:
        raise ImportError(
            "pytesseract and/or Pillow not installed.\n"
            "Run: pip install pytesseract pillow\n"
            "Also install Tesseract: brew install tesseract tesseract-lang"
        )
    try:
        text = pytesseract.image_to_string(_open_enhanced(buffer), lang="eng+fra")
        return text.strip()
    except pytesseract.TesseractNotFoundError:
        raise RuntimeError(
            "Tesseract binary not found. Install it:\n"
            "  macOS: brew install tesseract tesseract-lang\n"
            "  Ubuntu: sudo apt install tesseract-ocr tesseract-ocr-fra"
        )


def extract_image_text_blocks(buffer: bytes) -> tuple:
    """
    Extract positioned text lines from an image via OCR.
    Returns (blocks, image_width, image_height).
    Each block: {text, translated, left, top, right, bottom}

    Filters out:
    - Low-confidence words (< 50)
    - Blocks with < 25% alphabetic characters (icon/logo OCR artifacts)
    """
    if not OCR_AVAILABLE:
        raise ImportError(
            "pytesseract and/or Pillow not installed.\n"
            "Run: pip install pytesseract pillow\n"
            "Also install Tesseract: brew install tesseract tesseract-lang"
        )
    try:
        img = Image.open(io.BytesIO(buffer)).convert("RGB")
        iw, ih = img.size
        enhanced = _open_enhanced(buffer)

        data = pytesseract.image_to_data(
            enhanced,
            lang="eng+fra",
            config="--oem 3 --psm 3",
            output_type=pytesseract.Output.DICT,
        )

        lines: dict = {}
        n = len(data["text"])
        for i in range(n):
            try:
                conf = int(data["conf"][i])
            except (ValueError, TypeError):
                continue
            word = (data["text"][i] or "").strip()
            if conf < 50 or not word:
                continue
            # Filter icon/logo OCR artifacts: need ≥25% real letters
            alpha_count = sum(1 for c in word if c.isalpha())
            if len(word) > 2 and alpha_count < len(word) * 0.25:
                continue

            key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
            if key not in lines:
                lines[key] = {
                    "words": [],
                    "left": data["left"][i],
                    "top": data["top"][i],
                    "right": data["left"][i] + data["width"][i],
                    "bottom": data["top"][i] + data["height"][i],
                }
            lines[key]["words"].append(word)
            lines[key]["right"] = max(lines[key]["right"], data["left"][i] + data["width"][i])
            lines[key]["bottom"] = max(lines[key]["bottom"], data["top"][i] + data["height"][i])

        blocks = []
        for key in sorted(lines.keys()):
            v = lines[key]
            text = " ".join(v["words"]).strip()
            if not text:
                continue
            blocks.append({
                "text": text,
                "translated": "",
                "left": v["left"],
                "top": v["top"],
                "right": v["right"],
                "bottom": v["bottom"],
            })

        return blocks, iw, ih

    except pytesseract.TesseractNotFoundError:
        raise RuntimeError(
            "Tesseract binary not found. Install it:\n"
            "  macOS: brew install tesseract tesseract-lang\n"
            "  Ubuntu: sudo apt install tesseract-ocr tesseract-ocr-fra"
        )
