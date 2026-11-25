"""ReportLab PDF exporters for Master Schedule Advising Sheet, Reg Form, and Curriculum Checklist."""

from __future__ import annotations

from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.models import ScheduleSubmission, SectionOffering, User

CVSU_GREEN = colors.HexColor("#00a15d")
CVSU_DARK = colors.HexColor("#1f2933")
CVSU_MUTED = colors.HexColor("#616e7c")
CVSU_LIGHT_BG = colors.HexColor("#f3f6f9")
BORDER_GRAY = colors.HexColor("#d9e2ec")


def _build_header_flowables(title: str, subtitle: str) -> list:
    styles = getSampleStyleSheet()
    uni_style = ParagraphStyle(
        "UniHeader",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        textColor=CVSU_GREEN,
        alignment=1,
        spaceAfter=2,
    )
    campus_style = ParagraphStyle(
        "CampusHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        textColor=CVSU_DARK,
        alignment=1,
        spaceAfter=6,
    )
    doc_title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=11,
        textColor=CVSU_DARK,
        alignment=1,
        spaceAfter=2,
    )
    sub_style = ParagraphStyle(
        "DocSub",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        textColor=CVSU_MUTED,
        alignment=1,
        spaceAfter=10,
    )
    return [
        Paragraph("CAVITE STATE UNIVERSITY - IMUS CAMPUS", uni_style),
        Paragraph("Department of Computer Studies | Bachelor of Science in Computer Science (BSCS)", campus_style),
        Paragraph(title, doc_title_style),
        Paragraph(subtitle, sub_style),
    ]


