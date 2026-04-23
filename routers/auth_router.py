from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db, User
from auth import hash_password, verify_password, create_token

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.post("/signup")
def signup(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    if len(password) < 6:
        return templates.TemplateResponse("signup.html", {
            "request": request,
            "user": None,
            "error": "Password must be at least 6 characters",
            "email": email,
        })

    existing = db.query(User).filter(User.email == email).first()
    if existing:
        return templates.TemplateResponse("signup.html", {
            "request": request,
            "user": None,
            "error": "An account with this email already exists",
            "email": email,
        })

    user = User(email=email, password=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_token(user.id, user.email, user.role)
    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie("access_token", token, httponly=True, samesite="lax", max_age=7 * 24 * 3600)
    return response


@router.post("/login")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.password):
        return templates.TemplateResponse("login.html", {
            "request": request,
            "user": None,
            "error": "Invalid email or password",
            "email": email,
        })

    token = create_token(user.id, user.email, user.role)
    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie("access_token", token, httponly=True, samesite="lax", max_age=7 * 24 * 3600)
    return response


@router.post("/logout")
def logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("access_token")
    return response
