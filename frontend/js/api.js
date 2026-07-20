/* Thin API client for the FastAPI backend. */
(function () {
  "use strict";
  window.HOE = window.HOE || { state: {} };

  const BASE = "/api";

  async function parseError(res) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || body.error || detail;
    } catch (_) {
      /* ignore */
    }
    return new Error(detail);
  }

  HOE.api = {
    /** Upload a file with progress callback. Returns upload metadata. */
    upload(file, onProgress) {
      return new Promise((resolve, reject) => {
        const form = new FormData();
        form.append("file", file);
        const xhr = new XMLHttpRequest();
        xhr.open("POST", BASE + "/upload");
        xhr.upload.onprogress = (e) => {
          if (onProgress && e.lengthComputable) {
            onProgress(Math.round((e.loaded / e.total) * 100));
          }
        };
        xhr.onload = () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve(JSON.parse(xhr.responseText));
          } else {
            let msg = "Upload failed";
            try {
              const b = JSON.parse(xhr.responseText);
              msg = b.detail || b.error || msg;
            } catch (_) {}
            reject(new Error(msg));
          }
        };
        xhr.onerror = () => reject(new Error("Network error during upload"));
        xhr.send(form);
      });
    },

    /** Run OCR + table reconstruction. */
    async process(fileId, lang) {
      const res = await fetch(BASE + "/process", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_id: fileId, lang: lang || null }),
      });
      if (!res.ok) throw await parseError(res);
      return res.json();
    },

    /** Export a table to xlsx; returns a Blob. */
    async export(table, filename, header) {
      const res = await fetch(BASE + "/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          table: table,
          filename: filename || "hindi_ocr_export",
          header: header !== false,
        }),
      });
      if (!res.ok) throw await parseError(res);
      return res.blob();
    },

    async health() {
      const res = await fetch(BASE + "/health");
      if (!res.ok) throw await parseError(res);
      return res.json();
    },

    fileUrl(fileId) {
      return BASE + "/file/" + encodeURIComponent(fileId);
    },
    pageUrl(fileId, page) {
      return BASE + "/preview/" + encodeURIComponent(fileId) + "/" + page;
    },
  };
})();
