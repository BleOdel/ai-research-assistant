/* Marks drawn on the map: the model behind the drawing toolbar (annotate.js).

   A mark belongs to a saved view - the globe's camera and the filters it was drawn under -
   not to the sphere: anchored to a turning sphere, a ring round a cluster would drift off
   what it marked. Marks are drawn only while the page shows that view; elsewhere a chip
   offers to go back to it. Their points are in globe units (offsets from the globe's
   centre, in globe radii), so a resized window or a card that moves the globe keeps them
   on the dots they marked. They are saved, whole, to notes/annotations.json through the
   local helper, with the notes' rules: never over a change made elsewhere. */

const MARK_TOKENS = ["--mk1", "--mk2", "--mk3", "--mk4", "--mk5"];
const MARK_NAMES = ["Ink", "Red", "Lime", "Green", "Violet"];
const PEN_WIDTHS = [2, 4, 7];
const LABEL_MAX = 60, LABEL_PX = 14, HISTORY_MAX = 100, MARK_POINTS_MAX = 2000;
const AN = {
  views: [], version: null, error: null,
  active: null,      /* the view the page shows now, if it has one */
  last: null,        /* the view the "Back to it" chip names */
  tool: "select", shape: "rect", colour: 1, width: 1, selected: null,
  history: null, save: "off", msg: "", conflict: null, inFlight: false, pending: false, timer: null,
  onChange: [],      /* what to redraw when the marks or their saving change */
};

/* ---------- units and views ---------- */
function toUnits(x, y, geo) { return [(x - geo.cx) / geo.R, (y - geo.cy) / geo.R]; }
function fromUnits(u, v, geo) { return [geo.cx + u * geo.R, geo.cy + v * geo.R]; }
function cameraOf(gl) { return { yaw: gl.yaw, pitch: gl.pitch, zoom: gl.zoom, panX: gl.panX, panY: gl.panY }; }
/* The same view within what an eye could tell apart: a free drag can leave the yaw any
   number of turns away, so angles compare round the circle. */
function sameCamera(a, b) {
  return Math.abs(wrapAngle(a.yaw - b.yaw)) < 0.002 && Math.abs(wrapAngle(a.pitch - b.pitch)) < 0.002
    && Math.abs(a.zoom / b.zoom - 1) < 0.002 && Math.abs(a.panX - b.panX) < 1 && Math.abs(a.panY - b.panY) < 1;
}
/* One key for the same filters, whatever order their sets, keys or values come in. */
function filterKey(flt) {
  const norm = (v) => Array.isArray(v) ? v.map(norm).sort() : v && typeof v === "object"
    ? Object.fromEntries(Object.keys(v).sort().filter((k) => !(Array.isArray(v[k]) && !v[k].length)).map((k) => [k, norm(v[k])])) : v;
  return JSON.stringify(norm(flt || {}));
}
function viewAt(views, camera, fkey) {
  return views.find((v) => sameCamera(v.camera, camera) && filterKey(v.filters) === fkey) || null;
}
/* "<what the filters show> · <date>", e.g. "Whole library · 1 Nov". */
function viewName(flt, today) {
  const sets = (flt && flt.sets) || {}, interests = sets.interest || [], kinds = sets.type || [];
  const parts = [interests.length === 1 ? interests[0] : interests.length ? interests.length + " interests" : "Whole library"];
  if (kinds.length === 1) parts.push(kinds[0] === KIND_WEB ? "web only" : "papers only");
  return parts.concat(shortDate(today)).join(" · ");
}
function activeView() {
  if (!GL.model) return null;
  return viewAt(AN.views, cameraOf(GL), filterKey(filterState()));
}

