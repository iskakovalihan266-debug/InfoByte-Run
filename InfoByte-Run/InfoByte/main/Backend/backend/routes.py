import os

from fastapi import APIRouter, Depends, Response
from fastapi.security import APIKeyCookie
from sqlalchemy.orm import Session

from .database import get_db
from .schemas import Login, Profile, Registration
from .service import current, login as create_login, logout as end_session, register as create_user

accounts = APIRouter(prefix="/api", tags=["Accounts"])

cookie_name = "infobyte_session"
cookie = APIKeyCookie(name=cookie_name, auto_error=False)


def current_user(token: str | None = Depends(cookie), db: Session = Depends(get_db)) -> Profile:
    return current(db, token or "")


@accounts.post("/users", response_model=Profile, status_code=201)
def register(data: Registration, db: Session = Depends(get_db)):
    return create_user(db, data)


@accounts.post("/sessions", response_model=Profile, status_code=201)
def login(data: Login, response: Response, db: Session = Depends(get_db)):
    user, token, ttl = create_login(db, data)
    response.set_cookie(cookie_name, token, httponly=True, samesite="strict",
                        secure=os.getenv("COOKIE_SECURE") == "1", path="/",
                        max_age=ttl if data.remember else None)
    return user


@accounts.get("/me", response_model=Profile)
def profile(user: Profile = Depends(current_user)):
    return user


@accounts.delete("/sessions/current", status_code=204)
def logout(token: str | None = Depends(cookie), user: Profile = Depends(current_user),
           db: Session = Depends(get_db)):
    end_session(db, token or "")
    response = Response(status_code=204)
    response.delete_cookie(cookie_name, path="/")
    return response




