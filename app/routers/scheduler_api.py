"""REST JSON API for the AI-Driven Irregular Student Enrollment Scheduler."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import CURRENT_ACADEMIC_YEAR, CURRENT_SEMESTER, MAX_UNITS_DEFAULT
from app.database import get_db
from app.models import (
    AvailabilityMatrix,
    Course,
    PrerequisiteOverride,
    ScheduleSubmission,
    SectionOffering,
    StudentTranscript,
    User,
)
from app.routers.deps import require_user
from app.schemas.scheduler import (
    AvailabilityMatrixPayload,
    ConflictLogItem,
    SolveRequest,
    SolveResponse,
    SubmitScheduleRequest,
    SubmitScheduleResponse,
    TranscriptUpdateRequest,
)
from app.services.csp_solver import (
    compute_schedule_metrics,
    serialize_offering,
    solve_schedule_csp,
)
from app.services.pdf_exporter import generate_master_schedule_pdf
from app.services.prerequisite_engine import (
    evaluate_student_prerequisites,
    validate_requested_courses,
)
from app.services.snapshot_loader import build_availability_matrix, reset_student_demo_state
from app.services.swap_engine import (
    diagnose_conflicts,
    find_dynamic_swaps,
    find_minimal_matrix_relaxation,
)

router = APIRouter(prefix="/api/scheduler", tags=["scheduler-api"])


def _get_student_matrix(db: Session, student: User) -> dict[str, list[int]]:
    row = db.scalar(select(AvailabilityMatrix).where(AvailabilityMatrix.student_id == student.id))
    if row is None:
        return build_availability_matrix()
    return json.loads(row.matrix_json)


def _load_offerings_grouped(db: Session) -> dict[str, list[SectionOffering]]:
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
    grouped: dict[str, list[SectionOffering]] = defaultdict(list)
    for off in offerings:
        grouped[off.course.code].append(off)
    return dict(grouped)


def _build_demo_conflict_preset(student_number: str) -> dict:
    """Provide a deterministic conflict preset per demo persona for thesis presentations."""
    if student_number == "202310205":  # Clarisse (Working Student - Mornings blocked)
        return {
            "label": "Working Student Clash + Closed Section Demo",
            "description": (
                "Selects 3rd-Year subjects with COSC 75A BSCS-3A (Closed) and COSC 85A BSCS-3A "
                "(Weekday Morning - Blocked) pinned to demonstrate conflict diagnostics & instant swapping."
            ),
            "course_codes": ["MATH 3A", "COSC 75A", "COSC 80B", "COSC 85A", "COSC 101", "DCIT 26A", "DCIT 65A"],
            "pinned_offerings": {
                "COSC 75A": "202610602",  # Closed BSCS-3A
                "COSC 85A": "202610604",  # Blocked Morning T 8-10 / TH 8-11
            },
        }
    if student_number == "202410308":  # Paolo (Transferee / Shiftee)
        return {
            "label": "Cross-Year Overlap + Closed Section Demo",
            "description": (
                "Selects mixed 2nd-Year CS majors with DCIT 50A BSCS-2A (Closed) and overlapping "
                "MATH 1A / COSC 60B sections to demonstrate automated swap resolution."
            ),
            "course_codes": ["MATH 1A", "COSC 55A", "COSC 60B", "DCIT 24A", "DCIT 50A", "INSY 50"],
            "pinned_offerings": {
                "DCIT 50A": "202610205",  # Closed BSCS-2A
                "MATH 1A": "202610202",   # T 8-10 / TH 8-9
                "COSC 55A": "202610203",  # M 10-12 / W 10-11
            },
        }
    # Default: Miguel (202410101) — Irregular 3rd Year retaking failed MATH 2A & COSC 70A
    return {
        "label": "Retake + 3rd-Year Overlap Demo",
        "description": (
            "Selects retakes (MATH 2A, COSC 70A) plus eligible 3rd-Year majors with colliding Monday & "
            "Wednesday sections pinned so the Dynamic Section-Swapping Engine resolves all clashes."
        ),
        "course_codes": ["MATH 2A", "COSC 70A", "COSC 80B", "COSC 85A", "COSC 101", "DCIT 26A", "DCIT 65A"],
        "pinned_offerings": {
            "MATH 2A": "202610253",   # M 14-16 / TH 11-12 (overlaps COSC 80B BSCS-3A on M 14-15)
            "COSC 80B": "202610603",  # M 13-15 / W 13-16 (overlaps COSC 101 BSCS-3B on W 13-15)
            "COSC 101": "202610625",  # W 13-15 / F 14-17
        },
    }


@router.get("/state")
def get_scheduler_state(
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    """Return full workspace state: prerequisite DAG results, saved matrix, offerings, and submission."""
    eligibility = evaluate_student_prerequisites(db, user)
    matrix = _get_student_matrix(db, user)
    grouped_offerings = _load_offerings_grouped(db)

    serialized_offerings = {
        code: [serialize_offering(o).model_dump() for o in offs]
        for code, offs in grouped_offerings.items()
    }

    latest_sub = db.scalar(
        select(ScheduleSubmission)
        .where(ScheduleSubmission.student_id == user.id)
        .order_by(ScheduleSubmission.submitted_at.desc())
    )
    sub_payload = None
    if latest_sub is not None:
        sched_codes = json.loads(latest_sub.selected_offerings_json or "[]")
        sub_offerings = list(
            db.scalars(
                select(SectionOffering)
                .where(SectionOffering.schedule_code.in_(sched_codes))
                .options(
                    selectinload(SectionOffering.course),
                    selectinload(SectionOffering.meetings),
                )
            ).all()
        ) if sched_codes else []
        sub_payload = {
            "id": latest_sub.id,
            "status": latest_sub.status,
            "total_units": latest_sub.total_units,
            "solver_time_ms": latest_sub.solver_time_ms,
            "idle_gap_hours": latest_sub.idle_gap_hours,
            "adviser_notes": latest_sub.adviser_notes,
            "submitted_at": latest_sub.submitted_at.strftime("%B %d, %Y %I:%M %p"),
            "reviewed_at": latest_sub.reviewed_at.strftime("%B %d, %Y %I:%M %p") if latest_sub.reviewed_at else None,
            "offerings": [serialize_offering(o).model_dump() for o in sub_offerings],
        }

    overrides = list(
        db.scalars(
            select(PrerequisiteOverride)
            .where(PrerequisiteOverride.student_id == user.id)
            .options(selectinload(PrerequisiteOverride.course))
        ).all()
    )

    return {
        "student": {
            "id": user.id,
            "student_number": user.student_number,
            "formal_name": user.formal_name,
            "student_type": user.student_type,
            "year_level": user.year_level,
            "enrollment_status": user.enrollment_status,
            "scenario_label": user.scenario_label,
            "scenario_summary": user.scenario_summary,
        },
        "academic_year": CURRENT_ACADEMIC_YEAR,
        "semester": CURRENT_SEMESTER,
        "max_units_default": MAX_UNITS_DEFAULT,
        "eligibility": [item.model_dump() for item in eligibility],
        "availability_matrix": matrix,
        "offerings_by_course": serialized_offerings,
        "latest_submission": sub_payload,
        "overrides": [
            {
                "id": ov.id,
                "course_code": ov.course.code,
                "course_title": ov.course.title,
                "reason": ov.reason,
            }
            for ov in overrides
        ],
        "demo_conflict_preset": _build_demo_conflict_preset(user.student_number),
    }


@router.post("/availability")
def save_availability_matrix(
    payload: AvailabilityMatrixPayload,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    """Persist the student's Mon-Sat 7:00 AM-8:00 PM binary availability matrix."""
    row = db.scalar(select(AvailabilityMatrix).where(AvailabilityMatrix.student_id == user.id))
    serialized = json.dumps(payload.matrix)
    if row is None:
        db.add(AvailabilityMatrix(student_id=user.id, matrix_json=serialized))
    else:
        row.matrix_json = serialized
        row.updated_at = datetime.now(timezone.utc)
    db.commit()

    available_hours = sum(sum(slots) for slots in payload.matrix.values())
    blocked_hours = 78 - available_hours
    return {
        "saved": True,
        "available_hours": available_hours,
        "blocked_hours": blocked_hours,
        "matrix": payload.matrix,
    }


