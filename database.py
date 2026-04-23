import uuid
from datetime import datetime
from sqlalchemy import create_engine, Column, String, DateTime, ForeignKey
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker, Session

DATABASE_URL = "sqlite:///./dev.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    role = Column(String, default="user")
    created_at = Column(DateTime, default=datetime.utcnow)
    translations = relationship("Translation", back_populates="user")


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String, nullable=False)
    original_path = Column(String, nullable=False)
    translated_path = Column(String)
    language = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    translation = relationship("Translation", back_populates="document", uselist=False)


class Translation(Base):
    __tablename__ = "translations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String, ForeignKey("documents.id", ondelete="CASCADE"), unique=True)
    document = relationship("Document", back_populates="translation")
    user_id = Column(String, ForeignKey("users.id"))
    user = relationship("User", back_populates="translations")
    status = Column(String, nullable=False, default="completed")
    source_lang = Column(String, nullable=False)
    target_lang = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    Base.metadata.create_all(bind=engine)
