"""Constraint Satisfaction Problem (CSP) Overlap Detection & Optimization Engine using Google OR-Tools CP-SAT."""

from __future__ import annotations

import time
from collections import defaultdict

from ortools.sat.python import cp_model

from app.config import DAYS, END_HOUR, HOURS, START_HOUR
from app.models import SectionOffering
from app.schemas.scheduler import MeetingDTO, OfferingDTO, ScheduleOptionDTO


def serialize_offering(offering: SectionOffering) -> OfferingDTO:
    """Convert an ORM SectionOffering with its course and meetings into an OfferingDTO."""
    course = offering.course
    meetings = [
        MeetingDTO(
            meeting_type=m.meeting_type,
            day=m.day,
            start_hour=m.start_hour,
            end_hour=m.end_hour,
            room=m.room,
            time_range_24h=m.time_range_24h,
            portal_format=m.portal_format,
        )
        for m in offering.meetings
    ]
    return OfferingDTO(
        offering_id=offering.id,
        schedule_code=offering.schedule_code,
        course_code=course.code,
        course_title=course.title,
        lec_units=course.lec_units,
        lab_units=course.lab_units,
        total_units=course.total_units,
        section_name=offering.section_name,
        instructor=offering.instructor,
        max_capacity=offering.max_capacity,
        enrolled_count=offering.enrolled_count,
        seats_remaining=offering.seats_remaining,
        status=offering.status,
        is_open=offering.is_open,
        meetings=meetings,
    )


def offering_slots(offering: SectionOffering) -> list[tuple[str, int]]:
    """Return every (day, hour) 1-hour block occupied by all LEC and LAB meetings of an offering."""
    slots: list[tuple[str, int]] = []
    for meeting in offering.meetings:
        for h in range(meeting.start_hour, meeting.end_hour):
            slots.append((meeting.day, h))
    return slots


def blocked_slots_violated(
    offering: SectionOffering,
    availability_matrix: dict[str, list[int]],
) -> list[tuple[str, int]]:
    """Return any (day, hour) blocks where the offering collides with a 0 (Blocked) matrix cell."""
    violations: list[tuple[str, int]] = []
    for day, hour in offering_slots(offering):
        idx = hour - START_HOUR
        day_slots = availability_matrix.get(day)
        if day_slots is not None and 0 <= idx < len(day_slots) and day_slots[idx] == 0:
            violations.append((day, hour))
    return violations


def compute_schedule_metrics(offerings: list[SectionOffering]) -> tuple[int, int]:
    """Compute (total_idle_gap_hours, active_days_count) for a concrete schedule."""
    hours_by_day: dict[str, set[int]] = defaultdict(set)
    for off in offerings:
        for day, hour in offering_slots(off):
            hours_by_day[day].add(hour)

    idle_gap_hours = 0
    active_days = 0
    for day in DAYS:
        occupied = sorted(hours_by_day.get(day, set()))
        if occupied:
            active_days += 1
            span = occupied[-1] - occupied[0] + 1
            idle_gap_hours += max(0, span - len(occupied))
    return idle_gap_hours, active_days


def _add_gap_and_compactness_objective(
    model: cp_model.CpModel,
    x_vars: dict[int, cp_model.IntVar],
    slot_to_off_ids: dict[tuple[str, int], list[int]],
    extra_penalty_expr=None,
) -> None:
    """Attach soft-constraint objective minimizing daily idle gaps and total active school days."""
    gap_terms: list[cp_model.IntVar] = []
    active_day_terms: list[cp_model.IntVar] = []

    for day in DAYS:
        day_occ_exprs: dict[int, cp_model.LinearExpr] = {}
        day_total_terms: list[cp_model.IntVar] = []
        for hour in HOURS:
            off_ids = slot_to_off_ids.get((day, hour), [])
            if off_ids:
                occ = model.NewBoolVar(f"occ_{day}_{hour}")
                model.Add(occ == sum(x_vars[oid] for oid in off_ids))
                day_occ_exprs[hour] = occ
                day_total_terms.append(occ)

        if not day_total_terms:
            continue

        active_day = model.NewBoolVar(f"active_{day}")
        total_hours_day = model.NewIntVar(0, len(HOURS), f"tot_{day}")
        model.Add(total_hours_day == sum(day_total_terms))
        model.Add(total_hours_day >= 1).OnlyEnforceIf(active_day)
        model.Add(total_hours_day == 0).OnlyEnforceIf(active_day.Not())
        active_day_terms.append(active_day)

        first_h = model.NewIntVar(START_HOUR, END_HOUR, f"first_{day}")
        last_h = model.NewIntVar(START_HOUR - 1, END_HOUR - 1, f"last_{day}")

        for hour, occ in day_occ_exprs.items():
            model.Add(first_h <= hour).OnlyEnforceIf(occ)
            model.Add(last_h >= hour).OnlyEnforceIf(occ)

        # Anchor values when day is inactive so span stays 0
        model.Add(first_h == END_HOUR).OnlyEnforceIf(active_day.Not())
        model.Add(last_h == START_HOUR - 1).OnlyEnforceIf(active_day.Not())

        span = model.NewIntVar(0, len(HOURS), f"span_{day}")
        model.Add(span >= last_h - first_h + 1).OnlyEnforceIf(active_day)
        model.Add(span == 0).OnlyEnforceIf(active_day.Not())

        gap = model.NewIntVar(0, len(HOURS), f"gap_{day}")
        model.Add(gap == span - total_hours_day)
        gap_terms.append(gap)

    obj = 10 * sum(gap_terms) + 3 * sum(active_day_terms)
    if extra_penalty_expr is not None:
        obj = extra_penalty_expr + obj
    model.Minimize(obj)


