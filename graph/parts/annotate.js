/* The drawing toolbar on the Overview: select, pen, shapes, text, eraser, colours, undo.

   One tool at a time, the pressed one highlighted, Esc back to Select, so it is always
   clear whether a drag draws or turns the globe: in Select a plain drag still turns it,
   and Shift+drag picks the papers under a box. Marks join the view on screen (marks.js);
   the first mark where there is none makes one. The status line under the tools says
   what the tool does and whether the marks are being kept. */

const TOOLS = ["select", "pen", "shape", "text", "eraser"];
const TOOL_HINTS = {
  select: "Click a mark to move, resize, recolour or delete it. Shift+drag across dots to pick papers.",
  pen: "Draw freehand. Esc returns to Select.",
  shape: "Drag to draw. An arrow snaps to the dot it points at.",
  text: "Click where the label goes. Anything longer belongs in a note.",
  eraser: "Click a mark to remove it.",
};
MIN_CARDS.push("annotbar");
AN.drawing = null;     /* what is being drawn now: a pen stroke, a shape, a pick box or a label */
AN.note = "";          /* a passing word from the toolbar, e.g. why a mark was not added */

function setTool(tool) {
  if (!TOOLS.includes(tool)) tool = "select";
  if (AN.drawing && AN.drawing.cancel) AN.drawing.cancel();
  AN.tool = tool; AN.drawing = null; AN.note = "";
  for (const t of TOOLS) document.getElementById("ann-" + t).setAttribute("aria-pressed", String(t === tool));
  marksNotify(); globeRequestDraw();
}
/* Esc steps back one thing: the drawing in progress, then the tool, then the selected mark. */
function annotEsc() {
  if (AN.drawing) { if (AN.drawing.cancel) AN.drawing.cancel(); AN.drawing = null; globeRequestDraw(); return true; }
  if (AN.tool !== "select") { setTool("select"); return true; }
  if (AN.selected) { AN.selected = null; marksNotify(); globeRequestDraw(); return true; }
  return false;
}
function annotHint(tool, save) {
  const said = AN.error ? "Marks cannot be saved: " + AN.error : {
    saved: "Marks saved.", saving: "Saving…", unsaved: "Saving…",
    off: "Marks are not kept: saving is off (run /graph to save). Save as image keeps a picture.",
    failed: "Not saved: " + AN.msg + " Save as image keeps a picture.",
    conflict: "Your marks changed somewhere else.", deleted: "Your saved marks were deleted elsewhere.",
  }[save] || "";
  return (TOOL_HINTS[tool] || TOOL_HINTS.select) + (said ? " " + said : "");
}
/* The shown items on the globe's near side, in globe units: what a box or a mark holds. */
function visibleCands() {
  if (!GL.model) return [];
  const m = GL.model, rot = rotation(GL.yaw, GL.pitch), out = [];
  for (let i = 0; i < m.n; i++) {
    if (!GL.mask[i]) continue;
    const p = project(rot, m.vx[i], m.vy[i], m.vz[i]);
    if (p[2] > 0) out.push({ id: m.ids[i], u: p[0], v: -p[1], score: (byId.get(m.ids[i]) || {}).score });
  }
  return out;
}
/* The dots drawn right now, in globe units: what an arrow can snap to. */
function drawnCands(geo) {
  return GL.hits.map(([x, y, i]) => ({ id: GL.model.ids[i], u: (x - geo.cx) / geo.R, v: (y - geo.cy) / geo.R }));
}

