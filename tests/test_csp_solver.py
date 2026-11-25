"""Unit tests for the Google OR-Tools CP-SAT Overlap Detection & Optimization Engine."""

from __future__ import annotations

import json
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import CURRENT_ACADEMIC_YEAR, CURRENT_SEMESTER
from app.models import AvailabilityMatrix, SectionOffering, User
from app.services.csp_solver import (
    blocked_slots_violated,
    offering_slots,
    solve_schedule_csp,
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


def test_working_student_strict_availability_and_zero_overlaps(db_session):
    """Clarisse (Mon-Fri 7AM-1PM blocked) gets conflict-free afternoon/evening/Sat schedules."""
    clarisse = db_session.scalar(select(User).where(User.student_number == "202310205"))
    mat_row = db_session.scalar(
        select(AvailabilityMatrix).where(AvailabilityMatrix.student_id == clarisse.id)
    )
    matrix = json.loads(mat_row.matrix_json)

    courses = ["MATH 3A", "COSC 75A", "COSC 80B", "COSC 85A", "COSC 101", "DCIT 26A", "DCIT 65A"]
    grouped = _offerings_map(db_session, courses)

    options, elapsed_ms, status = solve_schedule_csp(grouped, matrix, max_solutions=5)
    assert status == "OPTIMAL"
    assert len(options) >= 1
    assert elapsed_ms < 2000.0

    # Verify strict zero overlaps, open capacity, and zero blocked-matrix violations across every option
    by_sched = {o.schedule_code: o for offs in grouped.values() for o in offs}
    for opt in options:
        assert len(opt.offerings) == len(courses)
        assert opt.total_units == 21
        occupied_slots = set()
        for dto in opt.offerings:
            off = by_sched[dto.schedule_code]
            assert off.is_open is True
            assert off.schedule_code != "202610602"  # Closed COSC 75A BSCS-3A excluded
            assert blocked_slots_violated(off, matrix) == []
            for slot in offering_slots(off):
                assert slot not in occupied_slots, f"Overlap detected at {slot}"
                occupied_slots.add(slot)

    # First option must have minimal or equal idle gaps compared to subsequent ranked options
    if len(options) > 1:
        assert options[0].idle_gap_hours <= options[-1].idle_gap_hours


def test_irregular_retake_mix_produces_multiple_distinct_schedules(db_session):
    """Miguel retaking MATH 2A & COSC 70A alongside 3rd-year majors yields multiple distinct options."""
    miguel = db_session.scalar(select(User).where(User.student_number == "202410101"))
    mat_row = db_session.scalar(
        select(AvailabilityMatrix).where(AvailabilityMatrix.student_id == miguel.id)
    )
    matrix = json.loads(mat_row.matrix_json)

    courses = ["MATH 2A", "COSC 70A", "COSC 80B", "COSC 85A", "COSC 101", "DCIT 26A", "DCIT 65A"]
    grouped = _offerings_map(db_session, courses)

    options, _ms, status = solve_schedule_csp(grouped, matrix, max_solutions=5)
    assert status == "OPTIMAL"
    assert len(options) >= 3

    # Every option must be a distinct combination of schedule codes
    combos = {frozenset(o.schedule_code for o in opt.offerings) for opt in options}
    assert len(combos) == len(options)
