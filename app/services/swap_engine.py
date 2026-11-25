"""Conflict Report Log Diagnostics & Dynamic Section-Swapping Engine (Minimum-Deviation CP-SAT)."""

from __future__ import annotations

from collections import defaultdict

from ortools.sat.python import cp_model

from app.config import DAY_LABELS, DAYS, HOURS, START_HOUR
from app.models import SectionOffering
from app.schemas.scheduler import (
    ConflictLogItem,
    RelaxationSuggestion,
    SwapActionDTO,
    SwapRecommendationDTO,
)
from app.services.csp_solver import (
    _add_gap_and_compactness_objective,
    blocked_slots_violated,
    compute_schedule_metrics,
    offering_slots,
    serialize_offering,
)


def _format_hour_ranges(hours: list[int]) -> str:
    """Compress sorted hour integers into readable 24h ranges, e.g. [13, 14] -> '13:00-15:00'."""
    if not hours:
        return ""
    sorted_h = sorted(set(hours))
    ranges: list[str] = []
    start = prev = sorted_h[0]
    for h in sorted_h[1:]:
        if h == prev + 1:
            prev = h
        else:
            ranges.append(f"{start:02d}:00-{prev + 1:02d}:00")
            start = prev = h
    ranges.append(f"{start:02d}:00-{prev + 1:02d}:00")
    return ", ".join(ranges)


