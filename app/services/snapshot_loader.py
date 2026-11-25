"""Idempotent SQLite database initializer and institutional BSCS snapshot loader."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.config import (
    CURRENT_ACADEMIC_YEAR,
    CURRENT_SEMESTER,
    DAYS,
    HOURS,
    SNAPSHOTS_DIR,
    START_HOUR,
)
from app.database import Base, SessionLocal, engine
from app.models import (
    AccountBalanceRecord,
    AvailabilityMatrix,
    Course,
    CoursePrerequisite,
    CurrentEnrollment,
    NewsUpdate,
    PrerequisiteOverride,
    ScheduleSubmission,
    SectionMeeting,
    SectionOffering,
    StudentTranscript,
    User,
)


def hash_password(plain_password: str, salt: str | None = None) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256."""
    use_salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        plain_password.encode("utf-8"),
        use_salt.encode("utf-8"),
        120_000,
    ).hex()
    return f"pbkdf2_sha256${use_salt}${digest}"


def verify_password(plain_password: str, stored_hash: str) -> bool:
    """Verify a plaintext password against a stored PBKDF2 hash."""
    try:
        scheme, salt, expected = stored_hash.split("$", 2)
    except ValueError:
        return False
    if scheme != "pbkdf2_sha256":
        return False
    candidate = hash_password(plain_password, salt=salt).split("$", 2)[2]
    return hmac.compare_digest(candidate, expected)


def build_availability_matrix(blocked_slots: dict[str, list[int]] | None = None) -> dict[str, list[int]]:
    """Build a 6x13 Mon-Sat 7:00 AM-8:00 PM binary availability matrix (1=Available, 0=Blocked)."""
    blocked_map = blocked_slots or {}
    matrix: dict[str, list[int]] = {}
    for day in DAYS:
        blocked_hours = set(blocked_map.get(day, []))
        matrix[day] = [0 if hour in blocked_hours else 1 for hour in HOURS]
    return matrix


