"""End-to-end integration tests for Auth, all 12 Pseudo-Portal Pages, Scheduler API, PDF Export & Adviser Workflow."""

from __future__ import annotations


def _login(client, username: str, password: str):
    return client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=False,
    )


def test_auth_and_all_pseudo_portal_pages(client):
    """Verify login rejection, Regular student portal pages, and Subjects Offered search filter."""
    # Invalid password rejected
    bad = _login(client, "202410001", "wrongpass")
    assert bad.status_code == 401
    assert "Invalid Student Number or Password" in bad.text

    # Regular student login
    ok = _login(client, "202410001", "demo123")
    assert ok.status_code == 303
    assert ok.headers["location"] == "/dashboard"

    for path in (
        "/dashboard",
        "/dashboard/news/116",
        "/profile",
        "/preregistration",
        "/subjects",
        "/grades",
        "/checklist",
        "/accountbalance",
        "/schedules",
        "/schedules?keyword=COSC+75A&field=code&day=T",
        "/announcement",
        "/dataprivacy",
        "/account",
    ):
        resp = client.get(path)
        assert resp.status_code == 200, f"Route {path} returned {resp.status_code}"

    # Regular student sees authentic unavailable notice on Pre-Registration
    prereg = client.get("/preregistration")
    assert "Pre-Registration is currently unavailable" in prereg.text

    # Reg Form & Checklist PDF downloads return valid PDF bytes
    reg_pdf = client.get("/subjects/regform")
    assert reg_pdf.status_code == 200
    assert reg_pdf.headers["content-type"] == "application/pdf"
    assert reg_pdf.content.startswith(b"%PDF-")

    cl_pdf = client.get("/checklist/download")
    assert cl_pdf.status_code == 200
    assert cl_pdf.content.startswith(b"%PDF-")


def test_full_irregular_scheduler_and_adviser_signoff_workflow(client):
    """
    End-to-end research paper flow:
      1. Irregular student Miguel logs in -> Pre-Registration shows AI Scheduler.
      2. Tests conflict & dynamic swap via /api/scheduler/solve.
      3. Solves conflict-free load -> exports Master Schedule PDF -> submits for Advising.
      4. Adviser logs in -> grants manual override for COSC 75A -> approves submission.
      5. Miguel logs back in -> Dashboard shows 'Enrolled' and Current Subjects has approved classes.
    """
    # 1. Login as Miguel (Irregular 3rd Yr)
    r = _login(client, "202410101", "demo123")
    assert r.status_code == 303

    prereg = client.get("/preregistration")
    assert prereg.status_code == 200
    assert "AI-Driven Enrollment Scheduler" in prereg.text

    state_res = client.get("/api/scheduler/state")
    assert state_res.status_code == 200
    state_data = state_res.json()
    assert len(state_data["eligibility"]) == 57

    # 2. Save availability matrix
    matrix = state_data["availability_matrix"]
    save_mat = client.post("/api/scheduler/availability", json={"matrix": matrix})
    assert save_mat.status_code == 200
    assert save_mat.json()["saved"] is True

    # 3. Attempting to schedule prerequisite-locked COSC 75A is blocked
    blocked_solve = client.post(
        "/api/scheduler/solve",
        json={"course_codes": ["COSC 75A", "COSC 80B"]},
    )
    assert blocked_solve.status_code == 200
    assert blocked_solve.json()["solver_status"] == "PREREQUISITE_BLOCKED"

    # 4. Solve eligible retake + 3rd-year courses
    clean_solve = client.post(
        "/api/scheduler/solve",
        json={
            "course_codes": ["MATH 2A", "COSC 70A", "COSC 80B", "COSC 85A", "COSC 101", "DCIT 26A", "DCIT 65A"],
            "max_units": 24,
            "max_solutions": 5,
        },
    )
    assert clean_solve.status_code == 200
    solve_data = clean_solve.json()
    assert solve_data["feasible"] is True
    assert len(solve_data["options"]) >= 1
    chosen_codes = [o["schedule_code"] for o in solve_data["options"][0]["offerings"]]

    # 5. Export Master Schedule PDF
    pdf_res = client.get(f"/api/scheduler/export-pdf?schedule_codes={','.join(chosen_codes)}")
    assert pdf_res.status_code == 200
    assert pdf_res.headers["content-type"] == "application/pdf"
    assert pdf_res.content.startswith(b"%PDF-")

    # 6. Submit to Academic Adviser
    sub_res = client.post(
        "/api/scheduler/submit",
        json={
            "schedule_codes": chosen_codes,
            "solver_time_ms": solve_data["solver_time_ms"],
            "idle_gap_hours": solve_data["options"][0]["idle_gap_hours"],
        },
    )
    assert sub_res.status_code == 200
    sub_id = sub_res.json()["submission_id"]
    assert sub_res.json()["status"] == "PENDING_ADVISING"

    # 7. Sign out and log in as Academic Adviser (ADV202601)
    client.get("/signout")
    adv_login = _login(client, "ADV202601", "adviser123")
    assert adv_login.status_code == 303
    assert adv_login.headers["location"] == "/adviser"

    adv_dash = client.get("/adviser")
    assert adv_dash.status_code == 200
    assert "DELA CRUZ, MIGUEL" in adv_dash.text

    miguel_id = state_data["student"]["id"]
    rev_page = client.get(f"/adviser/student/{miguel_id}")
    assert rev_page.status_code == 200
    assert "Approve &amp; Sign-Off" in rev_page.text

    # Grant manual prerequisite override for COSC 75A
    cosc75_id = next(e["course_id"] for e in state_data["eligibility"] if e["code"] == "COSC 75A")
    ov_res = client.post(
        f"/adviser/student/{miguel_id}/override",
        data={"course_id": str(cosc75_id), "reason": "Approved concurrent retake for BSCS demo"},
        follow_redirects=False,
    )
    assert ov_res.status_code == 303

    # Approve and sign off Miguel's submitted master schedule
    dec_res = client.post(
        f"/adviser/submission/{sub_id}/decision",
        data={"decision": "APPROVED", "adviser_notes": "Verified conflict-free schedule. Approved."},
        follow_redirects=False,
    )
    assert dec_res.status_code == 303

    # 8. Log back in as Miguel -> Dashboard shows Enrolled, Current Subjects lists 7 courses, COSC 75A Overridden
    client.get("/signout")
    _login(client, "202410101", "demo123")

    dash = client.get("/dashboard")
    assert "Enrolled" in dash.text

    subj = client.get("/subjects")
    assert subj.status_code == 200
    assert "COSC 80B" in subj.text
    assert "MATH 2A" in subj.text

    updated_state = client.get("/api/scheduler/state").json()
    cosc75_state = next(e for e in updated_state["eligibility"] if e["code"] == "COSC 75A")
    assert cosc75_state["eligibility"] == "OVERRIDDEN"


