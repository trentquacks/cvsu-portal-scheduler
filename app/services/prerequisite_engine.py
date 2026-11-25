"""Automated Prerequisite Validation Module (BSCS Directed Acyclic Graph)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import CURRENT_ACADEMIC_YEAR, CURRENT_SEMESTER
from app.models import (
    Course,
    CoursePrerequisite,
    PrerequisiteOverride,
    SectionOffering,
    StudentTranscript,
    User,
)
from app.schemas.scheduler import ConflictLogItem, CourseEligibilityItem

COMPLETED_STATUSES = {"PASSED", "CREDITED"}


def evaluate_student_prerequisites(db: Session, student: User) -> list[CourseEligibilityItem]:
    """Cross-reference student transcript + adviser overrides against the BSCS prerequisite DAG."""
    courses = list(
        db.scalars(
            select(Course)
            .options(
                selectinload(Course.prerequisite_links).selectinload(CoursePrerequisite.prerequisite)
            )
            .order_by(Course.display_order.asc())
        ).all()
    )

    transcripts = {
        row.course_id: row
        for row in db.scalars(
            select(StudentTranscript).where(StudentTranscript.student_id == student.id)
        ).all()
    }

    overrides = {
        row.course_id: row
        for row in db.scalars(
            select(PrerequisiteOverride).where(PrerequisiteOverride.student_id == student.id)
        ).all()
    }

    offerings = list(
        db.scalars(
            select(SectionOffering).where(
                SectionOffering.academic_year == CURRENT_ACADEMIC_YEAR,
                SectionOffering.semester == CURRENT_SEMESTER,
            )
        ).all()
    )
    offerings_count: dict[int, int] = {}
    open_offerings_count: dict[int, int] = {}
    for off in offerings:
        offerings_count[off.course_id] = offerings_count.get(off.course_id, 0) + 1
        if off.is_open:
            open_offerings_count[off.course_id] = open_offerings_count.get(off.course_id, 0) + 1

    completed_course_ids = {
        cid for cid, tr in transcripts.items() if tr.status in COMPLETED_STATUSES
    }

    results: list[CourseEligibilityItem] = []
    for course in courses:
        tr = transcripts.get(course.id)
        tr_status = tr.status if tr is not None else "NOT_TAKEN"
        grade = tr.grade if tr is not None else "-"

        prereq_courses = [link.prerequisite for link in course.prerequisite_links if link.prerequisite is not None]
        prereq_codes = [p.code for p in prereq_courses]
        missing_codes = [p.code for p in prereq_courses if p.id not in completed_course_ids]

        override = overrides.get(course.id)
        override_reason: str | None = None

        if tr_status in COMPLETED_STATUSES:
            eligibility = "COMPLETED"
            missing_codes = []
        elif not missing_codes:
            eligibility = "ELIGIBLE"
        elif override is not None:
            eligibility = "OVERRIDDEN"
            override_reason = override.reason
        else:
            eligibility = "LOCKED"

        results.append(
            CourseEligibilityItem(
                course_id=course.id,
                code=course.code,
                title=course.title,
                lec_units=course.lec_units,
                lab_units=course.lab_units,
                total_units=course.total_units,
                year_level=course.year_level,
                semester=course.semester,
                major=course.major,
                transcript_status=tr_status,
                grade=grade,
                eligibility=eligibility,
                prerequisites=prereq_codes,
                missing_prerequisites=missing_codes,
                override_reason=override_reason,
                offered_this_sem=offerings_count.get(course.id, 0) > 0,
                open_offerings_count=open_offerings_count.get(course.id, 0),
            )
        )

    return results


def validate_requested_courses(
    eligibility_items: list[CourseEligibilityItem],
    requested_codes: list[str],
) -> tuple[list[str], list[ConflictLogItem]]:
    """Separate enrollable courses from prerequisite-locked or already-completed requests."""
    by_code = {item.code: item for item in eligibility_items}
    valid_codes: list[str] = []
    conflicts: list[ConflictLogItem] = []
    seen: set[str] = set()

    for code in requested_codes:
        clean_code = code.strip().upper()
        if clean_code in seen:
            continue
        seen.add(clean_code)

        item = by_code.get(clean_code)
        if item is None:
            conflicts.append(
                ConflictLogItem(
                    conflict_type="NO_OFFERING",
                    severity="ERROR",
                    course_codes=[clean_code],
                    message=f"Course '{clean_code}' does not exist in the official BSCS curriculum.",
                )
            )
            continue

        if item.eligibility == "COMPLETED":
            conflicts.append(
                ConflictLogItem(
                    conflict_type="PREREQUISITE_UNMET",
                    severity="WARNING",
                    course_codes=[item.code],
                    message=f"{item.code} ({item.title}) is already completed ({item.transcript_status}, Grade: {item.grade}).",
                )
            )
            continue

        if item.eligibility == "LOCKED":
            missing_str = ", ".join(item.missing_prerequisites)
            conflicts.append(
                ConflictLogItem(
                    conflict_type="PREREQUISITE_UNMET",
                    severity="ERROR",
                    course_codes=[item.code],
                    message=(
                        f"{item.code} ({item.title}) is locked: missing required prerequisite(s) {missing_str}. "
                        "Complete the prerequisite(s) or request an Academic Adviser manual override."
                    ),
                )
            )
            continue

        valid_codes.append(item.code)

    return valid_codes, conflicts
