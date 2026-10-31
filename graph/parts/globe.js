/* The research globe: its maths (pure functions) and its canvas renderer.

   Positions carry meaning. Longitude is the research interest: each interest owns a
   band sized by its item count, never narrower than MIN_BAND_DEG, and inside the band
   each sub-area owns an equal slot. Latitude is publication year, newest at the top,
   undated items at the south pole. Spread inside a slot comes from a stable hash of
   the item's id, so the same library always draws the same picture. */

const MIN_BAND_DEG = 8;   /* the narrowest band, so a small interest stays readable */
const DOT_CAP = 2500;     /* most dots drawn at once; the rest are counted, not drawn */
const ARC_CAP = 300;      /* faint citation lines drawn with nothing selected */
const ZOOM_MIN = 1, ZOOM_MAX = 14;

function hash01(s) {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
  /* FNV alone barely moves when only the last characters differ; mix the bits. */
  h ^= h >>> 16; h = Math.imul(h, 0x85ebca6b); h ^= h >>> 13; h = Math.imul(h, 0xc2b2ae35); h ^= h >>> 16;
  return (h >>> 0) / 4294967296;
}

/* Degrees of latitude for a year. A library with a long tail of old papers would
   squash recent work into a sliver, so above ten years the newest ten years take the
   top 60% of the height and every earlier year shares the rest. */
function yearLat(year, lo, hi) {
  if (year == null) return -80;
  if (lo == null || hi == null || hi <= lo) return 0;
  const span = hi - lo;
  if (span <= 10) return -62 + (year - lo) / span * 124;
  const recent = hi - 9;
  if (year >= recent) return -62 + 124 * 0.4 + (year - recent) / 9 * 124 * 0.6;
  return -62 + (year - lo) / (recent - lo) * 124 * 0.4;
}

/* ENTRIES is [[name, count], ...] in display order; widths fill 360 degrees. */
function bands(entries) {
  const k = entries.length;
  if (!k) return [];
  const min = MIN_BAND_DEG * k > 360 ? 360 / k : MIN_BAND_DEG;
  const total = entries.reduce((a, [, c]) => a + c, 0), free = 360 - min * k;
  let start = 0;
  return entries.map(([name, count]) => {
    const width = min + (total ? count / total : 1 / k) * free;
    const b = { name, start, width };
    start += width;
    return b;
  });
}

/* An item's cluster: its first label the profile still lists, or one of the two
   "no sub-area" clusters (never labelled; labelled but nothing listed fits). */
function clusterKey(item, subareasOfInterest) {
  const interest = item.interest || "Uncategorized";
  if (item.subareas == null) return interest + "::__unlabelled";
  const hit = item.subareas.find((s) => (subareasOfInterest || []).includes(s));
  return interest + "::" + (hit == null ? "__none" : hit);
}
function clusterName(key) {
  const sub = key.slice(key.indexOf("::") + 2);
  return sub === "__unlabelled" ? "Not yet labelled" : sub === "__none" ? "Fits no listed sub-area" : sub;
}

