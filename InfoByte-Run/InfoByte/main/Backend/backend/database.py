"""PostgreSQL engine and per-request SQLAlchemy sessions for InfoByte."""
import os
from pathlib import Path
from typing import Iterator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session, sessionmaker


# Keep local development settings next to the FastAPI package. Environment
# variables already present in the process take precedence over this file.
load_dotenv(Path(__file__).with_name(".env"), override=False)

_configured_url = os.getenv("DATABASE_URL")
if not _configured_url:
    raise RuntimeError("DATABASE_URL must be configured in the environment or backend/.env")

_url = make_url(_configured_url)
if _url.get_backend_name() != "postgresql":
    raise RuntimeError("InfoByte account storage requires a PostgreSQL DATABASE_URL")
if _url.database != "InfoByte":
    raise RuntimeError("DATABASE_URL must target the existing InfoByte PostgreSQL database")

# Use the installed Psycopg 3 driver for the common PostgreSQL URL schemes.
if _url.drivername in {"postgres", "postgresql"}:
    _url = _url.set(drivername="postgresql+psycopg")
elif _url.drivername == "postgresql+psycopg2":
    _url = _url.set(drivername="postgresql+psycopg")

DATABASE_URL: URL = _url

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, class_=Session, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """Provide one database session per request and always close it."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