/* ---------- geometry, in globe units ---------- */
/* A pen stroke without the points too close to matter, its end kept, at most 2,000 points. */
function simplify(pts, minUnits) {
  if (pts.length < 2) return pts.slice();
  const out = [pts[0]];
  for (let i = 1; i < pts.length; i++) {
    const a = out[out.length - 1];
    if (Math.hypot(pts[i][0] - a[0], pts[i][1] - a[1]) >= minUnits) out.push(pts[i]);
  }
  if (out[out.length - 1] !== pts[pts.length - 1]) out.push(pts[pts.length - 1]);
  if (out.length <= MARK_POINTS_MAX) return out;
  const step = (out.length - 1) / (MARK_POINTS_MAX - 1);
  return Array.from({ length: MARK_POINTS_MAX }, (_, i) => out[Math.round(i * step)]);
}
function markBox(mark, R) {
  if (mark.kind === "text") {
    const [u, v] = mark.pts[0], w = 0.6 * LABEL_PX * mark.text.length / R, h = (LABEL_PX * 0.65) / R;
    return { x0: u, y0: v - h, x1: u + w, y1: v + h };
  }
  const us = mark.pts.map((p) => p[0]), vs = mark.pts.map((p) => p[1]);
  return { x0: Math.min(...us), y0: Math.min(...vs), x1: Math.max(...us), y1: Math.max(...vs) };
}
function segDistU(u, v, a, b) {
  const du = b[0] - a[0], dv = b[1] - a[1], l = du * du + dv * dv;
  const t = l ? Math.max(0, Math.min(1, ((u - a[0]) * du + (v - a[1]) * dv) / l)) : 0;
  return Math.hypot(u - a[0] - t * du, v - a[1] - t * dv);
}
function pointInPolygon(u, v, pts) {
  let inside = false;
  for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
    const [ui, vi] = pts[i], [uj, vj] = pts[j];
    if ((vi > v) !== (vj > v) && u < (uj - ui) * (v - vi) / (vj - vi) + ui) inside = !inside;
  }
  return inside;
}
/* Whether a click at (u, v) picks MARK: near its line, or inside a label. */
function hitMark(mark, u, v, tol, R) {
  const b = markBox(mark, R);
  if (mark.kind === "text") return u >= b.x0 - tol && u <= b.x1 + tol && v >= b.y0 - tol && v <= b.y1 + tol;
  if (mark.kind === "pen" || mark.kind === "arrow") {
    for (let i = 1; i < mark.pts.length; i++) if (segDistU(u, v, mark.pts[i - 1], mark.pts[i]) <= tol) return true;
    return false;
  }
  if (mark.kind === "rect") {
    const c = [[b.x0, b.y0], [b.x1, b.y0], [b.x1, b.y1], [b.x0, b.y1]];
    return c.some((p, i) => segDistU(u, v, p, c[(i + 1) % 4]) <= tol);
  }
  const rx = (b.x1 - b.x0) / 2, ry = (b.y1 - b.y0) / 2, cx = b.x0 + rx, cy = b.y0 + ry;
  if (rx < 1e-9 || ry < 1e-9) return segDistU(u, v, [b.x0, b.y0], [b.x1, b.y1]) <= tol;
  const d = Math.hypot((u - cx) / rx, (v - cy) / ry);
  return Math.abs(d - 1) * Math.min(rx, ry) <= tol;
}
/* What a mark encloses: a rectangle, an ellipse, or a pen stroke read as a closed loop. */
function insideMark(mark, u, v) {
  if (mark.kind === "pen") return pointInPolygon(u, v, mark.pts);
  if (mark.kind !== "rect" && mark.kind !== "ellipse") return false;
  const us = mark.pts.map((p) => p[0]), vs = mark.pts.map((p) => p[1]);
  const x0 = Math.min(...us), x1 = Math.max(...us), y0 = Math.min(...vs), y1 = Math.max(...vs);
  if (mark.kind === "rect") return u >= x0 && u <= x1 && v >= y0 && v <= y1;
  const rx = (x1 - x0) / 2, ry = (y1 - y0) / 2;
  return rx > 0 && ry > 0 && ((u - x0 - rx) / rx) ** 2 + ((v - y0 - ry) / ry) ** 2 <= 1;
}
/* The items a mark holds, for a note made from it: CANDS are the shown, near-side items
   ({id, u, v, score}); the CAP highest scored are kept. An arrow holds the dot it snapped to. */