/* ---------- views and marks ---------- */
function hex6() { return Array.from(crypto.getRandomValues(new Uint8Array(3)), (b) => b.toString(16).padStart(2, "0")).join(""); }
function newViewId(today) { return "v-" + today.replace(/-/g, "") + "-" + hex6(); }
/* The view on screen, or a new one for it: the camera and filters, named for what they show. */
function ensureView() {
  const on = activeView();
  if (on) return on;
  const today = new Date().toISOString().slice(0, 10), flt = filterState(), now = new Date().toISOString().replace(/\.\d+Z$/, "Z");
  const v = { id: newViewId(today), name: viewName(flt, today), created: now, updated: now, camera: cameraOf(GL), filters: flt, marks: [] };
  AN.views.push(v);
  return v;
}
function addMark(mark) {
  const existed = activeView();
  if (!existed && AN.views.length >= 200) { AN.note = "200 saved views is the most the map keeps; delete one in the notes list first."; marksNotify(); return; }
  if (existed && existed.marks.length >= 500) { AN.note = "This view holds 500 marks, the most it can."; marksNotify(); return; }
  const v = ensureView(), before = existed ? JSON.stringify(v) : null;
  mark.pts = mark.pts.map(([u, v2]) => [Math.max(-50, Math.min(50, u)), Math.max(-50, Math.min(50, v2))]);
  v.marks.push(mark); AN.note = "";
  marksChanged(v.id, before);
}
/* Change the view on screen through FN, so undo can take it back. */
function changeView(fn) {
  const v = activeView();
  if (!v) return;
  const before = JSON.stringify(v);
  fn(v);
  marksChanged(v.id, before);
}
function markOnTop(view, u, v, tol, R) {
  for (let i = view.marks.length - 1; i >= 0; i--) if (hitMark(view.marks[i], u, v, tol, R)) return view.marks[i];
  return null;
}
function selectedMark() {
  const v = activeView();
  return v && AN.selected ? v.marks.find((m) => m.id === AN.selected) || null : null;
}
function onHandle(mark, x, y, geo) {
  if (mark.kind === "text") return false;
  const b = markBox(mark, geo.R), [hx, hy] = fromUnits(b.x1, b.y1, geo);
  return x >= hx - 3 && x <= hx + 11 && y >= hy - 3 && y <= hy + 11;
}
function afterHistory() {
  AN.selected = null;
  AN.save = NT.serving ? "unsaved" : "off";
  clearTimeout(AN.timer);
  if (NT.serving) AN.timer = setTimeout(saveMarks, 800);
  marksNotify(); globeRequestDraw();
}
function annotUndo() { if (AN.history && AN.history.undo.length) { AN.views = undoStep(AN.views, AN.history); afterHistory(); } }
function annotRedo() { if (AN.history && AN.history.redo.length) { AN.views = redoStep(AN.views, AN.history); afterHistory(); } }
function deleteSelected() {
  const id = AN.selected;
  if (!id) return;
  changeView((v) => { v.marks = v.marks.filter((m) => m.id !== id); });
  AN.selected = null; marksNotify();
}

