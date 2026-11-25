/**
 * AI-Driven Enrollment Scheduler Client Application (Pre-Registration Module)
 * Option A 3-Step Workflow:
 *   Step 1: Select Subjects (auto-validated against official BSCS Prerequisite DAG)
 *   Step 2: Weekly Availability Matrix (optional blocked hours) -> Generate Schedule
 *   Step 3: Master Schedule, Conflict Report Log, Dynamic Section Swapping, PDF & Advising
 * Plus Presenter Sandbox Modal (Transcript DAG Simulator & Conflict Demo) via Topbar Demo Menu.
 */
(function () {
  "use strict";

  const DAYS = ["M", "T", "W", "TH", "F", "S"];
  const DAY_SHORT = { M: "Mon", T: "Tue", W: "Wed", TH: "Thu", F: "Fri", S: "Sat" };
  const START_HOUR = 7;
  const HOUR_COUNT = 13;

  const state = {
    student: null,
    eligibility: [],
    offeringsByCourse: {},
    matrix: null,
    matrixWidget: null,
    selectedCourses: new Set(),
    pinnedOfferings: {},
    showPinColumn: false,
    maxUnits: 24,
    lastSolveResult: null,
    activeOptionIndex: 0,
    swapHistory: [],
    latestSubmission: null,
    demoPreset: null,
    transcriptFilter: "ALL",
  };

  function el(id) {
    return document.getElementById(id);
  }

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text == null ? "" : String(text);
    return div.innerHTML;
  }

  function showToast(message, type) {
    const box = el("schedulerAlertBanner");
    if (!box) return;
    box.className = `alert alert-${type || "info"} alert-dismissible fade show`;
    box.innerHTML = `
      <span>${escapeHtml(message)}</span>
      <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    box.classList.remove("d-none");
  }

  function switchToTab(tabButtonId) {
    const btn = el(tabButtonId);
    if (btn && window.bootstrap) {
      window.bootstrap.Tab.getOrCreateInstance(btn).show();
    }
  }

  function openTranscriptModal() {
    const modalEl = el("demoTranscriptModal");
    if (modalEl && window.bootstrap) {
      renderTranscriptModal();
      window.bootstrap.Modal.getOrCreateInstance(modalEl).show();
    }
  }

  async function apiFetch(url, options) {
    const res = await fetch(url, Object.assign({ headers: { "Content-Type": "application/json" } }, options || {}));
    const data = await res.json().catch(function () {
      return {};
    });
    if (!res.ok) {
      throw new Error(data.detail || `Request failed with status ${res.status}`);
    }
    return data;
  }

  // ---------------------------------------------------------------------------
  // Presenter Sandbox Modal: Transcript & Prerequisite DAG Simulator
  // ---------------------------------------------------------------------------
  function renderTranscriptModal() {
    const tbody = el("transcriptTableBody");
    if (!tbody) return;

    const counts = { COMPLETED: 0, ELIGIBLE: 0, OVERRIDDEN: 0, LOCKED: 0 };
    state.eligibility.forEach(function (item) {
      if (counts[item.eligibility] !== undefined) counts[item.eligibility] += 1;
    });

    if (el("statCompletedCount")) el("statCompletedCount").textContent = counts.COMPLETED;
    if (el("statEligibleCount")) el("statEligibleCount").textContent = counts.ELIGIBLE + counts.OVERRIDDEN;
    if (el("statLockedCount")) el("statLockedCount").textContent = counts.LOCKED;

    const filter = state.transcriptFilter;
    const rows = state.eligibility.filter(function (item) {
      if (filter === "ALL") return true;
      if (filter === "ELIGIBLE") return item.eligibility === "ELIGIBLE" || item.eligibility === "OVERRIDDEN";
      if (filter === "LOCKED") return item.eligibility === "LOCKED";
      if (filter === "FAILED") return item.transcript_status === "FAILED";
      return true;
    });

    tbody.innerHTML = rows
      .map(function (item) {
        let badgeHtml = "";
        if (item.eligibility === "COMPLETED") {
          badgeHtml = '<span class="badge bg-success">Completed</span>';
        } else if (item.eligibility === "ELIGIBLE") {
          badgeHtml = '<span class="badge bg-primary">Eligible</span>';
        } else if (item.eligibility === "OVERRIDDEN") {
          badgeHtml = `<span class="badge bg-info" title="${escapeHtml(item.override_reason || "")}">Overridden</span>`;
        } else {
          badgeHtml = '<span class="badge bg-danger">Locked</span>';
        }

        const prereqText = item.prerequisites.length
          ? item.prerequisites
              .map(function (p) {
                const isMissing = item.missing_prerequisites.includes(p);
                return isMissing
                  ? `<span class="text-danger fw-semibold">${escapeHtml(p)}</span>`
                  : `<span class="text-success">${escapeHtml(p)}</span>`;
              })
              .join(", ")
          : '<span class="text-muted">-</span>';

        const offeredBadge = item.offered_this_sem
          ? `<span class="badge bg-success">${item.open_offerings_count} open</span>`
          : '<span class="text-muted fs-12">Not offered</span>';

        return `
          <tr>
            <td class="text-center text-nowrap">${escapeHtml(item.code)}</td>
            <td>
              <div>${escapeHtml(item.title)}</div>
              ${item.override_reason ? `<div class="fs-12 text-info">Adviser Override: ${escapeHtml(item.override_reason)}</div>` : ""}
            </td>
            <td class="text-center text-nowrap">Y${item.year_level} ${escapeHtml(item.semester.slice(0, 3))}</td>
            <td class="text-center">${item.total_units.toFixed(2)}</td>
            <td class="text-center">${prereqText}</td>
            <td>
              <select class="form-select form-select-sm transcript-status-select" data-course="${escapeHtml(item.code)}" style="min-width:120px;">
                <option value="NOT_TAKEN" ${item.transcript_status === "NOT_TAKEN" ? "selected" : ""}>Not Taken</option>
                <option value="PASSED" ${item.transcript_status === "PASSED" ? "selected" : ""}>Passed</option>
                <option value="CREDITED" ${item.transcript_status === "CREDITED" ? "selected" : ""}>Credited</option>
                <option value="FAILED" ${item.transcript_status === "FAILED" ? "selected" : ""}>Failed</option>
              </select>
            </td>
            <td class="text-center">${badgeHtml}</td>
            <td class="text-center">${offeredBadge}</td>
          </tr>
        `;
      })
      .join("");

    tbody.querySelectorAll(".transcript-status-select").forEach(function (selectEl) {
      selectEl.addEventListener("change", async function () {
        const courseCode = selectEl.dataset.course;
        const newStatus = selectEl.value;
        try {
          const data = await apiFetch("/api/scheduler/transcript/update", {
            method: "POST",
            body: JSON.stringify({
              updates: [{ course_code: courseCode, status: newStatus, grade: "-" }],
            }),
          });
          state.eligibility = data.eligibility;
          const updatedItem = state.eligibility.find((e) => e.code === courseCode);
          if (updatedItem && (updatedItem.eligibility === "COMPLETED" || updatedItem.eligibility === "LOCKED")) {
            state.selectedCourses.delete(courseCode);
            delete state.pinnedOfferings[courseCode];
          }
          // Also drop any course that became newly locked by a cascading failure
          state.eligibility.forEach(function (e) {
            if (e.eligibility === "LOCKED" || e.eligibility === "COMPLETED") {
              state.selectedCourses.delete(e.code);
              delete state.pinnedOfferings[e.code];
            }
          });
          renderTranscriptModal();
          renderCourseSelector();
          showToast(
            `Simulated ${courseCode} as ${newStatus}. BSCS prerequisite eligibility updated automatically.`,
            "success"
          );
        } catch (err) {
          showToast(err.message, "danger");
        }
      });
    });
  }

  // ---------------------------------------------------------------------------
  // Step 1: Select Subjects (Spacious, Calm Table + Optional Section Pinning)
  // ---------------------------------------------------------------------------
  function getOfferedEligibilityItems() {
    return state.eligibility.filter(function (item) {
      return item.offered_this_sem && item.eligibility !== "COMPLETED";
    });
  }

  function computeSelectedUnits() {
    let total = 0;
    state.eligibility.forEach(function (item) {
      if (state.selectedCourses.has(item.code)) {
        total += item.total_units;
      }
    });
    return total;
  }

  function updateUnitCounter() {
    const total = computeSelectedUnits();
    const count = state.selectedCourses.size;
    if (el("selectedCourseCount")) el("selectedCourseCount").textContent = count;
    if (el("selectedUnitsCount")) el("selectedUnitsCount").textContent = total;
    const badge = el("unitCapBadge");
    if (badge) {
      badge.className = total > state.maxUnits ? "badge bg-danger fs-12" : "badge bg-primary fs-12";
      badge.textContent = `${total} / ${state.maxUnits} Units`;
    }
  }

  function syncPinColumnVisibility() {
    document.querySelectorAll(".pin-section-col").forEach(function (node) {
      node.classList.toggle("d-none", !state.showPinColumn);
    });
    const sw = el("togglePinSectionsSwitch");
    if (sw) sw.checked = state.showPinColumn;
  }

  function renderCourseSelector() {
    const tbody = el("courseSelectorBody");
    if (!tbody) return;

    const items = getOfferedEligibilityItems();
    const pinColClass = state.showPinColumn ? "pin-section-col" : "d-none pin-section-col";

    tbody.innerHTML = items
      .map(function (item) {
        const isChecked = state.selectedCourses.has(item.code);
        const isLocked = item.eligibility === "LOCKED";
        const offerings = state.offeringsByCourse[item.code] || [];
        const pinnedVal = state.pinnedOfferings[item.code] || "";

        const optionsHtml = [
          '<option value="">Auto-Optimize (Any Open Section)</option>',
          ...offerings.map(function (off) {
            const slotsStr = off.meetings
              .map(function (m) {
                return `${m.day} ${m.time_range_24h}`;
              })
              .join(", ");
            const capTag = off.is_open ? `${off.seats_remaining} seats` : "CLOSED";
            const selectedAttr = pinnedVal === off.schedule_code ? "selected" : "";
            return `<option value="${escapeHtml(off.schedule_code)}" ${selectedAttr}>${escapeHtml(off.section_name)} | ${escapeHtml(slotsStr)} [${capTag}]</option>`;
          }),
        ].join("");

        let statusBadge = "";
        if (item.eligibility === "ELIGIBLE") {
          statusBadge =
            item.transcript_status === "FAILED"
              ? '<span class="badge bg-warning">Retake</span>'
              : '<span class="badge bg-success">Eligible</span>';
        } else if (item.eligibility === "OVERRIDDEN") {
          statusBadge = `<span class="badge bg-info" title="${escapeHtml(item.override_reason || "")}">Overridden</span>`;
        } else {
          statusBadge = `<span class="badge bg-danger">Locked</span><div class="fs-11 text-danger mt-1">Needs: ${escapeHtml(item.missing_prerequisites.join(", "))}</div>`;
        }

        return `
          <tr class="course-select-row ${isChecked ? "is-selected" : ""} ${isLocked ? "is-locked" : ""}">
            <td class="text-center">
              <input
                type="checkbox"
                class="form-check-input course-checkbox"
                data-code="${escapeHtml(item.code)}"
                ${isChecked ? "checked" : ""}
                ${isLocked ? 'disabled title="Missing required prerequisite(s)"' : ""}
              >
            </td>
            <td class="text-center text-nowrap">${escapeHtml(item.code)}</td>
            <td>${escapeHtml(item.title)}</td>
            <td class="text-center text-nowrap">${item.total_units.toFixed(2)}</td>
            <td class="text-center">${statusBadge}</td>
            <td class="${pinColClass}">
              <select class="form-select form-select-sm pin-section-select" data-code="${escapeHtml(item.code)}" ${!isChecked || isLocked ? "disabled" : ""}>
                ${optionsHtml}
              </select>
            </td>
          </tr>
        `;
      })
      .join("");

    tbody.querySelectorAll(".course-checkbox").forEach(function (cb) {
      cb.addEventListener("change", function () {
        const code = cb.dataset.code;
        if (cb.checked) {
          state.selectedCourses.add(code);
        } else {
          state.selectedCourses.delete(code);
          delete state.pinnedOfferings[code];
        }
        renderCourseSelector();
        updateUnitCounter();
      });
    });

    tbody.querySelectorAll(".pin-section-select").forEach(function (sel) {
      sel.addEventListener("change", function () {
        const code = sel.dataset.code;
        if (sel.value) {
          state.pinnedOfferings[code] = sel.value;
        } else {
          delete state.pinnedOfferings[code];
        }
      });
    });

    syncPinColumnVisibility();
    updateUnitCounter();
  }

  // ---------------------------------------------------------------------------
  // Step 2: Weekly Availability Matrix
  // ---------------------------------------------------------------------------
  function updateMatrixStats(stats) {
    if (el("matrixAvailableHours")) el("matrixAvailableHours").textContent = stats.available;
    if (el("matrixBlockedHours")) el("matrixBlockedHours").textContent = stats.blocked;
  }

  async function saveAvailabilityMatrix(silent) {
    const matrixData = state.matrixWidget ? state.matrixWidget.getMatrix() : state.matrix;
    const res = await apiFetch("/api/scheduler/availability", {
      method: "POST",
      body: JSON.stringify({ matrix: matrixData }),
    });
    state.matrix = res.matrix;
    if (!silent) {
      showToast(
        `Availability matrix saved (${res.available_hours} available hrs, ${res.blocked_hours} blocked hrs).`,
        "success"
      );
    }
    return res;
  }

  function initMatrixTab() {
    const mount = el("availabilityMatrixContainer");
    if (!mount || !window.AvailabilityToggleMatrix) return;

    state.matrixWidget = new window.AvailabilityToggleMatrix(
      mount,
      state.matrix,
      function (updatedMatrix, stats) {
        state.matrix = updatedMatrix;
        updateMatrixStats(stats);
      }
    );
    updateMatrixStats(state.matrixWidget.getStats());

    document.querySelectorAll("[data-matrix-preset]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        state.matrixWidget.applyPreset(btn.dataset.matrixPreset);
      });
    });

    const saveBtn = el("saveMatrixBtn");
    if (saveBtn) {
      saveBtn.addEventListener("click", async function () {
        saveBtn.disabled = true;
        try {
          await saveAvailabilityMatrix(false);
        } catch (err) {
          showToast(err.message, "danger");
        } finally {
          saveBtn.disabled = false;
        }
      });
    }
  }

  // ---------------------------------------------------------------------------
  // Step 3: Solver Diagnostics, Conflict Report Log, Dynamic Swaps & Timetable
  // ---------------------------------------------------------------------------
  function renderSolverOutput(result) {
    const panel = el("solverDiagnosticsPanel");
    if (!panel) return;

    if (!result) {
      panel.classList.add("d-none");
      panel.innerHTML = "";
      return;
    }

    panel.classList.remove("d-none");

    const hasConflicts = result.conflict_logs && result.conflict_logs.length > 0;
    const hasSwaps = result.swap_recommendations && result.swap_recommendations.length > 0;
    const hasRelaxation = Boolean(result.relaxation_suggestion);

    // Calm compact status bar when feasible with zero conflicts
    if (result.feasible && !hasConflicts && !hasSwaps) {
      panel.innerHTML = `
        <div class="alert alert-light d-flex flex-wrap align-items-center justify-content-between gap-2 mb-0">
          <div class="d-flex align-items-center gap-2 flex-wrap">
            <span class="badge bg-success">${escapeHtml(result.solver_status)}</span>
            <span>${escapeHtml(result.message)}</span>
            <span class="text-muted fs-12">(Solved in ${Number(result.solver_time_ms).toFixed(2)} ms)</span>
          </div>
          <div class="d-flex gap-2">
            <button type="button" class="btn btn-light btn-sm" id="diagBackSubjectsBtn">Modify Subjects</button>
            <button type="button" class="btn btn-light btn-sm" id="diagBackMatrixBtn">Edit Availability</button>
          </div>
        </div>
      `;
      bindDiagNavButtons();
      return;
    }

    const statusBadgeClass = result.feasible ? "bg-success" : "bg-danger";
    let html = `
      <div class="border rounded p-3">
        <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 pb-3 mb-3 border-bottom">
          <div class="d-flex align-items-center gap-2 flex-wrap">
            <span class="badge ${statusBadgeClass}">${escapeHtml(result.solver_status)}</span>
            <span class="fw-semibold">${escapeHtml(result.message)}</span>
          </div>
          <div class="d-flex align-items-center gap-2">
            <span class="fs-12 text-muted">CP-SAT Time: <strong>${Number(result.solver_time_ms).toFixed(2)} ms</strong></span>
            <button type="button" class="btn btn-light btn-sm" id="diagBackSubjectsBtn">Modify Subjects</button>
            <button type="button" class="btn btn-light btn-sm" id="diagBackMatrixBtn">Edit Availability</button>
          </div>
        </div>
    `;

    // Conflict Report Log
    if (hasConflicts) {
      html += `
        <h6 class="fw-semibold text-danger mb-2">
          <i class="fa fa-exclamation-triangle me-1"></i>Conflict Report Log (${result.conflict_logs.length})
        </h6>
        <div class="mb-3">
          ${result.conflict_logs
            .map(function (c) {
              const sevClass = c.severity === "WARNING" ? "severity-warning" : "";
              return `
                <div class="conflict-log-item ${sevClass}">
                  <div class="d-flex justify-content-between align-items-center mb-1">
                    <span class="badge bg-danger">${escapeHtml(c.conflict_type)}</span>
                    <span class="fs-12 text-muted">${escapeHtml((c.course_codes || []).join(" / "))}</span>
                  </div>
                  <div class="fs-13">${escapeHtml(c.message)}</div>
                </div>
              `;
            })
            .join("")}
        </div>
      `;
    }

    // Dynamic Section-Swapping Engine Recommendations
    if (hasSwaps) {
      html += `
        <h6 class="fw-semibold text-primary mb-2">
          <i class="fa fa-exchange me-1"></i>Dynamic Section-Swapping Recommendations (${result.swap_recommendations.length})
        </h6>
      `;
      result.swap_recommendations.forEach(function (rec, idx) {
        const actionsHtml = rec.actions
          .map(function (act) {
            return `
              <li class="mb-1 fs-13">
                <strong>${escapeHtml(act.course_code)}</strong>:
                <span class="text-danger text-decoration-line-through">${escapeHtml(act.from_section || "-")}</span>
                <i class="fa fa-long-arrow-right mx-1 text-primary"></i>
                <span class="text-success fw-semibold">${escapeHtml(act.to_section)}</span>
                <span class="text-muted">(${escapeHtml(act.reason)})</span>
              </li>
            `;
          })
          .join("");

        html += `
          <div class="swap-card">
            <div class="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-2">
              <div class="fw-semibold">${escapeHtml(rec.summary)}</div>
              <div class="d-flex align-items-center gap-2">
                <span class="swap-metric-chip">${rec.idle_gap_hours} hr idle gap &middot; ${rec.active_days} days</span>
                <button type="button" class="btn btn-sm btn-primary apply-swap-btn" data-swap-idx="${idx}">
                  <i class="fa fa-check me-1"></i>Apply Swap Solution
                </button>
              </div>
            </div>
            <ul class="mb-0 ps-3">${actionsHtml}</ul>
          </div>
        `;
      });
    }

    // Minimal Availability Slot Relaxation Suggestion
    if (hasRelaxation) {
      const rel = result.relaxation_suggestion;
      html += `
        <div class="swap-card border-warning mb-0">
          <div class="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-2">
            <div class="fw-semibold text-warning">
              <i class="fa fa-unlock-alt me-1"></i>Minimal Availability Slot Relaxation
            </div>
            <button type="button" class="btn btn-sm btn-outline-primary" id="applyRelaxationBtn">
              <i class="fa fa-unlock me-1"></i>Unblock Suggested Slot(s) &amp; Re-Solve
            </button>
          </div>
          <div class="fs-13 mb-0">${escapeHtml(rel.description)}</div>
        </div>
      `;
    }

    html += "</div>";
    panel.innerHTML = html;

    bindDiagNavButtons();

    // Bind Apply Swap buttons
    panel.querySelectorAll(".apply-swap-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        const idx = Number(btn.dataset.swapIdx);
        const rec = result.swap_recommendations[idx];
        if (!rec) return;

        state.pinnedOfferings = {};
        rec.resulting_offerings.forEach(function (off) {
          state.pinnedOfferings[off.course_code] = off.schedule_code;
        });
        state.swapHistory = rec.actions;
        renderCourseSelector();

        state.lastSolveResult = Object.assign({}, result, {
          feasible: true,
          solver_status: "OPTIMAL",
          conflict_logs: [],
          swap_recommendations: [],
          relaxation_suggestion: null,
          options: [
            {
              rank: 1,
              label: `Swapped Conflict-Free Schedule (${rec.swap_count} swap${rec.swap_count > 1 ? "s" : ""})`,
              total_units: rec.total_units,
              total_lec_units: rec.resulting_offerings.reduce((s, o) => s + o.lec_units, 0),
              total_lab_units: rec.resulting_offerings.reduce((s, o) => s + o.lab_units, 0),
              idle_gap_hours: rec.idle_gap_hours,
              active_days: rec.active_days,
              offerings: rec.resulting_offerings,
            },
          ],
          message: `Applied ${rec.summary}. All conflicts resolved (0 overlaps).`,
        });
        state.activeOptionIndex = 0;
        renderSolverOutput(state.lastSolveResult);
        renderMasterScheduleTab();
        showToast("Dynamic section swap applied. Zero-conflict master schedule is ready.", "success");
      });
    });

    // Bind Relaxation button
    const relBtn = el("applyRelaxationBtn");
    if (relBtn && result.relaxation_suggestion) {
      relBtn.addEventListener("click", async function () {
        state.matrixWidget.unblockSlots(result.relaxation_suggestion.slots_to_unblock);
        state.matrix = state.matrixWidget.getMatrix();
        await saveAvailabilityMatrix(true);
        await runSolver();
      });
    }
  }

  function bindDiagNavButtons() {
    const sBtn = el("diagBackSubjectsBtn");
    if (sBtn) sBtn.addEventListener("click", () => switchToTab("tab-subjects-btn"));
    const mBtn = el("diagBackMatrixBtn");
    if (mBtn) mBtn.addEventListener("click", () => switchToTab("tab-matrix-btn"));
  }

  async function runSolver() {
    const courseCodes = Array.from(state.selectedCourses);
    if (courseCodes.length === 0) {
      showToast("Please select at least one subject in Step 1 before generating a schedule.", "warning");
      switchToTab("tab-subjects-btn");
      return;
    }

    const solveBtn = el("runSolverBtn");
    if (solveBtn) {
      solveBtn.disabled = true;
      solveBtn.innerHTML = '<i class="fa fa-spinner fa-spin me-2"></i>Solving Schedule...';
    }

    try {
      // Automatically persist current availability matrix before solving
      await saveAvailabilityMatrix(true);

      const payload = {
        course_codes: courseCodes,
        pinned_offerings: state.pinnedOfferings,
        availability_matrix: state.matrixWidget ? state.matrixWidget.getMatrix() : state.matrix,
        max_units: state.maxUnits,
        max_solutions: 5,
      };
      const result = await apiFetch("/api/scheduler/solve", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      state.lastSolveResult = result;
      state.activeOptionIndex = 0;
      state.swapHistory = [];
      renderSolverOutput(result);
      renderMasterScheduleTab();
      switchToTab("tab-master-btn");
    } catch (err) {
      showToast(err.message, "danger");
    } finally {
      if (solveBtn) {
        solveBtn.disabled = false;
        solveBtn.innerHTML = '<i class="fa fa-cogs me-2"></i>Generate Conflict-Free Schedule';
      }
    }
  }

  function getActiveOption() {
    if (state.lastSolveResult) {
      if (state.lastSolveResult.options && state.lastSolveResult.options.length > 0) {
        return state.lastSolveResult.options[state.activeOptionIndex] || state.lastSolveResult.options[0];
      }
      // Solver ran and returned an infeasible/conflict result -> don't show stale submission below conflicts
      return null;
    }
    if (state.latestSubmission && state.latestSubmission.offerings && state.latestSubmission.offerings.length > 0) {
      return {
        rank: 1,
        label: `Submitted Schedule (${state.latestSubmission.status.replace("_", " ")})`,
        total_units: state.latestSubmission.total_units,
        total_lec_units: state.latestSubmission.offerings.reduce((s, o) => s + o.lec_units, 0),
        total_lab_units: state.latestSubmission.offerings.reduce((s, o) => s + o.lab_units, 0),
        idle_gap_hours: state.latestSubmission.idle_gap_hours,
        active_days: 0,
        offerings: state.latestSubmission.offerings,
      };
    }
    return null;
  }

  function renderTimetableGrid(offerings) {
    const container = el("masterTimetableGrid");
    if (!container) return;

    const matrix = state.matrix || {};
    const parts = [];

    parts.push('<div class="timetable-grid">');

    // Row 1: Header row (Time + Mon..Sat)
    parts.push('<div class="tt-head" style="grid-column: 1; grid-row: 1;">Time</div>');
    DAYS.forEach(function (d, dayIdx) {
      parts.push(
        `<div class="tt-head" style="grid-column: ${dayIdx + 2}; grid-row: 1;">${DAY_SHORT[d]} (${d})</div>`
      );
    });

    // Rows 2..14: Time labels + background day/hour cells
    for (let i = 0; i < HOUR_COUNT; i++) {
      const hour = START_HOUR + i;
      const gridRow = i + 2;
      const label = `${String(hour).padStart(2, "0")}:00-${String(hour + 1).padStart(2, "0")}:00`;
      parts.push(`<div class="tt-time" style="grid-column: 1; grid-row: ${gridRow};">${label}</div>`);

      DAYS.forEach(function (d, dayIdx) {
        const isBlocked = matrix[d] && matrix[d][i] === 0;
        parts.push(
          `<div class="tt-cell ${isBlocked ? "slot-blocked" : ""}" style="grid-column: ${dayIdx + 2}; grid-row: ${gridRow};" title="${isBlocked ? "Blocked Availability Slot" : ""}"></div>`
        );
      });
    }

    // Event blocks placed precisely across their exact start_hour -> end_hour grid rows
    offerings.forEach(function (off) {
      off.meetings.forEach(function (m) {
        const dayIdx = DAYS.indexOf(m.day);
        if (dayIdx === -1) return;
        const rowStart = Math.max(2, m.start_hour - START_HOUR + 2);
        const rowEnd = Math.min(HOUR_COUNT + 2, Math.max(rowStart + 1, m.end_hour - START_HOUR + 2));
        const isLab = m.meeting_type === "LAB";

        parts.push(`
          <div class="tt-event-wrap" style="grid-column: ${dayIdx + 2}; grid-row: ${rowStart} / ${rowEnd};">
            <div class="timetable-event ${isLab ? "event-lab" : ""}">
              <div class="timetable-event-code">${escapeHtml(off.course_code)} <span class="fw-normal">(${escapeHtml(m.meeting_type)})</span></div>
              <div class="timetable-event-meta">${escapeHtml(off.section_name)} | ${escapeHtml(m.room)}</div>
              <div class="timetable-event-meta">${escapeHtml(m.time_range_24h)}</div>
            </div>
          </div>
        `);
      });
    });

    parts.push("</div>");
    container.innerHTML = parts.join("");
  }

  function renderMasterScheduleTab() {
    const option = getActiveOption();
    const emptyState = el("masterScheduleEmpty");
    const contentWrap = el("masterScheduleContent");
    if (!emptyState || !contentWrap) return;

    if (!option) {
      contentWrap.classList.add("d-none");
      // If solver returned a conflict/infeasible diagnostic panel, hide the generic empty state
      if (state.lastSolveResult && !state.lastSolveResult.feasible) {
        emptyState.classList.add("d-none");
      } else {
        emptyState.classList.remove("d-none");
      }
      return;
    }

    emptyState.classList.add("d-none");
    contentWrap.classList.remove("d-none");

    const optionBar = el("scheduleOptionsBar");
    if (optionBar) {
      const optionsList = (state.lastSolveResult && state.lastSolveResult.options) || [];
      if (optionsList.length > 1) {
        optionBar.classList.remove("d-none");
        optionBar.innerHTML = optionsList
          .map(function (opt, idx) {
            return `
              <div class="option-selector-card ${idx === state.activeOptionIndex ? "active" : ""}" data-opt-idx="${idx}">
                <div class="fw-semibold fs-13">Option #${opt.rank}: ${escapeHtml(opt.label)}</div>
                <div class="fs-12 text-muted">${opt.total_units} units | ${opt.idle_gap_hours} hr gap | ${opt.active_days} days</div>
              </div>
            `;
          })
          .join("");
        optionBar.querySelectorAll(".option-selector-card").forEach(function (card) {
          card.addEventListener("click", function () {
            state.activeOptionIndex = Number(card.dataset.optIdx);
            renderMasterScheduleTab();
          });
        });
      } else {
        optionBar.classList.add("d-none");
      }
    }

    if (el("masterSummaryLabel")) el("masterSummaryLabel").textContent = option.label;
    if (el("masterSummaryMetrics")) {
      el("masterSummaryMetrics").textContent = `${option.offerings.length} Subjects | ${option.total_units} Units (${option.total_lec_units} Lec / ${option.total_lab_units} Lab) | ${option.idle_gap_hours} hr(s) Idle Gap`;
    }

    renderTimetableGrid(option.offerings);

    const tbody = el("masterScheduleTableBody");
    if (tbody) {
      tbody.innerHTML = option.offerings
        .map(function (off) {
          const schedLines = off.meetings
            .map(function (m) {
              return `<div><span class="badge ${m.meeting_type === "LAB" ? "bg-info" : "bg-primary"} me-1">${escapeHtml(m.meeting_type)}</span>${escapeHtml(m.portal_format)}</div>`;
            })
            .join("");
          return `
            <tr>
              <td class="text-center text-nowrap">${escapeHtml(off.schedule_code)}</td>
              <td class="text-center text-nowrap">${escapeHtml(off.course_code)}</td>
              <td>${escapeHtml(off.course_title)}</td>
              <td class="text-center text-nowrap">${escapeHtml(off.section_name)}</td>
              <td class="text-center text-nowrap">${off.lec_units}/${off.lab_units} (${off.total_units})</td>
              <td class="text-nowrap">${schedLines}</td>
              <td>${escapeHtml(off.instructor)}</td>
            </tr>
          `;
        })
        .join("");
    }

    const pdfBtn = el("exportMasterPdfBtn");
    if (pdfBtn) {
      const codes = option.offerings.map((o) => o.schedule_code).join(",");
      pdfBtn.href = `/api/scheduler/export-pdf?schedule_codes=${encodeURIComponent(codes)}`;
    }

    syncSubmitButtonState(option);
  }

  function isSameScheduleAsSubmission(option) {
    if (!option || !state.latestSubmission || !state.latestSubmission.offerings) return false;
    const optCodes = option.offerings.map((o) => o.schedule_code).sort().join(",");
    const subCodes = state.latestSubmission.offerings.map((o) => o.schedule_code).sort().join(",");
    return optCodes.length > 0 && optCodes === subCodes;
  }

  function syncSubmitButtonState(option) {
    const submitBtn = el("submitScheduleBtn");
    if (!submitBtn) return;

    if (!option || !option.offerings || option.offerings.length === 0) {
      submitBtn.disabled = true;
      submitBtn.className = "btn btn-sm btn-secondary";
      submitBtn.innerHTML = '<i class="fa fa-paper-plane me-1"></i>Submit to Academic Adviser';
      return;
    }

    const sub = state.latestSubmission;
    if (sub && sub.status === "APPROVED") {
      submitBtn.disabled = true;
      submitBtn.className = "btn btn-sm btn-secondary";
      submitBtn.innerHTML = '<i class="fa fa-check-circle me-1"></i>Approved &amp; Enrolled';
      return;
    }

    if (sub && sub.status === "PENDING_ADVISING" && (!state.lastSolveResult || isSameScheduleAsSubmission(option))) {
      submitBtn.disabled = true;
      submitBtn.className = "btn btn-sm btn-secondary";
      submitBtn.innerHTML = '<i class="fa fa-check me-1"></i>Submitted (Pending Advising)';
      return;
    }

    submitBtn.disabled = false;
    submitBtn.className = "btn btn-sm btn-primary";
    if (sub && sub.status === "REVISION_REQUESTED") {
      submitBtn.innerHTML = '<i class="fa fa-paper-plane me-1"></i>Resubmit Revised Schedule';
    } else {
      submitBtn.innerHTML = '<i class="fa fa-paper-plane me-1"></i>Submit to Academic Adviser';
    }
  }

  // ---------------------------------------------------------------------------
  // Action Bindings & Bootstrapping
  // ---------------------------------------------------------------------------
  function preselectRecommendedCourses() {
    state.selectedCourses.clear();
    state.pinnedOfferings = {};
    const offered = getOfferedEligibilityItems().filter(
      (i) => i.eligibility === "ELIGIBLE" || i.eligibility === "OVERRIDDEN"
    );
    offered.sort(function (a, b) {
      const aRetake = a.transcript_status === "FAILED" ? 0 : 1;
      const bRetake = b.transcript_status === "FAILED" ? 0 : 1;
      if (aRetake !== bRetake) return aRetake - bRetake;
      return a.year_level - b.year_level;
    });

    let runningUnits = 0;
    const targetYr = state.student ? state.student.year_level : 3;
    for (let i = 0; i < offered.length; i++) {
      const item = offered[i];
      if (item.year_level > targetYr && item.transcript_status !== "FAILED") continue;
      if (runningUnits + item.total_units <= state.maxUnits) {
        state.selectedCourses.add(item.code);
        runningUnits += item.total_units;
      }
    }
    renderCourseSelector();
  }

  async function triggerConflictDemoPreset() {
    if (!state.demoPreset) return;
    state.selectedCourses = new Set(state.demoPreset.course_codes);
    state.pinnedOfferings = Object.assign({}, state.demoPreset.pinned_offerings);
    state.showPinColumn = true;
    renderCourseSelector();
    showToast(state.demoPreset.description, "info");
    await runSolver();
  }

  function bindGlobalActions() {
    // Step navigation buttons
    const nextBtn = el("nextToAvailabilityBtn");
    if (nextBtn) {
      nextBtn.addEventListener("click", function () {
        if (state.selectedCourses.size === 0) {
          showToast("Please select at least one subject before continuing to Weekly Availability.", "warning");
          return;
        }
        switchToTab("tab-matrix-btn");
      });
    }

    const backBtn = el("backToSubjectsBtn");
    if (backBtn) {
      backBtn.addEventListener("click", function () {
        switchToTab("tab-subjects-btn");
      });
    }

    const emptyGoBtn = el("emptyGoToSubjectsBtn");
    if (emptyGoBtn) {
      emptyGoBtn.addEventListener("click", function () {
        switchToTab("tab-subjects-btn");
      });
    }

    // Optional Section Pinning toggle
    const pinSwitch = el("togglePinSectionsSwitch");
    if (pinSwitch) {
      pinSwitch.addEventListener("change", function () {
        state.showPinColumn = pinSwitch.checked;
        if (!state.showPinColumn) {
          state.pinnedOfferings = {};
        }
        renderCourseSelector();
      });
    }

    // Select Recommended / Clear
    const selectRecBtn = el("selectRecommendedBtn");
    if (selectRecBtn) {
      selectRecBtn.addEventListener("click", function () {
        preselectRecommendedCourses();
        showToast("Loaded recommended eligible subjects within the 24-unit load limit.", "info");
      });
    }

    const clearSelBtn = el("clearSelectionBtn");
    if (clearSelBtn) {
      clearSelBtn.addEventListener("click", function () {
        state.selectedCourses.clear();
        state.pinnedOfferings = {};
        renderCourseSelector();
      });
    }

    // Run CP-SAT Solver (from Step 2)
    const solveBtn = el("runSolverBtn");
    if (solveBtn) {
      solveBtn.addEventListener("click", runSolver);
    }

    // Submit Master Schedule to Adviser (opens confirmation modal first)
    const submitBtn = el("submitScheduleBtn");
    const confirmSubmitBtn = el("confirmSubmitActionBtn");
    if (submitBtn) {
      submitBtn.addEventListener("click", function () {
        const option = getActiveOption();
        if (!option || !option.offerings.length) {
          showToast("Generate a conflict-free schedule first before submitting.", "warning");
          return;
        }
        const summaryBox = el("confirmSubmitSummary");
        if (summaryBox) {
          summaryBox.innerHTML = `
            <div class="fw-semibold mb-1">${escapeHtml(option.label)}</div>
            <div class="fs-13 text-muted">
              ${option.offerings.length} Subject(s) &middot; ${option.total_units} Units (${option.total_lec_units} Lec / ${option.total_lab_units} Lab) &middot; ${option.idle_gap_hours} hr(s) Idle Gap
            </div>
          `;
        }
        const modalEl = el("confirmSubmitModal");
        if (modalEl && window.bootstrap) {
          window.bootstrap.Modal.getOrCreateInstance(modalEl).show();
        }
      });
    }

    if (confirmSubmitBtn) {
      confirmSubmitBtn.addEventListener("click", async function () {
        const option = getActiveOption();
        if (!option || !option.offerings.length) return;

        confirmSubmitBtn.disabled = true;
        confirmSubmitBtn.innerHTML = '<i class="fa fa-spinner fa-spin me-1"></i>Submitting...';
        try {
          const res = await apiFetch("/api/scheduler/submit", {
            method: "POST",
            body: JSON.stringify({
              schedule_codes: option.offerings.map((o) => o.schedule_code),
              solver_time_ms: state.lastSolveResult ? state.lastSolveResult.solver_time_ms : 0,
              idle_gap_hours: option.idle_gap_hours || 0,
              conflict_logs: (state.lastSolveResult && state.lastSolveResult.conflict_logs) || [],
              swap_history: state.swapHistory || [],
            }),
          });

          state.latestSubmission = {
            id: res.submission_id,
            status: res.status || "PENDING_ADVISING",
            total_units: option.total_units,
            idle_gap_hours: option.idle_gap_hours || 0,
            offerings: option.offerings,
          };

          const modalEl = el("confirmSubmitModal");
          if (modalEl && window.bootstrap) {
            window.bootstrap.Modal.getOrCreateInstance(modalEl).hide();
          }

          showToast(res.message, "success");
          const badge = el("advisingStatusBadge");
          if (badge) {
            badge.className = "badge bg-warning";
            badge.textContent = "PENDING ADVISING";
          }
          syncSubmitButtonState(option);
        } catch (err) {
          showToast(err.message, "danger");
        } finally {
          confirmSubmitBtn.disabled = false;
          confirmSubmitBtn.innerHTML = '<i class="fa fa-paper-plane me-1"></i>Confirm &amp; Submit';
        }
      });
    }

    // Presenter Modal: Transcript Filters & Reset
    document.querySelectorAll("[data-transcript-filter]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        document.querySelectorAll("[data-transcript-filter]").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        state.transcriptFilter = btn.dataset.transcriptFilter;
        renderTranscriptModal();
      });
    });

    const resetBtn = el("resetTranscriptBtn");
    if (resetBtn) {
      resetBtn.addEventListener("click", async function () {
        try {
          const data = await apiFetch("/api/scheduler/transcript/reset", { method: "POST" });
          state.eligibility = data.eligibility;
          state.matrix = data.availability_matrix;
          if (state.matrixWidget) state.matrixWidget.setMatrix(state.matrix);
          preselectRecommendedCourses();
          renderTranscriptModal();
          showToast("Transcript and availability matrix restored to persona defaults.", "info");
        } catch (err) {
          showToast(err.message, "danger");
        }
      });
    }

    // Intercept Topbar Presenter Demo links when already on /preregistration
    const headerConflictLink = el("headerLoadConflictDemo");
    if (headerConflictLink) {
      headerConflictLink.addEventListener("click", function (ev) {
        ev.preventDefault();
        triggerConflictDemoPreset();
      });
    }

    const headerSimLink = el("headerOpenTranscriptSim");
    if (headerSimLink) {
      headerSimLink.addEventListener("click", function (ev) {
        ev.preventDefault();
        openTranscriptModal();
      });
    }
  }

  async function init() {
    if (!el("schedulerWorkspaceRoot")) return;
    try {
      const data = await apiFetch("/api/scheduler/state");
      state.student = data.student;
      state.eligibility = data.eligibility;
      state.offeringsByCourse = data.offerings_by_course;
      state.matrix = data.availability_matrix;
      state.maxUnits = data.max_units_default || 24;
      state.latestSubmission = data.latest_submission;
      state.demoPreset = data.demo_conflict_preset;

      renderTranscriptModal();
      initMatrixTab();
      preselectRecommendedCourses();
      renderMasterScheduleTab();
      bindGlobalActions();

      // Handle Presenter Demo triggers navigated from another page
      const params = new URLSearchParams(window.location.search);
      if (params.get("demo_transcript") === "1") {
        openTranscriptModal();
      } else if (params.get("demo_conflict") === "1") {
        await triggerConflictDemoPreset();
      }
    } catch (err) {
      showToast("Unable to initialize scheduler workspace: " + err.message, "danger");
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})();
