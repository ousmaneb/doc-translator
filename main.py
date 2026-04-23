from contextlib import asynccontextmanager
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from database import create_tables
from routers import pages, auth_router, upload_router, documents_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    Path("public/uploads").mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="DocTranslator", lifespan=lifespan)

app.mount("/uploads", StaticFiles(directory="public/uploads"), name="uploads")
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(pages.router)
app.include_router(auth_router.router, prefix="/auth")
app.include_router(upload_router.router, prefix="/api")
app.include_router(documents_router.router, prefix="/api")