def _load_json(filename: str) -> dict:
    path: Path = SNAPSHOTS_DIR / filename
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def seed_database(db: Session, force_reset: bool = False) -> None:
    """Populate BSCS curriculum, offerings, demo users, transcripts, and portal records."""
    if force_reset:
        for model in (
            CurrentEnrollment,
            ScheduleSubmission,
            PrerequisiteOverride,
            AvailabilityMatrix,
            StudentTranscript,
            AccountBalanceRecord,
            SectionMeeting,
            SectionOffering,
            CoursePrerequisite,
            Course,
            NewsUpdate,
            User,
        ):
            db.execute(delete(model))
        db.commit()

    course_count = db.scalar(select(func.count(Course.id))) or 0
    if course_count > 0 and not force_reset:
        return

    # 1. Seed 57-course official BSCS Curriculum & Prerequisite DAG
    curriculum_data = _load_json("bscs_curriculum.json")
    courses_by_code: dict[str, Course] = {}
    for idx, item in enumerate(curriculum_data["courses"], start=1):
        lec = int(item["lec_units"])
        lab = int(item["lab_units"])
        course = Course(
            code=item["code"],
            title=item["title"],
            lec_units=lec,
            lab_units=lab,
            total_units=lec + lab,
            year_level=int(item["year_level"]),
            semester=item["semester"],
            major=item.get("major", "N/A"),
            display_order=idx,
        )
        db.add(course)
        courses_by_code[course.code] = course
    db.flush()

    for item in curriculum_data["courses"]:
        course = courses_by_code[item["code"]]
        for prereq_code in item.get("prerequisites", []):
            prereq = courses_by_code.get(prereq_code)
            if prereq is not None:
                db.add(CoursePrerequisite(course_id=course.id, prerequisite_id=prereq.id))
    db.flush()

    # 2. Seed Institutional AY 2026-2027 First Semester BSCS Offerings
    offerings_data = _load_json("ay2026_sem1_offerings.json")
    snapshot_tag = offerings_data.get("snapshot_tag", "AY2026-2027-FIRST-BSCS")
    offerings_by_sched: dict[str, SectionOffering] = {}
    for off_item in offerings_data["offerings"]:
        course = courses_by_code.get(off_item["course_code"])
        if course is None:
            continue
        offering = SectionOffering(
            schedule_code=off_item["schedule_code"],
            course_id=course.id,
            section_name=off_item["section_name"],
            academic_year=offerings_data.get("academic_year", CURRENT_ACADEMIC_YEAR),
            semester=offerings_data.get("semester", CURRENT_SEMESTER),
            instructor=off_item.get("instructor", "TBA"),
            max_capacity=int(off_item.get("max_capacity", 40)),
            enrolled_count=int(off_item.get("enrolled_count", 0)),
            status=off_item.get("status", "Open"),
            snapshot_tag=snapshot_tag,
        )
        db.add(offering)
        db.flush()
        offerings_by_sched[offering.schedule_code] = offering

        for m in off_item.get("meetings", []):
            db.add(
                SectionMeeting(
                    offering_id=offering.id,
                    meeting_type=m.get("meeting_type", "LEC"),
                    day=m["day"],
                    start_hour=int(m["start_hour"]),
                    end_hour=int(m["end_hour"]),
                    room=m.get("room", "TBA"),
                )
            )
    db.flush()

    # 3. Seed News Updates, Demo Users, Transcripts, Matrices, Current Enrollments, Account Balances
    personas_data = _load_json("demo_personas.json")
    for news_item in personas_data.get("news_updates", []):
        db.add(
            NewsUpdate(
                id=int(news_item["id"]),
                title=news_item["title"],
                date_posted=news_item["date_posted"],
                content=news_item["content"],
            )
        )

    balance_templates = personas_data.get("account_balances", [])

    for u_item in personas_data.get("users", []):
        user = User(
            student_number=u_item["student_number"],
            password_hash=hash_password(u_item["password"]),
            role=u_item.get("role", "student"),
            student_type=u_item.get("student_type", "Irregular"),
            enrollment_status=u_item.get("enrollment_status", "Pre-Registration"),
            scenario_label=u_item.get("scenario_label", ""),
            scenario_summary=u_item.get("scenario_summary", ""),
            first_name=u_item["first_name"],
            middle_name=u_item.get("middle_name", ""),
            last_name=u_item["last_name"],
            suffix=u_item.get("suffix", ""),
            sex=u_item.get("sex", "MALE"),
            date_of_birth=u_item.get("date_of_birth", ""),
            civil_status=u_item.get("civil_status", "SINGLE"),
            religion=u_item.get("religion", ""),
            citizenship=u_item.get("citizenship", "FILIPINO"),
            secondary_school=u_item.get("secondary_school", ""),
            province=u_item.get("province", "CAVITE"),
            city=u_item.get("city", "IMUS CITY"),
            barangay=u_item.get("barangay", ""),
            street_address=u_item.get("street_address", ""),
            cvsu_email=u_item["cvsu_email"],
            temp_password=u_item.get("temp_password", ""),
            mobile_number=u_item.get("mobile_number", ""),
            personal_email=u_item.get("personal_email", ""),
            guardian_name=u_item.get("guardian_name", ""),
            guardian_number=u_item.get("guardian_number", ""),
            course_code=u_item.get("course_code", "BSCS"),
            year_level=int(u_item.get("year_level", 3)),
            year_admitted=u_item.get("year_admitted", "2024-2025"),
            sem_admitted=u_item.get("sem_admitted", "FIRST"),
            balance=float(u_item.get("balance", 0.0)),
        )
        db.add(user)
        db.flush()

        # Availability matrix for every student
        if user.role == "student":
            matrix = build_availability_matrix(u_item.get("blocked_slots"))
            db.add(AvailabilityMatrix(student_id=user.id, matrix_json=json.dumps(matrix)))

            # Transcript records
            for t in u_item.get("transcript", []):
                course = courses_by_code.get(t["code"])
                if course is None:
                    continue
                db.add(
                    StudentTranscript(
                        student_id=user.id,
                        course_id=course.id,
                        academic_year=t.get("ay", "2024-2025"),
                        semester=t.get("sem", "FIRST"),
                        section_name=t.get("sec", "-"),
                        schedule_code=t.get("sched", "-"),
                        grade=t.get("grade", "-"),
                        completion=t.get("completion", "-"),
                        status=t.get("status", "PASSED"),
                    )
                )

            # Current enrollments (e.g., Regular block student Andrea)
            for sched_code in u_item.get("current_schedule_codes", []):
                off = offerings_by_sched.get(sched_code)
                if off is not None:
                    db.add(
                        CurrentEnrollment(
                            student_id=user.id,
                            offering_id=off.id,
                            academic_year=CURRENT_ACADEMIC_YEAR,
                            semester=CURRENT_SEMESTER,
                        )
                    )

            # Account balance records
            for bal in balance_templates:
                db.add(
                    AccountBalanceRecord(
                        student_id=user.id,
                        academic_year=bal["academic_year"],
                        semester=bal["semester"],
                        total_fee=float(bal["total_fee"]),
                        total_paid=float(bal["total_paid"]),
                        balance=float(bal["balance"]),
                    )
                )

    db.commit()


def reset_student_demo_state(db: Session, student: User) -> None:
    """Reset a single student's transcript and availability matrix back to snapshot defaults."""
    personas_data = _load_json("demo_personas.json")
    persona = next(
        (u for u in personas_data.get("users", []) if u["student_number"] == student.student_number),
        None,
    )
    if persona is None:
        return

    courses_by_code = {c.code: c for c in db.scalars(select(Course)).all()}

    # Reset transcripts
    db.execute(delete(StudentTranscript).where(StudentTranscript.student_id == student.id))
    for t in persona.get("transcript", []):
        course = courses_by_code.get(t["code"])
        if course is not None:
            db.add(
                StudentTranscript(
                    student_id=student.id,
                    course_id=course.id,
                    academic_year=t.get("ay", "2024-2025"),
                    semester=t.get("sem", "FIRST"),
                    section_name=t.get("sec", "-"),
                    schedule_code=t.get("sched", "-"),
                    grade=t.get("grade", "-"),
                    completion=t.get("completion", "-"),
                    status=t.get("status", "PASSED"),
                )
            )

    # Reset availability matrix
    matrix = build_availability_matrix(persona.get("blocked_slots"))
    existing_matrix = db.scalar(
        select(AvailabilityMatrix).where(AvailabilityMatrix.student_id == student.id)
    )
    if existing_matrix is None:
        db.add(AvailabilityMatrix(student_id=student.id, matrix_json=json.dumps(matrix)))
    else:
        existing_matrix.matrix_json = json.dumps(matrix)

    db.commit()


def init_db() -> None:
    """Create all SQLite tables and seed institutional BSCS data if empty."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_database(db, force_reset=False)
    finally:
        db.close()