def test_evaluation_qr_standee_and_demo_reset(client):
    """Verify offline QR SVG, printable standee PDF, and one-click demo data reset."""
    # Offline QR SVG endpoint
    qr_res = client.get("/api/evaluation/qr.svg?url=https://forms.gle/cvsuTest2026")
    assert qr_res.status_code == 200
    assert "image/svg+xml" in qr_res.headers["content-type"]
    assert "<svg" in qr_res.text

    # Printable A4 Evaluation Standee PDF (single QR and dual QR modes)
    standee_res = client.get("/evaluation/standee.pdf?url=https://forms.gle/cvsuTest2026")
    assert standee_res.status_code == 200
    assert standee_res.headers["content-type"] == "application/pdf"
    assert standee_res.content.startswith(b"%PDF-")

    dual_standee = client.get(
        "/evaluation/standee.pdf?url=https://forms.gle/cvsuTest2026&portal_url=http://192.168.1.5:8000/login"
    )
    assert dual_standee.status_code == 200
    assert dual_standee.content.startswith(b"%PDF-")

    # Login as Miguel, mutate transcript, then trigger one-click POST /demo/reset
    _login(client, "202410101", "demo123")
    upd = client.post(
        "/api/scheduler/transcript/update",
        json={"updates": [{"course_code": "MATH 2A", "status": "PASSED", "grade": "1.75"}]},
    )
    assert upd.status_code == 200

    reset_res = client.post("/demo/reset", follow_redirects=False)
    assert reset_res.status_code == 303
    assert reset_res.headers["location"] == "/dashboard"

    # Session remains valid and MATH 2A is restored back to FAILED (COSC 75A locked again)
    state_after = client.get("/api/scheduler/state").json()
    cosc75 = next(e for e in state_after["eligibility"] if e["code"] == "COSC 75A")
    assert cosc75["eligibility"] == "LOCKED"