/* ---------- the pointer ---------- */
let ADRAG = null;
function labelInput(x, y, at) {
  const input = el("input", { class: "ann-label", type: "text", maxlength: String(LABEL_MAX), placeholder: "Label (60 characters)", "aria-label": "Label" });
  input.style.left = x + "px"; input.style.top = (y - 12) + "px";
  let done = false;
  const finish = (keep) => {
    if (done) return;
    done = true; input.remove(); AN.drawing = null;
    const text = input.value.trim();
    if (keep && text) addMark({ id: "m-" + hex6(), kind: "text", colour: AN.colour, width: 0, pts: [at], text: text.slice(0, LABEL_MAX) });
    globeRequestDraw();
  };
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); finish(true); }
    else if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); finish(false); }
  });
  input.addEventListener("blur", () => finish(true));
  $("#tab-overview").append(input);
  AN.drawing = { kind: "label", cancel: () => finish(false) };
  input.focus();
}
GL.input = {
  down(x, y, e) {
    if (S.tab !== "overview" || e.button > 0) return false;
    const geo = globeGeometry(), [u, v] = toUnits(x, y, geo), tol = 6 / geo.R, view = activeView();
    if (AN.tool === "select") {
      const sel = selectedMark();
      if (sel && onHandle(sel, x, y, geo)) {
        ADRAG = { mode: "resize", before: JSON.stringify(view), orig: JSON.parse(JSON.stringify(sel.pts)), box: markBox(sel, geo.R), moved: false };
        return true;
      }
      const hit = view && markOnTop(view, u, v, tol, geo.R);
      if (hit) {
        AN.selected = hit.id;
        ADRAG = { mode: "move", before: JSON.stringify(view), orig: JSON.parse(JSON.stringify(hit.pts)), start: [u, v], moved: false };
        marksNotify(); globeRequestDraw();
        return true;
      }
      if (e.shiftKey) { AN.drawing = { kind: "pick", a: [x, y], b: [x, y] }; ADRAG = { mode: "pick" }; return true; }
      if (AN.selected) { AN.selected = null; marksNotify(); globeRequestDraw(); }
      return false;
    }
    if (AN.tool === "pen") { AN.drawing = { kind: "pen", pts: [[u, v]] }; ADRAG = { mode: "pen" }; return true; }
    if (AN.tool === "shape") { AN.drawing = { kind: AN.shape, pts: [[u, v], [u, v]], a: [x, y] }; ADRAG = { mode: "shape" }; return true; }
    /* the label box opens when the click ends: opened on the press, the press's own focus change would close it */
    if (AN.tool === "text") { ADRAG = { mode: AN.drawing ? "none" : "label" }; return true; }
    /* eraser: a drag never turns the globe while it is the tool */
    const hit = view && markOnTop(view, u, v, tol, geo.R);
    if (hit) { changeView((vw) => { vw.marks = vw.marks.filter((m) => m.id !== hit.id); }); if (AN.selected === hit.id) AN.selected = null; }
    ADRAG = { mode: "none" };
    return true;
  },
  move(x, y) {
    if (!ADRAG) return;
    const geo = globeGeometry(), [u, v] = toUnits(x, y, geo), d = AN.drawing;
    if (ADRAG.mode === "pen") d.pts.push([u, v]);
    else if (ADRAG.mode === "shape") d.pts[1] = [u, v];
    else if (ADRAG.mode === "pick") d.b = [x, y];
    else if (ADRAG.mode === "move") {
      const m = selectedMark(), du = u - ADRAG.start[0], dv = v - ADRAG.start[1];
      if (m) { m.pts = ADRAG.orig.map(([a, b]) => [a + du, b + dv]); ADRAG.moved = true; }
    } else if (ADRAG.mode === "resize") {
      const m = selectedMark(), b = ADRAG.box;
      if (m) {
        if (m.kind === "arrow") m.pts = [ADRAG.orig[0], [u, v]];
        else {
          const sx = (u - b.x0) / Math.max(1e-6, b.x1 - b.x0), sy = (v - b.y0) / Math.max(1e-6, b.y1 - b.y0);
          m.pts = ADRAG.orig.map(([a, c]) => [b.x0 + (a - b.x0) * sx, b.y0 + (c - b.y0) * sy]);
        }
        ADRAG.moved = true;
      }
    } else return;
    globeRequestDraw();
  },
  up(x, y) {
    const drag = ADRAG, d = AN.drawing, geo = globeGeometry();
    ADRAG = null;
    if (!drag) return;
    if (drag.mode === "pen") {
      AN.drawing = null;
      if (d.pts.length >= 2) addMark({ id: "m-" + hex6(), kind: "pen", colour: AN.colour, width: AN.width, pts: simplify(d.pts, 2 / geo.R) });
    } else if (drag.mode === "shape") {
      AN.drawing = null;
      if (Math.hypot(x - d.a[0], y - d.a[1]) < 4) { globeRequestDraw(); return; }
      const mark = { id: "m-" + hex6(), kind: d.kind, colour: AN.colour, width: AN.width, pts: d.pts };
      if (d.kind === "arrow") {
        const t = snapTarget(d.pts[1][0], d.pts[1][1], drawnCands(geo), 14 / geo.R);
        mark.snap = t ? t.id : null;
        if (t) mark.pts = [d.pts[0], [t.u, t.v]];
      }
      addMark(mark);
    } else if (drag.mode === "pick") {
      AN.drawing = null;
      const [a, b] = [toUnits(...d.a, geo), toUnits(...d.b, geo)];
      const box = { kind: "rect", pts: [a, b] }, ids = visibleCands().filter((c) => insideMark(box, c.u, c.v)).map((c) => c.id);
      if (ids.length) { highlightSet(ids, "picked on the globe"); renderHighlightChip(); }
      globeRequestDraw();
    } else if (drag.mode === "label") {
      labelInput(x, y, toUnits(x, y, geo));
    } else if ((drag.mode === "move" || drag.mode === "resize") && drag.moved) {
      const v = activeView();
      if (v) marksChanged(v.id, drag.before);
    }
  },
};