function buildGlobe(items, interestOrder, subareasByInterest) {
  const n = items.length;
  const interestOf = (it) => it.interest || "Uncategorized";
  const counts = new Map();
  for (const it of items) counts.set(interestOf(it), (counts.get(interestOf(it)) || 0) + 1);
  const names = interestOrder.filter((x) => counts.has(x))
    .concat([...counts.keys()].filter((x) => !interestOrder.includes(x)).sort());
  const bandList = bands(names.map((x) => [x, counts.get(x)]));
  /* Clusters per interest, in the profile's sub-area order, then the two "none" ones. */
  const keys = items.map((it) => clusterKey(it, subareasByInterest[interestOf(it)]));
  const present = new Set(keys);
  const clusters = [], clusterIndex = new Map(), slots = new Map();
  names.forEach((name, ii) => {
    const order = (subareasByInterest[name] || []).map((s) => name + "::" + s)
      .concat([name + "::__none", name + "::__unlabelled"]).filter((k) => present.has(k));
    order.forEach((k, slot) => {
      clusterIndex.set(k, clusters.length);
      slots.set(k, [slot, order.length]);
      clusters.push({ key: k, name: clusterName(k), interest: ii, members: [] });
    });
  });
  const years = items.map((it) => it.year).filter((y) => y != null);
  const lo = years.length ? Math.min(...years) : null, hi = years.length ? Math.max(...years) : null;
  const vx = new Float32Array(n), vy = new Float32Array(n), vz = new Float32Array(n);
  const interest = new Uint16Array(n), cluster = new Uint16Array(n), ids = new Array(n);
  const R = Math.PI / 180;
  for (let i = 0; i < n; i++) {
    const it = items[i], ii = names.indexOf(interestOf(it)), b = bandList[ii], ci = clusterIndex.get(keys[i]);
    const [slot, of] = slots.get(keys[i]), sw = b.width / of;
    const lon = (b.start + (slot + 0.5) * sw + (hash01(String(it.id)) - 0.5) * 0.8 * sw) * R;
    const h = hash01(it.id + "y");
    const lat = (it.year != null ? yearLat(it.year, lo, hi) + (h - 0.5) * 4 : -80 + h * 6) * R;
    vx[i] = Math.cos(lat) * Math.cos(lon); vy[i] = Math.sin(lat); vz[i] = Math.cos(lat) * Math.sin(lon);
    interest[i] = ii; cluster[i] = ci; ids[i] = it.id;
    clusters[ci].members.push(i);
  }
  const score = (i) => (items[i].score == null ? 50 : items[i].score);
  const order = Uint32Array.from(Array.from({ length: n }, (_, i) => i)
    .sort((a, b) => score(b) - score(a) || (ids[a] < ids[b] ? -1 : ids[a] > ids[b] ? 1 : 0)));
  return { n, ids, items, vx, vy, vz, interest, cluster, interests: names, clusters, bands: bandList, lo, hi, order };
}

function rotation(yaw, pitch) {
  return { cy: Math.cos(yaw), sy: Math.sin(yaw), cp: Math.cos(pitch), sp: Math.sin(pitch) };
}
/* A unit-sphere point, turned to the view: [right, up, towards the viewer]. */
function project(rot, x, y, z) {
  const x1 = x * rot.cy + z * rot.sy, z1 = -x * rot.sy + z * rot.cy;
  return [x1, y * rot.cp - z1 * rot.sp, y * rot.sp + z1 * rot.cp];
}

/* The dots to draw: every unmasked item facing the viewer and on screen is counted,
   the first CAP of them by score are drawn. INVIEW(x, y) takes view coordinates. */
function pickDots(model, mask, rot, inView, cap) {
  const drawn = [];
  let count = 0;
  const { cy, sy, cp, sp } = rot, { vx, vy, vz, order } = model;
  for (let q = 0; q < model.n; q++) {
    const i = order[q];
    if (!mask[i]) continue;
    const x1 = vx[i] * cy + vz[i] * sy, z1 = -vx[i] * sy + vz[i] * cy;
    if (vy[i] * sp + z1 * cp <= 0.02) continue;
    if (!inView(x1, vy[i] * cp - z1 * sp)) continue;
    count++;
    if (drawn.length < cap) drawn.push(i);
  }
  return { drawn, inView: count };
}

/* Per cluster: how many unmasked items, how many of those are new, and their centre. */
function clusterStats(model, mask, isNewFlags) {
  return model.clusters.map((c) => {
    let count = 0, fresh = 0, x = 0, y = 0, z = 0;
    for (const i of c.members) {
      if (!mask[i]) continue;
      count++; if (isNewFlags[i]) fresh++;
      x += model.vx[i]; y += model.vy[i]; z += model.vz[i];
    }
    const m = Math.hypot(x, y, z);
    return m ? { count, fresh, x: x / m, y: y / m, z: z / m } : { count, fresh, x: 0, y: 0, z: 0 };
  });
}

/* How much of each layer shows: regions when zoomed out, dots when zoomed in. */
function zoomBlend(zoom) {
  const c = (v) => Math.max(0, Math.min(1, v));
  return { regions: c((2.4 - zoom) / 1.0), dots: c((zoom - 1.3) / 0.9) };
}

/* An angle kept within one turn, -pi to pi. */
function wrapAngle(a) {
  return a - 2 * Math.PI * Math.floor((a + Math.PI) / (2 * Math.PI));
}
/* A drag of (DX, DY) pixels turns the globe freely, over the poles and all the way
   round. Once it is upside down, left and right are swapped so the surface still
   follows the hand. Slower when zoomed in, so a drag never jumps across the globe. */
