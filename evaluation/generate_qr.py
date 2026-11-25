"""CLI helper to generate standalone QR Code SVG and Printable A4 Evaluation Standee PDF.

Usage:
    .venv/bin/python evaluation/generate_qr.py "https://forms.gle/YOUR_SHORT_CODE"
    .venv/bin/python evaluation/generate_qr.py "https://forms.gle/YOUR_SHORT_CODE" --portal-url "http://192.168.1.10:8000/login"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.services.evaluation_tools import generate_evaluation_standee_pdf, generate_qr_svg


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate QR Code SVG and A4 Printable Standee PDF.")
    parser.add_argument("form_url", help="Shortened Google Form URL (e.g., https://forms.gle/xxxxx)")
    parser.add_argument("--portal-url", default="", help="Optional LAN or tunnel URL for the portal demo")
    parser.add_argument("--out-dir", default=str(ROOT_DIR / "evaluation" / "output"), help="Output directory")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    svg_path = out_dir / "evaluation_survey_qr.svg"
    pdf_path = out_dir / "cvsu_evaluation_standee.pdf"

    svg_path.write_text(generate_qr_svg(args.form_url, size=320), encoding="utf-8")
    pdf_path.write_bytes(generate_evaluation_standee_pdf(args.form_url, portal_url=args.portal_url))

    print(f"Saved QR Code SVG:      {svg_path}")
    print(f"Saved Printable PDF:    {pdf_path}")


if __name__ == "__main__":
    main()