def diagnose_conflicts(
    offerings_by_course: dict[str, list[SectionOffering]],
    availability_matrix: dict[str, list[int]],
    pinned_offerings: dict[str, str] | None = None,
) -> tuple[list[ConflictLogItem], dict[str, str]]:
    """
    Generate structured Conflict Report Log entries for pinned selections or infeasible combinations.

    Returns:
      (conflict_logs, pin_issue_reason_by_course)
    """
    pinned = pinned_offerings or {}
    logs: list[ConflictLogItem] = []
    pin_reasons: dict[str, str] = {}

    # 1. Check courses with zero offerings at all
    for course_code, offerings in offerings_by_course.items():
        if not offerings:
            logs.append(
                ConflictLogItem(
                    conflict_type="NO_OFFERING",
                    severity="ERROR",
                    course_codes=[course_code],
                    message=f"{course_code} has no institutional section offerings in the current semester snapshot.",
                )
            )
            continue

        open_offerings = [o for o in offerings if o.is_open]
        if not open_offerings:
            logs.append(
                ConflictLogItem(
                    conflict_type="CAPACITY_FULL",
                    severity="ERROR",
                    course_codes=[course_code],
                    schedule_codes=[o.schedule_code for o in offerings],
                    message=f"All sections for {course_code} are currently full/closed.",
                )
            )
            continue

        compliant_open = [o for o in open_offerings if not blocked_slots_violated(o, availability_matrix)]
        if not compliant_open:
            # Find which blocked slots interfere across open offerings
            sample = open_offerings[0]
            violated = blocked_slots_violated(sample, availability_matrix)
            by_day: dict[str, list[int]] = defaultdict(list)
            for d, h in violated:
                by_day[d].append(h)
            day_summary = "; ".join(
                f"{DAY_LABELS.get(d, d)} ({_format_hour_ranges(hrs)})" for d, hrs in by_day.items()
            )
            logs.append(
                ConflictLogItem(
                    conflict_type="BLOCKED_TIME_SLOT",
                    severity="ERROR",
                    course_codes=[course_code],
                    schedule_codes=[o.schedule_code for o in open_offerings],
                    day=next(iter(by_day.keys()), None),
                    time_range=_format_hour_ranges(next(iter(by_day.values()), [])),
                    message=(
                        f"Every open section for {course_code} falls inside your blocked availability slots "
                        f"(e.g., {sample.section_name} clashes with {day_summary})."
                    ),
                )
            )

    # 2. Explicitly inspect pinned sections for CAPACITY_FULL, BLOCKED_TIME_SLOT, and pairwise TIME_OVERLAP
    pinned_objs: list[SectionOffering] = []
    for course_code, sched_code in pinned.items():
        if course_code not in offerings_by_course:
            continue
        match = next(
            (o for o in offerings_by_course[course_code] if o.schedule_code == sched_code),
            None,
        )
        if match is None:
            continue
        pinned_objs.append(match)

        if not match.is_open:
            pin_reasons[course_code] = (
                f"Replaced closed/full section {match.section_name} "
                f"({match.enrolled_count}/{match.max_capacity} seats)"
            )
            logs.append(
                ConflictLogItem(
                    conflict_type="CAPACITY_FULL",
                    severity="ERROR",
                    course_codes=[course_code],
                    schedule_codes=[match.schedule_code],
                    message=(
                        f"{course_code} ({match.section_name}, Sched {match.schedule_code}) is Closed "
                        f"({match.enrolled_count}/{match.max_capacity} slots filled)."
                    ),
                )
            )

        violated = blocked_slots_violated(match, availability_matrix)
        if violated:
            by_day_v: dict[str, list[int]] = defaultdict(list)
            for d, h in violated:
                by_day_v[d].append(h)
            first_day = next(iter(by_day_v.keys()))
            first_range = _format_hour_ranges(by_day_v[first_day])
            detail = "; ".join(
                f"{DAY_LABELS.get(d, d)} {_format_hour_ranges(hrs)}" for d, hrs in by_day_v.items()
            )
            pin_reasons.setdefault(
                course_code,
                f"Moved out of blocked availability window ({detail})",
            )
            logs.append(
                ConflictLogItem(
                    conflict_type="BLOCKED_TIME_SLOT",
                    severity="ERROR",
                    course_codes=[course_code],
                    schedule_codes=[match.schedule_code],
                    day=first_day,
                    time_range=first_range,
                    message=(
                        f"{course_code} ({match.section_name}) violates your blocked availability matrix on {detail}."
                    ),
                )
            )

    # Pairwise overlap detection among pinned offerings
    for i in range(len(pinned_objs)):
        for j in range(i + 1, len(pinned_objs)):
            off_a = pinned_objs[i]
            off_b = pinned_objs[j]
            common = sorted(set(offering_slots(off_a)).intersection(offering_slots(off_b)))
            if common:
                by_day_c: dict[str, list[int]] = defaultdict(list)
                for d, h in common:
                    by_day_c[d].append(h)
                first_day = next(iter(by_day_c.keys()))
                first_range = _format_hour_ranges(by_day_c[first_day])
                detail = "; ".join(
                    f"{DAY_LABELS.get(d, d)} ({d}) {_format_hour_ranges(hrs)}"
                    for d, hrs in by_day_c.items()
                )
                c_a = off_a.course.code
                c_b = off_b.course.code
                pin_reasons.setdefault(c_a, f"Resolved timetable clash with {c_b} ({detail})")
                pin_reasons.setdefault(c_b, f"Resolved timetable clash with {c_a} ({detail})")
                logs.append(
                    ConflictLogItem(
                        conflict_type="TIME_OVERLAP",
                        severity="ERROR",
                        course_codes=[c_a, c_b],
                        schedule_codes=[off_a.schedule_code, off_b.schedule_code],
                        day=first_day,
                        time_range=first_range,
                        message=(
                            f"Time overlap between {c_a} ({off_a.section_name}) and "
                            f"{c_b} ({off_b.section_name}) on {detail}."
                        ),
                    )
                )

    # 3. If no pins caused errors yet, check pairwise unavoidable clashes among open compliant pools
    if not logs and len(offerings_by_course) >= 2:
        course_list = list(offerings_by_course.keys())
        compliant_map = {
            code: [
                o
                for o in offs
                if o.is_open and not blocked_slots_violated(o, availability_matrix)
            ]
            for code, offs in offerings_by_course.items()
        }
        for i in range(len(course_list)):
            for j in range(i + 1, len(course_list)):
                ca, cb = course_list[i], course_list[j]
                pool_a = compliant_map.get(ca, [])
                pool_b = compliant_map.get(cb, [])
                if not pool_a or not pool_b:
                    continue
                compatible = any(
                    not set(offering_slots(oa)).intersection(offering_slots(ob))
                    for oa in pool_a
                    for ob in pool_b
                )
                if not compatible:
                    # Report sample overlap window
                    sample_overlap = sorted(
                        set(offering_slots(pool_a[0])).intersection(offering_slots(pool_b[0]))
                    )
                    first_day = sample_overlap[0][0] if sample_overlap else None
                    first_range = (
                        _format_hour_ranges([h for d, h in sample_overlap if d == first_day])
                        if first_day
                        else None
                    )
                    logs.append(
                        ConflictLogItem(
                            conflict_type="TIME_OVERLAP",
                            severity="ERROR",
                            course_codes=[ca, cb],
                            day=first_day,
                            time_range=first_range,
                            message=(
                                f"All available sections of {ca} overlap with all available sections of {cb} "
                                "under your current availability matrix."
                            ),
                        )
                    )

        # If still empty (multi-way 3+ course pigeonhole clash), add a clear multi-course conflict summary
        if not logs:
            logs.append(
                ConflictLogItem(
                    conflict_type="TIME_OVERLAP",
                    severity="ERROR",
                    course_codes=course_list,
                    message=(
                        "Multi-course time-slot collision detected across the selected courses under your "
                        "current availability constraints. See swap or slot-relaxation suggestions below."
                    ),
                )
            )

    return logs, pin_reasons


