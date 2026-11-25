"""Authentic 1:1 pseudo CvSU-Imus Student Portal pages."""

from __future__ import annotations

import math
from collections import OrderedDict

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import CURRENT_ACADEMIC_YEAR, CURRENT_SEMESTER, DAYS, DAY_LABELS
from app.database import get_db
from app.models import (
    AccountBalanceRecord,
    Course,
    CurrentEnrollment,
    NewsUpdate,
    ScheduleSubmission,
    SectionOffering,
    StudentTranscript,
    User,
)
from app.routers.deps import add_flash, get_current_user, portal_context, templates
from app.services.pdf_exporter import generate_checklist_pdf, generate_reg_form_pdf
from app.services.prerequisite_engine import evaluate_student_prerequisites
from app.services.snapshot_loader import hash_password, verify_password

router = APIRouter(tags=["portal"])

YEAR_ORDINAL = {1: "1ST YEAR", 2: "2ND YEAR", 3: "3RD YEAR", 4: "4TH YEAR"}
SEM_ORDER = {"FIRST": 1, "SECOND": 2, "SUMMER": 3}


def _redirect_if_unauthenticated(user: User | None):
    if user is None:
        return RedirectResponse(url="/login", status_code=303)
    return None


@router.get("/")
def root_redirect(user: User | None = Depends(get_current_user)):
    if user is None:
        return RedirectResponse(url="/login", status_code=303)
    if user.role == "adviser":
        return RedirectResponse(url="/adviser", status_code=303)
    return RedirectResponse(url="/dashboard", status_code=303)


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(
    request: Request,
    page: int = Query(default=1, ge=1),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    redir = _redirect_if_unauthenticated(user)
    if redir:
        return redir
    assert user is not None

    all_news = list(db.scalars(select(NewsUpdate).order_by(NewsUpdate.id.desc())).all())
    per_page = 5
    total_pages = max(1, math.ceil(len(all_news) / per_page))
    page = min(page, total_pages)
    start = (page - 1) * per_page
    paged_news = all_news[start : start + per_page]

    latest_submission = db.scalar(
        select(ScheduleSubmission)
        .where(ScheduleSubmission.student_id == user.id)
        .order_by(ScheduleSubmission.submitted_at.desc())
    )

    ctx = portal_context(request, db, user, "Dashboard", active_nav="dashboard")
    ctx.update(
        {
            "news_list": paged_news,
            "news_page": page,
            "news_total_pages": total_pages,
            "latest_submission": latest_submission,
        }
    )
    return templates.TemplateResponse(request, "portal/dashboard.html", ctx)


@router.get("/dashboard/news/{news_id}", response_class=HTMLResponse)
def news_detail_page(
    news_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    redir = _redirect_if_unauthenticated(user)
    if redir:
        return redir
    assert user is not None

    article = db.get(NewsUpdate, news_id)
    if article is None:
        add_flash(request, "News announcement not found.", "warning")
        return RedirectResponse(url="/dashboard", status_code=303)

    ctx = portal_context(request, db, user, "News and Updates", active_nav="dashboard")
    ctx["article"] = article
    return templates.TemplateResponse(request, "portal/news_detail.html", ctx)


@router.get("/profile", response_class=HTMLResponse)
def profile_page(
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    redir = _redirect_if_unauthenticated(user)
    if redir:
        return redir
    assert user is not None

    ctx = portal_context(request, db, user, "My Profile", active_nav="profile")
    return templates.TemplateResponse(request, "portal/profile.html", ctx)


@router.get("/preregistration", response_class=HTMLResponse)
def preregistration_page(
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    redir = _redirect_if_unauthenticated(user)
    if redir:
        return redir
    assert user is not None

    if user.role == "adviser":
        return RedirectResponse(url="/adviser", status_code=303)

    latest_submission = db.scalar(
        select(ScheduleSubmission)
        .where(ScheduleSubmission.student_id == user.id)
        .order_by(ScheduleSubmission.submitted_at.desc())
    )

    ctx = portal_context(request, db, user, "Pre-Registration", active_nav="preregistration")
    ctx.update(
        {
            "is_irregular": user.student_type.lower() == "irregular",
            "latest_submission": latest_submission,
            "days": DAYS,
            "day_labels": DAY_LABELS,
        }
    )
    return templates.TemplateResponse(request, "portal/preregistration.html", ctx)


@router.get("/subjects", response_class=HTMLResponse)
def current_subjects_page(
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    redir = _redirect_if_unauthenticated(user)
    if redir:
        return redir
    assert user is not None

    enrollments = list(
        db.scalars(
            select(CurrentEnrollment)
            .where(
                CurrentEnrollment.student_id == user.id,
                CurrentEnrollment.academic_year == CURRENT_ACADEMIC_YEAR,
                CurrentEnrollment.semester == CURRENT_SEMESTER,
            )
            .options(
                selectinload(CurrentEnrollment.offering).selectinload(SectionOffering.course),
                selectinload(CurrentEnrollment.offering).selectinload(SectionOffering.meetings),
            )
        ).all()
    )
    enrollments.sort(key=lambda e: e.offering.schedule_code)
    total_units = sum(e.offering.course.total_units for e in enrollments)

    ctx = portal_context(
        request,
        db,
        user,
        "Current Subjects",
        active_nav="enrollment",
        active_sub="subjects",
    )
    ctx.update({"enrollments": enrollments, "total_units": total_units})
    return templates.TemplateResponse(request, "portal/current_subjects.html", ctx)


@router.get("/subjects/regform")
def download_reg_form(
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    redir = _redirect_if_unauthenticated(user)
    if redir:
        return redir
    assert user is not None

    enrollments = list(
        db.scalars(
            select(CurrentEnrollment)
            .where(
                CurrentEnrollment.student_id == user.id,
                CurrentEnrollment.academic_year == CURRENT_ACADEMIC_YEAR,
                CurrentEnrollment.semester == CURRENT_SEMESTER,
            )
            .options(
                selectinload(CurrentEnrollment.offering).selectinload(SectionOffering.course),
                selectinload(CurrentEnrollment.offering).selectinload(SectionOffering.meetings),
            )
        ).all()
    )
    offerings = sorted([e.offering for e in enrollments], key=lambda o: o.schedule_code)
    pdf_bytes = generate_reg_form_pdf(user, offerings, CURRENT_ACADEMIC_YEAR, CURRENT_SEMESTER)
    filename = f"CvSU_RegForm_{user.student_number}_{CURRENT_ACADEMIC_YEAR}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/grades", response_class=HTMLResponse)
def grades_page(
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    redir = _redirect_if_unauthenticated(user)
    if redir:
        return redir
    assert user is not None

    records = list(
        db.scalars(
            select(StudentTranscript)
            .where(StudentTranscript.student_id == user.id)
            .options(selectinload(StudentTranscript.course))
        ).all()
    )
    records.sort(
        key=lambda r: (
            r.academic_year,
            SEM_ORDER.get(r.semester, 9),
            r.course.display_order,
        ),
        reverse=False,
    )

    grouped: OrderedDict[tuple[str, str], dict] = OrderedDict()
    overall_lec = 0
    overall_lab = 0
    overall_units = 0

    for rec in records:
        if rec.status == "NOT_TAKEN":
            continue
        key = (rec.academic_year, rec.semester)
        if key not in grouped:
            grouped[key] = {
                "academic_year": rec.academic_year,
                "semester": rec.semester,
                "rows": [],
                "lec_sum": 0,
                "lab_sum": 0,
                "total_sum": 0,
                "weighted_sum": 0.0,
                "graded_units": 0,
                "gwa": None,
            }
        bucket = grouped[key]
        bucket["rows"].append(rec)
        bucket["lec_sum"] += rec.course.lec_units
        bucket["lab_sum"] += rec.course.lab_units
        bucket["total_sum"] += rec.course.total_units

        overall_lec += rec.course.lec_units
        overall_lab += rec.course.lab_units
        overall_units += rec.course.total_units

        try:
            num_grade = float(rec.grade)
            bucket["weighted_sum"] += num_grade * rec.course.total_units
            bucket["graded_units"] += rec.course.total_units
        except ValueError:
            pass

    # Display chronological order (matching real CvSU Grades.html)
    semester_groups = list(grouped.values())
    for grp in semester_groups:
        if grp["graded_units"] > 0:
            grp["gwa"] = f"{grp['weighted_sum'] / grp['graded_units']:.2f}"
        else:
            grp["gwa"] = "-"

    ctx = portal_context(
        request,
        db,
        user,
        "Grades",
        active_nav="enrollment",
        active_sub="grades",
    )
    ctx.update(
        {
            "semester_groups": semester_groups,
            "overall_lec": overall_lec,
            "overall_lab": overall_lab,
            "overall_units": overall_units,
        }
    )
    return templates.TemplateResponse(request, "portal/grades.html", ctx)


@router.get("/checklist", response_class=HTMLResponse)
def checklist_page(
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    redir = _redirect_if_unauthenticated(user)
    if redir:
        return redir
    assert user is not None

    eligibility_rows = evaluate_student_prerequisites(db, user)
    grouped: OrderedDict[str, list] = OrderedDict()
    for item in eligibility_rows:
        yr_label = YEAR_ORDINAL.get(item.year_level, f"{item.year_level}TH YEAR")
        group_title = f"{yr_label} - {item.semester} SEMESTER"
        grouped.setdefault(group_title, []).append(item)

    completed_count = sum(1 for r in eligibility_rows if r.eligibility == "COMPLETED")
    eligible_count = sum(1 for r in eligibility_rows if r.eligibility in ("ELIGIBLE", "OVERRIDDEN"))
    locked_count = sum(1 for r in eligibility_rows if r.eligibility == "LOCKED")

    ctx = portal_context(
        request,
        db,
        user,
        "Curriculum Checklist",
        active_nav="enrollment",
        active_sub="checklist",
    )
    ctx.update(
        {
            "checklist_groups": grouped,
            "completed_count": completed_count,
            "eligible_count": eligible_count,
            "locked_count": locked_count,
            "total_courses": len(eligibility_rows),
        }
    )
    return templates.TemplateResponse(request, "portal/checklist.html", ctx)


@router.get("/checklist/download")
def checklist_download_pdf(
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    redir = _redirect_if_unauthenticated(user)
    if redir:
        return redir
    assert user is not None

    eligibility_rows = evaluate_student_prerequisites(db, user)
    pdf_bytes = generate_checklist_pdf(user, eligibility_rows)
    filename = f"CvSU_BSCS_Checklist_{user.student_number}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/accountbalance", response_class=HTMLResponse)
def account_balance_page(
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    redir = _redirect_if_unauthenticated(user)
    if redir:
        return redir
    assert user is not None

    balances = list(
        db.scalars(
            select(AccountBalanceRecord)
            .where(AccountBalanceRecord.student_id == user.id)
            .order_by(AccountBalanceRecord.id.desc())
        ).all()
    )

    ctx = portal_context(
        request,
        db,
        user,
        "Account Balance",
        active_nav="enrollment",
        active_sub="accountbalance",
    )
    ctx["balances"] = balances
    return templates.TemplateResponse(request, "portal/account_balance.html", ctx)


@router.get("/schedules", response_class=HTMLResponse)
def subjects_offered_page(
    request: Request,
    keyword: str = Query(default=""),
    field: str = Query(default="any"),
    day: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    redir = _redirect_if_unauthenticated(user)
    if redir:
        return redir
    assert user is not None

    offerings = list(
        db.scalars(
            select(SectionOffering)
            .where(
                SectionOffering.academic_year == CURRENT_ACADEMIC_YEAR,
                SectionOffering.semester == CURRENT_SEMESTER,
            )
            .options(
                selectinload(SectionOffering.course),
                selectinload(SectionOffering.meetings),
            )
            .order_by(SectionOffering.section_name.asc(), SectionOffering.schedule_code.asc())
        ).all()
    )

    clean_kw = keyword.strip().lower()
    clean_day = day.strip().upper()
    filtered: list[SectionOffering] = []
    for off in offerings:
        if clean_day:
            if not any(m.day == clean_day for m in off.meetings):
                continue
        if clean_kw:
            if field == "section" and clean_kw not in off.section_name.lower():
                continue
            elif field == "code" and clean_kw not in off.course.code.lower():
                continue
            elif field == "title" and clean_kw not in off.course.title.lower():
                continue
            elif field == "schedule_code" and clean_kw not in off.schedule_code.lower():
                continue
            elif field == "any":
                haystack = " ".join(
                    [
                        off.section_name,
                        off.course.code,
                        off.course.title,
                        off.schedule_code,
                        off.instructor,
                    ]
                ).lower()
                if clean_kw not in haystack:
                    continue
        filtered.append(off)

    per_page = 10
    total_records = len(filtered)
    total_pages = max(1, math.ceil(total_records / per_page))
    page = min(page, total_pages)
    start = (page - 1) * per_page
    paged_offerings = filtered[start : start + per_page]

    ctx = portal_context(request, db, user, "Subjects Offered", active_nav="schedules")
    ctx.update(
        {
            "offerings": paged_offerings,
            "keyword": keyword,
            "field": field,
            "day": clean_day,
            "page": page,
            "total_pages": total_pages,
            "total_records": total_records,
            "days": DAYS,
            "day_labels": DAY_LABELS,
        }
    )
    return templates.TemplateResponse(request, "portal/subjects_offered.html", ctx)


@router.get("/announcement", response_class=HTMLResponse)
def announcements_page(
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    redir = _redirect_if_unauthenticated(user)
    if redir:
        return redir
    assert user is not None

    ctx = portal_context(request, db, user, "Class Announcements", active_nav="announcement")
    return templates.TemplateResponse(request, "portal/announcements.html", ctx)


@router.get("/dataprivacy", response_class=HTMLResponse)
def data_privacy_page(
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    redir = _redirect_if_unauthenticated(user)
    if redir:
        return redir
    assert user is not None

    ctx = portal_context(request, db, user, "Data Privacy", active_nav="dataprivacy")
    return templates.TemplateResponse(request, "portal/data_privacy.html", ctx)


@router.get("/account", response_class=HTMLResponse)
def account_settings_page(
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    redir = _redirect_if_unauthenticated(user)
    if redir:
        return redir
    assert user is not None

    ctx = portal_context(request, db, user, "Account Settings", active_nav="account")
    return templates.TemplateResponse(request, "portal/account_settings.html", ctx)


@router.post("/account/contact")
def update_contact_details(
    request: Request,
    mobile_number: str = Form(""),
    personal_email: str = Form(""),
    guardian_name: str = Form(""),
    guardian_number: str = Form(""),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    redir = _redirect_if_unauthenticated(user)
    if redir:
        return redir
    assert user is not None

    user.mobile_number = mobile_number.strip()
    user.personal_email = personal_email.strip()
    user.guardian_name = guardian_name.strip().upper()
    user.guardian_number = guardian_number.strip()
    db.commit()

    add_flash(request, "Contact details have been updated successfully.", "success")
    return RedirectResponse(url="/account", status_code=303)


@router.post("/account/password")
def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    redir = _redirect_if_unauthenticated(user)
    if redir:
        return redir
    assert user is not None

    if not verify_password(current_password, user.password_hash):
        add_flash(request, "Current password is incorrect.", "danger")
        return RedirectResponse(url="/account", status_code=303)

    if len(new_password) < 6:
        add_flash(request, "New password must be at least 6 characters long.", "danger")
        return RedirectResponse(url="/account", status_code=303)

    if new_password != confirm_password:
        add_flash(request, "New password and confirmation do not match.", "danger")
        return RedirectResponse(url="/account", status_code=303)

    user.password_hash = hash_password(new_password)
    db.commit()
    add_flash(request, "Account password updated successfully.", "success")
    return RedirectResponse(url="/account", status_code=303)
