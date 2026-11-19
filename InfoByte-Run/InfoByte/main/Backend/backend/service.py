"""Account operations backed by PostgreSQL."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from pwdlib import PasswordHash
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from .models import AuthSession, User
from .schemas import Login, Profile, Registration


class Problem(Exception):
    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message


SHORT_SESSION = 8 * 3600
LONG_SESSION = 7 * 24 * 3600
password_hasher = PasswordHash.recommended()
_dummy_password_hash = password_hasher.hash(secrets.token_urlsafe(32))


def token_key(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()


def _profile(user: User) -> Profile:
    return Profile(id=user.id, email=user.email, full_name=user.full_name, phone=user.phone)


def _integrity_constraint(error: IntegrityError) -> str | None:
    diagnostic = getattr(error.orig, "diag", None)
    return getattr(diagnostic, "constraint_name", None)


def register(db: Session, data: Registration) -> Profile:
    # This lookup gives the common duplicate case a clear response. The named
    # PostgreSQL constraint below still handles concurrent registrations.
    if db.scalar(select(User.id).where(User.email == data.email)) is not None:
        raise Problem(409, "Бұл пошта бұрын тіркелген.")

    user = User(
        email=data.email,
        password_hash=password_hasher.hash(data.password.get_secret_value()),
        full_name=data.full_name,
        phone=data.phone,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        if _integrity_constraint(error) == "uq_users_email":
            raise Problem(409, "Бұл пошта бұрын тіркелген.") from error
        raise
    except Exception:
        db.rollback()
        raise

    db.refresh(user)
    return _profile(user)


def login(db: Session, data: Login) -> tuple[Profile, str, int]:
    user = db.scalar(select(User).where(User.email == data.email))
    stored_hash = user.password_hash if user else _dummy_password_hash
    password_matches = password_hasher.verify(data.password.get_secret_value(), stored_hash)
    if user is None or not password_matches:
        raise Problem(401, "Пошта немесе құпиясөз қате.")

    token = secrets.token_urlsafe(32)
    ttl = LONG_SESSION if data.remember else SHORT_SESSION
    now = datetime.now(timezone.utc)
    db.execute(delete(AuthSession).where(AuthSession.expires_at <= now))
    db.add(
        AuthSession(
            token_hash=token_key(token),
            user_id=user.id,
            expires_at=now + timedelta(seconds=ttl),
        )
    )
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    return _profile(user), token, ttl


def current(db: Session, token: str) -> Profile:
    session = db.scalar(
        select(AuthSession)
        .options(joinedload(AuthSession.user))
        .where(AuthSession.token_hash == token_key(token))
    )
    if session is None or session.expires_at <= datetime.now(timezone.utc):
        raise Problem(401, "Аккаунтқа кіріңіз.")
    return _profile(session.user)


def logout(db: Session, token: str) -> None:
    db.execute(delete(AuthSession).where(AuthSession.token_hash == token_key(token)))
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
