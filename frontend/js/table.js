/* Editable spreadsheet: edit, add/del row & col, undo/redo, copy/paste, search. */
(function () {
  "use strict";
  window.HOE = window.HOE || { state: {} };

  const MAX_HISTORY = 60;

  const editor = {
    el: null,
    thead: null,
    tbody: null,
    data: [], // 2D array, row 0 = header
    sel: { r: 0, c: 0 },
    undoStack: [],
    redoStack: [],

    init(tableEl) {
      this.el = tableEl;
      this.thead = tableEl.querySelector("thead");
      this.tbody = tableEl.querySelector("tbody");
      document.addEventListener("keydown", (e) => this._onKey(e));
    },

    /** Replace all data and reset history. */
    load(matrix) {
      if (!matrix || !matrix.length) matrix = [[""]];
      this.data = matrix.map((row) => row.map((c) => (c == null ? "" : "" + c)));
      this.undoStack = [];
      this.redoStack = [];
      this.sel = { r: 1 < this.data.length ? 1 : 0, c: 0 };
      this.render();
    },

    isEmpty() {
      return !this.data.length || !this.data.some((r) => r.some((c) => c));
    },

    getData() {
      return this.data.map((r) => r.slice());
    },

    nCols() {
      return this.data.reduce((m, r) => Math.max(m, r.length), 0);
    },

    _snapshot() {
      this.undoStack.push(JSON.stringify(this.data));
      if (this.undoStack.length > MAX_HISTORY) this.undoStack.shift();
      this.redoStack = [];
    },

    undo() {
      if (!this.undoStack.length) return;
      this.redoStack.push(JSON.stringify(this.data));
      this.data = JSON.parse(this.undoStack.pop());
      this.render();
      HOE.toast("Undo", "secondary");
    },

    redo() {
      if (!this.redoStack.length) return;
      this.undoStack.push(JSON.stringify(this.data));
      this.data = JSON.parse(this.redoStack.pop());
      this.render();
      HOE.toast("Redo", "secondary");
    },

    _rectangularize() {
      const w = this.nCols() || 1;
      this.data = this.data.map((r) => {
        const row = r.slice();
        while (row.length < w) row.push("");
        return row;
      });
    },

    render() {
      this._rectangularize();
      const w = this.nCols();
      // Header
      let h = "<tr><th class='col-tools' style='min-width:36px'>#</th>";
      for (let c = 0; c < w; c++) {
        h +=
          "<th contenteditable='true' data-r='0' data-c='" +
          c +
          "'>" +
          escapeHtml(this.data[0][c] || "") +
          "</th>";
      }
      h += "</tr>";
      this.thead.innerHTML = h;

      // Body
      let b = "";
      for (let r = 1; r < this.data.length; r++) {
        b += "<tr><td class='row-head text-secondary small'>" + r + "</td>";
        for (let c = 0; c < w; c++) {
          b +=
            "<td contenteditable='true' data-r='" +
            r +
            "' data-c='" +
            c +
            "'>" +
            escapeHtml(this.data[r][c] || "") +
            "</td>";
        }
        b += "</tr>";
      }
      this.tbody.innerHTML = b;
      this._bindCells();
      this._highlightSelection();
      if (HOE.workspace) HOE.workspace.updateStats();
    },

    _bindCells() {
      const cells = this.el.querySelectorAll("[contenteditable='true']");
      cells.forEach((cell) => {
        cell.addEventListener("focus", () => {
          this.sel = {
            r: +cell.dataset.r,
            c: +cell.dataset.c,
          };
          this._highlightSelection();
        });
        cell.addEventListener("beforeinput", () => this._maybeSnapshot(cell));
        cell.addEventListener("input", () => {
          this.data[+cell.dataset.r][+cell.dataset.c] = cell.textContent;
        });
        cell.addEventListener("paste", (e) => this._onPaste(e, cell));
      });
    },

    _maybeSnapshot(cell) {
      // Snapshot once per editing session on a cell.
      if (this._editingCell !== cell) {
        this._snapshot();
        this._editingCell = cell;
      }
    },

    _highlightSelection() {
      this.el
        .querySelectorAll(".cell-selected")
        .forEach((c) => c.classList.remove("cell-selected"));
      const target = this.el.querySelector(
        "[data-r='" + this.sel.r + "'][data-c='" + this.sel.c + "']"
      );
      if (target) target.classList.add("cell-selected");
    },

    addRow() {
      this._snapshot();
      const w = this.nCols() || 1;
      const at = Math.max(1, this.sel.r + 1);
      this.data.splice(at, 0, new Array(w).fill(""));
      this.sel = { r: at, c: 0 };
      this.render();
    },

    addCol() {
      this._snapshot();
      const at = this.sel.c + 1;
      this.data.forEach((row) => row.splice(at, 0, ""));
      this.sel = { r: this.sel.r, c: at };
      this.render();
    },

    delRow() {
      if (this.data.length <= 1) {
        HOE.toast("Cannot delete the header row", "warning");
        return;
      }
      if (this.sel.r < 1) {
        HOE.toast("Select a data row to delete", "warning");
        return;
      }
      this._snapshot();
      this.data.splice(this.sel.r, 1);
      this.sel.r = Math.min(this.sel.r, this.data.length - 1);
      this.render();
    },

    delCol() {
      if (this.nCols() <= 1) {
        HOE.toast("Cannot delete the last column", "warning");
        return;
      }
      this._snapshot();
      this.data.forEach((row) => row.splice(this.sel.c, 1));
      this.sel.c = Math.max(0, this.sel.c - 1);
      this.render();
    },

    clearCell() {
      this._snapshot();
      if (this.data[this.sel.r]) this.data[this.sel.r][this.sel.c] = "";
      this.render();
      this._focusSel();
    },

    _focusSel() {
      const t = this.el.querySelector(
        "[data-r='" + this.sel.r + "'][data-c='" + this.sel.c + "']"
      );
      if (t) t.focus();
    },

    search(term) {
      this.el
        .querySelectorAll(".cell-match")
        .forEach((c) => c.classList.remove("cell-match"));
      term = (term || "").trim().toLowerCase();
      if (!term) return 0;
      let count = 0;
      this.el.querySelectorAll("[contenteditable='true']").forEach((cell) => {
        if (cell.textContent.toLowerCase().includes(term)) {
          cell.classList.add("cell-match");
          count++;
        }
      });
      return count;
    },

    _onPaste(e, cell) {
      const text = (e.clipboardData || window.clipboardData).getData("text");
      if (!text || (!text.includes("\t") && !text.includes("\n"))) {
        return; // single value: let the browser handle it
      }
      e.preventDefault();
      this._snapshot();
      const rows = text.replace(/\r/g, "").split("\n").filter((r, i, a) =>
        r !== "" || i < a.length - 1
      );
      const startR = +cell.dataset.r;
      const startC = +cell.dataset.c;
      rows.forEach((line, dr) => {
        const cols = line.split("\t");
        const r = startR + dr;
        while (this.data.length <= r) this.data.push([]);
        cols.forEach((val, dc) => {
          const c = startC + dc;
          while (this.data[r].length <= c) this.data[r].push("");
          this.data[r][c] = val;
        });
      });
      this.render();
      HOE.toast("Pasted " + rows.length + " row(s)", "success");
    },

    _onKey(e) {
      const mod = e.ctrlKey || e.metaKey;
      if (!mod) return;
      const k = e.key.toLowerCase();
      if (k === "z") {
        e.preventDefault();
        this.undo();
      } else if (k === "y") {
        e.preventDefault();
        this.redo();
      }
    },
  };

  function escapeHtml(s) {
    return ("" + s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  HOE.table = editor;
})();