def solve_schedule_csp(
    offerings_by_course: dict[str, list[SectionOffering]],
    availability_matrix: dict[str, list[int]],
    pinned_offerings: dict[str, str] | None = None,
    max_solutions: int = 5,
) -> tuple[list[ScheduleOptionDTO], float, str]:
    """
    Solve the multi-course BSCS irregular scheduling problem via OR-Tools CP-SAT.

    Enforces:
      - Exactly one open, availability-compliant section per requested course.
      - Zero time overlap across all paired LEC & LAB blocks (Mon-Sat, 7AM-8PM).
      - Optional pinned section restrictions (when evaluating user's explicit picks).
    Optimizes:
      - Minimizes daily idle gap hours and total active campus days.

    Returns:
      (ranked ScheduleOptionDTO list, total_solver_time_ms, status_label)
    """
    t0 = time.perf_counter()
    pinned = pinned_offerings or {}

    if not offerings_by_course:
        return [], 0.0, "INFEASIBLE"

    # Build filtered candidate pool per course
    valid_candidates: dict[str, list[SectionOffering]] = {}
    all_valid_by_id: dict[int, SectionOffering] = {}

    for course_code, offerings in offerings_by_course.items():
        pin_sched = pinned.get(course_code)
        filtered: list[SectionOffering] = []
        for off in offerings:
            if pin_sched and off.schedule_code != pin_sched:
                continue
            if not off.is_open:
                continue
            if blocked_slots_violated(off, availability_matrix):
                continue
            filtered.append(off)
            all_valid_by_id[off.id] = off

        if not filtered:
            elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            return [], elapsed_ms, "INFEASIBLE"
        valid_candidates[course_code] = filtered

    # Construct CP-SAT model
    model = cp_model.CpModel()
    x_vars: dict[int, cp_model.IntVar] = {}
    slot_to_off_ids: dict[tuple[str, int], list[int]] = defaultdict(list)

    for course_code, candidates in valid_candidates.items():
        course_vars: list[cp_model.IntVar] = []
        for off in candidates:
            var = model.NewBoolVar(f"x_{off.id}")
            x_vars[off.id] = var
            course_vars.append(var)
            for slot in set(offering_slots(off)):
                slot_to_off_ids[slot].append(off.id)

        # Hard Constraint 1: Exactly one section chosen for each requested course
        model.Add(sum(course_vars) == 1)

    # Hard Constraint 2: No time-slot overlaps across any day/hour block (LEC + LAB paired)
    for _slot, off_ids in slot_to_off_ids.items():
        if len(off_ids) > 1:
            model.Add(sum(x_vars[oid] for oid in off_ids) <= 1)

    # Soft Constraint Objective: Minimize idle gaps & compact school days
    _add_gap_and_compactness_objective(model, x_vars, slot_to_off_ids)

    options: list[ScheduleOptionDTO] = []
    first_status_str = "INFEASIBLE"

    for rank in range(1, max_solutions + 1):
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 3.0
        solver.parameters.num_search_workers = 1  # deterministic & minimal startup overhead for fast small models
        status = solver.Solve(model)

        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            break

        if rank == 1:
            first_status_str = "OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE"

        chosen_ids = [oid for oid, var in x_vars.items() if solver.Value(var) == 1]
        chosen_offerings = sorted(
            [all_valid_by_id[oid] for oid in chosen_ids],
            key=lambda o: (o.course.year_level, o.course.display_order),
        )
        idle_gaps, active_days = compute_schedule_metrics(chosen_offerings)
        total_lec = sum(o.course.lec_units for o in chosen_offerings)
        total_lab = sum(o.course.lab_units for o in chosen_offerings)
        total_units = sum(o.course.total_units for o in chosen_offerings)

        if rank == 1:
            label = "Recommended Optimal (Minimal Idle Gaps)"
        else:
            label = f"Conflict-Free Alternative #{rank}"

        options.append(
            ScheduleOptionDTO(
                rank=rank,
                label=label,
                total_units=total_units,
                total_lec_units=total_lec,
                total_lab_units=total_lab,
                idle_gap_hours=idle_gaps,
                active_days=active_days,
                offerings=[serialize_offering(o) for o in chosen_offerings],
            )
        )

        # No-good cut to discover distinct next-best schedule
        model.Add(sum(x_vars[oid] for oid in chosen_ids) <= len(chosen_ids) - 1)

    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    return options, elapsed_ms, first_status_str
