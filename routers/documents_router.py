from pathlib import Path

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from database import SessionLocal, Document, Translation, User
from auth import require_user

router = APIRouter()

UPLOADS_DIR = Path("public")


@router.delete("/documents/{doc_id}")
def delete_document(request: Request, doc_id: str):
    user_data = require_user(request)

    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_data["id"]).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        doc = (
            db.query(Document)
            .join(Translation, Translation.document_id == Document.id)
            .filter(Document.id == doc_id, Translation.user_id == user.id)
            .first()
        )
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        for file_path in [doc.original_path, doc.translated_path]:
            if file_path and file_path != "#":
                try:
                    full = UPLOADS_DIR / file_path.lstrip("/")
                    full.unlink(missing_ok=True)
                except Exception:
                    pass

        db.query(Translation).filter(Translation.document_id == doc_id).delete()
        db.delete(doc)
        db.commit()

        return JSONResponse({"success": True})
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()