/* What is being drawn, before it becomes a mark. */
GL.overlays.push({
  draw: (g, P, R, cx, cy) => {
    const d = AN.drawing, geo = { cx, cy, R };
    if (d && d.kind === "pick") {
      g.save(); g.strokeStyle = css("--focus"); g.lineWidth = 1; g.setLineDash([4, 3]);
      g.strokeRect(Math.min(d.a[0], d.b[0]), Math.min(d.a[1], d.b[1]), Math.abs(d.b[0] - d.a[0]), Math.abs(d.b[1] - d.a[1])); g.restore();
    } else if (d && d.pts) {
      drawMarks(g, { marks: [{ id: "drawing", kind: d.kind, colour: AN.colour, width: AN.width, pts: d.pts }] }, geo, markColours(), null, null);
    }
    placeMarkActions(geo);
  },
  hit: () => null,
});
/* The bar beside the selected mark: make a note from it, or delete it. */
function placeMarkActions(geo) {
  const bar = $("#mark-actions"), m = selectedMark();
  if (!m || AN.tool !== "select") { bar.hidden = true; return; }
  const b = markBox(m, geo.R), [x0] = fromUnits(b.x0, b.y1, geo), [, y1] = fromUnits(b.x1, b.y1, geo), area = $("#tab-overview");
  if (bar.hidden || bar.dataset.mark !== m.id) {
    bar.dataset.mark = m.id;
    bar.replaceChildren(
      el("button", { on: { click: () => { if (typeof noteFromMark === "function") noteFromMark(m.id); } } }, "Make a note from this"),
      el("button", { on: { click: deleteSelected } }, "Delete"));
    bar.hidden = false;
  }
  bar.style.left = Math.max(8, Math.min(area.clientWidth - bar.offsetWidth - 8, x0)) + "px";
  bar.style.top = Math.max(8, Math.min(area.clientHeight - bar.offsetHeight - 8, y1 + 14)) + "px";
}

