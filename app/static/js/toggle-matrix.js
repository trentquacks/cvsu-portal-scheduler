/**
 * Interactive Mon-Sat 7:00 AM - 8:00 PM Time-Slot Toggle Matrix
 * Produces a strict binary availability map: 1 = Available, 0 = Blocked.
 */
(function (global) {
  "use strict";

  const DAYS = ["M", "T", "W", "TH", "F", "S"];
  const DAY_NAMES = {
    M: "Monday",
    T: "Tuesday",
    W: "Wednesday",
    TH: "Thursday",
    F: "Friday",
    S: "Saturday",
  };
  const START_HOUR = 7;
  const HOUR_COUNT = 13; // 07:00-08:00 .. 19:00-20:00

  function formatHourLabel(hour) {
    const startH = hour % 12 === 0 ? 12 : hour % 12;
    const endHour = hour + 1;
    const endH = endHour % 12 === 0 ? 12 : endHour % 12;
    const startSuffix = hour < 12 ? "AM" : "PM";
    const endSuffix = endHour < 12 ? "AM" : "PM";
    return `${startH}:00 ${startSuffix} - ${endH}:00 ${endSuffix}`;
  }

  class AvailabilityToggleMatrix {
    constructor(containerEl, initialMatrix, onChange) {
      this.container = containerEl;
      this.onChange = typeof onChange === "function" ? onChange : function () {};
      this.matrix = this._cloneMatrix(initialMatrix);
      this.isDragging = false;
      this.dragValue = 0;

      this._bindGlobalMouseUp();
      this.render();
    }

    _cloneMatrix(src) {
      const copy = {};
      DAYS.forEach(function (d) {
        const arr = src && Array.isArray(src[d]) && src[d].length === HOUR_COUNT ? src[d] : null;
        copy[d] = arr ? arr.map(function (v) { return v ? 1 : 0; }) : new Array(HOUR_COUNT).fill(1);
      });
      return copy;
    }

    _bindGlobalMouseUp() {
      const self = this;
      document.addEventListener("mouseup", function () {
        if (self.isDragging) {
          self.isDragging = false;
          self.onChange(self.getMatrix(), self.getStats());
        }
      });
    }

    setMatrix(newMatrix) {
      this.matrix = this._cloneMatrix(newMatrix);
      this.render();
      this.onChange(this.getMatrix(), this.getStats());
    }

    getMatrix() {
      return this._cloneMatrix(this.matrix);
    }

    getStats() {
      let available = 0;
      const total = DAYS.length * HOUR_COUNT;
      DAYS.forEach((d) => {
        this.matrix[d].forEach((v) => {
          if (v === 1) available += 1;
        });
      });
      return { available: available, blocked: total - available, total: total };
    }

    applyPreset(presetName) {
      DAYS.forEach((d) => {
        for (let i = 0; i < HOUR_COUNT; i++) {
          const hour = START_HOUR + i;
          if (presetName === "clear") {
            this.matrix[d][i] = 1;
          } else if (presetName === "block_weekday_mornings") {
            if (d !== "S" && hour >= 7 && hour <= 12) this.matrix[d][i] = 0;
          } else if (presetName === "block_weekday_afternoons") {
            if (d !== "S" && hour >= 13 && hour <= 16) this.matrix[d][i] = 0;
          } else if (presetName === "block_evenings") {
            if (hour >= 17 && hour <= 19) this.matrix[d][i] = 0;
          } else if (presetName === "block_saturday") {
            if (d === "S") this.matrix[d][i] = 0;
          }
        }
      });
      this.render();
      this.onChange(this.getMatrix(), this.getStats());
    }

    unblockSlots(slots) {
      (slots || []).forEach((s) => {
        const idx = Number(s.hour) - START_HOUR;
        if (this.matrix[s.day] && idx >= 0 && idx < HOUR_COUNT) {
          this.matrix[s.day][idx] = 1;
        }
      });
      this.render();
      this.onChange(this.getMatrix(), this.getStats());
    }

    _updateCellElement(td, val) {
      td.classList.toggle("is-available", val === 1);
      td.classList.toggle("is-blocked", val === 0);
      td.textContent = val === 1 ? "Available" : "Blocked";
      td.setAttribute("aria-pressed", val === 0 ? "true" : "false");
    }

    render() {
      const self = this;
      const table = document.createElement("table");
      table.className = "availability-matrix-table";

      const thead = document.createElement("thead");
      const headRow = document.createElement("tr");
      const cornerTh = document.createElement("th");
      cornerTh.className = "time-col";
      cornerTh.textContent = "Time Slot";
      headRow.appendChild(cornerTh);

      DAYS.forEach(function (d) {
        const th = document.createElement("th");
        th.textContent = `${DAY_NAMES[d]} (${d})`;
        th.style.cursor = "pointer";
        th.title = `Click to toggle entire ${DAY_NAMES[d]} column`;
        th.addEventListener("click", function () {
          const allAvail = self.matrix[d].every((v) => v === 1);
          self.matrix[d] = new Array(HOUR_COUNT).fill(allAvail ? 0 : 1);
          self.render();
          self.onChange(self.getMatrix(), self.getStats());
        });
        headRow.appendChild(th);
      });
      thead.appendChild(headRow);
      table.appendChild(thead);

      const tbody = document.createElement("tbody");
      for (let i = 0; i < HOUR_COUNT; i++) {
        const hour = START_HOUR + i;
        const tr = document.createElement("tr");

        const timeTd = document.createElement("td");
        timeTd.className = "time-col";
        timeTd.textContent = formatHourLabel(hour);
        timeTd.style.cursor = "pointer";
        timeTd.title = "Click to toggle entire row";
        timeTd.addEventListener("click", function () {
          const allAvail = DAYS.every((d) => self.matrix[d][i] === 1);
          DAYS.forEach((d) => {
            self.matrix[d][i] = allAvail ? 0 : 1;
          });
          self.render();
          self.onChange(self.getMatrix(), self.getStats());
        });
        tr.appendChild(timeTd);

        DAYS.forEach(function (d) {
          const td = document.createElement("td");
          td.className = "matrix-cell";
          td.dataset.day = d;
          td.dataset.idx = String(i);
          self._updateCellElement(td, self.matrix[d][i]);

          td.addEventListener("mousedown", function (e) {
            e.preventDefault();
            self.isDragging = true;
            self.dragValue = self.matrix[d][i] === 1 ? 0 : 1;
            self.matrix[d][i] = self.dragValue;
            self._updateCellElement(td, self.dragValue);
          });

          td.addEventListener("mouseenter", function () {
            if (!self.isDragging) return;
            self.matrix[d][i] = self.dragValue;
            self._updateCellElement(td, self.dragValue);
          });

          tr.appendChild(td);
        });
        tbody.appendChild(tr);
      }

      table.appendChild(tbody);
      this.container.innerHTML = "";
      this.container.appendChild(table);
    }
  }

  global.AvailabilityToggleMatrix = AvailabilityToggleMatrix;
})(window);
