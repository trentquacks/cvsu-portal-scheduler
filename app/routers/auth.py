"""Authentication and demo account switching routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.routers.deps import add_flash, get_current_user, pop_flashes, templates
from app.services.snapshot_loader import verify_password

router = APIRouter(tags=["auth"])


def _demo_accounts(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.id.asc())).all())


@router.get("/login", response_class=HTMLResponse)
def login_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    if current_user is not None:
        dest = "/adviser" if current_user.role == "adviser" else "/dashboard"
        return RedirectResponse(url=dest, status_code=303)

    return templates.TemplateResponse(
        request,
        "auth/login.html",
        {
            "request": request,
            "error": None,
            "flashes": pop_flashes(request),
            "demo_users": _demo_accounts(db),
        },
    )


@router.post("/login", response_class=HTMLResponse)
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    clean_username = username.strip()
    user = db.scalar(select(User).where(User.student_number == clean_username))

    if user is None or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            {
                "request": request,
                "error": "Invalid Student Number or Password. Please check your credentials and try again.",
                "entered_username": clean_username,
                "flashes": pop_flashes(request),
                "demo_users": _demo_accounts(db),
            },
            status_code=401,
        )

    request.session["user_id"] = user.id
    dest = "/adviser" if user.role == "adviser" else "/dashboard"
    return RedirectResponse(url=dest, status_code=303)


@router.get("/demo-login/{student_number}")
def demo_quick_login(student_number: str, request: Request, db: Session = Depends(get_db)):
    """One-click demo persona switcher for thesis presentation walkthroughs."""
    user = db.scalar(select(User).where(User.student_number == student_number.strip()))
    if user is None:
        add_flash(request, "Demo account not found.", "danger")
        return RedirectResponse(url="/login", status_code=303)

    request.session["user_id"] = user.id
    dest = "/adviser" if user.role == "adviser" else "/dashboard"
    return RedirectResponse(url=dest, status_code=303)


@router.get("/signout")
def signout(request: Request):
    request.session.clear()
    add_flash(request, "You have been signed out of the Student Portal.", "info")
    return RedirectResponse(url="/login", status_code=303)


@router.get("/account/register", response_class=HTMLResponse)
def account_register_notice(request: Request):
    return templates.TemplateResponse(
        request,
        "auth/notice.html",
        {
            "request": request,
            "notice_title": "Account Registration",
            "notice_body": (
                "Online account registration is disabled in this BSCS simulation environment. "
                "Please sign in using one of the pre-seeded Irregular Student, Regular Student, "
                "or Academic Adviser accounts listed on the Sign In page."
            ),
        },
    )


@router.get("/account/verify", response_class=HTMLResponse)
def account_verify_notice(request: Request):
    return templates.TemplateResponse(
        request,
        "auth/notice.html",
        {
            "request": request,
            "notice_title": "Password Recovery",
            "notice_body": (
                "Email-based password reset is simulated in this local demonstration build. "
                "Student demo accounts use password 'demo123' and the Academic Adviser account uses 'adviser123'."
            ),
        },
    )
