"""Academic / Registration Adviser portal for irregular student review, manual overrides, and sign-off."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.config import CURRENT_ACADEMIC_YEAR, CURRENT_SEMESTER
from app.database import get_db
from app.models import (
    Course,
    CurrentEnrollment,
    PrerequisiteOverride,
    ScheduleSubmission,
    SectionOffering,
    User,
)
from app.routers.deps import add_flash, get_current_user, portal_context, templates
from app.services.prerequisite_engine import evaluate_student_prerequisites

router = APIRouter(prefix="/adviser", tags=["adviser"])


def _require_adviser_page(request: Request, user: User | None):
    if user is None:
        return RedirectResponse(url="/login", status_code=303)
    if user.role != "adviser":
        add_flash(request, "Access restricted to Department Registration Advisers.", "warning")
        return RedirectResponse(url="/dashboard", status_code=303)
    return None


@router.get("", response_class=HTMLResponse)
def adviser_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    redir = _require_adviser_page(request, user)
    if redir:
        return redir
    assert user is not None

    submissions = list(
        db.scalars(
            select(ScheduleSubmission)
            .options(
                selectinload(ScheduleSubmission.student),
                selectinload(ScheduleSubmission.reviewed_by),
            )
            .order_by(ScheduleSubmission.submitted_at.desc())
        ).all()
    )

    irregular_students = list(
        db.scalars(
            select(User)
            .where(User.role == "student", User.student_type == "Irregular")
            .options(selectinload(User.overrides), selectinload(User.submissions))
            .order_by(User.student_number.asc())
        ).all()
    )

    all_overrides = list(
        db.scalars(
            select(PrerequisiteOverride)
            .options(
                selectinload(PrerequisiteOverride.student),
                selectinload(PrerequisiteOverride.course),
            )
            .order_by(PrerequisiteOverride.created_at.desc())
        ).all()
    )

    pending_count = sum(1 for s in submissions if s.status == "PENDING_ADVISING")
    approved_count = sum(1 for s in submissions if s.status == "APPROVED")
    revision_count = sum(1 for s in submissions if s.status == "REVISION_REQUESTED")

    ctx = portal_context(request, db, user, "Adviser Review & Sign-Off", active_nav="adviser")
    ctx.update(
        {
            "submissions": submissions,
            "irregular_students": irregular_students,
            "all_overrides": all_overrides,
            "pending_count": pending_count,
            "approved_count": approved_count,
            "revision_count": revision_count,
            "override_count": len(all_overrides),
        }
    )
    return templates.TemplateResponse(request, "adviser/dashboard.html", ctx)


@router.get("/student/{student_id}", response_class=HTMLResponse)
def adviser_student_review(
    student_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    redir = _require_adviser_page(request, user)
    if redir:
        return redir
    assert user is not None

    student = db.get(User, student_id)
    if student is None or student.role != "student":
        add_flash(request, "Student record not found.", "danger")
        return RedirectResponse(url="/adviser", status_code=303)

    eligibility = evaluate_student_prerequisites(db, student)
    locked_courses = [e for e in eligibility if e.eligibility == "LOCKED"]
    failed_courses = [e for e in eligibility if e.transcript_status == "FAILED"]
    overridden_courses = [e for e in eligibility if e.eligibility == "OVERRIDDEN"]
    completed_count = sum(1 for e in eligibility if e.eligibility == "COMPLETED")

    overrides = list(
        db.scalars(
            select(PrerequisiteOverride)
            .where(PrerequisiteOverride.student_id == student.id)
            .options(selectinload(PrerequisiteOverride.course))
            .order_by(PrerequisiteOverride.created_at.desc())
        ).all()
    )

    submissions = list(
        db.scalars(
            select(ScheduleSubmission)
            .where(ScheduleSubmission.student_id == student.id)
            .order_by(ScheduleSubmission.submitted_at.desc())
        ).all()
    )

    latest_sub = submissions[0] if submissions else None
    sub_offerings: list[SectionOffering] = []
    sub_conflicts: list[dict] = []
    sub_swaps: list[dict] = []

    if latest_sub is not None:
        sched_codes = json.loads(latest_sub.selected_offerings_json or "[]")
        if sched_codes:
            sub_offerings = list(
                db.scalars(
                    select(SectionOffering)
                    .where(SectionOffering.schedule_code.in_(sched_codes))
                    .options(
                        selectinload(SectionOffering.course),
                        selectinload(SectionOffering.meetings),
                    )
                ).all()
            )
            sub_offerings.sort(key=lambda o: (o.course.year_level, o.course.display_order))
        sub_conflicts = json.loads(latest_sub.conflict_logs_json or "[]")
        sub_swaps = json.loads(latest_sub.swap_history_json or "[]")

    ctx = portal_context(
        request,
        db,
        user,
        f"Advising Review - {student.formal_name}",
        active_nav="adviser",
    )
    ctx.update(
        {
            "student": student,
            "eligibility": eligibility,
            "locked_courses": locked_courses,
            "failed_courses": failed_courses,
            "overridden_courses": overridden_courses,
            "completed_count": completed_count,
            "overrides": overrides,
            "submissions": submissions,
            "latest_sub": latest_sub,
            "sub_offerings": sub_offerings,
            "sub_conflicts": sub_conflicts,
            "sub_swaps": sub_swaps,
        }
    )
    return templates.TemplateResponse(request, "adviser/student_review.html", ctx)


@router.post("/student/{student_id}/override")
def create_prerequisite_override(
    student_id: int,
    request: Request,
    course_id: int = Form(...),
    reason: str = Form(...),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    redir = _require_adviser_page(request, user)
    if redir:
        return redir
    assert user is not None

    student = db.get(User, student_id)
    course = db.get(Course, course_id)
    if student is None or course is None:
        add_flash(request, "Invalid student or course selected.", "danger")
        return RedirectResponse(url="/adviser", status_code=303)

    clean_reason = reason.strip()
    if not clean_reason:
        add_flash(request, "Please provide a justification reason for the manual override.", "warning")
        return RedirectResponse(url=f"/adviser/student/{student_id}", status_code=303)

    existing = db.scalar(
        select(PrerequisiteOverride).where(
            PrerequisiteOverride.student_id == student.id,
            PrerequisiteOverride.course_id == course.id,
        )
    )
    if existing is not None:
        existing.reason = clean_reason
        existing.adviser_id = user.id
    else:
        db.add(
            PrerequisiteOverride(
                student_id=student.id,
                course_id=course.id,
                adviser_id=user.id,
                reason=clean_reason,
            )
        )
    db.commit()

    add_flash(
        request,
        f"Manual constraint override granted for {course.code} ({course.title}). "
        "The course is now unlocked in the student's AI Enrollment Scheduler.",
        "success",
    )
    return RedirectResponse(url=f"/adviser/student/{student_id}", status_code=303)


@router.post("/override/{override_id}/delete")
def revoke_prerequisite_override(
    override_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    redir = _require_adviser_page(request, user)
    if redir:
        return redir
    assert user is not None

    override = db.get(PrerequisiteOverride, override_id)
    if override is None:
        add_flash(request, "Override record not found.", "warning")
        return RedirectResponse(url="/adviser", status_code=303)

    student_id = override.student_id
    db.delete(override)
    db.commit()
    add_flash(request, "Manual prerequisite override has been revoked.", "info")
    return RedirectResponse(url=f"/adviser/student/{student_id}", status_code=303)


@router.post("/submission/{submission_id}/decision")
def decide_submission(
    submission_id: int,
    request: Request,
    decision: str = Form(...),
    adviser_notes: str = Form(""),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    redir = _require_adviser_page(request, user)
    if redir:
        return redir
    assert user is not None

    submission = db.get(ScheduleSubmission, submission_id)
    if submission is None:
        add_flash(request, "Schedule submission not found.", "danger")
        return RedirectResponse(url="/adviser", status_code=303)

    student = db.get(User, submission.student_id)
    if student is None:
        add_flash(request, "Student record not found.", "danger")
        return RedirectResponse(url="/adviser", status_code=303)

    clean_decision = decision.strip().upper()
    submission.adviser_notes = adviser_notes.strip()
    submission.reviewed_by_id = user.id
    submission.reviewed_at = datetime.now(timezone.utc)

    if clean_decision == "APPROVED":
        submission.status = "APPROVED"
        sched_codes = json.loads(submission.selected_offerings_json or "[]")
        offerings = list(
            db.scalars(
                select(SectionOffering).where(SectionOffering.schedule_code.in_(sched_codes))
            ).all()
        )

        # Replace current semester enrollments with the adviser-approved schedule
        db.execute(
            delete(CurrentEnrollment).where(
                CurrentEnrollment.student_id == student.id,
                CurrentEnrollment.academic_year == CURRENT_ACADEMIC_YEAR,
                CurrentEnrollment.semester == CURRENT_SEMESTER,
            )
        )
        for off in offerings:
            db.add(
                CurrentEnrollment(
                    student_id=student.id,
                    offering_id=off.id,
                    academic_year=CURRENT_ACADEMIC_YEAR,
                    semester=CURRENT_SEMESTER,
                )
            )
        student.enrollment_status = "Enrolled"
        db.commit()
        add_flash(
            request,
            f"Schedule approved and signed off for {student.formal_name}. "
            f"{len(offerings)} subjects have been enrolled into Current Subjects.",
            "success",
        )
    elif clean_decision == "REVISION_REQUESTED":
        submission.status = "REVISION_REQUESTED"
        student.enrollment_status = "Revision Requested"
        db.commit()
        add_flash(
            request,
            f"Revision requested for {student.formal_name}. Adviser notes have been sent back to Pre-Registration.",
            "warning",
        )
    else:
        add_flash(request, "Unsupported decision value.", "danger")

    return RedirectResponse(url=f"/adviser/student/{student.id}", status_code=303)