function dragRotate(yaw, pitch, dx, dy, zoom) {
  const k = 0.0055 / Math.pow(zoom, 0.75), upright = Math.cos(pitch) >= 0 ? 1 : -1;
  return { yaw: wrapAngle(yaw - dx * k * upright), pitch: wrapAngle(pitch + dy * k) };
}
/* The yaw and pitch that turn the point (x, y, z) to face the viewer. */
function flyTarget(x, y, z) {
  return { yaw: Math.atan2(z, x) - Math.PI / 2, pitch: Math.atan2(y, Math.hypot(x, z)) };
}

/* Year rings to label: both ends and every fifth year at least 3 years from either. */
function yearMarks(lo, hi) {
  if (lo == null || hi == null) return [];
  if (lo === hi) return [lo];
  const out = [lo];
  for (let y = Math.ceil((lo + 1) / 5) * 5; y < hi; y += 5) if (y - lo >= 3 && hi - y >= 3) out.push(y);
  out.push(hi);
  return out;
}

/* A citation line: the great circle from A to B, lifted off the surface in the
   middle so it never hides the dots it passes over. */
function arcPath(a, b, steps) {
  const d = Math.acos(Math.max(-1, Math.min(1, a[0] * b[0] + a[1] * b[1] + a[2] * b[2])));
  if (d < 1e-6) return Array.from({ length: steps + 1 }, () => a.slice());
  const s = Math.sin(d), out = [];
  for (let k = 0; k <= steps; k++) {
    const t = k / steps, wa = Math.sin((1 - t) * d) / s, wb = Math.sin(t * d) / s;
    const lift = 1 + 0.16 * Math.sin(Math.PI * t) * d;
    out.push([(a[0] * wa + b[0] * wb) * lift, (a[1] * wa + b[1] * wb) * lift, (a[2] * wa + b[2] * wb) * lift]);
  }
  return out;
}

/* Labels that fit without overlapping, highest priority first. Each candidate's x and
   y are its centre; big labels (interest names) do not count toward MAXSMALL. */
function placeLabels(cands, maxSmall) {
  const kept = [], boxes = [];
  let small = 0;
  for (const c of cands.slice().sort((a, b) => b.priority - a.priority)) {
    if (!c.big && small >= maxSmall) continue;
    const box = [c.x - c.w / 2, c.y - c.h / 2, c.x + c.w / 2, c.y + c.h / 2];
    if (boxes.some((o) => box[0] < o[2] && box[2] > o[0] && box[1] < o[3] && box[3] > o[1])) continue;
    boxes.push(box); kept.push(c);
    if (!c.big) small++;
  }
  return kept;
}

/* ---------- the renderer ---------- */
/* One object holds the globe's state. The selection itself is S.current, shared with
   Explore, and the highlight is S.highlight, so every tab agrees on both. */
const GL = {
  model: null, index: null, mask: null, fresh: null, stats: [], out: null, inn: null, strong: [],
  yaw: -0.6, pitch: 0.2, zoom: 1, panX: 0, panY: 0, mode: "rotate", back: null,
  hits: [], clusterHits: [], arcHits: [], counts: { inView: 0, drawn: 0 }, lastDraw: 0, firstDraw: null,
  insets: () => ({ left: 0, right: 0 }),   /* room the Overview's cards take; overview.js sets it */
  onSelect: (id) => select(id),
  onHover: () => {}, afterDraw: () => {},
};
function globeEnsure() {
  if (GL.model) return;
  const subs = Object.fromEntries(D.interests.map((i) => [i.name, i.subareas]));
  GL.model = buildGlobe(ITEMS.map((n) => ({ id: n.id, type: n.type, interest: interestOf(n), year: n.year,
    subareas: n.subareas, score: n.score })), INTERESTS, subs);
  const m = GL.model;
  GL.index = new Map(m.ids.map((id, i) => [id, i]));
  GL.out = Array.from({ length: m.n }, () => []);
  GL.inn = Array.from({ length: m.n }, () => []);
  for (const e of D.edges) {
    if (e.type !== "cites") continue;
    const a = GL.index.get(e.source), b = GL.index.get(e.target);
    if (a != null && b != null) { GL.out[a].push(b); GL.inn[b].push(a); }
  }
  GL.mask = new Uint8Array(m.n); GL.fresh = new Uint8Array(m.n);
  globeInput();
  globeRefresh();
}
/* After any filter change: what is shown, what is new, the cluster totals, and the
   strongest citation lines among what is shown. */
