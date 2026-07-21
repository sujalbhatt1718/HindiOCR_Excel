/* Global namespace, dark-mode toggle and toast helper. */
(function () {
  "use strict";

  window.HOE = window.HOE || { state: {} };

  // ---- Theme ----
  const KEY = "hoe-theme";
  const root = document.documentElement;

  function apply(theme) {
    root.setAttribute("data-bs-theme", theme);
    const icon = document.querySelector("#themeToggle i");
    if (icon) {
      icon.className = theme === "dark" ? "bi bi-sun" : "bi bi-moon-stars";
    }
  }

  function current() {
    return localStorage.getItem(KEY) ||
      (window.matchMedia("(prefers-color-scheme: dark)").matches
        ? "dark"
        : "light");
  }

  apply(current());

  document.addEventListener("DOMContentLoaded", function () {
    apply(current());
    const btn = document.getElementById("themeToggle");
    if (btn) {
      btn.addEventListener("click", function () {
        const next =
          root.getAttribute("data-bs-theme") === "dark" ? "light" : "dark";
        localStorage.setItem(KEY, next);
        apply(next);
      });
    }
    const yr = document.getElementById("year");
    if (yr) yr.textContent = new Date().getFullYear();
  });

  // ---- Toast helper ----
  HOE.toast = function (message, kind) {
    kind = kind || "primary";
    let container = document.getElementById("toastContainer");
    if (!container) {
      container = document.createElement("div");
      container.id = "toastContainer";
      container.className =
        "toast-container position-fixed bottom-0 end-0 p-3";
      document.body.appendChild(container);
    }
    const el = document.createElement("div");
    el.className = "toast align-items-center text-bg-" + kind + " border-0";
    el.setAttribute("role", "alert");
    el.innerHTML =
      '<div class="d-flex"><div class="toast-body">' +
      message +
      '</div><button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button></div>';
    container.appendChild(el);
    const t = new bootstrap.Toast(el, { delay: 3800 });
    t.show();
    el.addEventListener("hidden.bs.toast", () => el.remove());
  };
})();