@router.post("/transcript/update")
def update_transcript(
    payload: TranscriptUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    """Allow interactive transcript simulation (e.g., passing/failing prerequisites) and re-run DAG validation."""
    courses_by_code = {c.code: c for c in db.scalars(select(Course)).all()}
    existing_by_course_id = {
        tr.course_id: tr
        for tr in db.scalars(
            select(StudentTranscript).where(StudentTranscript.student_id == user.id)
        ).all()
    }

    for item in payload.updates:
        course = courses_by_code.get(item.course_code.strip().upper())
        if course is None:
            continue
        existing = existing_by_course_id.get(course.id)
        default_grade = item.grade
        if default_grade == "-" or not default_grade:
            default_grade = (
                "1.75"
                if item.status in ("PASSED", "CREDITED")
                else ("5.00" if item.status == "FAILED" else "-")
            )

        if item.status == "NOT_TAKEN":
            if existing is not None:
                db.delete(existing)
        elif existing is None:
            db.add(
                StudentTranscript(
                    student_id=user.id,
                    course_id=course.id,
                    academic_year="2025-2026",
                    semester=course.semester,
                    section_name="CREDITED" if item.status == "CREDITED" else "BSCS-SIM",
                    schedule_code="SIM-001",
                    grade=default_grade,
                    status=item.status,
                )
            )
        else:
            existing.status = item.status
            existing.grade = default_grade

    db.commit()
    refreshed = evaluate_student_prerequisites(db, user)
    return {"updated": True, "eligibility": [e.model_dump() for e in refreshed]}


@router.post("/transcript/reset")
def reset_transcript_and_matrix(
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    """Reset the student's transcript and availability matrix back to seeded persona defaults."""
    reset_student_demo_state(db, user)
    refreshed = evaluate_student_prerequisites(db, user)
    matrix = _get_student_matrix(db, user)
    return {
        "reset": True,
        "eligibility": [e.model_dump() for e in refreshed],
        "availability_matrix": matrix,
    }


@router.post("/solve", response_model=SolveResponse)
def solve_schedule(
    payload: SolveRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    """Run Automated Prerequisite Validation, OR-Tools CP-SAT Solver, Conflict Diagnostics, and Swap Engine."""
    eligibility = evaluate_student_prerequisites(db, user)
    elig_by_code = {e.code: e for e in eligibility}

    valid_codes, prereq_conflicts = validate_requested_courses(eligibility, payload.course_codes)
    total_units = sum(elig_by_code[c].total_units for c in valid_codes if c in elig_by_code)

    # If any requested course is locked by unmet prerequisites, report immediately in Conflict Log
    prereq_errors = [c for c in prereq_conflicts if c.severity == "ERROR"]
    if prereq_errors:
        return SolveResponse(
            feasible=False,
            solver_status="PREREQUISITE_BLOCKED",
            solver_time_ms=0.0,
            selected_courses_count=len(payload.course_codes),
            total_requested_units=total_units,
            max_units=payload.max_units,
            conflict_logs=prereq_conflicts,
            message=(
                f"{len(prereq_errors)} requested subject(s) failed automated prerequisite validation. "
                "Remove locked subjects or request an Academic Adviser manual override."
            ),
        )

    if not valid_codes:
        return SolveResponse(
            feasible=False,
            solver_status="INFEASIBLE",
            solver_time_ms=0.0,
            selected_courses_count=0,
            total_requested_units=0,
            max_units=payload.max_units,
            conflict_logs=prereq_conflicts,
            message="No eligible uncompleted courses were selected for scheduling.",
        )

    # Check maximum unit load cap
    if total_units > payload.max_units:
        unit_conflict = ConflictLogItem(
            conflict_type="UNIT_LIMIT",
            severity="ERROR",
            course_codes=valid_codes,
            message=(
                f"Selected load ({total_units} units) exceeds the maximum allowed unit limit "
                f"({payload.max_units} units)."
            ),
        )
        return SolveResponse(
            feasible=False,
            solver_status="UNIT_LIMIT_EXCEEDED",
            solver_time_ms=0.0,
            selected_courses_count=len(valid_codes),
            total_requested_units=total_units,
            max_units=payload.max_units,
            conflict_logs=[*prereq_conflicts, unit_conflict],
            message=unit_conflict.message,
        )

    # Resolve availability matrix (use inline payload if provided, else DB-saved matrix)
    if payload.availability_matrix is not None:
        matrix = AvailabilityMatrixPayload(matrix=payload.availability_matrix).matrix
    else:
        matrix = _get_student_matrix(db, user)

    all_grouped = _load_offerings_grouped(db)
    target_offerings = {code: all_grouped.get(code, []) for code in valid_codes}
    clean_pins = {
        k.strip().upper(): v.strip()
        for k, v in payload.pinned_offerings.items()
        if k.strip().upper() in target_offerings and v.strip()
    }

    # Run OR-Tools CP-SAT Solver
    options, solver_time_ms, solver_status = solve_schedule_csp(
        offerings_by_course=target_offerings,
        availability_matrix=matrix,
        pinned_offerings=clean_pins,
        max_solutions=payload.max_solutions,
    )

    if options:
        return SolveResponse(
            feasible=True,
            solver_status=solver_status,
            solver_time_ms=solver_time_ms,
            selected_courses_count=len(valid_codes),
            total_requested_units=total_units,
            max_units=payload.max_units,
            options=options,
            conflict_logs=prereq_conflicts,
            message=(
                f"Generated {len(options)} conflict-free master schedule option(s) in {solver_time_ms:.2f} ms "
                f"(0 overlaps, {options[0].idle_gap_hours} hr(s) idle gap)."
            ),
        )

    # Infeasible: run Conflict Report Log diagnostics + Dynamic Section-Swapping Engine
    diag_logs, pin_reasons = diagnose_conflicts(
        offerings_by_course=target_offerings,
        availability_matrix=matrix,
        pinned_offerings=clean_pins,
    )
    all_logs = [*prereq_conflicts, *diag_logs]

    swap_recs = (
        find_dynamic_swaps(
            offerings_by_course=target_offerings,
            availability_matrix=matrix,
            pinned_offerings=clean_pins,
            pin_reasons=pin_reasons,
            max_recommendations=3,
        )
        if clean_pins
        else []
    )

    relaxation = None
    if not swap_recs:
        relaxation = find_minimal_matrix_relaxation(
            offerings_by_course=target_offerings,
            availability_matrix=matrix,
        )

    if swap_recs:
        msg = (
            f"Detected {len(diag_logs)} scheduling conflict(s) in pinned sections. "
            f"Dynamic Section-Swapping Engine found {len(swap_recs)} conflict-free swap solution(s)."
        )
    elif relaxation is not None:
        msg = (
            "No conflict-free schedule fits within your current blocked time slots. "
            "See the minimal slot-unblocking recommendation below."
        )
    else:
        msg = "No feasible schedule could be generated for the selected combination. Review the Conflict Report Log."

    return SolveResponse(
        feasible=False,
        solver_status="INFEASIBLE",
        solver_time_ms=solver_time_ms,
        selected_courses_count=len(valid_codes),
        total_requested_units=total_units,
        max_units=payload.max_units,
        options=[],
        conflict_logs=all_logs,
        swap_recommendations=swap_recs,
        relaxation_suggestion=relaxation,
        message=msg,
    )


@router.post("/submit", response_model=SubmitScheduleResponse)
def submit_schedule_for_advising(
    payload: SubmitScheduleRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    """Submit a verified conflict-free master schedule for Academic/Registration Adviser sign-off."""
    offerings = list(
        db.scalars(
            select(SectionOffering)
            .where(SectionOffering.schedule_code.in_(payload.schedule_codes))
            .options(
                selectinload(SectionOffering.course),
                selectinload(SectionOffering.meetings),
            )
        ).all()
    )
    if len(offerings) != len(set(payload.schedule_codes)):
        raise HTTPException(status_code=400, detail="One or more schedule codes could not be found.")

    # Server-side integrity check: zero overlap across submitted sections
    seen_slots: dict[tuple[str, int], str] = {}
    for off in offerings:
        for m in off.meetings:
            for h in range(m.start_hour, m.end_hour):
                slot = (m.day, h)
                if slot in seen_slots:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Schedule conflict detected between {seen_slots[slot]} and {off.course.code}.",
                    )
                seen_slots[slot] = off.course.code

    total_units = sum(o.course.total_units for o in offerings)
    idle_gaps, _ = compute_schedule_metrics(offerings)

    submission = ScheduleSubmission(
        student_id=user.id,
        academic_year=CURRENT_ACADEMIC_YEAR,
        semester=CURRENT_SEMESTER,
        status="PENDING_ADVISING",
        total_units=total_units,
        solver_time_ms=payload.solver_time_ms,
        idle_gap_hours=idle_gaps,
        selected_offerings_json=json.dumps([o.schedule_code for o in offerings]),
        conflict_logs_json=json.dumps(payload.conflict_logs),
        swap_history_json=json.dumps(payload.swap_history),
        submitted_at=datetime.now(timezone.utc),
    )
    db.add(submission)
    user.enrollment_status = "Pending Advising"
    db.commit()
    db.refresh(submission)

    return SubmitScheduleResponse(
        submission_id=submission.id,
        status=submission.status,
        total_units=total_units,
        message=(
            f"Master Schedule ({len(offerings)} subjects, {total_units} units) submitted to your "
            "Department Registration Adviser for verification and sign-off."
        ),
    )


@router.get("/export-pdf")
def export_master_schedule_pdf(
    schedule_codes: str = Query(default=""),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    """Export the generated or submitted conflict-free master schedule as a printable PDF."""
    codes = [c.strip() for c in schedule_codes.split(",") if c.strip()]
    submission = None

    if not codes:
        submission = db.scalar(
            select(ScheduleSubmission)
            .where(ScheduleSubmission.student_id == user.id)
            .order_by(ScheduleSubmission.submitted_at.desc())
        )
        if submission is not None:
            codes = json.loads(submission.selected_offerings_json or "[]")

    if not codes:
        raise HTTPException(status_code=404, detail="No schedule selected or submitted to export.")

    offerings = list(
        db.scalars(
            select(SectionOffering)
            .where(SectionOffering.schedule_code.in_(codes))
            .options(
                selectinload(SectionOffering.course),
                selectinload(SectionOffering.meetings),
            )
        ).all()
    )
    offerings.sort(key=lambda o: (o.course.year_level, o.course.display_order))

    pdf_bytes = generate_master_schedule_pdf(
        student=user,
        offerings=offerings,
        academic_year=CURRENT_ACADEMIC_YEAR,
        semester=CURRENT_SEMESTER,
        submission=submission,
    )
    filename = f"CvSU_MasterSchedule_{user.student_number}_{CURRENT_ACADEMIC_YEAR}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
