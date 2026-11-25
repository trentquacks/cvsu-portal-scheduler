"""User (Student and Adviser) ORM model."""

from datetime import datetime, timezone
from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    """Represents a Student or Academic/Registration Adviser in the portal."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_number: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="student", nullable=False)  # student | adviser
    student_type: Mapped[str] = mapped_column(String(20), default="Irregular", nullable=False)  # Regular | Irregular | Adviser
    enrollment_status: Mapped[str] = mapped_column(String(40), default="Pre-Registration", nullable=False)

    scenario_label: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    scenario_summary: Mapped[str] = mapped_column(Text, default="", nullable=False)

    first_name: Mapped[str] = mapped_column(String(80), nullable=False)
    middle_name: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    last_name: Mapped[str] = mapped_column(String(80), nullable=False)
    suffix: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    sex: Mapped[str] = mapped_column(String(15), default="MALE", nullable=False)
    date_of_birth: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    civil_status: Mapped[str] = mapped_column(String(30), default="SINGLE", nullable=False)
    religion: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    citizenship: Mapped[str] = mapped_column(String(40), default="FILIPINO", nullable=False)
    secondary_school: Mapped[str] = mapped_column(String(150), default="", nullable=False)

    province: Mapped[str] = mapped_column(String(60), default="CAVITE", nullable=False)
    city: Mapped[str] = mapped_column(String(60), default="IMUS CITY", nullable=False)
    barangay: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    street_address: Mapped[str] = mapped_column(String(180), default="", nullable=False)

    cvsu_email: Mapped[str] = mapped_column(String(120), nullable=False)
    temp_password: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    mobile_number: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    personal_email: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    guardian_name: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    guardian_number: Mapped[str] = mapped_column(String(20), default="", nullable=False)

    course_code: Mapped[str] = mapped_column(String(20), default="BSCS", nullable=False)
    year_level: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    year_admitted: Mapped[str] = mapped_column(String(20), default="2024-2025", nullable=False)
    sem_admitted: Mapped[str] = mapped_column(String(20), default="FIRST", nullable=False)
    balance: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    transcripts = relationship("StudentTranscript", back_populates="student", cascade="all, delete-orphan")
    availability = relationship("AvailabilityMatrix", back_populates="student", uselist=False, cascade="all, delete-orphan")
    submissions = relationship(
        "ScheduleSubmission",
        foreign_keys="ScheduleSubmission.student_id",
        back_populates="student",
        cascade="all, delete-orphan",
    )
    overrides = relationship(
        "PrerequisiteOverride",
        foreign_keys="PrerequisiteOverride.student_id",
        back_populates="student",
        cascade="all, delete-orphan",
    )

    @property
    def display_name(self) -> str:
        """Full name in 'FIRST LAST' format for header."""
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def formal_name(self) -> str:
        """Full name in 'LAST, FIRST M.' format matching the real CvSU portal."""
        middle_initial = f" {self.middle_name[0]}." if self.middle_name else ""
        suffix = f" {self.suffix}" if self.suffix else ""
        return f"{self.last_name}, {self.first_name}{middle_initial}{suffix}".strip()
