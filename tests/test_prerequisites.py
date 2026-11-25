"""Unit tests for the Automated BSCS Prerequisite Validation DAG Module."""

from __future__ import annotations

from sqlalchemy import select

from app.models import Course, PrerequisiteOverride, User
from app.services.prerequisite_engine import (
    evaluate_student_prerequisites,
    validate_requested_courses,
)


def test_failed_prerequisites_lock_dependent_courses(db_session):
    """Miguel failed MATH 2A & COSC 70A -> MATH 3A and COSC 75A must be LOCKED."""
    miguel = db_session.scalar(select(User).where(User.student_number == "202410101"))
    assert miguel is not None

    items = evaluate_student_prerequisites(db_session, miguel)
    assert len(items) == 57
    by_code = {i.code: i for i in items}

    # Retakes themselves remain ELIGIBLE because their own prerequisites were passed
    assert by_code["MATH 2A"].transcript_status == "FAILED"
    assert by_code["MATH 2A"].eligibility == "ELIGIBLE"
    assert by_code["COSC 70A"].transcript_status == "FAILED"
    assert by_code["COSC 70A"].eligibility == "ELIGIBLE"

    # Dependent courses must be LOCKED with exact missing prereqs
    assert by_code["MATH 3A"].eligibility == "LOCKED"
    assert by_code["MATH 3A"].missing_prerequisites == ["MATH 2A"]

    assert by_code["COSC 75A"].eligibility == "LOCKED"
    assert by_code["COSC 75A"].missing_prerequisites == ["COSC 70A"]

    # Independent 3rd-year courses whose prerequisites were passed must be ELIGIBLE
    assert by_code["COSC 80B"].eligibility == "ELIGIBLE"
    assert by_code["COSC 85A"].eligibility == "ELIGIBLE"
    assert by_code["DCIT 26A"].eligibility == "ELIGIBLE"

    valid, conflicts = validate_requested_courses(items, ["MATH 3A", "COSC 75A", "COSC 80B"])
    assert valid == ["COSC 80B"]
    assert len(conflicts) == 2
    assert all(c.conflict_type == "PREREQUISITE_UNMET" for c in conflicts)


def test_credited_courses_satisfy_prerequisites_for_transferee(db_session):
    """Paolo's credited subjects count as COMPLETED and unlock downstream subjects."""
    paolo = db_session.scalar(select(User).where(User.student_number == "202410308"))
    assert paolo is not None

    items = evaluate_student_prerequisites(db_session, paolo)
    by_code = {i.code: i for i in items}

    assert by_code["GNED 03"].transcript_status == "CREDITED"
    assert by_code["GNED 03"].eligibility == "COMPLETED"
    # MATH 1A requires GNED 03 -> must be ELIGIBLE
    assert by_code["MATH 1A"].eligibility == "ELIGIBLE"
    # FITT 3 requires FITT 1 (credited) -> must be ELIGIBLE
    assert by_code["FITT 3"].eligibility == "ELIGIBLE"
    # COSC 105 requires MATH 4B, COSC 55A, and DCIT 50A -> must be LOCKED with all 3 missing
    assert by_code["COSC 105"].eligibility == "LOCKED"
    assert set(by_code["COSC 105"].missing_prerequisites) == {"MATH 4B", "COSC 55A", "DCIT 50A"}
    # COSC 200-A requires all 1st-3rd year CS majors + COSC 199B Practicum -> must be LOCKED
    assert by_code["COSC 200-A"].eligibility == "LOCKED"
    assert {"COSC 199B", "DCIT 60B", "COSC 90"}.issubset(set(by_code["COSC 200-A"].missing_prerequisites))


def test_adviser_manual_override_unlocks_locked_course(db_session):
    """An Adviser PrerequisiteOverride transitions a LOCKED course to OVERRIDDEN and enrollable."""
    miguel = db_session.scalar(select(User).where(User.student_number == "202410101"))
    adviser = db_session.scalar(select(User).where(User.student_number == "ADV202601"))
    cosc75 = db_session.scalar(select(Course).where(Course.code == "COSC 75A"))
    assert miguel and adviser and cosc75

    db_session.add(
        PrerequisiteOverride(
            student_id=miguel.id,
            course_id=cosc75.id,
            adviser_id=adviser.id,
            reason="Concurrent enrollment approved by DCS Chairperson.",
        )
    )
    db_session.commit()

    items = evaluate_student_prerequisites(db_session, miguel)
    by_code = {i.code: i for i in items}
    assert by_code["COSC 75A"].eligibility == "OVERRIDDEN"
    assert by_code["COSC 75A"].override_reason == "Concurrent enrollment approved by DCS Chairperson."

    valid, conflicts = validate_requested_courses(items, ["COSC 75A", "COSC 80B"])
    assert set(valid) == {"COSC 75A", "COSC 80B"}
    assert conflicts == []