/* ---------- the toolbar ---------- */
/* Whether the toolbar's box TB ([left, top, right, bottom]) covers any of the CARDS (null: not shown). */
function crowds(tb, cards) {
  return cards.some((c) => c && tb[0] < c[2] && c[0] < tb[2] && tb[1] < c[3] && c[1] < tb[3]);
}
function renderAnnotbar() {
  const tb = $("#annotbar"), min = !!S.min.cards.annotbar;
  tb.classList.toggle("min", min);
  $("#globe").classList.toggle("draw-mode", AN.tool !== "select");
  for (const b of document.querySelectorAll(".ann-colour")) b.setAttribute("aria-pressed", String(+b.dataset.c === AN.colour));
  $("#ann-width").value = String(AN.width); $("#ann-shape-kind").value = AN.shape;
  $("#ann-undo").disabled = !(AN.history && AN.history.undo.length);
  $("#ann-redo").disabled = !(AN.history && AN.history.redo.length);
  const v = activeView();
  $("#ann-clear").disabled = !(v && v.marks.length);
  const msg = $("#ann-msg"), warn = AN.error || ["off", "failed", "conflict", "deleted"].includes(AN.save);
  msg.replaceChildren(el("span", { class: warn ? "warn" : "" }, annotHint(AN.tool, AN.save)));
  if (AN.save === "conflict" && AN.conflict) msg.append(el("button", { on: { click: keepMine } }, "Keep mine"), el("button", { on: { click: useFilesMarks } }, "Use the file's"));
  if (AN.save === "deleted") msg.append(el("button", { on: { click: saveAgain } }, "Save them again"));
  if (AN.note) msg.append(el("div", {}, AN.note));
}
function annotInit() {
  const tb = $("#annotbar"), area = $("#tab-overview");
  /* Centred, just above the cards along the bottom: until the researcher moves it, it stays centred as
     it grows from its chip or its status line wraps. */
  const home = () => {
    const tops = ["globe-nav", "globe-legend", "globe-notice"].map((id) => document.getElementById(id)).filter((e) => e && !e.hidden && e.offsetHeight).map((e) => e.offsetTop);
    return { x: (area.clientWidth - tb.offsetWidth) / 2, y: Math.min(area.clientHeight - 14, ...tops) - tb.offsetHeight - 8 };
  };
  makeToolbar(tb, area, $("#ann-grip"), "kg-annotbar", home);
  let firstPlace = true;
  new ResizeObserver(() => {
    if (!area.clientWidth || store.get("kg-annotbar") != null) return;
    const d = home();
    placeToolbar(tb, area, "kg-annotbar", d.x, d.y, false);
    /* On a narrow window its first spot can cover a card: then it starts as the "▸ Draw" chip,
       unless the researcher has already opened or closed it. */
    if (firstPlace && !tb.classList.contains("min") && S.min.cards.annotbar === undefined) {
      firstPlace = false;
      const box = (e) => { if (!e || e.hidden || !e.offsetWidth || e.classList.contains("min")) return null; const b = e.getBoundingClientRect(); return [b.left, b.top, b.right, b.bottom]; };
      if (crowds(box(tb), ["mapcard", "selcard", "noteeditor", "noteslist"].map((id) => box(document.getElementById(id))))) setCardMin("annotbar", true);
    }
  }).observe(tb);
  for (const t of TOOLS) $("#ann-" + t).addEventListener("click", () => setTool(t));
  $("#ann-shape-kind").addEventListener("change", (e) => { AN.shape = e.target.value; setTool("shape"); });
  for (const b of document.querySelectorAll(".ann-colour")) b.addEventListener("click", () => {
    AN.colour = +b.dataset.c;
    const m = selectedMark();
    if (m) changeView(() => { m.colour = AN.colour; }); else marksNotify();
  });
  $("#ann-width").addEventListener("change", (e) => {
    AN.width = +e.target.value;
    const m = selectedMark();
    if (m && m.kind !== "text") changeView(() => { m.width = AN.width; }); else marksNotify();
  });
  $("#ann-undo").addEventListener("click", annotUndo);
  $("#ann-redo").addEventListener("click", annotRedo);
  $("#ann-clear").addEventListener("click", () => {
    const v = activeView();
    if (v && v.marks.length && window.confirm("Remove all " + v.marks.length + " marks in this view?")) { changeView((vw) => { vw.marks = []; }); AN.selected = null; }
  });
  $("#ann-note").addEventListener("click", () => { if (typeof noteFromToolbar === "function") noteFromToolbar(); });
  $("#ann-image").addEventListener("click", () => { if (typeof saveImage === "function") saveImage(); });
  $("#ann-close").addEventListener("click", () => { setTool("select"); setCardMin("annotbar", true); });
  $("#ann-chip").addEventListener("click", () => setCardMin("annotbar", false));
  document.addEventListener("keydown", (e) => {
    if (S.tab !== "overview" || /INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)) return;
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "z") { e.preventDefault(); if (e.shiftKey) annotRedo(); else annotUndo(); }
    else if ((e.key === "Delete" || e.key === "Backspace") && AN.selected) { e.preventDefault(); deleteSelected(); }
  });
  AN.onChange.push(renderAnnotbar);
  renderAnnotbar();
}
annotInit();