function globeRefresh() {
  if (!GL.model) return;
  const m = GL.model;
  for (let i = 0; i < m.n; i++) {
    const n = byId.get(m.ids[i]);
    GL.mask[i] = VISIBLE.has(m.ids[i]) ? 1 : 0;
    GL.fresh[i] = isNew(n) ? 1 : 0;
  }
  GL.stats = clusterStats(m, GL.mask, GL.fresh);
  const indeg = new Map(), pairs = [];
  for (let b = 0; b < m.n; b++) {
    if (!GL.mask[b]) continue;
    for (const a of GL.inn[b]) if (GL.mask[a]) { pairs.push([a, b]); indeg.set(b, (indeg.get(b) || 0) + 1); }
  }
  pairs.sort((p, q) => indeg.get(q[1]) - indeg.get(p[1]) || p[0] - q[0] || p[1] - q[1]);
  GL.strong = pairs.slice(0, ARC_CAP);
  globeRequestDraw();
}
/* Whether item I is drawn at full strength: the highlight decides when there is one,
   else a selection lights itself and the papers its lines join, and dims the rest. */
function globeLit(i, sel, hlHas, out, inn) {
  if (hlHas) return hlHas(i);
  if (sel == null) return true;
  return i === sel || out[sel].includes(i) || inn[sel].includes(i);
}
function globeSelectedIndex() {
  return S.current != null && GL.index ? GL.index.get(S.current) : undefined;
}
let GL_PENDING = false;
function globeRequestDraw() {
  if (S.tab !== "overview") return;
  if (document.hidden) { globeDraw(); return; }   /* a hidden page gets no animation frames */
  if (GL_PENDING) return;
  GL_PENDING = true;
  requestAnimationFrame(() => { GL_PENDING = false; globeDraw(); });
}
function globeGeometry() {
  const cv = $("#globe"), W = cv.clientWidth, H = cv.clientHeight, ins = GL.insets();
  const free = Math.max(160, W - ins.left - ins.right);
  return { W, H, cx: ins.left + free / 2 + GL.panX, cy: H / 2 + GL.panY, R: 0.36 * Math.min(free, 0.95 * H) * GL.zoom };
}
function globeDraw() {
  const cv = $("#globe");
  if (!GL.model || !cv.clientWidth) return;
  const t0 = performance.now(), dpr = window.devicePixelRatio || 1;
  const { W, H, cx, cy, R } = globeGeometry();
  if (cv.width !== Math.round(W * dpr) || cv.height !== Math.round(H * dpr)) { cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr); }
  const g = cv.getContext("2d");
  g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, W, H);
  const m = GL.model, rot = rotation(GL.yaw, GL.pitch), blend = zoomBlend(GL.zoom), dark = isDark();
  const P = (x, y, z) => { const p = project(rot, x, y, z); return [cx + p[0] * R, cy - p[1] * R, p[2]]; };
  const colour = m.interests.map((name) => interestColor(name));
  const tok = { ink: css("--ink"), muted: css("--muted"), surface: css("--surface"), line: css("--globe-line"),
    cites: css("--cites"), citedby: css("--citedby"), fresh: css("--new"), inkLine: css("--ink-2") };
  const DEG = Math.PI / 180;
  /* the sphere */
  const body = g.createRadialGradient(cx - R * 0.3, cy - R * 0.3, R * 0.1, cx, cy, R);
  body.addColorStop(0, css("--globe-hi")); body.addColorStop(1, css("--globe-lo"));
  g.fillStyle = body; g.beginPath(); g.arc(cx, cy, R, 0, 2 * Math.PI); g.fill();
  g.strokeStyle = css("--globe-edge"); g.lineWidth = 1; g.stroke();
  const polyline = (pts, cut) => {
    g.beginPath(); let first = true;
    for (const p of pts) { if (p[2] < cut) { first = true; continue; } if (first) g.moveTo(p[0], p[1]); else g.lineTo(p[0], p[1]); first = false; }
    g.stroke();
  };
  /* region boundaries and year rings */
  g.strokeStyle = tok.line;
  for (const b of m.bands) {
    const lo = b.start * DEG, pts = [];
    for (let l = -88; l <= 88; l += 4) pts.push(P(Math.cos(l * DEG) * Math.cos(lo), Math.sin(l * DEG), Math.cos(l * DEG) * Math.sin(lo)));
    polyline(pts, 0);
  }
  g.font = "10.5px system-ui"; g.textAlign = "right"; g.fillStyle = tok.muted;
  for (const y of yearMarks(m.lo, m.hi)) {
    const la = yearLat(y, m.lo, m.hi) * DEG, pts = [];
    let left = null;
    for (let d = 0; d <= 360; d += 6) {
      const p = P(Math.cos(la) * Math.cos(d * DEG), Math.sin(la), Math.cos(la) * Math.sin(d * DEG));
      pts.push(p);
      if (p[2] > 0.05 && (!left || p[0] < left[0])) left = p;
    }
    polyline(pts, 0);
    if (left) g.fillText(String(y), left[0] - 4, left[1] + 3);
  }
  /* sub-area regions, when zoomed out */
  GL.clusterHits = [];
  const labels = [];
  g.globalCompositeOperation = dark ? "lighter" : "source-over";
  /* A glow's area follows its count relative to the largest, so it reads at any size. */
  const biggest = Math.max(1, ...GL.stats.map((st) => st.count));
  GL.stats.forEach((st, k) => {
    if (!st.count) return;
    const p = P(st.x, st.y, st.z);
    if (p[2] < -0.05) return;
    const rad = R * (0.03 + 0.11 * Math.sqrt(st.count / biggest)) * (0.6 + 0.4 * Math.max(0.2, p[2]));
    if (blend.regions > 0.01) {
      const c = colour[m.clusters[k].interest], gr = g.createRadialGradient(p[0], p[1], 0, p[0], p[1], rad);
      gr.addColorStop(0, hexA(c, dark ? 0.88 : 0.55)); gr.addColorStop(0.45, hexA(c, dark ? 0.44 : 0.28)); gr.addColorStop(1, hexA(c, 0));
      g.globalAlpha = blend.regions * (S.highlight ? 0.35 : 1) * Math.max(0, Math.min(1, 0.3 + p[2]));
      g.fillStyle = gr; g.beginPath(); g.arc(p[0], p[1], rad, 0, 2 * Math.PI); g.fill();
    }
    if (p[2] > 0.1) {
      GL.clusterHits.push([p[0], p[1], Math.max(rad * 0.7, 10), k]);
      labels.push({ text: m.clusters[k].name + " · " + st.count.toLocaleString() + (st.fresh ? " · " + st.fresh.toLocaleString() + " new" : ""),
        x: p[0], y: p[1], priority: st.count, big: false });
    }
  });
  g.globalCompositeOperation = "source-over"; g.globalAlpha = 1;
  /* citation lines: the selection's own, or the strongest few when nothing is selected */
  GL.arcHits = [];
  const sel = globeSelectedIndex();
  const arc = (a, b, colourText, width, arrow) => {
    const pts = arcPath([m.vx[a], m.vy[a], m.vz[a]], [m.vx[b], m.vy[b], m.vz[b]], 20).map((v) => P(v[0], v[1], v[2]));
    g.strokeStyle = colourText; g.lineWidth = width; polyline(pts, -0.05);
    GL.arcHits.push({ from: a, to: b, pts: pts.filter((p) => p[2] >= -0.05) });
    const end = pts[20], prev = pts[19];
    if (arrow && end[2] > 0) {
      const an = Math.atan2(end[1] - prev[1], end[0] - prev[0]);
      g.fillStyle = colourText; g.beginPath(); g.moveTo(end[0], end[1]);
      g.lineTo(end[0] - 9 * Math.cos(an - 0.4), end[1] - 9 * Math.sin(an - 0.4));
      g.lineTo(end[0] - 9 * Math.cos(an + 0.4), end[1] - 9 * Math.sin(an + 0.4)); g.closePath(); g.fill();
    }
  };
  if (sel != null && m.items[sel].type === "paper") {
    for (const b of GL.out[sel]) if (GL.mask[b]) arc(sel, b, tok.cites, 1.6, true);
    for (const a of GL.inn[sel]) if (GL.mask[a]) arc(a, sel, tok.citedby, 1.6, true);
  } else if (sel == null && GL.zoom > 1.15 && GL.zoom < 4) {
    g.globalAlpha = dark ? 0.18 : 0.1;
    for (const [a, b] of GL.strong) arc(a, b, tok.inkLine, 1, false);
    g.globalAlpha = 1;
  }
  /* items, highest score first, capped */
  GL.hits = [];
  GL.counts = { inView: 0, drawn: 0 };
  let selPt = null;
  if (blend.dots > 0.02) {
    const inView = (x, y) => { const sx = cx + x * R, sy = cy - y * R; return sx > -8 && sx < W + 8 && sy > -8 && sy < H + 8; };
    const pick = pickDots(m, GL.mask, rot, inView, DOT_CAP);
    GL.counts = { inView: pick.inView, drawn: pick.drawn.length };
    const rr = 2.3 * Math.pow(GL.zoom, 0.3);
    const hlHas = S.highlight ? (j) => S.highlight.has(m.ids[j]) : null;
    for (const i of pick.drawn) {
      const p = P(m.vx[i], m.vy[i], m.vz[i]), r = rr * (0.7 + 0.3 * p[2]);
      const lit = globeLit(i, sel, hlHas, GL.out, GL.inn);
      g.globalAlpha = blend.dots * (lit ? 1 : 0.1);
      g.fillStyle = colour[m.interest[i]]; g.beginPath();
      if (m.items[i].type === "web") g.rect(p[0] - r, p[1] - r, 2 * r, 2 * r); else g.arc(p[0], p[1], r, 0, 2 * Math.PI);
      g.fill();
      if (GL.fresh[i] && lit && i !== sel) { g.strokeStyle = tok.fresh; g.lineWidth = 1.2; g.beginPath(); g.arc(p[0], p[1], r + 2.5, 0, 2 * Math.PI); g.stroke(); }
      if (i === sel) selPt = r;
      GL.hits.push([p[0], p[1], i]);
    }
    g.globalAlpha = 1;
  }
  /* the selected item: a filled dot with a soft glow, never a ring (a ring means new) */
  if (sel != null) {
    const p = P(m.vx[sel], m.vy[sel], m.vz[sel]);
    if (p[2] > 0) {
      const r = Math.max(selPt || 3, 3) * 1.7, glow = g.createRadialGradient(p[0], p[1], 0, p[0], p[1], r * 4.5);
      glow.addColorStop(0, hexA(tok.fresh, 0.7)); glow.addColorStop(0.35, hexA(tok.fresh, 0.2)); glow.addColorStop(1, hexA(tok.fresh, 0));
      g.fillStyle = glow; g.beginPath(); g.arc(p[0], p[1], r * 4.5, 0, 2 * Math.PI); g.fill();
      g.fillStyle = tok.fresh; g.beginPath();
      if (m.items[sel].type === "web") g.rect(p[0] - r, p[1] - r, 2 * r, 2 * r); else g.arc(p[0], p[1], r, 0, 2 * Math.PI);
      g.fill();
    }
  }
  /* names: interests while zoomed out, then sub-areas, never overlapping */
  if (GL.zoom < 3.2) {
    m.bands.forEach((b, k) => {
      if (!GL.stats.some((st, c) => st.count && m.clusters[c].interest === k)) return;
      const lo = (b.start + b.width / 2) * DEG, p = P(Math.cos(lo), 0, Math.sin(lo));
      if (p[2] > 0.25) labels.push({ text: b.name, x: p[0], y: p[1] - 16, priority: 1e9 - k, big: true });
    });
  }
  for (const lb of labels) {
    g.font = (lb.big ? "600 14px" : "500 11.5px") + " system-ui";
    lb.w = g.measureText(lb.text).width + 8; lb.h = lb.big ? 18 : 14;
  }
  g.textAlign = "center";
  for (const lb of placeLabels(labels.filter((l) => l.x > -l.w && l.x < W + l.w && l.y > 0 && l.y < H), GL.zoom < 1.5 ? 16 : 60)) {
    g.font = (lb.big ? "600 14px" : "500 11.5px") + " system-ui";
    g.lineWidth = 3; g.strokeStyle = hexA(tok.surface, 0.85); g.strokeText(lb.text, lb.x, lb.y + 4);
    g.fillStyle = tok.ink; g.fillText(lb.text, lb.x, lb.y + 4);
  }
  GL.lastDraw = performance.now() - t0;
  if (GL.firstDraw == null) { GL.firstDraw = performance.now(); globePerfRun(); }
  GL.afterDraw();
}

