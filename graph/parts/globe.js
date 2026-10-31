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
