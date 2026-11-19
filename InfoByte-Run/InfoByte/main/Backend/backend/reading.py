"""Catalog and on-demand PDF delivery for the reading section."""
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response

from .routes import current_user

BOOKS = Path(__file__).resolve().parents[2] / "Frontend" / "books"
CATALOG = BOOKS / "catalog.json"

router = APIRouter(
    prefix="/api/reading",
    tags=["Reading"],
    dependencies=[Depends(current_user)],
)


def _safe_pdf_name(value):
    return (
        isinstance(value, str)
        and bool(value.strip())
        and value == Path(value).name
        and "/" not in value
        and "\\" not in value
        and Path(value).suffix.lower() == ".pdf"
    )


def _pdf_path(book):
    filename = book.get("file")
    if not _safe_pdf_name(filename):
        return None
    candidate = BOOKS / filename
    try:
        root = BOOKS.resolve(strict=True)
        if candidate.is_symlink() or not candidate.is_file():
            return None
        resolved = candidate.resolve(strict=True)
    except OSError:
        return None
    if resolved.parent != root or resolved.suffix.lower() != ".pdf":
        return None
    return resolved


def _catalog():
    try:
        entries = json.loads(CATALOG.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except (OSError, json.JSONDecodeError) as error:
        raise HTTPException(500, "Кітап каталогын оқу мүмкін болмады.") from error

    if not isinstance(entries, list):
        raise HTTPException(500, "Кітап каталогының пішімі дұрыс емес.")

    books = []
    seen_ids = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        book_id = entry.get("id")
        title = entry.get("title")
        if (
            not isinstance(book_id, str)
            or not book_id.strip()
            or book_id in seen_ids
            or not isinstance(title, str)
            or not title.strip()
            or not _safe_pdf_name(entry.get("file"))
        ):
            continue
        seen_ids.add(book_id)
        book = {
            key: entry.get(key)
            for key in ("id", "title", "subject", "grade", "publisher", "year", "authors", "file")
        }
        authors = book.get("authors")
        book["authors"] = [name for name in authors if isinstance(name, str) and name.strip()] if isinstance(authors, list) else []
        book["available"] = _pdf_path(book) is not None
        books.append(book)
    return books


def _find_book(book_id):
    for book in _catalog():
        if book["id"] == book_id:
            return book
    raise HTTPException(404, "Кітап табылмады.")


def _require_pdf(book):
    path = _pdf_path(book)
    if path is None:
        raise HTTPException(404, "Бұл кітаптың PDF файлы табылмады.")
    return path


@router.get("/books")
def list_books():
    """Return metadata only; PDF bytes are read on an explicit request."""
    return _catalog()


@router.head("/books/{book_id}/pdf")
def check_pdf(book_id: str):
    path = _require_pdf(_find_book(book_id))
    return Response(
        status_code=200,
        headers={
            "Content-Type": "application/pdf",
            "Content-Length": str(path.stat().st_size),
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/books/{book_id}/pdf")
def get_pdf(book_id: str):
    path = _require_pdf(_find_book(book_id))
    return FileResponse(
        path,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{path.name}"',
            "Cache-Control": "private, no-store",
        },
    )