/* ---------- moving around ---------- */
function globeClamp(z) { return Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, z)); }
function globeFly(x, y, z, zoom) {
  const t = flyTarget(x, y, z);
  /* The short way round for both angles, wherever a free drag has left them. */
  const from = { yaw: GL.yaw, pitch: GL.pitch, zoom: GL.zoom, panX: GL.panX, panY: GL.panY };
  const to = { yaw: GL.yaw + wrapAngle(t.yaw - GL.yaw), pitch: GL.pitch + wrapAngle(t.pitch - GL.pitch), zoom: globeClamp(zoom), panX: 0, panY: 0 };
  globeTween(from, to);
}
function globeTween(from, to) {
  const set = (e) => { for (const k of Object.keys(to)) GL[k] = from[k] + (to[k] - from[k]) * e; };
  if (document.hidden) { set(1); globeDraw(); return; }
  const t0 = performance.now();
  const step = (now) => {
    const t = Math.min(1, (now - t0) / 650), e = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
    set(e); globeDraw();
    if (t < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}
function globeFit() { globeTween({ yaw: GL.yaw, pitch: GL.pitch, zoom: GL.zoom, panX: GL.panX, panY: GL.panY },
  { yaw: -0.6, pitch: 0.2, zoom: 1, panX: 0, panY: 0 }); GL.back = null; }
function globeZoomBy(f) { GL.zoom = globeClamp(GL.zoom * f); globeRequestDraw(); }
function globeSetMode(mode) {
  GL.mode = mode;
  $("#gnav-rotate").setAttribute("aria-pressed", String(mode === "rotate"));
  $("#gnav-pan").setAttribute("aria-pressed", String(mode === "pan"));
  $("#globe").classList.toggle("pan-mode", mode === "pan");
}
/* What is under the pointer: the nearest drawn item within 12px, else a region. */
function globeHitAt(x, y) {
  let best = null, bd = 12;
  for (const [hx, hy, i] of GL.hits) { const d = Math.hypot(hx - x, hy - y); if (d < bd) { bd = d; best = i; } }
  if (best != null) return { kind: "item", i: best };
  let cl = null, cd = Infinity;
  for (const [hx, hy, r, k] of GL.clusterHits) { const d = Math.hypot(hx - x, hy - y); if (d < r && d < cd) { cd = d; cl = k; } }
  return cl != null ? { kind: "cluster", k: cl } : null;
}
function segDist(px, py, a, b) {
  const dx = b[0] - a[0], dy = b[1] - a[1], l = dx * dx + dy * dy;
  const t = l ? Math.max(0, Math.min(1, ((px - a[0]) * dx + (py - a[1]) * dy) / l)) : 0;
  return Math.hypot(px - a[0] - t * dx, py - a[1] - t * dy);
}
function globeHover(x, y) {
  let best = null, bd = 9;
  for (const [hx, hy, i] of GL.hits) { const d = Math.hypot(hx - x, hy - y); if (d < bd) { bd = d; best = i; } }
  if (best != null) return { kind: "item", id: GL.model.ids[best] };
  for (const h of GL.arcHits) for (let k = 1; k < h.pts.length; k++) {
    if (segDist(x, y, h.pts[k - 1], h.pts[k]) < 6) return { kind: "line", from: GL.model.ids[h.from], to: GL.model.ids[h.to] };
  }
  return null;
}
function globeTarget(hit) {
  const m = GL.model;
  if (hit.kind === "item") return [m.vx[hit.i], m.vy[hit.i], m.vz[hit.i]];
  const st = GL.stats[hit.k];
  return [st.x, st.y, st.z];
}
function globeClear() {
  S.current = null; S.focus = null; S.highlight = null; S.highlightWhy = "";
  computeNeighbours(); refreshObjects(); renderDetail(null); writeHash(true);
  GL.onSelect(null);
  globeRequestDraw();
}
function globeInput() {
  const cv = $("#globe");
  let drag = null, last = null;
  const at = (e) => { const r = cv.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
  cv.addEventListener("pointerdown", (e) => { drag = { x: e.clientX, y: e.clientY, moved: 0 }; cv.setPointerCapture(e.pointerId); });
  cv.addEventListener("pointermove", (e) => {
    if (!drag) { const [x, y] = at(e); GL.onHover(globeHover(x, y), e.clientX, e.clientY); return; }
    const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    drag.x = e.clientX; drag.y = e.clientY; drag.moved += Math.abs(dx) + Math.abs(dy);
    if (GL.mode === "pan") { GL.panX += dx; GL.panY += dy; }
    else { const v = dragRotate(GL.yaw, GL.pitch, dx, dy, GL.zoom); GL.yaw = v.yaw; GL.pitch = v.pitch; }
    GL.onHover(null);
    globeRequestDraw();
  });
  cv.addEventListener("pointerup", (e) => {
    const d = drag; drag = null;
    if (!d || d.moved > 4) return;
    const [x, y] = at(e), now = performance.now(), hit = globeHitAt(x, y);
    const double = last && now - last.t < 350 && Math.hypot(x - last.x, y - last.y) < 10;
    last = double ? null : { t: now, x, y };
    if (double) {
      if (GL.back) { const b = GL.back; GL.back = null; globeTween({ yaw: GL.yaw, pitch: GL.pitch, zoom: GL.zoom, panX: GL.panX, panY: GL.panY }, b); }
      else if (hit) { GL.back = { yaw: GL.yaw, pitch: GL.pitch, zoom: GL.zoom, panX: GL.panX, panY: GL.panY }; globeFly(...globeTarget(hit), Math.max(GL.zoom * 2, 3.4)); }
      return;
    }
    if (hit && hit.kind === "item") { GL.onSelect(GL.model.ids[hit.i]); globeRequestDraw(); }
    else if (hit) globeFly(...globeTarget(hit), Math.max(GL.zoom, 3.4));
    else if (S.current != null || S.highlight) globeClear();
  });
  cv.addEventListener("pointerleave", () => GL.onHover(null));
  cv.addEventListener("wheel", (e) => { e.preventDefault(); GL.zoom = globeClamp(GL.zoom * Math.exp(-e.deltaY * 0.0016)); globeRequestDraw(); }, { passive: false });
  new ResizeObserver(globeRequestDraw).observe(cv);
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", globeRequestDraw);
  const tb = $("#globe-nav"), area = $("#tab-overview");
  makeToolbar(tb, area, $("#gnav-grip"), "kg-globenav",
    () => ({ x: (area.clientWidth - tb.offsetWidth) / 2, y: area.clientHeight - tb.offsetHeight - 14 }));
  $("#gnav-zoom-in").addEventListener("click", () => globeZoomBy(1.5));
  $("#gnav-zoom-out").addEventListener("click", () => globeZoomBy(1 / 1.5));
  $("#gnav-fit").addEventListener("click", globeFit);
  $("#gnav-rotate").addEventListener("click", () => globeSetMode("rotate"));
  $("#gnav-pan").addEventListener("click", () => globeSetMode("pan"));
  document.addEventListener("keydown", (e) => {
    if (S.tab !== "overview" || /INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName) || e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.key === "+" || e.key === "=") globeZoomBy(1.5);
    else if (e.key === "-" || e.key === "_") globeZoomBy(1 / 1.5);
    else if (e.key === "0") globeFit();
    else if (e.key.toLowerCase() === "h") globeSetMode(GL.mode === "pan" ? "rotate" : "pan");
    /* Esc is handled by the page's onKey, for every tab. */
  });
}
/* #perf=1: after the first draw, turn the globe for 120 frames and keep each frame's
   draw time in window.kgPerf, next to the time of the first draw since navigation. */
const GL_PERF = /(^|[#&])perf=1(&|$)/.test(location.hash); /* read before the start-up rewrites the address */
function globePerfRun() {
  if (!GL_PERF) return;
  const frames = [];
  let k = 0;
  const step = () => {
    GL.yaw += 0.02; globeDraw(); frames.push(GL.lastDraw);
    if (++k < 120) requestAnimationFrame(step);
    else window.kgPerf = { firstDraw: GL.firstDraw, frames };
  };
  requestAnimationFrame(step);
}
TAB_HOOKS.overview = () => { globeEnsure(); globeRefresh(); };
ON_FILTERS.push(globeRefresh);
