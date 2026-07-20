/* Excel export: send the current table to the backend and trigger download. */
(function () {
  "use strict";
  window.HOE = window.HOE || { state: {} };

  HOE.exportExcel = async function () {
    const table = HOE.table.getData();
    if (!table.length || HOE.table.isEmpty()) {
      HOE.toast("Nothing to export", "warning");
      return;
    }
    const nameInput = document.getElementById("exportName");
    const filename = (nameInput && nameInput.value.trim()) || "hindi_ocr_export";
    const btn = document.getElementById("exportBtn");
    const original = btn ? btn.innerHTML : "";
    if (btn) {
      btn.disabled = true;
      btn.innerHTML =
        '<span class="spinner-border spinner-border-sm"></span> Exporting…';
    }
    try {
      const blob = await HOE.api.export(table, filename, true);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename.replace(/\.xlsx$/i, "") + ".xlsx";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      HOE.toast("Excel file downloaded", "success");
    } catch (err) {
      HOE.toast("Export failed: " + err.message, "danger");
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = original;
      }
    }
  };
})();
