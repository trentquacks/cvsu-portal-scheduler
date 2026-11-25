# 50-Respondent ISO/IEC 25010 Evaluation Kit (CvSU–Imus BSCS)

Everything needed to launch your **Google Form**, **Live QR Code**, and **Printable Testing Standee** in minutes.

## Step 1: Auto-Create the Google Form (10 Seconds)
1. Open [script.google.com](https://script.google.com) and click **New project**.
2. Open [create_evaluation_form.gs](create_evaluation_form.gs), copy the entire script, and paste it into the editor.
3. Click **Save**, select `createCvsuEvaluationForm`, and click **Run** (approve Google Forms & Sheets permissions when asked).
4. From the **Execution Log**, open the **Form Edit URL** and click **Publish / Send → Link icon → Shorten URL** to copy your short `https://forms.gle/...` link.
5. Open the **Linked Sheet URL** — it already includes a **`Chapter 4 Summary`** tab with a live `35 Student / 10 Adviser / 5 IT Professional` quota tracker and Chapter 3 Table 3 verbal interpretation formulas.

## Step 2: Set Your Google Form QR Code (Two Ways)
- **Inside the Live Portal (Zero Restart Needed):** Click the topbar **Grid Icon → Evaluation Survey (QR Code)**, paste your `https://forms.gle/...` URL, click **Update QR**, and click **Download Printable Standee (PDF)**.
- **Permanent Default:** Paste your `https://forms.gle/...` link into `EVALUATION_FORM_URL` in `app/config.py`, or run the CLI generator:
  ```bash
  .venv/bin/python evaluation/generate_qr.py "https://forms.gle/YOUR_SHORT_CODE"
  ```
  *(Optional: pass `--portal-url "http://<your-lan-ip>:8000/login"` to put both System Access QR and Evaluation Survey QR side-by-side on the printable A4 standee!)*

## Step 3: Resetting Between Live Testers
Click the topbar **Grid Icon → Reset All Demo Data** to cleanly restore all 5 demo accounts, submissions, overrides, simulated transcripts, and availability matrices back to their starting defaults in one click.
