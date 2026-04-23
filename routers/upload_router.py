import time
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import JSONResponse

from auth import require_user
from database import SessionLocal, Document, Translation
from services.translate import detect_language, translate_texts
from services.pdf_processor import (
    extract_pdf_pages,
    build_translated_pdf,
    build_docx_from_pages,
    build_simple_pdf,
    build_simple_docx,
)
from services.docx_processor import translate_docx_in_place
from services.ocr import extract_text_from_image

router = APIRouter()

UPLOADS_DIR = Path("public/uploads")
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


def _unique_name(original: str, suffix: str) -> str:
    stem = Path(original).stem
    return f"{stem}_{int(time.time() * 1000)}{suffix}"


def _translate_text_lines(text: str, from_lang: str, to_lang: str) -> str:
    lines = text.split("\n")
    translated = translate_texts(lines, from_lang, to_lang)
    return "\n".join(translated)


@router.post("/upload")
def upload_file(
    request: Request,
    file: UploadFile = File(...),
    output_format: str = Form("pdf"),
):
    user = require_user(request)
    stage = "reading file"

    try:
        output_format = "docx" if output_format == "docx" else "pdf"
        filename = file.filename or "upload"
        ext = Path(filename).suffix.lower()
        buffer = file.file.read()

        stage = "saving file"
        saved_orig_name = _unique_name(filename, ext)
        orig_path = UPLOADS_DIR / saved_orig_name
        orig_path.write_bytes(buffer)

        source_lang = "en"
        target_lang = "fr"
        preview_text = ""
        out_ext = "_translated.docx" if output_format == "docx" else "_translated.pdf"

        # ── PDF ──────────────────────────────────────────────────────────────
        if ext == ".pdf":
            stage = "extracting PDF structure"
            pages = extract_pdf_pages(buffer)

            all_text = " ".join(
                cell["text"]
                for page in pages
                for line in page["lines"]
                for cell in line["cells"]
            )
            if not all_text.strip():
                raise ValueError(
                    "No readable text found. If this PDF is scanned, upload as PNG/JPG instead."
                )

            source_lang = detect_language(all_text)
            target_lang = "fr" if source_lang == "en" else "en"

            stage = "translating"
            all_cell_texts: list[str] = []
            cell_refs: list[tuple[int, int, int]] = []
            for pi, page in enumerate(pages):
                for li, line in enumerate(page["lines"]):
                    for ci, cell in enumerate(line["cells"]):
                        all_cell_texts.append(cell["text"])
                        cell_refs.append((pi, li, ci))

            translated_cells = translate_texts(all_cell_texts, source_lang, target_lang)
            for k, (pi, li, ci) in enumerate(cell_refs):
                pages[pi]["lines"][li]["cells"][ci]["translated"] = translated_cells[k]

            preview_text = " ".join(
                cell.get("translated", "") or cell["text"]
                for cell in (pages[0]["lines"][0]["cells"] if pages and pages[0]["lines"] else [])
            )[:800]

            stage = "building output file"
            translated_name = _unique_name(filename, out_ext)
            translated_path = UPLOADS_DIR / translated_name

            if output_format == "docx":
                build_docx_from_pages(pages, str(translated_path))
            else:
                build_translated_pdf(pages, buffer, str(translated_path))

        # ── DOCX ─────────────────────────────────────────────────────────────
        elif ext == ".docx":
            stage = "extracting text"
            try:
                from docx import Document as DocxDoc
                doc = DocxDoc(orig_path)
                raw_text = "\n".join(p.text for p in doc.paragraphs)
            except Exception:
                raw_text = ""

            if not raw_text.strip():
                raise ValueError("No readable text found in the DOCX file.")

            source_lang = detect_language(raw_text)
            target_lang = "fr" if source_lang == "en" else "en"

            stage = "building output file"
            translated_name = _unique_name(filename, out_ext)
            translated_path = UPLOADS_DIR / translated_name

            if output_format == "docx":
                translate_docx_in_place(buffer, source_lang, target_lang, str(translated_path))
                preview_text = raw_text[:800]
            else:
                stage = "translating"
                translated_docx = _translate_text_lines(raw_text, source_lang, target_lang)
                preview_text = translated_docx[:800]
                build_simple_pdf(translated_docx, str(translated_path))

        # ── Image / scanned document (OCR) ───────────────────────────────────
        elif ext in (".png", ".jpg", ".jpeg"):
            stage = "running OCR"
            ocr_text = extract_text_from_image(buffer)
            if not ocr_text.strip():
                raise ValueError("OCR found no text in the image.")

            source_lang = detect_language(ocr_text)
            target_lang = "fr" if source_lang == "en" else "en"

            stage = "translating"
            translated_img = _translate_text_lines(ocr_text, source_lang, target_lang)
            preview_text = translated_img[:800]

            stage = "building output file"
            translated_name = _unique_name(filename, out_ext)
            translated_path = UPLOADS_DIR / translated_name

            if output_format == "pdf":
                build_simple_pdf(translated_img, str(translated_path))
            else:
                build_simple_docx(translated_img, str(translated_path))

        else:
            raise ValueError("Unsupported file type. Please upload PDF, DOCX, PNG, or JPG.")

        # ── Save to DB ───────────────────────────────────────────────────────
        original_url = f"/uploads/{saved_orig_name}"
        translated_url = f"/uploads/{translated_name}"

        db = SessionLocal()
        try:
            doc_record = Document(
                filename=filename,
                original_path=original_url,
                translated_path=translated_url,
                language=source_lang,
            )
            db.add(doc_record)
            db.flush()

            translation_record = Translation(
                document_id=doc_record.id,
                user_id=user["id"],
                status="completed",
                source_lang=source_lang,
                target_lang=target_lang,
            )
            db.add(translation_record)
            db.commit()
            doc_id = doc_record.id
        finally:
            db.close()

        return JSONResponse({
            "documentId": doc_id,
            "originalUrl": original_url,
            "translatedUrl": translated_url,
            "sourceLang": source_lang,
            "targetLang": target_lang,
            "inputType": ext.lstrip("."),
            "outputFormat": output_format,
            "translatedPreview": preview_text,
        })

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[upload] failed at stage '{stage}':", e)
        raise HTTPException(status_code=500, detail=f"Failed during {stage}: {e}")
