"""Enrollment, Transcript, Availability Matrix, Advising Review, and Portal Data models."""

from datetime import datetime, timezone
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class StudentTranscript(Base):
    """Historical or active subject record for a student."""

    __tablename__ = "student_transcripts"
    __table_args__ = (UniqueConstraint("student_id", "course_id", name="uq_student_course_transcript"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    academic_year: Mapped[str] = mapped_column(String(20), default="2025-2026", nullable=False)
    semester: Mapped[str] = mapped_column(String(20), default="FIRST", nullable=False)
    section_name: Mapped[str] = mapped_column(String(30), default="-", nullable=False)
    schedule_code: Mapped[str] = mapped_column(String(20), default="-", nullable=False)
    grade: Mapped[str] = mapped_column(String(12), default="-", nullable=False)
    completion: Mapped[str] = mapped_column(String(12), default="-", nullable=False)
    # PASSED | CREDITED | FAILED | DROPPED | ENROLLED | NOT_TAKEN
    status: Mapped[str] = mapped_column(String(20), default="NOT_TAKEN", nullable=False)

    student = relationship("User", back_populates="transcripts")
    course = relationship("Course")


class CurrentEnrollment(Base):
    """Active enrolled sections for the current semester (populates Current Subjects & Dashboard)."""

    __tablename__ = "current_enrollments"
    __table_args__ = (UniqueConstraint("student_id", "offering_id", name="uq_student_offering_enrolled"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    offering_id: Mapped[int] = mapped_column(ForeignKey("section_offerings.id", ondelete="CASCADE"), nullable=False)
    academic_year: Mapped[str] = mapped_column(String(20), nullable=False)
    semester: Mapped[str] = mapped_column(String(20), nullable=False)
    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    offering = relationship("SectionOffering")


class AvailabilityMatrix(Base):
    """Saved Mon-Sat 7:00 AM-8:00 PM binary availability matrix per student."""

    __tablename__ = "availability_matrices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    # JSON dict: {"M": [1,1,...,1], "T": [...], ..., "S": [...]} where each list has 13 ints (hours 7..19)
    matrix_json: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    student = relationship("User", back_populates="availability")


class ScheduleSubmission(Base):
    """Generated and submitted master schedule snapshot awaiting/approved by an Adviser."""

    __tablename__ = "schedule_submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    academic_year: Mapped[str] = mapped_column(String(20), nullable=False)
    semester: Mapped[str] = mapped_column(String(20), nullable=False)
    # DRAFT | PENDING_ADVISING | APPROVED | REVISION_REQUESTED
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", nullable=False)
    total_units: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    solver_time_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    idle_gap_hours: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    selected_offerings_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    conflict_logs_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    swap_history_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    adviser_notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    student = relationship("User", foreign_keys=[student_id], back_populates="submissions")
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_id])


class PrerequisiteOverride(Base):
    """Adviser manual constraint override for a specific student and course."""

    __tablename__ = "prerequisite_overrides"
    __table_args__ = (UniqueConstraint("student_id", "course_id", name="uq_student_course_override"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    adviser_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    student = relationship("User", foreign_keys=[student_id], back_populates="overrides")
    course = relationship("Course")
    adviser = relationship("User", foreign_keys=[adviser_id])


class NewsUpdate(Base):
    """Campus news and enrollment updates displayed on the portal Dashboard."""

    __tablename__ = "news_updates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    date_posted: Mapped[str] = mapped_column(String(60), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)


class AccountBalanceRecord(Base):
    """Historical semester fee ledger displayed on Account Balance."""

    __tablename__ = "account_balances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    academic_year: Mapped[str] = mapped_column(String(20), nullable=False)
    semester: Mapped[str] = mapped_column(String(20), nullable=False)
    total_fee: Mapped[float] = mapped_column(Float, nullable=False)
    total_paid: Mapped[float] = mapped_column(Float, nullable=False)
    balance: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
