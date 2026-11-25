"""Institutional Section Offerings and Meeting Time Slots ORM models."""

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SectionOffering(Base):
    """A section offering for a specific BSCS course in a semester snapshot."""

    __tablename__ = "section_offerings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    schedule_code: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    section_name: Mapped[str] = mapped_column(String(30), index=True, nullable=False)
    academic_year: Mapped[str] = mapped_column(String(20), nullable=False)
    semester: Mapped[str] = mapped_column(String(20), nullable=False)
    instructor: Mapped[str] = mapped_column(String(120), default="TBA", nullable=False)
    max_capacity: Mapped[int] = mapped_column(Integer, default=40, nullable=False)
    enrolled_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="Open", nullable=False)  # Open | Closed
    snapshot_tag: Mapped[str] = mapped_column(String(60), default="AY2026-2027-FIRST-BSCS", nullable=False)

    course = relationship("Course", back_populates="offerings")
    meetings = relationship(
        "SectionMeeting",
        back_populates="offering",
        cascade="all, delete-orphan",
        order_by="SectionMeeting.id",
    )

    @property
    def seats_remaining(self) -> int:
        return max(0, self.max_capacity - self.enrolled_count)

    @property
    def is_open(self) -> bool:
        return self.status.lower() == "open" and self.enrolled_count < self.max_capacity


class SectionMeeting(Base):
    """Individual weekly lecture or laboratory meeting block for a section offering."""

    __tablename__ = "section_meetings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    offering_id: Mapped[int] = mapped_column(
        ForeignKey("section_offerings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    meeting_type: Mapped[str] = mapped_column(String(10), default="LEC", nullable=False)  # LEC | LAB
    day: Mapped[str] = mapped_column(String(4), nullable=False)  # M, T, W, TH, F, S
    start_hour: Mapped[int] = mapped_column(Integer, nullable=False)  # 7..19
    end_hour: Mapped[int] = mapped_column(Integer, nullable=False)    # 8..20
    room: Mapped[str] = mapped_column(String(40), default="TBA", nullable=False)

    offering = relationship("SectionOffering", back_populates="meetings")

    @property
    def time_range_24h(self) -> str:
        return f"{self.start_hour:02d}:00-{self.end_hour:02d}:00"

    @property
    def portal_format(self) -> str:
        """Exact display format from CvSU-Imus Subjects Offered table."""
        return f"{self.start_hour:02d}:00-{self.end_hour:02d}:00 / {self.day} / {self.room}"

    @property
    def current_subjects_format(self) -> str:
        """Exact display format from CvSU-Imus Current Subjects list."""
        return f"{self.start_hour:02d}:00 - {self.end_hour:02d}:00 | {self.day} | {self.room}"
