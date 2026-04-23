from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db, User, Translation
from auth import get_user_from_request

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def _ctx(request: Request, **extra):
    user = get_user_from_request(request)
    return {"request": request, "user": user, **extra}


@router.get("/")
def index(request: Request):
    return templates.TemplateResponse("index.html", _ctx(request))


@router.get("/login")
def login_page(request: Request):
    user = get_user_from_request(request)
    if user:
        return RedirectResponse(url="/dashboard", status_code=302)
    return templates.TemplateResponse("login.html", _ctx(request))


@router.get("/signup")
def signup_page(request: Request):
    user = get_user_from_request(request)
    if user:
        return RedirectResponse(url="/dashboard", status_code=302)
    return templates.TemplateResponse("signup.html", _ctx(request))


@router.get("/dashboard")
def dashboard_page(request: Request, db: Session = Depends(get_db)):
    user = get_user_from_request(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    db_user = db.query(User).filter(User.id == user["id"]).first()
    translations = []
    if db_user:
        translations = (
            db.query(Translation)
            .filter(Translation.user_id == db_user.id)
            .order_by(Translation.created_at.desc())
            .limit(10)
            .all()
        )

    total = len(translations)
    pending = sum(1 for t in translations if t.status != "completed")
    lang_pairs = len({f"{t.source_lang}→{t.target_lang}" for t in translations})

    recent = []
    for t in translations[:5]:
        doc = t.document
        recent.append({
            "documentId": doc.id if doc else None,
            "filename": doc.filename if doc else "Untitled",
            "sourceLang": t.source_lang or "Auto",
            "targetLang": t.target_lang or "Unknown",
            "status": t.status or "completed",
            "createdAt": t.created_at.strftime("%b %d, %Y") if t.created_at else "",
            "originalUrl": doc.original_path if doc else "#",
            "translatedUrl": doc.translated_path if doc else "#",
        })

    return templates.TemplateResponse("dashboard.html", _ctx(
        request,
        stats={
            "totalDocuments": total,
            "totalTranslations": total,
            "pendingTranslations": pending,
            "languagePairs": lang_pairs,
        },
        recent_activity=recent,
    ))


@router.get("/about")
def about_page(request: Request):
    return templates.TemplateResponse("about.html", _ctx(request))
