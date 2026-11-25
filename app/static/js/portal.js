/**
 * CvSU-Imus Student Portal Core UI Controller
 * Handles sidebar navigation, mobile drawer, dark/light theme mode, fullscreen, and popovers.
 */
(function () {
  "use strict";

  const THEME_KEY = "cvsu_portal_theme_mode";

  function applyTheme(mode) {
    document.documentElement.setAttribute("data-theme-mode", mode);
    document.documentElement.setAttribute("data-bs-theme", mode);
    const moonIcon = document.getElementById("themeIconDark");
    const sunIcon = document.getElementById("themeIconLight");
    if (moonIcon && sunIcon) {
      moonIcon.classList.toggle("d-none", mode === "dark");
      sunIcon.classList.toggle("d-none", mode !== "dark");
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    // 1. Restore saved light/dark theme
    const savedTheme = localStorage.getItem(THEME_KEY) || "light";
    applyTheme(savedTheme);

    const themeToggle = document.getElementById("themeModeToggle");
    if (themeToggle) {
      themeToggle.addEventListener("click", function () {
        const current = document.documentElement.getAttribute("data-theme-mode") || "light";
        const next = current === "dark" ? "light" : "dark";
        localStorage.setItem(THEME_KEY, next);
        applyTheme(next);
      });
    }

    // 2. Sidebar Toggle (Desktop Collapse + Mobile Drawer)
    const sidebarToggle = document.getElementById("sidebarToggleBtn");
    const sidebarBackdrop = document.getElementById("sidebarBackdrop");

    function closeMobileSidebar() {
      document.body.classList.remove("sidebar-mobile-open");
    }

    if (sidebarToggle) {
      sidebarToggle.addEventListener("click", function () {
        if (window.innerWidth < 992) {
          document.body.classList.toggle("sidebar-mobile-open");
        } else {
          document.body.classList.toggle("sidebar-collapsed");
        }
      });
    }

    if (sidebarBackdrop) {
      sidebarBackdrop.addEventListener("click", closeMobileSidebar);
    }

    // 3. Expandable Sidebar Submenu Accordion (Enrollment Record)
    document.querySelectorAll(".slide.has-sub > .side-menu__item").forEach(function (trigger) {
      trigger.addEventListener("click", function (e) {
        e.preventDefault();
        const parentSlide = trigger.closest(".slide.has-sub");
        if (parentSlide) {
          parentSlide.classList.toggle("is-expanded");
        }
      });
    });

    // 4. Fullscreen Toggle
    const fsBtn = document.getElementById("fullscreenToggleBtn");
    if (fsBtn) {
      fsBtn.addEventListener("click", function () {
        if (!document.fullscreenElement) {
          document.documentElement.requestFullscreen().catch(function () {});
        } else {
          document.exitFullscreen().catch(function () {});
        }
      });
    }

    // 5. Bootstrap Popovers & Tooltips
    if (window.bootstrap) {
      document.querySelectorAll('[data-bs-toggle="popover"]').forEach(function (el) {
        new window.bootstrap.Popover(el);
      });
      document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (el) {
        new window.bootstrap.Tooltip(el);
      });
    }

    // 6. Scroll-To-Top Button
    const scrollBtn = document.getElementById("scrollToTopBtn");
    if (scrollBtn) {
      window.addEventListener("scroll", function () {
        scrollBtn.classList.toggle("show", window.scrollY > 240);
      });
      scrollBtn.addEventListener("click", function () {
        window.scrollTo({ top: 0, behavior: "smooth" });
      });
    }

    // 7. Evaluation Survey QR Code Modal (live URL update + printable standee PDF link)
    const evalWrap = document.getElementById("evalQrImageWrap");
    const evalInput = document.getElementById("evalFormUrlInput");
    const evalImg = document.getElementById("evalQrSvgImg");
    const evalSaveBtn = document.getElementById("evalFormUrlSaveBtn");
    const evalOpenLink = document.getElementById("evalOpenFormLink");
    const evalStandeeBtn = document.getElementById("evalDownloadStandeeBtn");
    const evalNotice = document.getElementById("evalQrNotice");
    const EVAL_URL_KEY = "cvsu_eval_form_url";

    function syncEvaluationQr(rawUrl) {
      const cleanUrl = (rawUrl || "").trim();
      if (evalInput) evalInput.value = cleanUrl;
      if (cleanUrl) {
        const enc = encodeURIComponent(cleanUrl);
        if (evalImg) evalImg.src = `/api/evaluation/qr.svg?url=${enc}`;
        if (evalStandeeBtn) evalStandeeBtn.href = `/evaluation/standee.pdf?url=${enc}`;
        if (evalOpenLink) {
          evalOpenLink.href = cleanUrl;
          evalOpenLink.classList.remove("d-none");
        }
        if (evalNotice) evalNotice.classList.add("d-none");
      } else {
        if (evalImg) evalImg.src = "/api/evaluation/qr.svg";
        if (evalStandeeBtn) evalStandeeBtn.href = "/evaluation/standee.pdf";
        if (evalOpenLink) evalOpenLink.classList.add("d-none");
        if (evalNotice) evalNotice.classList.remove("d-none");
      }
    }

    if (evalWrap) {
      const serverDefault = (evalWrap.dataset.defaultUrl || "").trim();
      const savedUrl = (localStorage.getItem(EVAL_URL_KEY) || "").trim();
      syncEvaluationQr(serverDefault || savedUrl);

      if (evalSaveBtn && evalInput) {
        evalSaveBtn.addEventListener("click", function () {
          const val = evalInput.value.trim();
          if (val) {
            localStorage.setItem(EVAL_URL_KEY, val);
          } else {
            localStorage.removeItem(EVAL_URL_KEY);
          }
          syncEvaluationQr(val);
        });
      }
    }
  });
})();
