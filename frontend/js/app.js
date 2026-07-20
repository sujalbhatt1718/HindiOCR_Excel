/* Page wiring for the Home and Workspace pages. */
(function () {
  "use strict";
  window.HOE = window.HOE || { state: {} };

  document.addEventListener("DOMContentLoaded", function () {
    const maxSpan = document.getElementById("maxSize");
    if (maxSpan) maxSpan.textContent = HOE.upload.maxMb;

    if (document.getElementById("startBtn")) initHome();
    if (document.getElementById("dataTable")) initWorkspace();
  });

  /* ------------------------------------------------------------------ */
  /* Home page                                                          */
  /* ------------------------------------------------------------------ */
  function initHome() {
    const input = document.getElementById("fileInput");
    const zone = document.getElementById("dropZone");
    const browse = document.getElementById("browseBtn");
    const wrap = document.getElementById("previewWrap");
    const img = document.getElementById("previewImg");
    const nameEl = document.getElementById("fileName");
    const metaEl = document.getElementById("fileMeta");
    const startBtn = document.getElementById("startBtn");
    const clearBtn = document.getElementById("clearBtn");
    const progress = document.getElementById("uploadProgress");
    let selected = null;

    HOE.upload.setupDropZone(zone, input, browse, onFile);

    function onFile(file) {
      const v = HOE.upload.validate(file);
      if (!v.ok) {
        HOE.toast(v.error, "danger");
        return;
      }
      selected = file;
      wrap.classList.remove("d-none");
      nameEl.textContent = file.name;
      metaEl.textContent =
        (file.size / 1024).toFixed(0) + " KB · " + (v.ext.toUpperCase());
      startBtn.disabled = false;
      if (v.ext === "pdf") {
        img.src =
          "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='64' height='64'><rect width='64' height='64' fill='%23e9ecef'/><text x='32' y='40' font-size='14' text-anchor='middle' fill='%23dc3545'>PDF</text></svg>";
      } else {
        const reader = new FileReader();
        reader.onload = (e) => (img.src = e.target.result);
        reader.readAsDataURL(file);
      }
    }

    clearBtn.addEventListener("click", () => {
      selected = null;
      input.value = "";
      wrap.classList.add("d-none");
      startBtn.disabled = true;
    });

    startBtn.addEventListener("click", async () => {
      if (!selected) return;
      startBtn.disabled = true;
      startBtn.innerHTML =
        '<span class="spinner-border spinner-border-sm"></span> Uploading…';
      try {
        const meta = await HOE.upload.send(selected, progress);
        sessionStorage.setItem("hoe-file", JSON.stringify(meta));
        window.location.href = "/workspace";
      } catch (err) {
        HOE.toast("Upload failed: " + err.message, "danger");
        startBtn.disabled = false;
        startBtn.innerHTML = '<i class="bi bi-magic"></i> Extract table';
      }
    });
  }

  /* ------------------------------------------------------------------ */
  /* Workspace page                                                     */
  /* ------------------------------------------------------------------ */
  function initWorkspace() {
    const view = {
      scale: 1,
      rotation: 0,
      page: 1,
      pages: 1,
      fileId: null,
      kind: "image",
    };

    HOE.table.init(document.getElementById("dataTable"));

    const docImage = document.getElementById("docImage");
    const previewEmpty = document.getElementById("previewEmpty");
    const uploadBar = document.getElementById("uploadBar");
    const ocrStatus = document.getElementById("ocrStatus");
    const ocrText = document.getElementById("ocrStatusText");
    const toolbar = document.getElementById("tableToolbar");
    const tableEmpty = document.getElementById("tableEmpty");
    const dataTable = document.getElementById("dataTable");
    const exportBtn = document.getElementById("exportBtn");
    const confBadge = document.getElementById("confBadge");
    const timeBadge = document.getElementById("timeBadge");
    const statsEl = document.getElementById("tableStats");
    const pager = document.getElementById("pdfPager");
    const pageLabel = document.getElementById("pageLabel");

    HOE.workspace = {
      updateStats() {
        const d = HOE.table.getData();
        const rows = Math.max(0, d.length - 1);
        const cols = HOE.table.nCols();
        if (statsEl) statsEl.textContent = rows + " rows × " + cols + " cols";
      },
    };

    // ---- Upload bar ----
    HOE.upload.setupDropZone(
      document.getElementById("dropZone"),
      document.getElementById("fileInput"),
      document.getElementById("browseBtn"),
      onWorkspaceFile
    );

    async function onWorkspaceFile(file) {
      const v = HOE.upload.validate(file);
      if (!v.ok) {
        HOE.toast(v.error, "danger");
        return;
      }
      try {
        const meta = await HOE.upload.send(
          file,
          document.getElementById("uploadProgress")
        );
        loadDocument(meta);
        runProcess(meta.file_id);
      } catch (err) {
        HOE.toast("Upload failed: " + err.message, "danger");
      }
    }

    function loadDocument(meta) {
      view.fileId = meta.file_id;
      view.kind = meta.kind;
      view.pages = meta.pages || 1;
      view.page = 1;
      view.scale = 1;
      view.rotation = 0;
      previewEmpty.classList.add("d-none");
      docImage.classList.remove("d-none");
      showPage();
      pager.classList.toggle("d-none", !(meta.kind === "pdf" && view.pages > 1));
      applyTransform();
    }

    function showPage() {
      if (!view.fileId) return;
      docImage.src =
        view.kind === "pdf"
          ? HOE.api.pageUrl(view.fileId, view.page)
          : HOE.api.fileUrl(view.fileId);
      if (pageLabel)
        pageLabel.textContent = "Page " + view.page + " / " + view.pages;
    }

    async function runProcess(fileId) {
      ocrStatus.classList.remove("d-none");
      ocrStatus.classList.add("d-flex");
      ocrText.textContent = "Running OCR… this can take a moment on first run.";
      tableEmpty.classList.add("d-none");
      try {
        const res = await HOE.api.process(fileId);
        HOE.table.load(res.table);
        dataTable.classList.remove("d-none");
        toolbar.classList.remove("d-none");
        toolbar.classList.add("d-flex");
        exportBtn.disabled = false;
        confBadge.classList.remove("d-none");
        timeBadge.classList.remove("d-none");
        confBadge.textContent =
          "confidence: " + Math.round((res.confidence || 0) * 100) + "%";
        timeBadge.textContent = (res.processing_time || 0).toFixed(2) + "s";
        HOE.toast("Table extracted", "success");
      } catch (err) {
        tableEmpty.classList.remove("d-none");
        HOE.toast("Processing failed: " + err.message, "danger");
      } finally {
        ocrStatus.classList.add("d-none");
        ocrStatus.classList.remove("d-flex");
      }
    }

    // ---- Preview controls ----
    function applyTransform() {
      docImage.style.transform =
        "scale(" + view.scale + ") rotate(" + view.rotation + "deg)";
    }
    document.getElementById("zoomIn").onclick = () => {
      view.scale = Math.min(4, view.scale + 0.2);
      applyTransform();
    };
    document.getElementById("zoomOut").onclick = () => {
      view.scale = Math.max(0.2, view.scale - 0.2);
      applyTransform();
    };
    document.getElementById("rotateLeft").onclick = () => {
      view.rotation -= 90;
      applyTransform();
    };
    document.getElementById("rotateRight").onclick = () => {
      view.rotation += 90;
      applyTransform();
    };
    document.getElementById("prevPage").onclick = () => {
      if (view.page > 1) {
        view.page--;
        showPage();
      }
    };
    document.getElementById("nextPage").onclick = () => {
      if (view.page < view.pages) {
        view.page++;
        showPage();
      }
    };

    // ---- Table toolbar ----
    document.getElementById("addRow").onclick = () => HOE.table.addRow();
    document.getElementById("addCol").onclick = () => HOE.table.addCol();
    document.getElementById("delRow").onclick = () => HOE.table.delRow();
    document.getElementById("delCol").onclick = () => HOE.table.delCol();
    document.getElementById("undoBtn").onclick = () => HOE.table.undo();
    document.getElementById("redoBtn").onclick = () => HOE.table.redo();
    document.getElementById("clearCell").onclick = () => HOE.table.clearCell();
    document.getElementById("searchInput").addEventListener("input", (e) => {
      const n = HOE.table.search(e.target.value);
      if (e.target.value.trim())
        HOE.toast(n + " match(es)", n ? "secondary" : "warning");
    });
    exportBtn.onclick = () => HOE.exportExcel();

    // ---- Resume from Home page upload ----
    const pending = sessionStorage.getItem("hoe-file");
    if (pending) {
      sessionStorage.removeItem("hoe-file");
      try {
        const meta = JSON.parse(pending);
        uploadBar.classList.add("d-none");
        loadDocument(meta);
        runProcess(meta.file_id);
      } catch (_) {
        uploadBar.classList.remove("d-none");
      }
    }
  }
})();
