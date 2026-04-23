import os
from datetime import datetime, timedelta
from typing import Optional
import bcrypt
from fastapi import Request, HTTPException
from jose import jwt, JWTError

SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 7


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_token(user_id: str, email: str, role: str) -> str:
    expire = datetime.utcnow() + timedelta(days=TOKEN_EXPIRE_DAYS)
    payload = {"sub": user_id, "email": email, "role": role, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if not payload.get("sub"):
            return None
        return {"id": payload["sub"], "email": payload.get("email"), "role": payload.get("role")}
    except JWTError:
        return None


def get_user_from_request(request: Request) -> Optional[dict]:
    token = request.cookies.get("access_token")
    if not token:
        return None
    return decode_token(token)


def require_user(request: Request) -> dict:
    user = get_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user
