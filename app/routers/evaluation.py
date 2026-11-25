"""Evaluation QR Code, Printable Standee PDF, and Demo Reset routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import EVALUATION_FORM_URL
from app.database import get_db
from app.models import User
from app.routers.deps import add_flash, get_current_user
from app.services.evaluation_tools import generate_evaluation_standee_pdf, generate_qr_svg
from app.services.snapshot_loader import seed_database

router = APIRouter(tags=["evaluation"])


@router.get("/api/evaluation/qr.svg")
def evaluation_qr_svg(url: str = Query(default="", max_length=500)):
    """Serve an offline ISO/IEC 18004 QR Code SVG for the evaluation survey URL."""
    target = url.strip() or EVALUATION_FORM_URL or "https://forms.gle/configure-your-evaluation-form"
    svg_str = generate_qr_svg(target, size=240)
    return Response(content=svg_str, media_type="image/svg+xml")


@router.get("/evaluation/standee.pdf")
def evaluation_standee_pdf(
    url: str = Query(default="", max_length=500),
    portal_url: str = Query(default="", max_length=500),
):
    """Download a print-ready A4 CvSU-Imus Evaluation Standee PDF with Task Card + QR Code."""
    target = url.strip() or EVALUATION_FORM_URL or "https://forms.gle/configure-your-evaluation-form"
    pdf_bytes = generate_evaluation_standee_pdf(target, portal_url=portal_url.strip())
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="CvSU_Evaluation_Standee.pdf"'},
    )


@router.post("/demo/reset")
def reset_all_demo_data(
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    """Reset all demo personas, submissions, overrides, and availability matrices cleanly."""
    if user is None:
        return RedirectResponse(url="/login", status_code=303)

    current_student_number = user.student_number
    current_role = user.role

    seed_database(db, force_reset=True)

    fresh_user = db.scalar(select(User).where(User.student_number == current_student_number))
    if fresh_user is not None:
        request.session["user_id"] = fresh_user.id
        dest = "/adviser" if current_role == "adviser" else "/dashboard"
    else:
        request.session.clear()
        dest = "/login"

    add_flash(
        request,
        "Demo database reset complete. All accounts, submissions, overrides, and availability matrices restored to defaults.",
        "success",
    )
    return RedirectResponse(url=dest, status_code=303)