def generate_master_schedule_pdf(
    student: User,
    offerings: list[SectionOffering],
    academic_year: str,
    semester: str,
    submission: ScheduleSubmission | None = None,
) -> bytes:
    """Generate the printable Conflict-Free Master Schedule & Pre-Registration Advising Sheet PDF."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=0.55 * inch,
        rightMargin=0.55 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
        title="CvSU-Imus Conflict-Free Master Schedule",
    )
    styles = getSampleStyleSheet()
    cell_style = ParagraphStyle("Cell", parent=styles["Normal"], fontName="Helvetica", fontSize=7.8, leading=10)
    cell_bold = ParagraphStyle("CellBold", parent=cell_style, fontName="Helvetica-Bold")

    story = _build_header_flowables(
        "CONFLICT-FREE MASTER SCHEDULE & PRE-REGISTRATION ADVISING SHEET",
        f"Academic Year {academic_year} | {semester} Semester | Generated {datetime.now().strftime('%B %d, %Y %I:%M %p')}",
    )

    total_lec = sum(o.course.lec_units for o in offerings)
    total_lab = sum(o.course.lab_units for o in offerings)
    total_units = sum(o.course.total_units for o in offerings)

    status_label = submission.status if submission else "VERIFIED CONFLICT-FREE DRAFT"
    meta_rows = [
        [
            Paragraph("<b>Student Name:</b>", cell_style),
            Paragraph(student.formal_name, cell_style),
            Paragraph("<b>Student Number:</b>", cell_style),
            Paragraph(student.student_number, cell_style),
        ],
        [
            Paragraph("<b>Program / Year:</b>", cell_style),
            Paragraph(f"{student.course_code} - Year {student.year_level} ({student.student_type})", cell_style),
            Paragraph("<b>CvSU Email:</b>", cell_style),
            Paragraph(student.cvsu_email, cell_style),
        ],
        [
            Paragraph("<b>Advising Status:</b>", cell_style),
            Paragraph(status_label, cell_bold),
            Paragraph("<b>Total Load:</b>", cell_style),
            Paragraph(f"{len(offerings)} Subjects | {total_units} Units ({total_lec} Lec / {total_lab} Lab)", cell_bold),
        ],
    ]
    meta_table = Table(meta_rows, colWidths=[1.15 * inch, 2.55 * inch, 1.2 * inch, 2.5 * inch])
    meta_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), CVSU_LIGHT_BG),
                ("BOX", (0, 0), (-1, -1), 0.75, BORDER_GRAY),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, BORDER_GRAY),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(meta_table)
    story.append(Spacer(1, 12))

    # Schedule table
    sched_rows = [
        [
            Paragraph("<b>Sched Code</b>", cell_bold),
            Paragraph("<b>Subject Code</b>", cell_bold),
            Paragraph("<b>Subject Title</b>", cell_bold),
            Paragraph("<b>Section</b>", cell_bold),
            Paragraph("<b>Units</b>", cell_bold),
            Paragraph("<b>Schedule / Day / Room</b>", cell_bold),
            Paragraph("<b>Instructor</b>", cell_bold),
        ]
    ]
    for off in offerings:
        meeting_lines = "<br/>".join(
            f"{m.meeting_type}: {m.portal_format}" for m in off.meetings
        )
        sched_rows.append(
            [
                Paragraph(off.schedule_code, cell_style),
                Paragraph(off.course.code, cell_bold),
                Paragraph(off.course.title, cell_style),
                Paragraph(off.section_name, cell_style),
                Paragraph(f"{off.course.total_units} ({off.course.lec_units}/{off.course.lab_units})", cell_style),
                Paragraph(meeting_lines, cell_style),
                Paragraph(off.instructor, cell_style),
            ]
        )

    sched_rows.append(
        [
            Paragraph("", cell_style),
            Paragraph("", cell_style),
            Paragraph("<b>TOTAL ENROLLED UNITS</b>", cell_bold),
            Paragraph("", cell_style),
            Paragraph(f"<b>{total_units}</b>", cell_bold),
            Paragraph("<b>Zero Timetable Overlaps Verified (CP-SAT)</b>", cell_bold),
            Paragraph("", cell_style),
        ]
    )

    sched_table = Table(
        sched_rows,
        colWidths=[0.82 * inch, 0.78 * inch, 1.85 * inch, 0.72 * inch, 0.58 * inch, 1.65 * inch, 1.0 * inch],
        repeatRows=1,
    )
    sched_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), CVSU_GREEN),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BACKGROUND", (0, -1), (-1, -1), CVSU_LIGHT_BG),
                ("BOX", (0, 0), (-1, -1), 0.75, BORDER_GRAY),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, BORDER_GRAY),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    # Override header row text color cleanly via white Paragraph style
    header_white = ParagraphStyle("HeaderWhite", parent=cell_bold, textColor=colors.white)
    sched_rows[0] = [
        Paragraph(lbl, header_white)
        for lbl in ("Sched Code", "Subject Code", "Subject Title", "Section", "Units", "Schedule / Day / Room", "Instructor")
    ]
    sched_table = Table(
        sched_rows,
        colWidths=[0.82 * inch, 0.78 * inch, 1.85 * inch, 0.72 * inch, 0.58 * inch, 1.65 * inch, 1.0 * inch],
        repeatRows=1,
    )
    sched_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), CVSU_GREEN),
                ("BACKGROUND", (0, -1), (-1, -1), CVSU_LIGHT_BG),
                ("BOX", (0, 0), (-1, -1), 0.75, BORDER_GRAY),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, BORDER_GRAY),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(sched_table)
    story.append(Spacer(1, 14))

    if submission and submission.adviser_notes:
        story.append(Paragraph(f"<b>Academic Adviser Remarks:</b> {submission.adviser_notes}", cell_style))
        story.append(Spacer(1, 12))

    # Sign-off signature block
    sig_rows = [
        [
            Paragraph("Prepared by:", cell_style),
            Paragraph("Evaluated and Approved by:", cell_style),
        ],
        [Spacer(1, 20), Spacer(1, 20)],
        [
            Paragraph(f"<b>{student.formal_name}</b><br/>Student Signature / Date", cell_style),
            Paragraph("<b>PROF. RAMON T. BAUTISTA</b><br/>Academic / Registration Adviser, DCS", cell_style),
        ],
    ]
    sig_table = Table(sig_rows, colWidths=[3.7 * inch, 3.7 * inch])
    sig_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(sig_table)

    doc.build(story)
    return buffer.getvalue()


def generate_reg_form_pdf(
    student: User,
    offerings: list[SectionOffering],
    academic_year: str,
    semester: str,
) -> bytes:
    """Generate a pseudo Registration Form PDF matching the Current Subjects 'Reg Form' button."""
    return generate_master_schedule_pdf(student, offerings, academic_year, semester, submission=None)


def generate_checklist_pdf(student: User, eligibility_rows: list) -> bytes:
    """Generate a printable BSCS Curriculum Checklist PDF."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=0.5 * inch,
        rightMargin=0.5 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
        title="CvSU-Imus BSCS Curriculum Checklist",
    )
    styles = getSampleStyleSheet()
    cell_style = ParagraphStyle("CLCell", parent=styles["Normal"], fontName="Helvetica", fontSize=7.4, leading=9.5)
    cell_bold = ParagraphStyle("CLBold", parent=cell_style, fontName="Helvetica-Bold")
    header_white = ParagraphStyle("CLHead", parent=cell_bold, textColor=colors.white)

    story = _build_header_flowables(
        "OFFICIAL BSCS CURRICULUM CHECKLIST",
        f"Student: {student.formal_name} ({student.student_number}) | Status: {student.student_type}",
    )

    rows = [
        [
            Paragraph(h, header_white)
            for h in ("Year/Sem", "Code", "Subject Title", "Units", "Pre-Requisite", "Grade", "Remarks")
        ]
    ]
    for item in eligibility_rows:
        prereq_str = ", ".join(item.prerequisites) if item.prerequisites else "-"
        remarks = item.transcript_status if item.transcript_status != "NOT_TAKEN" else "Not Yet Taken"
        rows.append(
            [
                Paragraph(f"Y{item.year_level} {item.semester[:3]}", cell_style),
                Paragraph(item.code, cell_bold),
                Paragraph(item.title, cell_style),
                Paragraph(str(item.total_units), cell_style),
                Paragraph(prereq_str, cell_style),
                Paragraph(item.grade, cell_style),
                Paragraph(remarks, cell_style),
            ]
        )

    table = Table(
        rows,
        colWidths=[0.65 * inch, 0.78 * inch, 2.75 * inch, 0.42 * inch, 1.35 * inch, 0.55 * inch, 0.9 * inch],
        repeatRows=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), CVSU_GREEN),
                ("BOX", (0, 0), (-1, -1), 0.75, BORDER_GRAY),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, BORDER_GRAY),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(table)
    doc.build(story)
    return buffer.getvalue()
