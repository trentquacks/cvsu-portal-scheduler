"""Offline QR Code SVG & Printable CvSU-Imus Evaluation Standee PDF generator (ReportLab)."""

from __future__ import annotations

import io
from xml.sax.saxutils import escape

from reportlab.graphics import renderPDF, renderSVG
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing, Rect
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

CVSU_GREEN = colors.HexColor("#00a15d")
CVSU_DARK = colors.HexColor("#212427")
CVSU_MUTED = colors.HexColor("#4f5b6b")
CVSU_LIGHT_BG = colors.HexColor("#f3f6f9")
CVSU_BORDER = colors.HexColor("#dde3ec")


def _build_qr_drawing(url: str, size: int = 240, pad: int = 14) -> Drawing:
    """Build a crisp high-contrast QR Code Drawing with a guaranteed white quiet zone."""
    inner = max(60, size - 2 * pad)
    widget = qr.QrCodeWidget(url, barLevel="M", barBorder=0)
    x1, y1, x2, y2 = widget.getBounds()
    w = max(1.0, x2 - x1)
    h = max(1.0, y2 - y1)

    drawing = Drawing(size, size)
    # Explicit white background keeps QR scannable even inside Dark Mode modals
    drawing.add(Rect(0, 0, size, size, fillColor=colors.white, strokeColor=None))

    qr_group = Drawing(
        inner,
        inner,
        transform=[inner / w, 0, 0, inner / h, pad - x1 * (inner / w), pad - y1 * (inner / h)],
    )
    qr_group.add(widget)
    drawing.add(qr_group)
    return drawing


def generate_qr_svg(url: str, size: int = 240) -> str:
    """Render an offline ISO/IEC 18004 QR code as an SVG string."""
    clean_url = url.strip() or "https://forms.gle/your-evaluation-form"
    drawing = _build_qr_drawing(clean_url, size=size, pad=14)
    return renderSVG.drawToString(drawing)


