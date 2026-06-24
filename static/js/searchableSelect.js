/* searchableSelect.js
 * Pure-JS searchable dropdown for the AI Road Safety Platform.
 * Zero external dependencies — matches the existing dark-mode design tokens.
 *
 * Key UX behaviour:
 *   • Opening the dropdown ALWAYS clears the search box and shows ALL options.
 *   • The selected label is displayed in the closed state, never in the search box.
 *   • Closing restores the selected label.
 *
 * Public API (per instance):
 *   ss.setOptions(dataArray, valueFn, labelFn, searchFn)
 *   ss.getValue()
 *   ss.setValue(val)
 *   ss.onChange(fn)     →  fn(value, rawOpt)
 *   ss.destroy()
 */

(function (global) {
  "use strict";

  /* HTML-escape helper — self-contained so load order doesn't matter. */
  function esc(s) {
    if (s == null) return "";
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  /* Build a debounced version of fn (ms = debounce window). */
  function debounce(fn, ms) {
    let t;
    return function (...args) {
      clearTimeout(t);
      t = setTimeout(() => fn.apply(this, args), ms);
    };
  }

  class SearchableSelect {
    /**
     * @param {HTMLSelectElement} selectEl   Original <select> to enhance.
     * @param {object}            [cfg]
     *   cfg.placeholder    {string}  Search box placeholder (shown when open).
     *   cfg.displayLabel   {string}  Label shown in the closed button state.
     *                                Defaults to cfg.placeholder without "Search ".
     *   cfg.noResultsText  {string}  Empty-state message.
     *   cfg.maxVisible     {number}  Max rows rendered (default 300).
     */
    constructor(selectEl, cfg = {}) {
      this._sel    = selectEl;
      this._opts   = [];
      this._filt   = [];
      this._value  = null;
      this._cbs    = [];
      this._open   = false;
      this._hi     = -1;

      this._ph     = cfg.placeholder   || "Search…";
      this._noRes  = cfg.noResultsText || "No matching results found";
      this._maxVis = cfg.maxVisible    || 300;

      this._buildDom();
    }

    /* ── DOM construction ─────────────────────────────────────────────── */
    _buildDom() {
      const sel = this._sel;

      /* Wrapper */
      const wrap = document.createElement("div");
      wrap.className = "ss-wrap";

      /* Closed-state button — shows the selected label */
      const trigger = document.createElement("div");
      trigger.className = "ss-trigger";
      trigger.setAttribute("tabindex", "0");
      trigger.setAttribute("role", "button");
      trigger.setAttribute("aria-haspopup", "listbox");
      trigger.setAttribute("aria-expanded", "false");

      const triggerLabel = document.createElement("span");
      triggerLabel.className = "ss-trigger-label";

      const triggerArrow = document.createElement("span");
      triggerArrow.className = "ss-arrow";
      triggerArrow.innerHTML = "▾";
      triggerArrow.setAttribute("aria-hidden", "true");

      trigger.appendChild(triggerLabel);
      trigger.appendChild(triggerArrow);

      /* Dropdown panel */
      const panel = document.createElement("div");
      panel.className = "ss-panel";
      panel.setAttribute("role", "listbox");

      /* Search row inside panel */
      const searchRow = document.createElement("div");
      searchRow.className = "ss-search-row";

      const searchIcon = document.createElement("span");
      searchIcon.className = "ss-search-icon";
      searchIcon.innerHTML = "⌕";
      searchIcon.setAttribute("aria-hidden", "true");

      const inp = document.createElement("input");
      inp.type         = "text";
      inp.className    = "ss-search-input";
      inp.placeholder  = this._ph;
      inp.autocomplete = "off";
      inp.spellcheck   = false;
      inp.setAttribute("role", "combobox");
      inp.setAttribute("aria-autocomplete", "list");
      if (sel.id) inp.id = "ss-input-" + sel.id;

      searchRow.appendChild(searchIcon);
      searchRow.appendChild(inp);

      /* Option list */
      const list = document.createElement("div");
      list.className = "ss-list";

      panel.appendChild(searchRow);
      panel.appendChild(list);

      wrap.appendChild(trigger);
      wrap.appendChild(panel);

      /* Hide native select; keep it in DOM for form submit compatibility */
      sel.style.display = "none";
      sel.parentNode.insertBefore(wrap, sel.nextSibling);

      this._wrap        = wrap;
      this._trigger     = trigger;
      this._triggerLabel = triggerLabel;
      this._panel       = panel;
      this._inp         = inp;
      this._list        = list;

      this._wireEvents();
    }

    /* ── Event wiring ─────────────────────────────────────────────────── */
    _wireEvents() {
      const { _trigger: trigger, _inp: inp, _wrap: wrap } = this;

      /* Toggle on trigger click */
      trigger.addEventListener("click",  () => this._open ? this._closeDd() : this._openDd());
      trigger.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " " || e.key === "ArrowDown") {
          e.preventDefault();
          this._openDd();
        }
      });

      /* Real-time search — debounced at 60 ms for thousands of items */
      const debouncedFilter = debounce((val) => this._filter(val), 60);
      inp.addEventListener("input", () => debouncedFilter(inp.value));

      /* Keyboard navigation inside search */
      inp.addEventListener("keydown", (e) => {
        switch (e.key) {
          case "ArrowDown":
            e.preventDefault();
            this._moveHi(1);
            break;
          case "ArrowUp":
            e.preventDefault();
            this._moveHi(-1);
            break;
          case "Enter":
            e.preventDefault();
            if (this._hi >= 0 && this._hi < this._filt.length)
              this._pick(this._filt[this._hi]);
            break;
          case "Escape":
          case "Tab":
            this._closeDd();
            break;
        }
      });

      /* Close on outside click */
      document.addEventListener("click", (e) => {
        if (this._open && !wrap.contains(e.target)) this._closeDd();
      }, true);
    }

    /* ── Open / close ─────────────────────────────────────────────────── */
    _openDd() {
      if (this._open) return;
      this._open = true;

      this._panel.classList.add("ss-panel-open");
      this._trigger.setAttribute("aria-expanded", "true");
      this._wrap.classList.add("ss-open");

      /* CRITICAL: clear search field so all options are shown immediately */
      this._inp.value = "";
      this._filter("");   // render full unfiltered list

      /* Focus the search input */
      requestAnimationFrame(() => {
        this._inp.focus();
        this._scrollHiIntoView();
      });
    }

    _closeDd() {
      if (!this._open) return;
      this._open = false;

      this._panel.classList.remove("ss-panel-open");
      this._trigger.setAttribute("aria-expanded", "false");
      this._wrap.classList.remove("ss-open");

      /* Restore display label in trigger */
      this._refreshTriggerLabel();
    }

    /* ── Trigger label ────────────────────────────────────────────────── */
    _refreshTriggerLabel() {
      const cur = this._opts.find((o) => o.value === this._value);
      this._triggerLabel.textContent = cur ? cur.label : (this._ph || "Select…");
    }

    /* ── Filtering ────────────────────────────────────────────────────── */
    _filter(raw) {
      const q = (raw || "").trim().toLowerCase();
      this._filt = q
        ? this._opts.filter((o) => o.searchText.includes(q)).slice(0, this._maxVis)
        : this._opts.slice(0, this._maxVis);
      this._renderList(q);
    }

    /* ── Render option rows ───────────────────────────────────────────── */
    _renderList(q) {
      const list = this._list;
      if (!this._filt.length) {
        list.innerHTML = `<div class="ss-no-results">${esc(this._noRes)}</div>`;
        this._hi = -1;
        return;
      }

      /* Use DocumentFragment for performance with large lists */
      const frag = document.createDocumentFragment();
      this._filt.forEach((opt, idx) => {
        const div = document.createElement("div");
        div.className  = "ss-option" + (opt.value === this._value ? " ss-selected" : "");
        div.dataset.idx = idx;
        div.innerHTML  = this._hlText(opt.label, q);
        div.setAttribute("role", "option");
        div.setAttribute("aria-selected", opt.value === this._value ? "true" : "false");

        div.addEventListener("mousedown", (e) => {
          e.preventDefault();   // prevent blur before pick
          this._pick(opt);
        });
        div.addEventListener("mousemove", () => {
          this._hi = idx;
          this._syncHiClass();
        });
        frag.appendChild(div);
      });

      list.innerHTML = "";
      list.appendChild(frag);

      /* Auto-highlight the currently selected option, or first item */
      const selIdx = this._filt.findIndex((o) => o.value === this._value);
      this._hi = selIdx >= 0 ? selIdx : 0;
      this._syncHiClass();
    }

    /* Highlight matching chars */
    _hlText(label, q) {
      const safe = esc(label);
      if (!q) return safe;
      const safeQ = esc(q).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      return safe.replace(
        new RegExp(safeQ, "gi"),
        (m) => `<mark class="ss-mark">${m}</mark>`
      );
    }

    /* ── Keyboard highlight ───────────────────────────────────────────── */
    _moveHi(dir) {
      const len = this._filt.length;
      if (!len) return;
      this._hi = Math.max(0, Math.min(len - 1, this._hi + dir));
      this._syncHiClass();
      this._scrollHiIntoView();
    }

    _syncHiClass() {
      this._list.querySelectorAll(".ss-option").forEach((el, i) => {
        el.classList.toggle("ss-highlighted", i === this._hi);
      });
    }

    _scrollHiIntoView() {
      const items = this._list.querySelectorAll(".ss-option");
      if (items[this._hi]) items[this._hi].scrollIntoView({ block: "nearest" });
    }

    /* ── Pick an option ───────────────────────────────────────────────── */
    _pick(opt) {
      this._value = opt.value;
      this._closeDd();
      this._syncNative(opt.value);
      this._cbs.forEach((fn) => fn(opt.value, opt._raw));
    }

    _syncNative(val) {
      const sel   = this._sel;
      const found = [...sel.options].find((o) => String(o.value) === String(val));
      if (found) {
        sel.value = val;
        sel.dispatchEvent(new Event("change", { bubbles: true }));
      }
    }

    /* ══════════════════════════════════════════════════════════════════
       PUBLIC API
       ══════════════════════════════════════════════════════════════════ */

    /**
     * Populate options.
     * @param {Array}           data
     * @param {string|function} valueFn   Key name or fn → value string.
     * @param {string|function} labelFn   Key name or fn → display label.
     * @param {function}       [searchFn] fn(row) → full searchable string
     *                                    (include all hidden metadata here).
     */
    setOptions(data, valueFn, labelFn, searchFn) {
      const gv = typeof valueFn === "function" ? valueFn : (o) => o[valueFn];
      const gl = typeof labelFn === "function" ? labelFn : (o) => o[labelFn];
      const gs = searchFn || ((o) => gl(o));

      this._opts = data.map((o) => ({
        value:      String(gv(o)),
        label:      String(gl(o)),
        searchText: String(gs(o)).toLowerCase(),
        _raw:       o,
      }));

      /* Rebuild native <select> to stay in sync */
      const sel     = this._sel;
      const prevVal = this._value || sel.value;
      sel.innerHTML = this._opts
        .map((o) => `<option value="${esc(o.value)}">${esc(o.label)}</option>`)
        .join("");

      const still = this._opts.some((o) => o.value === String(prevVal));
      if (still) {
        this._value = String(prevVal);
        sel.value   = this._value;
      } else if (this._opts.length) {
        this._value = this._opts[0].value;
        sel.value   = this._value;
      } else {
        this._value = null;
      }

      this._refreshTriggerLabel();
    }

    /** Returns the currently selected value string. */
    getValue() { return this._value; }

    /**
     * Programmatically set the selected value.
     * Does NOT fire onChange callbacks.
     */
    setValue(val) {
      const opt = this._opts.find((o) => o.value === String(val));
      if (!opt) return;
      this._value    = opt.value;
      this._sel.value = opt.value;
      this._refreshTriggerLabel();
    }

    /** Register a change callback: fn(value: string, rawOption: object) */
    onChange(fn) { this._cbs.push(fn); }

    /** Remove the widget and restore the original <select>. */
    destroy() {
      this._wrap.remove();
      this._sel.style.display = "";
    }
  }

  global.SearchableSelect = SearchableSelect;

})(window);
