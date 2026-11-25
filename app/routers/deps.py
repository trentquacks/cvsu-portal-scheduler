"""Shared FastAPI dependencies, session helpers, flash messaging, and template context."""

from __future__ import annotations

from datetime import datetime

from fastapi import Depends, HTTPException, Request, status
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import APP_DIR, CURRENT_ACADEMIC_YEAR, CURRENT_SEMESTER, EVALUATION_FORM_URL
from app.database import get_db
from app.models import CurrentEnrollment, ScheduleSubmission, User

templates = Jinja2Templates(directory=str(APP_DIR / "templates"))


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    """Return the logged-in User from signed session cookie, or None."""
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.get(User, int(user_id))


def require_user(user: User | None = Depends(get_current_user)) -> User:
    """Require an authenticated user for API routes."""
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    return user


def require_adviser(user: User = Depends(require_user)) -> User:
    """Require an authenticated Academic/Registration Adviser."""
    if user.role != "adviser":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Academic Adviser role required.",
        )
    return user


def add_flash(request: Request, message: str, category: str = "success") -> None:
    """Push a one-time flash notification into the signed session."""
    flashes = list(request.session.get("_flashes", []))
    flashes.append({"message": message, "category": category})
    request.session["_flashes"] = flashes


def pop_flashes(request: Request) -> list[dict]:
    """Consume and return pending flash notifications."""
    flashes = list(request.session.pop("_flashes", []))
    return flashes


def portal_context(
    request: Request,
    db: Session,
    user: User,
    page_title: str,
    active_nav: str,
    active_sub: str = "",
) -> dict:
    """Build standard template context matching the real CvSU-Imus Student Portal shell."""
    enrolled_count = (
        db.scalar(
            select(func.count(CurrentEnrollment.id)).where(
                CurrentEnrollment.student_id == user.id,
                CurrentEnrollment.academic_year == CURRENT_ACADEMIC_YEAR,
                CurrentEnrollment.semester == CURRENT_SEMESTER,
            )
        )
        or 0
    )

    pending_advising_count = 0
    if user.role == "adviser":
        pending_advising_count = (
            db.scalar(
                select(func.count(ScheduleSubmission.id)).where(
                    ScheduleSubmission.status == "PENDING_ADVISING"
                )
            )
            or 0
        )

    return {
        "request": request,
        "user": user,
        "page_title": page_title,
        "active_nav": active_nav,
        "active_sub": active_sub,
        "current_date": datetime.now().strftime("%A, %B %d, %Y"),
        "current_ay": CURRENT_ACADEMIC_YEAR,
        "current_sem": CURRENT_SEMESTER,
        "enrolled_count": enrolled_count,
        "pending_advising_count": pending_advising_count,
        "evaluation_form_url": EVALUATION_FORM_URL,
        "flashes": pop_flashes(request),
    }