function itemsInMark(mark, cands, cap) {
  if (mark.kind === "arrow") return mark.snap ? { ids: [mark.snap], total: 1 } : { ids: [], total: 0 };
  const inside = cands.filter((c) => insideMark(mark, c.u, c.v));
  inside.sort((a, b) => (b.score ?? 50) - (a.score ?? 50) || (a.id < b.id ? -1 : 1));
  return { ids: inside.slice(0, cap).map((c) => c.id), total: inside.length };
}
function snapTarget(u, v, cands, tol) {
  let best = null, bd = tol;
  for (const c of cands) { const d = Math.hypot(c.u - u, c.v - v); if (d <= bd) { bd = d; best = c; } }
  return best;
}

/* ---------- undo and redo: whole-view snapshots ---------- */
function newHistory() { return { undo: [], redo: [] }; }
/* BEFORE and AFTER are the view's JSON, or null when it did not (or no longer does) exist,
   so undoing a view's first mark removes the view it made. */
function record(h, id, before, after) {
  h.undo.push({ id, before, after });
  if (h.undo.length > HISTORY_MAX) h.undo.shift();
  h.redo = [];
}
function applySnapshot(views, id, snap) {
  const i = views.findIndex((v) => v.id === id), out = views.slice();
  if (snap == null) { if (i >= 0) out.splice(i, 1); return out; }
  if (i >= 0) out[i] = JSON.parse(snap); else out.push(JSON.parse(snap));
  return out;
}
function undoStep(views, h) {
  const step = h.undo.pop();
  if (!step) return views;
  h.redo.push(step);
  return applySnapshot(views, step.id, step.before);
}
function redoStep(views, h) {
  const step = h.redo.pop();
  if (!step) return views;
  h.undo.push(step);
  return applySnapshot(views, step.id, step.after);
}

/* ---------- drawing ---------- */
function markColours() { return MARK_TOKENS.map((t) => css(t)); }
function drawArrowHead(g, a, b, size) {
  const ang = Math.atan2(b[1] - a[1], b[0] - a[0]);
  g.beginPath(); g.moveTo(b[0], b[1]);
  g.lineTo(b[0] - size * Math.cos(ang - 0.45), b[1] - size * Math.sin(ang - 0.45));
  g.lineTo(b[0] - size * Math.cos(ang + 0.45), b[1] - size * Math.sin(ang + 0.45));
  g.closePath(); g.fill();
}
/* VIEW's marks on the canvas; the selected one gets a dashed box and a resize handle. */
function drawMarks(g, view, geo, colours, selectedId, halo) {
  const S2 = (p) => fromUnits(p[0], p[1], geo);
  g.save(); g.lineCap = "round"; g.lineJoin = "round"; g.setLineDash([]);
  for (const m of view.marks) {
    const colour = colours[m.colour] || colours[0], pts = m.pts.map(S2);
    g.strokeStyle = colour; g.fillStyle = colour; g.lineWidth = PEN_WIDTHS[m.width] || PEN_WIDTHS[1];
    if (m.kind === "pen" || m.kind === "arrow") {
      g.beginPath(); pts.forEach((p, i) => (i ? g.lineTo(p[0], p[1]) : g.moveTo(p[0], p[1]))); g.stroke();
      if (m.kind === "arrow") drawArrowHead(g, pts[0], pts[1], 8 + 2 * g.lineWidth);
    } else if (m.kind === "rect") {
      g.strokeRect(Math.min(pts[0][0], pts[1][0]), Math.min(pts[0][1], pts[1][1]), Math.abs(pts[1][0] - pts[0][0]), Math.abs(pts[1][1] - pts[0][1]));
    } else if (m.kind === "ellipse") {
      g.beginPath();
      g.ellipse((pts[0][0] + pts[1][0]) / 2, (pts[0][1] + pts[1][1]) / 2, Math.abs(pts[1][0] - pts[0][0]) / 2, Math.abs(pts[1][1] - pts[0][1]) / 2, 0, 0, 2 * Math.PI);
      g.stroke();
    } else if (m.kind === "text") {
      g.font = "600 " + LABEL_PX + "px system-ui"; g.textAlign = "left"; g.textBaseline = "middle";
      if (halo) { g.lineWidth = 3; g.strokeStyle = halo; g.strokeText(m.text, pts[0][0], pts[0][1]); }
      g.fillText(m.text, pts[0][0], pts[0][1]);
    }
    if (m.id === selectedId) {
      const b = markBox(m, geo.R), [x0, y0] = fromUnits(b.x0, b.y0, geo), [x1, y1] = fromUnits(b.x1, b.y1, geo);
      g.lineWidth = 1; g.strokeStyle = css("--focus"); g.setLineDash([4, 3]);
      g.strokeRect(x0 - 4, y0 - 4, x1 - x0 + 8, y1 - y0 + 8); g.setLineDash([]);
      if (m.kind !== "text") { g.fillStyle = css("--focus"); g.fillRect(x1, y1, 8, 8); }
    }
  }
  g.restore();
}
GL.overlays.push({
  draw: (g, P, R, cx, cy) => {
    const v = activeView(), was = AN.active;
    AN.active = v ? v.id : null;
    if (v) { AN.last = v.id; drawMarks(g, v, { cx, cy, R }, markColours(), AN.selected, css("--surface")); }
    if (was !== AN.active) marksNotify();
  },
  hit: () => null,
});

