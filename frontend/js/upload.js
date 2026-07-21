/* File selection, drag & drop, client-side validation and upload helpers. */
(function () {
  "use strict";
  window.HOE = window.HOE || { state: {} };

  const MAX_MB = 25;
  const ALLOWED = ["jpg", "jpeg", "png", "pdf"];

  HOE.upload = {
    maxMb: MAX_MB,
    allowed: ALLOWED,

    validate(file) {
      if (!file) return { ok: false, error: "No file selected" };
      const ext = (file.name.split(".").pop() || "").toLowerCase();
      if (!ALLOWED.includes(ext)) {
        return {
          ok: false,
          error: "Unsupported type ." + ext + " (allowed: " +
            ALLOWED.join(", ") + ")",
        };
      }
      if (file.size > MAX_MB * 1024 * 1024) {
        return {
          ok: false,
          error:
            "File is " +
            (file.size / 1024 / 1024).toFixed(1) +
            " MB; limit is " +
            MAX_MB +
            " MB",
        };
      }
      if (file.size === 0) return { ok: false, error: "File is empty" };
      return { ok: true, ext };
    },

    /** Wire drag & drop + click-to-browse on a drop zone. */
    setupDropZone(zone, input, browseBtn, onFile) {
      if (!zone || !input) return;
      const open = () => input.click();
      if (browseBtn) browseBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        open();
      });
      zone.addEventListener("click", open);
      input.addEventListener("change", () => {
        if (input.files && input.files[0]) onFile(input.files[0]);
      });
      ["dragenter", "dragover"].forEach((ev) =>
        zone.addEventListener(ev, (e) => {
          e.preventDefault();
          zone.classList.add("dragover");
        })
      );
      ["dragleave", "drop"].forEach((ev) =>
        zone.addEventListener(ev, (e) => {
          e.preventDefault();
          zone.classList.remove("dragover");
        })
      );
      zone.addEventListener("drop", (e) => {
        const f = e.dataTransfer.files && e.dataTransfer.files[0];
        if (f) onFile(f);
      });
    },

    /** Upload a file, driving a progress bar element (its inner .progress-bar). */
    async send(file, progressWrap) {
      let bar = null;
      if (progressWrap) {
        progressWrap.classList.remove("d-none");
        bar = progressWrap.querySelector(".progress-bar");
      }
      try {
        const meta = await HOE.api.upload(file, (pct) => {
          if (bar) bar.style.width = pct + "%";
        });
        return meta;
      } finally {
        if (progressWrap) {
          setTimeout(() => progressWrap.classList.add("d-none"), 600);
        }
      }
    },
  };
})();