def find_dynamic_swaps(
    offerings_by_course: dict[str, list[SectionOffering]],
    availability_matrix: dict[str, list[int]],
    pinned_offerings: dict[str, str],
    pin_reasons: dict[str, str],
    max_recommendations: int = 3,
) -> list[SwapRecommendationDTO]:
    """
    Dynamic Section-Swapping Engine.

    Given a student's conflicting pinned sections, runs a minimum-deviation CP-SAT search over
    all open, matrix-compliant sections to discover single-course and cascading swaps that produce
    a strictly 0-conflict master schedule.
    """
    if not offerings_by_course or not pinned_offerings:
        return []

    valid_candidates: dict[str, list[SectionOffering]] = {}
    all_valid_by_id: dict[int, SectionOffering] = {}
    pinned_obj_by_course: dict[str, SectionOffering] = {}

    for course_code, offerings in offerings_by_course.items():
        pin_sched = pinned_offerings.get(course_code)
        if pin_sched:
            orig = next((o for o in offerings if o.schedule_code == pin_sched), None)
            if orig is not None:
                pinned_obj_by_course[course_code] = orig

        filtered = [
            o for o in offerings if o.is_open and not blocked_slots_violated(o, availability_matrix)
        ]
        if not filtered:
            return []
        valid_candidates[course_code] = filtered
        for o in filtered:
            all_valid_by_id[o.id] = o

    model = cp_model.CpModel()
    x_vars: dict[int, cp_model.IntVar] = {}
    slot_to_off_ids: dict[tuple[str, int], list[int]] = defaultdict(list)
    swap_penalty_terms: list[cp_model.LinearExpr] = []

    for course_code, candidates in valid_candidates.items():
        c_vars: list[cp_model.IntVar] = []
        pin_sched = pinned_offerings.get(course_code)
        for off in candidates:
            var = model.NewBoolVar(f"swap_x_{off.id}")
            x_vars[off.id] = var
            c_vars.append(var)
            for slot in set(offering_slots(off)):
                slot_to_off_ids[slot].append(off.id)

            if pin_sched and off.schedule_code != pin_sched:
                swap_penalty_terms.append(1000 * var)

        model.Add(sum(c_vars) == 1)

    for _slot, off_ids in slot_to_off_ids.items():
        if len(off_ids) > 1:
            model.Add(sum(x_vars[oid] for oid in off_ids) <= 1)

    extra_penalty = sum(swap_penalty_terms) if swap_penalty_terms else None
    _add_gap_and_compactness_objective(model, x_vars, slot_to_off_ids, extra_penalty_expr=extra_penalty)

    recommendations: list[SwapRecommendationDTO] = []
    for _ in range(max_recommendations):
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 3.0
        solver.parameters.num_search_workers = 1
        status = solver.Solve(model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            break

        chosen_ids = [oid for oid, var in x_vars.items() if solver.Value(var) == 1]
        chosen_offerings = sorted(
            [all_valid_by_id[oid] for oid in chosen_ids],
            key=lambda o: (o.course.year_level, o.course.display_order),
        )

        actions: list[SwapActionDTO] = []
        for off in chosen_offerings:
            c_code = off.course.code
            orig = pinned_obj_by_course.get(c_code)
            if orig is not None and orig.schedule_code != off.schedule_code:
                reason = pin_reasons.get(
                    c_code,
                    f"Cascading section swap to maintain zero overlap across selected courses",
                )
                actions.append(
                    SwapActionDTO(
                        course_code=c_code,
                        from_schedule_code=orig.schedule_code,
                        from_section=orig.section_name,
                        to_schedule_code=off.schedule_code,
                        to_section=off.section_name,
                        reason=reason,
                    )
                )

        if actions:
            idle_gaps, active_days = compute_schedule_metrics(chosen_offerings)
            total_units = sum(o.course.total_units for o in chosen_offerings)
            swap_label = (
                f"Single-course swap ({actions[0].course_code}: {actions[0].from_section} -> {actions[0].to_section})"
                if len(actions) == 1
                else f"Cascading {len(actions)}-course swap ({', '.join(a.course_code for a in actions)})"
            )
            recommendations.append(
                SwapRecommendationDTO(
                    swap_count=len(actions),
                    summary=swap_label,
                    actions=actions,
                    resulting_offerings=[serialize_offering(o) for o in chosen_offerings],
                    total_units=total_units,
                    idle_gap_hours=idle_gaps,
                    active_days=active_days,
                )
            )

        # No-good cut to discover next alternative swap chain
        model.Add(sum(x_vars[oid] for oid in chosen_ids) <= len(chosen_ids) - 1)

    return recommendations


def find_minimal_matrix_relaxation(
    offerings_by_course: dict[str, list[SectionOffering]],
    availability_matrix: dict[str, list[int]],
) -> RelaxationSuggestion | None:
    """
    When blocked time slots cause a scheduling deadlock, find the minimal set of currently-blocked
    (day, hour) cells that can be unblocked to produce a conflict-free schedule.
    """
    if not offerings_by_course:
        return None

    open_candidates: dict[str, list[SectionOffering]] = {}
    all_open_by_id: dict[int, SectionOffering] = {}
    for course_code, offerings in offerings_by_course.items():
        open_only = [o for o in offerings if o.is_open]
        if not open_only:
            return None
        open_candidates[course_code] = open_only
        for o in open_only:
            all_open_by_id[o.id] = o

    blocked_set: set[tuple[str, int]] = set()
    for day in DAYS:
        day_slots = availability_matrix.get(day, [1] * len(HOURS))
        for idx, flag in enumerate(day_slots):
            if flag == 0:
                blocked_set.add((day, START_HOUR + idx))

    if not blocked_set:
        return None

    model = cp_model.CpModel()
    x_vars: dict[int, cp_model.IntVar] = {}
    slot_to_off_ids: dict[tuple[str, int], list[int]] = defaultdict(list)

    for _course_code, candidates in open_candidates.items():
        c_vars: list[cp_model.IntVar] = []
        for off in candidates:
            var = model.NewBoolVar(f"rel_x_{off.id}")
            x_vars[off.id] = var
            c_vars.append(var)
            for slot in set(offering_slots(off)):
                slot_to_off_ids[slot].append(off.id)
        model.Add(sum(c_vars) == 1)

    unblock_vars: dict[tuple[str, int], cp_model.IntVar] = {}
    for slot, off_ids in slot_to_off_ids.items():
        if len(off_ids) > 1:
            model.Add(sum(x_vars[oid] for oid in off_ids) <= 1)
        if slot in blocked_set:
            u_var = model.NewBoolVar(f"unblock_{slot[0]}_{slot[1]}")
            unblock_vars[slot] = u_var
            model.Add(sum(x_vars[oid] for oid in off_ids) <= u_var)

    if not unblock_vars:
        return None

    extra_penalty = 1000 * sum(unblock_vars.values())
    _add_gap_and_compactness_objective(model, x_vars, slot_to_off_ids, extra_penalty_expr=extra_penalty)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 3.0
    solver.parameters.num_search_workers = 1
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    chosen_ids = [oid for oid, var in x_vars.items() if solver.Value(var) == 1]
    chosen_offerings = sorted(
        [all_open_by_id[oid] for oid in chosen_ids],
        key=lambda o: (o.course.year_level, o.course.display_order),
    )

    to_unblock = sorted(
        [slot for slot, var in unblock_vars.items() if solver.Value(var) == 1],
        key=lambda s: (DAYS.index(s[0]), s[1]),
    )
    if not to_unblock:
        return None

    by_day: dict[str, list[int]] = defaultdict(list)
    for d, h in to_unblock:
        by_day[d].append(h)

    readable = "; ".join(
        f"{DAY_LABELS.get(d, d)} ({_format_hour_ranges(hrs)})" for d, hrs in by_day.items()
    )
    idle_gaps, _ = compute_schedule_metrics(chosen_offerings)

    return RelaxationSuggestion(
        slots_to_unblock=[
            {
                "day": d,
                "day_label": DAY_LABELS.get(d, d),
                "hour": h,
                "time_range": f"{h:02d}:00-{h + 1:02d}:00",
            }
            for d, h in to_unblock
        ],
        description=(
            f"Unblocking {len(to_unblock)} hourly slot(s) — {readable} — unlocks a conflict-free "
            f"schedule for all {len(chosen_offerings)} selected subjects."
        ),
        resulting_offerings=[serialize_offering(o) for o in chosen_offerings],
        idle_gap_hours=idle_gaps,
    )