def generate_evaluation_standee_pdf(form_url: str, portal_url: str = "") -> bytes:
    """Generate a print-ready A4 1-page Evaluation Standee PDF with wrapped Task Steps + QR Code."""
    clean_form_url = form_url.strip() or "https://forms.gle/your-evaluation-form"
    clean_portal_url = portal_url.strip()

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    page_w, page_h = A4

    # 1. Top CvSU Green Header Banner
    banner_h = 34 * mm
    c.setFillColor(CVSU_GREEN)
    c.rect(0, page_h - banner_h, page_w, banner_h, fill=1, stroke=0)

    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 15)
    c.drawCentredString(page_w / 2, page_h - 13.5 * mm, "CAVITE STATE UNIVERSITY - IMUS CAMPUS")
    c.setFont("Helvetica", 10.5)
    c.drawCentredString(page_w / 2, page_h - 20.5 * mm, "Department of Computer Studies | BSCS System Evaluation")
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(
        page_w / 2,
        page_h - 28 * mm,
        "AI-Driven Enrollment Scheduler for Irregular Students",
    )

    # 2. Quick Hands-On Testing Guide Box (auto-wrapped Paragraphs strictly inside inner margins)
    box_margin = 16 * mm
    box_pad_x = 8 * mm
    box_pad_y = 7 * mm
    box_w = page_w - 2 * box_margin
    inner_w = box_w - 2 * box_pad_x
    box_top = page_h - banner_h - 10 * mm

    step_style = ParagraphStyle(
        "StandeeStep",
        fontName="Helvetica",
        fontSize=9.4,
        leading=13.5,
        textColor=CVSU_MUTED,
        leftIndent=0,
        spaceAfter=0,
    )

    steps = [
        (
            "1. Sign In (Demo Accounts):",
            "Click Demo Accounts and choose an Irregular Student (Miguel, Clarisse, or Paolo) or Academic Adviser (Prof. Bautista).",
        ),
        (
            "2. Explore the Portal:",
            "Check Dashboard, Grades, Curriculum Checklist, and Subjects Offered to verify familiarity with the CvSU-Imus portal.",
        ),
        (
            "3. Run AI Pre-Registration:",
            "Step 1: Select eligible subjects -> Step 2: Block any unavailable hours -> Step 3: Generate Conflict-Free Schedule.",
        ),
        (
            "4. Inspect Output & Swaps:",
            "Review the Weekly Timetable, export Master Schedule (PDF), or try Run Conflict & Swap Demo from the topbar grid menu.",
        ),
        (
            "5. Submit & Evaluate:",
            "Submit the schedule to the Adviser (Advisers: review, test override & approve), then scan the QR code below.",
        ),
    ]

    # Measure all wrapped paragraphs first so the box height always fits cleanly with zero overflow
    rendered_steps: list[tuple[Paragraph, float]] = []
    step_gap = 3.2 * mm
    content_h = 8 * mm  # Title + gap under title
    for lead, body in steps:
        markup = f'<font color="#212427"><b>{escape(lead)}</b></font> {escape(body)}'
        p = Paragraph(markup, step_style)
        _, ph = p.wrap(inner_w, 100 * mm)
        rendered_steps.append((p, ph))
        content_h += ph + step_gap

    box_h = content_h - step_gap + 2 * box_pad_y

    c.setFillColor(CVSU_LIGHT_BG)
    c.setStrokeColor(CVSU_BORDER)
    c.setLineWidth(0.9)
    c.roundRect(box_margin, box_top - box_h, box_w, box_h, 4 * mm, fill=1, stroke=1)

    cursor_y = box_top - box_pad_y - 3.5 * mm
    c.setFillColor(CVSU_GREEN)
    c.setFont("Helvetica-Bold", 11.5)
    c.drawString(box_margin + box_pad_x, cursor_y, "Quick Hands-On Testing Guide (3 - 5 Minutes)")

    cursor_y -= 4.5 * mm
    for p, ph in rendered_steps:
        cursor_y -= ph
        p.drawOn(c, box_margin + box_pad_x, cursor_y)
        cursor_y -= step_gap

    # 3. QR Code Section (centered safely between the guide box and footer)
    footer_top = 26 * mm
    available_top = box_top - box_h - 10 * mm

    url_font_size = 8.0 if len(clean_form_url) > 65 else 9.5
    url_style = ParagraphStyle(
        "StandeeUrl",
        fontName="Helvetica-Bold",
        fontSize=url_font_size,
        leading=url_font_size + 3,
        textColor=CVSU_GREEN,
        alignment=1,  # centered
    )

    if clean_portal_url:
        qr_size = 62 * mm
        left_cx = page_w * 0.28
        right_cx = page_w * 0.72
        heading_y = available_top - 4 * mm

        for cx, heading, sub, target_url in (
            (left_cx, "1. OPEN SCHEDULER PORTAL", "Scan to access the web prototype", clean_portal_url),
            (right_cx, "2. EVALUATION SURVEY", "Scan after testing (ISO/IEC 25010)", clean_form_url),
        ):
            c.setFillColor(CVSU_DARK)
            c.setFont("Helvetica-Bold", 10.5)
            c.drawCentredString(cx, heading_y, heading)
            c.setFillColor(CVSU_MUTED)
            c.setFont("Helvetica", 8.8)
            c.drawCentredString(cx, heading_y - 5.2 * mm, sub)

            frame_x = cx - qr_size / 2
            frame_y = heading_y - 10 * mm - qr_size
            c.setFillColor(colors.white)
            c.setStrokeColor(CVSU_GREEN)
            c.setLineWidth(1.5)
            c.roundRect(frame_x - 3 * mm, frame_y - 3 * mm, qr_size + 6 * mm, qr_size + 6 * mm, 3 * mm, fill=1, stroke=1)

            drawing = _build_qr_drawing(target_url, size=int(qr_size), pad=4)
            renderPDF.draw(drawing, c, frame_x, frame_y)

            p_url = Paragraph(escape(target_url), url_style)
            uw = 78 * mm
            _, uh = p_url.wrap(uw, 20 * mm)
            p_url.drawOn(c, cx - uw / 2, frame_y - 6 * mm - uh)
    else:
        qr_size = 74 * mm
        cx = page_w / 2
        # Vertically center the QR block cleanly in the remaining space above the footer
        total_qr_block_h = 14 * mm + qr_size + 22 * mm
        block_top = footer_top + (available_top - footer_top + total_qr_block_h) / 2

        c.setFillColor(CVSU_DARK)
        c.setFont("Helvetica-Bold", 13.5)
        c.drawCentredString(cx, block_top - 4 * mm, "SCAN TO ANSWER THE EVALUATION SURVEY")
        c.setFillColor(CVSU_MUTED)
        c.setFont("Helvetica", 9.8)
        c.drawCentredString(cx, block_top - 10.5 * mm, "ISO/IEC 25010 Software Quality Evaluation Form (3 - 5 minutes)")

        frame_x = cx - qr_size / 2
        frame_y = block_top - 17 * mm - qr_size
        c.setFillColor(colors.white)
        c.setStrokeColor(CVSU_GREEN)
        c.setLineWidth(2)
        c.roundRect(frame_x - 4 * mm, frame_y - 4 * mm, qr_size + 8 * mm, qr_size + 8 * mm, 4 * mm, fill=1, stroke=1)

        drawing = _build_qr_drawing(clean_form_url, size=int(qr_size), pad=4)
        renderPDF.draw(drawing, c, frame_x, frame_y)

        c.setFillColor(CVSU_MUTED)
        c.setFont("Helvetica", 9.2)
        c.drawCentredString(cx, frame_y - 10 * mm, "Or open directly in your browser:")

        p_url = Paragraph(escape(clean_form_url), url_style)
        uw = box_w
        _, uh = p_url.wrap(uw, 20 * mm)
        p_url.drawOn(c, cx - uw / 2, frame_y - 13.5 * mm - uh)

    # 4. Footer Privacy Notice
    c.setStrokeColor(CVSU_BORDER)
    c.setLineWidth(0.75)
    c.line(box_margin, 23 * mm, page_w - box_margin, 23 * mm)
    c.setFillColor(CVSU_MUTED)
    c.setFont("Helvetica", 8.5)
    c.drawCentredString(
        page_w / 2,
        17.5 * mm,
        "All evaluation responses are strictly confidential in compliance with Republic Act No. 10173 (Data Privacy Act of 2012).",
    )
    c.drawCentredString(
        page_w / 2,
        12.5 * mm,
        "Cavite State University - Imus Campus | BS Computer Science Research Evaluation (N = 50)",
    )

    c.showPage()
    c.save()
    return buf.getvalue()
