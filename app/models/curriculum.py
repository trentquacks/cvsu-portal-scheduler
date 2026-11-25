"""BSCS Curriculum and Prerequisite DAG ORM models."""

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Course(Base):
    """Official BSCS curriculum subject."""

    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    lec_units: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    lab_units: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_units: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    year_level: Mapped[int] = mapped_column(Integer, nullable=False)
    semester: Mapped[str] = mapped_column(String(20), nullable=False)  # FIRST | SECOND | SUMMER
    major: Mapped[str] = mapped_column(String(30), default="N/A", nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    prerequisite_links = relationship(
        "CoursePrerequisite",
        foreign_keys="CoursePrerequisite.course_id",
        back_populates="course",
        cascade="all, delete-orphan",
    )
    offerings = relationship("SectionOffering", back_populates="course", cascade="all, delete-orphan")


class CoursePrerequisite(Base):
    """Directed edge representing a prerequisite requirement between two courses."""

    __tablename__ = "course_prerequisites"
    __table_args__ = (UniqueConstraint("course_id", "prerequisite_id", name="uq_course_prereq"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    prerequisite_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)

    course = relationship("Course", foreign_keys=[course_id], back_populates="prerequisite_links")
    prerequisite = relationship("Course", foreign_keys=[prerequisite_id])
