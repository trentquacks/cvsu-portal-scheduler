"""Application configuration settings."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
APP_DIR = BASE_DIR / "app"
DATA_DIR = BASE_DIR / "data"
SNAPSHOTS_DIR = DATA_DIR / "snapshots"
DATABASE_PATH = DATA_DIR / "cvsu_portal.db"

DATABASE_URL = f"sqlite:///{DATABASE_PATH}"
SECRET_KEY = "cvsu-imus-bscs-enrollment-scheduler-demo-secret-key"

# Set your shortened Google Form URL (e.g., "https://forms.gle/xxxxxxxx") once created
EVALUATION_FORM_URL = os.getenv("EVALUATION_FORM_URL", "https://docs.google.com/forms/d/e/1FAIpQLSeYSM0nSxSwGJqOZ0WxP084LRovo97zn5wFG53934_w9WdlDw/viewform")

CURRENT_ACADEMIC_YEAR = "2026-2027"
CURRENT_SEMESTER = "FIRST"

DAYS = ["M", "T", "W", "TH", "F", "S"]
DAY_LABELS = {
    "M": "Monday",
    "T": "Tuesday",
    "W": "Wednesday",
    "TH": "Thursday",
    "F": "Friday",
    "S": "Saturday",
}
START_HOUR = 7   # 7:00 AM
END_HOUR = 20    # 8:00 PM (13 hourly blocks: 7..19 representing 07:00-08:00 .. 19:00-20:00)
HOURS = list(range(START_HOUR, END_HOUR))
MAX_UNITS_DEFAULT = 24