/* ---------- saved views: the chip, going back, the list, notes and pictures ---------- */
/* "Annotated view: <name> · " while the view last shown with marks is not the one on screen. */
function viewChipText(views, last, active) {
  if (!last || last === active) return null;
  const v = views.find((x) => x.id === last);
  return v && v.marks.length ? "Annotated view: " + v.name + " · " : null;
}
function renderViewChip() {
  const chip = $("#view-chip"), text = viewChipText(AN.views, AN.last, AN.active);
  chip.hidden = !text;
  if (text) chip.replaceChildren(text, el("button", { class: "linkbtn", on: { click: () => backToView(AN.last) } }, "Back to it"));
}
/* The view's filters first (they decide what is drawn), then the globe turns to its camera. */
function backToView(id) {
  const v = AN.views.find((x) => x.id === id);
  if (!v) return;
  AN.last = id;
  filtersFromState(v.filters);
  refreshData();
  const c = v.camera;
  GL.back = null;
  globeTween({ yaw: GL.yaw, pitch: GL.pitch, zoom: GL.zoom, panX: GL.panX, panY: GL.panY },
    { yaw: GL.yaw + wrapAngle(c.yaw - GL.yaw), pitch: GL.pitch + wrapAngle(c.pitch - GL.pitch), zoom: c.zoom, panX: c.panX, panY: c.panY });
}
function renameView(id, name) {
  const v = AN.views.find((x) => x.id === id), t = String(name || "").trim();
  if (!v || !t || t.length > 80) return false;
  const before = JSON.stringify(v);
  v.name = t;
  marksChanged(id, before);
  return true;
}
function deleteView(id) {
  const v = AN.views.find((x) => x.id === id);
  if (!v || !window.confirm("Delete the view " + v.name + " and its " + v.marks.length + " " + (v.marks.length === 1 ? "mark" : "marks") + "?")) return;
  const before = JSON.stringify(v);
  AN.views = AN.views.filter((x) => x.id !== id);
  if (AN.last === id) AN.last = null;
  marksChanged(id, before);
}
/* A note that starts linked to what the mark holds: at most 100, highest scored first. */
function noteFromMark(markId) {
  const view = activeView(), mark = view && view.marks.find((m) => m.id === markId);
  if (!mark) return false;
  const r = itemsInMark(mark, visibleCands(), 100);
  AN.note = r.total > r.ids.length ? "Linked the " + r.ids.length + " highest-scored of " + r.total + " items in the mark." : "";
  marksNotify();
  openEditor(null, r.ids);
  return true;
}
/* ＋ Note: the selected mark's items, else the highlight, else the selected item, else nothing. */
function noteFromToolbar() {
  if (AN.selected && noteFromMark(AN.selected)) return;
  AN.note = "";
  openEditor(null, S.highlight ? [...S.highlight] : S.current ? [S.current] : []);
}
function imageName(view) {
  const slug = view ? String(view.name).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 60) : "";
  return "library-map-" + (slug || "view") + ".png";
}
/* The globe with its marks as a PNG, on the page's background, without the selection box. */
function saveImage() {
  const cv = $("#globe"), was = AN.selected;
  AN.selected = null; globeDraw();
  const out = document.createElement("canvas");
  out.width = cv.width; out.height = cv.height;
  const g = out.getContext("2d");
  g.fillStyle = css("--plane"); g.fillRect(0, 0, out.width, out.height); g.drawImage(cv, 0, 0);
  download(imageName(activeView()), "image/png", out.toDataURL("image/png"));
  AN.selected = was; globeDraw();
}
/* The Views rows in the notes list: go to, rename, delete. */
AN.renaming = null;
function viewRows(q) {
  const needle = String(q || "").toLowerCase();
  const views = AN.views.filter((v) => !needle || v.name.toLowerCase().includes(needle))
    .sort((a, b) => String(b.updated).localeCompare(String(a.updated)));
  if (!views.length) return [el("p", { class: "note" }, AN.views.length ? "No views match." : "No saved views yet. Draw on the globe to save one.")];
  return views.map((v) => {
    const name = AN.renaming === v.id
      ? el("input", { type: "text", maxlength: "80", value: v.name, "aria-label": "View name", on: { keydown: (e) => {
        if (e.key === "Enter") { e.preventDefault(); renameView(v.id, e.target.value); AN.renaming = null; renderNotesList(); }
        else if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); AN.renaming = null; renderNotesList(); }
      } } })
      : el("strong", {}, v.name);
    return el("div", { class: "nl-row" }, name,
      el("div", { class: "note muted" }, v.marks.length + " " + (v.marks.length === 1 ? "mark" : "marks") + " · updated " + shortDate(String(v.updated).slice(0, 10))),
      el("div", { class: "actions" },
        el("button", { class: "linkbtn", on: { click: () => { NL.open = false; renderNotesList(); backToView(v.id); } } }, "Go to"),
        el("button", { class: "linkbtn", on: { click: () => { AN.renaming = v.id; renderNotesList(); const i = $("#noteslist input[aria-label='View name']"); if (i) i.focus(); } } }, "Rename"),
        el("button", { class: "linkbtn", on: { click: () => { deleteView(v.id); renderNotesList(); } } }, "Delete")));
  });
}
AN.onChange.push(renderViewChip);
AN.onChange.push(() => { if (NL.open && NL.filter.views) renderNotesList(); });
