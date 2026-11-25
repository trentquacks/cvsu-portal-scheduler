"""Unit tests for the Conflict Report Log Diagnostics & Dynamic Section-Swapping Engine."""

from __future__ import annotations

import json
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import CURRENT_ACADEMIC_YEAR, CURRENT_SEMESTER
from app.models import AvailabilityMatrix, SectionOffering, User
from app.services.snapshot_loader import build_availability_matrix
from app.services.swap_engine import (
    diagnose_conflicts,
    find_dynamic_swaps,
    find_minimal_matrix_relaxation,
)


def _offerings_map(db_session, codes: list[str]) -> dict[str, list[SectionOffering]]:
    offs = list(
        db_session.scalars(
            select(SectionOffering)
            .where(
                SectionOffering.academic_year == CURRENT_ACADEMIC_YEAR,
                SectionOffering.semester == CURRENT_SEMESTER,
            )
            .options(selectinload(SectionOffering.course), selectinload(SectionOffering.meetings))
        ).all()
    )
    grouped: dict[str, list[SectionOffering]] = defaultdict(list)
    for o in offs:
        if o.course.code in codes:
            grouped[o.course.code].append(o)
    return dict(grouped)


def test_overlapping_pins_trigger_conflict_log_and_minimal_swaps(db_session):
    """Pinning overlapping Monday/Wednesday sections logs TIME_OVERLAP and finds minimal swaps."""
    miguel = db_session.scalar(select(User).where(User.student_number == "202410101"))
    matrix = json.loads(
        db_session.scalar(
            select(AvailabilityMatrix.matrix_json).where(AvailabilityMatrix.student_id == miguel.id)
        )
    )

    courses = ["MATH 2A", "COSC 70A", "COSC 80B", "COSC 85A", "COSC 101", "DCIT 26A", "DCIT 65A"]
    grouped = _offerings_map(db_session, courses)
    pinned = {
        "MATH 2A": "202610253",   # M 14-16 clashes with COSC 80B BSCS-3A (M 13-15)
        "COSC 80B": "202610603",  # W 13-16 clashes with COSC 101 BSCS-3B (W 13-15)
        "COSC 101": "202610625",
    }

    logs, reasons = diagnose_conflicts(grouped, matrix, pinned)
    overlap_logs = [c for c in logs if c.conflict_type == "TIME_OVERLAP"]
    assert len(overlap_logs) >= 2

    swaps = find_dynamic_swaps(grouped, matrix, pinned, reasons, max_recommendations=3)
    assert len(swaps) >= 1
    # Minimum-deviation swap should only need to swap 1 course (COSC 80B resolves BOTH overlaps!)
    assert swaps[0].swap_count == 1
    assert swaps[0].actions[0].course_code == "COSC 80B"


def test_closed_and_blocked_pins_resolved_by_dynamic_swapping(db_session):
    """Clarisse pinning Closed COSC 75A BSCS-3A & Blocked Morning COSC 85A BSCS-3A -> diagnosed & swapped."""
    clarisse = db_session.scalar(select(User).where(User.student_number == "202310205"))
    matrix = json.loads(
        db_session.scalar(
            select(AvailabilityMatrix.matrix_json).where(AvailabilityMatrix.student_id == clarisse.id)
        )
    )

    courses = ["MATH 3A", "COSC 75A", "COSC 80B", "COSC 85A", "COSC 101", "DCIT 26A", "DCIT 65A"]
    grouped = _offerings_map(db_session, courses)
    pinned = {
        "COSC 75A": "202610602",  # Closed BSCS-3A
        "COSC 85A": "202610604",  # Blocked morning T 8-10 / TH 8-11
    }

    logs, reasons = diagnose_conflicts(grouped, matrix, pinned)
    log_types = {c.conflict_type for c in logs}
    assert "CAPACITY_FULL" in log_types
    assert "BLOCKED_TIME_SLOT" in log_types

    swaps = find_dynamic_swaps(grouped, matrix, pinned, reasons, max_recommendations=3)
    assert len(swaps) >= 1
    swapped_codes = {a.course_code for a in swaps[0].actions}
    assert swapped_codes == {"COSC 75A", "COSC 85A"}


def test_deadlock_triggers_minimal_slot_relaxation_suggestion(db_session):
    """Blocking all hours of a single-section course yields a minimal unblock suggestion."""
    grouped = _offerings_map(db_session, ["ITEC 80D"])  # Only offered M 9-10 (1 slot!)
    strict_matrix = build_availability_matrix({"M": [7, 8, 9, 10, 11, 12]})

    relaxation = find_minimal_matrix_relaxation(grouped, strict_matrix)
    assert relaxation is not None
    assert len(relaxation.slots_to_unblock) == 1
    assert relaxation.slots_to_unblock[0]["day"] == "M"
    assert relaxation.slots_to_unblock[0]["hour"] == 9
