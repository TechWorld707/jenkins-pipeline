import os
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import DateTime, Integer, String, create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL must point to PostgreSQL.")

# Accept the common PostgreSQL URL forms and select psycopg 3 explicitly.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

if not DATABASE_URL.startswith("postgresql+psycopg://"):
    raise RuntimeError("DATABASE_URL must use PostgreSQL (postgresql+psycopg://).")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Enquiry(Base):
    __tablename__ = "enquiries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )


class EnquiryCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr


app = FastAPI(title="WebTech Technologies", version="1.0.0")


@app.on_event("startup")
def create_tables() -> None:
    # Suitable for this learning project. A production system should use migrations.
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/healthz", include_in_schema=False)
def health():
    return {"status": "ok"}


@app.post("/api/enquiries", status_code=201)
def create_enquiry(payload: EnquiryCreate, db: Annotated[Session, Depends(get_db)]):
    name = payload.name.strip()
    if len(name) < 2:
        raise HTTPException(status_code=422, detail="Please enter your name.")

    enquiry = Enquiry(name=name, email=str(payload.email).lower())
    db.add(enquiry)
    try:
        db.commit()
        db.refresh(enquiry)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="We could not save your enquiry. Please try again.") from exc

    return {"message": "Thank you. Your enquiry has been received."}


@app.get("/api/health/db", include_in_schema=False)
def database_health(db: Annotated[Session, Depends(get_db)]):
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database is unavailable.") from exc
    return {"status": "ok"}
