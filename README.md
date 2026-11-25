# CvSU-Imus Student Portal & AI-Driven Enrollment Scheduler (BSCS)

A 1:1 pseudo student portal recreating the **Cavite State University – Imus Campus** Student Portal, integrated with an **AI-Driven Enrollment Scheduler for Irregular BSCS Students**.

Built with **FastAPI**, **SQLAlchemy (SQLite)**, **Google OR-Tools CP-SAT**, **ReportLab**, and offline **Bootstrap 5.3.2**.

## Key Features

- **1:1 CvSU-Imus Student Portal Replica:** Sign In, Dashboard, My Profile, Current Subjects, Grades, Curriculum Checklist, Subjects Offered (with search/day filters), Account Balance, Class Announcements, Data Privacy (RA 10173), Account Settings, and Light/Dark Mode.
- **3-Step Irregular Pre-Registration Scheduler:**
  1. **Select Subjects** — automatically cross-checked against the 57-course BSCS Prerequisite DAG (`Eligible`, `Retake`, `Overridden`, or `Locked`).
  2. **Weekly Availability Matrix** — interactive Monday–Saturday (7:00 AM–8:00 PM) click-and-drag time-slot toggle grid with quick presets.
  3. **Master Schedule & Advising** — Google OR-Tools CP-SAT solver generating ranked conflict-free schedules, Conflict Report Log, Dynamic Section-Swapping recommendations, Weekly Timetable Visualizer, PDF Export, and Academic Adviser submission.
- **Academic / Registration Adviser Review (`/adviser`):** Inspect irregular student standing, grant manual prerequisite overrides with justification, and approve or request revisions on submitted schedules.
- **Evaluation Kit (`evaluation/`):** Includes an ISO/IEC 25010 Google Apps Script form builder, in-portal QR Code modal, printable A4 standee PDF generator, and one-click Demo Reset tool.

---

## Installation & Setup

### Prerequisites
- **Python 3.11+** ([python.org/downloads](https://www.python.org/downloads/) — on Windows, check **"Add Python to PATH"** during install)
- **Git**

### Windows (PowerShell / Command Prompt)

```powershell
git clone https://github.com/trentquacks/cvsu-portal-scheduler.git
cd cvsu-portal-scheduler

python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

uvicorn app.main:app --reload
```

### Linux / macOS

```bash
git clone https://github.com/trentquacks/cvsu-portal-scheduler.git
cd cvsu-portal-scheduler

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

uvicorn app.main:app --reload
```

Open **http://127.0.0.1:8000** in your browser.  
*(The SQLite database `data/cvsu_portal.db` is created and seeded automatically on first launch — no manual database setup is needed.)*

### Optional: Allow Campus Wi-Fi / Hotspot Access (Multi-Device Testing)
To let testers access the portal from phones or laptops on the same Wi-Fi/hotspot:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Then open `http://<your-computer-local-ip>:8000` on other devices.

---

## Pre-Seeded BSCS Demo Accounts

| Account ID | Password | Role / Classification | Scenario |
| :--- | :--- | :--- | :--- |
| `202410101` | `demo123` | Irregular Student (3rd Year) | Failed `MATH 2A` & `COSC 70A` (locks `MATH 3A` & `COSC 75A`) |
| `202310205` | `demo123` | Irregular Student (3rd Year) | Working Student (weekday mornings 7:00 AM – 1:00 PM blocked) |
| `202410308` | `demo123` | Irregular Student (2nd Year) | Transferee / Shiftee with credited GE/PE subjects |
| `202410001` | `demo123` | Regular Student (3rd Year) | Block-enrolled `BSCS-3C` reference account |
| `ADV202601` | `adviser123` | Academic / Registration Adviser | Reviews submitted schedules, grants overrides, and approves sign-off |

> Switch accounts instantly from the Sign In page (**Demo Accounts**) or via the top-right grid menu inside the portal. Use **Presenter / Evaluation Tools → Reset All Demo Data** anytime to restore fresh defaults between testers.

---

## Running Tests

With your virtual environment activated:

```bash
pytest -v
```