/* ---------- loading and saving ---------- */
function marksNotify() { for (const fn of AN.onChange) fn(); }
function marksLoad(st) {
  AN.views = (st && st.annotations && Array.isArray(st.annotations.views)) ? st.annotations.views : [];
  AN.version = (st && st.annotationsVersion) || null;
  AN.error = (st && st.annotationsError) || null;
  AN.history = newHistory(); AN.selected = null; AN.conflict = null;
  const marked = AN.views.filter((v) => v.marks.length).sort((a, b) => String(b.updated).localeCompare(String(a.updated)));
  AN.last = marked.length ? marked[0].id : null;
  AN.save = NT.serving ? "saved" : "off";
  marksNotify();
  globeRequestDraw();
}
/* After any change to a view: undo can take it back, and it saves a moment later. */
function marksChanged(viewId, before) {
  const view = AN.views.find((v) => v.id === viewId);
  if (view) { view.updated = new Date().toISOString().replace(/\.\d+Z$/, "Z"); AN.last = viewId; }
  record(AN.history || (AN.history = newHistory()), viewId, before, view ? JSON.stringify(view) : null);
  AN.save = NT.serving ? "unsaved" : "off";
  clearTimeout(AN.timer);
  if (NT.serving) AN.timer = setTimeout(saveMarks, 800);
  marksNotify();
  globeRequestDraw();
}
/* Save every view, one save at a time; a failure keeps the marks on the page and says why. */
async function saveMarks() {
  if (!NT.serving) { AN.save = "off"; marksNotify(); return; }
  if (AN.error) { marksNotify(); return; }   /* a file that cannot be read is never overwritten */
  if (AN.inFlight) { AN.pending = true; return; }
  const sent = JSON.stringify(AN.views);
  AN.inFlight = true; AN.save = "saving"; marksNotify();
  const r = await noteApi("/api/annotations", { annotations: { views: AN.views }, version: AN.version });
  AN.inFlight = false;
  if (r.status === 200) {
    AN.version = r.data.version;
    AN.save = JSON.stringify(AN.views) === sent ? "saved" : "unsaved";
    if (AN.pending || AN.save === "unsaved") { AN.pending = false; return saveMarks(); }
  } else if (r.status === 409 && r.data.deleted) {
    AN.save = "deleted";
  } else if (r.status === 409 && r.data.conflict) {
    AN.save = "conflict"; AN.conflict = { disk: r.data.disk, diskVersion: r.data.diskVersion };
  } else {
    AN.save = "failed"; AN.msg = (r.data && r.data.error) || "the helper is not answering.";
  }
  AN.pending = false;
  marksNotify();
}
function keepMine() {
  AN.version = AN.conflict.diskVersion; AN.conflict = null;
  return saveMarks();
}
function useFilesMarks() {
  AN.views = AN.conflict.disk.views; AN.version = AN.conflict.diskVersion; AN.conflict = null;
  AN.selected = null; AN.save = "saved";
  marksNotify(); globeRequestDraw();
}
/* After the file was deleted elsewhere (/reset notes): only on the researcher's word. */
function saveAgain() {
  AN.version = null;
  return saveMarks();
}
