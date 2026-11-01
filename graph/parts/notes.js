/* Notes on the library map: the notes model, the helper client, satellites, the list.

   Notes are the researcher's own writing, saved as files in notes/ by the local helper
   (python3 tools/knowledge_graph.py --serve). The build embeds them, so a page opened
   from disk still shows them, read-only. A note's orbit is how close it is to evidence:
   outer, an idea with no papers; middle, backed by at least one paper in the library;
   inner, marked as written into a report. Only a linked paper counts: a web source,
   research group or sub-area draws a tether but never passes for peer-reviewed backing,
   and a link to something this build no longer has is kept, shown and not counted. */

const NT = {
  serving: false, token: null, notes: new Map(), unreadable: [], prompts: [], built: null,
  evidence: new Map(),   /* note id -> [{id, why}], filled by the editor's matcher */
  dirty: false,          /* the open draft has text not yet saved */
  leaving: false,        /* the page asked about unsaved text already and is reloading */
  onChange: [],          /* redraws to run when the notes change */
};
function parseLink(link) {
  const m = /^(paper|web|group|subarea):(.+)$/.exec(String(link || ""));
  return m ? { kind: m[1], key: m[2] } : null;
}
/* The page's id for a link: papers, web sources and sub-area hubs are nodes; groups are labs. */
function linkNodeId(link) {
  const p = parseLink(link);
  if (!p) return null;
  if (p.kind === "group") return "lab:" + p.key;
  if (p.kind === "subarea") {
    const i = p.key.indexOf("::");
    return i < 0 ? null : "subarea:" + p.key.slice(0, i) + ":" + p.key.slice(i + 2);
  }
  return p.kind + ":" + p.key;
}
function resolveLinks(note, has) {
  return (note.links || []).map((link) => {
    const p = parseLink(link), id = linkNodeId(link);
    return { link, kind: p ? p.kind : null, id, missing: !id || !has(id), label: link };
  });
}
function noteOrbit(note, has) {
  if (note.in_report) return "inner";
  return resolveLinks(note, has).some((l) => l.kind === "paper" && !l.missing) ? "middle" : "outer";
}
function orbitWords(note, has, reportTitle) {
  const count = (n, one, many) => n + " " + (n === 1 ? one : many);
  if (note.in_report) return "Inner orbit · in a report: " + (reportTitle ? reportTitle(note.in_report) : note.in_report);
  const links = resolveLinks(note, has).filter((l) => !l.missing);
  const papers = links.filter((l) => l.kind === "paper").length;
  if (papers) return "Middle orbit · backed by " + count(papers, "paper", "papers");
  const web = links.filter((l) => l.kind === "web").length;
  if (web && web === links.length) return "Outer orbit · linked to " + count(web, "web source", "web sources") + ", no papers yet";
  if (links.length) return "Outer orbit · linked to " + count(links.length, "other item", "other items") + ", no papers yet";
  return "Outer orbit · an idea, no papers yet";
}
/* What exists in this build: items and hubs are nodes; research groups are labs. */
function noteHas(id) { return byId.has(id) || !!labOf(id); }
function reportTitleOf(slug) { const r = byId.get("report:" + slug); return r ? r.title : slug; }
function notesChanged() { for (const fn of NT.onChange) fn(); }
/* A PDF link, opened through the helper: it needs the token like the page did. */
function pdfHref(url) {
  return url && NT.token ? url + "?t=" + encodeURIComponent(NT.token) : url;
}

/* ---------- the helper ---------- */
/* Never throws: a helper that has stopped answers {status: 0}. */
async function noteApi(path, body) {
  try {
    const r = await fetch(path, { method: body === undefined ? "GET" : "POST", credentials: "same-origin",
      headers: { "X-KG-Token": NT.token || "", "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body) });
    let data = {};
    try { data = await r.json(); } catch (e) { /* not JSON */ }
    return { status: r.status, data };
  } catch (e) {
    return { status: 0, data: { error: "the helper is not answering." } };
  }
}
function setNotes(list) {
  NT.notes = new Map(list.map((n) => [n.id, n]));
}
async function notesInit() {
  setNotes(D.notes || []); NT.unreadable = D.notesUnreadable || []; NT.prompts = D.prompts || [];
  if (typeof marksLoad === "function") marksLoad({ annotations: D.annotations, annotationsVersion: null, annotationsError: D.annotationsError });
  if (location.protocol === "http:" || location.protocol === "https:") {
    /* The token stays in this page's address, so a reload keeps saving on. It is never
       stored or sent anywhere but this helper; it changes every time the helper starts. */
    NT.token = new URL(location.href).searchParams.get("t");
  }
  if (NT.token) {
    const st = await noteApi("/api/state");
    if (st.status === 200) {
      NT.serving = true; NT.built = st.data.built;
      setNotes(st.data.notes); NT.unreadable = st.data.unreadable; NT.prompts = st.data.prompts;
      if (typeof marksLoad === "function") marksLoad(st.data);
      setInterval(beatAndCheck, 60000);
    }
  }
  notesChanged();
  if (typeof syncEditorToHash === "function") syncEditorToHash();   /* opened at #note=<id> */
}
/* Every minute: keep the helper awake, and notice a rebuild made by another command. */
async function beatAndCheck() {
  const r = await noteApi("/api/heartbeat", {});
  if (r.status !== 200) { if (NT.serving) { NT.serving = false; notesChanged(); } return; }
  /* back after a gap (a laptop waking from sleep): saving comes back on */
  if (!NT.serving) { NT.serving = true; notesChanged(); }
  if (NT.built != null && r.data.built != null && r.data.built !== NT.built) showRebuilt();
}
function showRebuilt() {
  const b = $("#rebuilt");
  b.hidden = false;
  b.replaceChildren("The library was rebuilt. ", NT.dirty ? "Save or export your note first. " : "",
    el("button", { on: { click: reloadAfterRebuild } }, "Reload"));
}
/* Asks about unsaved text once: having asked, the browser's own leave-page check stands down. */
function reloadAfterRebuild() {
  if (NT.dirty && !window.confirm("Your note has unsaved changes. Reload anyway?")) return;
  NT.leaving = true;
  location.reload();
}
function warnBeforeLeaving(e) {
  if (NT.dirty && !NT.leaving) { e.preventDefault(); e.returnValue = ""; }
}
window.addEventListener("beforeunload", warnBeforeLeaving);

/* ---------- satellites ---------- */
/* Three shells around the globe; distance from it is distance from evidence. */
const SAT_ALT = { inner: 1.17, middle: 1.38, outer: 1.62 };
const SAT_CAP = 30;
const SAT_WORDS = { inner: "in a report", middle: "backed by papers", outer: "an idea, no papers yet" };
/* Where a note sits: above the middle of what it links to, so its tethers stay short and it
   moves only when its links change. A note with nothing placeable gets a stable direction
   from its id. POSITIONS(link) gives a unit vector for a link, or null. */
function satDirection(note, positions) {
  let x = 0, y = 0, z = 0;
  for (const l of note.links || []) { const v = positions(l); if (v) { x += v[0]; y += v[1]; z += v[2]; } }
  const m = Math.hypot(x, y, z);
  if (m > 1e-6) return [x / m, y / m, z / m];
  const lon = hash01(note.id) * 2 * Math.PI, lat = Math.asin(hash01(note.id + "z") * 1.6 - 0.8);
  return [Math.cos(lat) * Math.cos(lon), Math.sin(lat), Math.cos(lat) * Math.sin(lon)];
}
/* Which notes orbit: at most SAT_CAP, the selected one first, then those with new evidence,
   then those linked to what the filters show, then the most recently updated. The rest are
   counted per orbit. Archived notes never orbit. */
function pickSatellites(notes, ctx) {
  const rank = (n) => (n.id === ctx.selected ? 0 : ctx.hasNewEvidence(n.id) ? 1 : ctx.linkedVisible(n.id) ? 2 : 3);
  const live = notes.filter((n) => !n.archived)
    .sort((a, b) => rank(a) - rank(b) || String(b.updated || "").localeCompare(String(a.updated || "")) || (a.id < b.id ? -1 : 1));
  const shown = live.slice(0, SAT_CAP).map((n) => n.id), more = { inner: 0, middle: 0, outer: 0 };
  for (const n of live.slice(SAT_CAP)) more[ctx.orbit(n.id)]++;
  return { shown, more };
}
/* Where a shell's label goes: the top of the circle if it is on screen, else its left or
   right edge, else its bottom; null if none of them is (a W x H canvas, a label W wide). */
function shellLabelPlace(cx, cy, r, W, H, w) {
  const m = 6;
  if (cy - r - 4 > 14) return { x: cx, y: cy - r - 4, align: "center" };
  if (cx - r + m >= m && cx - r + m + w <= W && cy > 14 && cy < H - 14) return { x: cx - r + m, y: cy, align: "left" };
  if (cx + r - m <= W - m && cx + r - m - w >= 0 && cy > 14 && cy < H - 14) return { x: cx + r - m, y: cy, align: "right" };
  if (cy + r + 14 < H - 60) return { x: cx, y: cy + r + 14, align: "center" };
  return null;
}
const SAT = { hits: [], shellHits: [], pulseStart: null, moving: new Map() };   /* moving: id -> {from, to, start} */
function satPosition(link) {
  const id = linkNodeId(link), i = GL.index ? GL.index.get(id) : undefined;
  return i == null ? null : [GL.model.vx[i], GL.model.vy[i], GL.model.vz[i]];
}
function satColour(note) {
  for (const l of note.links || []) {
    const i = GL.index ? GL.index.get(linkNodeId(l)) : undefined;
    if (i != null) return interestColor(GL.model.interests[GL.model.interest[i]]);
  }
  return css("--muted");
}
/* A note's icon, as in the prototype: a diamond body between two solar panels, S the
   size. An idea (outer orbit) has a hollow body, filled with the background BG. */
function drawSatIcon(g, x, y, s, colour, hollow, bg) {
  g.save(); g.translate(x, y);
  g.fillStyle = colour; g.strokeStyle = colour; g.lineWidth = 1.6;
  g.fillRect(-s * 2.3, -s * 0.28, s * 1.5, s * 0.56); g.fillRect(s * 0.8, -s * 0.28, s * 1.5, s * 0.56);   /* solar panels */
  g.rotate(Math.PI / 4);
  if (hollow) { g.fillStyle = bg; g.fillRect(-s * 0.6, -s * 0.6, s * 1.2, s * 1.2); g.strokeRect(-s * 0.6, -s * 0.6, s * 1.2, s * 1.2); }
  else g.fillRect(-s * 0.6, -s * 0.6, s * 1.2, s * 1.2);
  g.restore();
}
function drawSatellites(g, P, R, cx, cy) {
  SAT.hits = []; SAT.shellHits = [];
  if (!NT.notes.size || !GL.model) return;
  const notes = [...NT.notes.values()], orbitOf = new Map(notes.map((n) => [n.id, noteOrbit(n, noteHas)]));
  const pick = pickSatellites(notes, { selected: S.note, hasNewEvidence: (id) => (NT.evidence.get(id) || []).length > 0,
    linkedVisible: (id) => (NT.notes.get(id).links || []).some((l) => VISIBLE.has(linkNodeId(l))), orbit: (id) => orbitOf.get(id) });
  const now = performance.now(), muted = css("--muted"), ink = css("--ink"), cites = css("--cites"), bg = css("--plane");
  /* the shells, labelled, with how many more each holds */
  g.lineWidth = 1; g.font = "10.5px system-ui"; g.textAlign = "center";
  for (const orbit of ["inner", "middle", "outer"]) {
    const r = R * SAT_ALT[orbit];
    g.strokeStyle = hexA(muted, 0.18); g.setLineDash([2, 5]); g.beginPath(); g.arc(cx, cy, r, 0, 2 * Math.PI); g.stroke(); g.setLineDash([]);
    const text = SAT_WORDS[orbit] + (pick.more[orbit] ? " · +" + pick.more[orbit] + " more" : "");
    const w = g.measureText(text).width, at = shellLabelPlace(cx, cy, r, g.canvas.clientWidth, g.canvas.clientHeight, w);
    if (!at) continue;
    g.fillStyle = muted; g.textAlign = at.align; g.fillText(text, at.x, at.y);
    const x0 = at.align === "center" ? at.x - w / 2 : at.align === "left" ? at.x : at.x - w;
    if (pick.more[orbit]) SAT.shellHits.push([x0, at.y - 12, x0 + w, at.y + 2, orbit]);
  }
  let animating = false;
  for (const id of pick.shown) {
    const n = NT.notes.get(id), orbit = orbitOf.get(id), d = satDirection(n, satPosition);
    let alt = SAT_ALT[orbit];
    const mv = SAT.moving.get(id);
    if (mv) {
      const t = Math.min(1, (now - mv.start) / 800);
      alt = SAT_ALT[mv.from] + (SAT_ALT[mv.to] - SAT_ALT[mv.from]) * (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2);
      if (t < 1) animating = true; else SAT.moving.delete(id);
    }
    const p = P(d[0] * alt, d[1] * alt, d[2] * alt);
    /* hidden behind the globe, unless it is out beyond the globe's edge */
    if (p[2] < 0 && Math.hypot(p[0] - cx, p[1] - cy) < R) continue;
    const selected = id === S.note, colour = satColour(n);
    /* tethers to what it links */
    g.strokeStyle = hexA(colour, selected ? 0.9 : 0.25); g.lineWidth = selected ? 1.4 : 1;
    for (const l of n.links || []) {
      const i = GL.index ? GL.index.get(linkNodeId(l)) : undefined;
      if (i == null || !GL.mask[i]) continue;
      const q = P(GL.model.vx[i], GL.model.vy[i], GL.model.vz[i]);
      if (q[2] < 0) continue;
      g.beginPath(); g.moveTo(p[0], p[1]); g.lineTo(q[0], q[1]); g.stroke();
    }
    const size = selected ? 7.5 : 5.5, r = size * 2.3;   /* r: half the icon's width, for the rings and hit-testing */
    drawSatIcon(g, p[0], p[1], size, colour, orbit === "outer", bg);
    if (selected) {
      g.strokeStyle = ink; g.lineWidth = 1.4; g.beginPath(); g.arc(p[0], p[1], r + 3, 0, 2 * Math.PI); g.stroke();
      const label = n.title.length > 34 ? n.title.slice(0, 32) + "…" : n.title;
      g.fillStyle = ink; g.font = "600 12px system-ui"; g.textAlign = "left"; g.fillText(label, p[0] + r + 8, p[1] + 4);
    }
    /* new evidence: three pulses when the map opens, then a steady ring */
    if ((NT.evidence.get(id) || []).length) {
      if (SAT.pulseStart == null) SAT.pulseStart = now;
      const t = (now - SAT.pulseStart) / 1000;
      g.strokeStyle = cites; g.lineWidth = 1.5;
      if (t < 3) {
        const ph = t % 1;
        g.globalAlpha = 1 - ph; g.beginPath(); g.arc(p[0], p[1], r + 3 + ph * 10, 0, 2 * Math.PI); g.stroke(); g.globalAlpha = 1;
        animating = true;
      } else { g.beginPath(); g.arc(p[0], p[1], r + 3, 0, 2 * Math.PI); g.stroke(); }
    }
    SAT.hits.push([p[0], p[1], r, id]);
  }
  if (animating) requestAnimationFrame(() => globeDraw());
}
function satHit(x, y) {
  for (const [hx, hy, r, id] of SAT.hits) if (Math.hypot(hx - x, hy - y) <= r) return { kind: "note", id };
  for (const [x0, y0, x1, y1, orbit] of SAT.shellHits) if (x >= x0 && x <= x1 && y >= y0 && y <= y1) return { kind: "shell", orbit };
  return null;
}
/* A note whose orbit changed moves to its new shell once, so the researcher sees it happen. */
function satMove(id, from, to) {
  if (from && to && from !== to) { SAT.moving.set(id, { from, to, start: performance.now() }); globeRequestDraw(); }
}
GL.overlays.push({ draw: drawSatellites, hit: satHit });
NT.onChange.push(() => globeRequestDraw());

/* ---------- the notes list: the precise counterpart to the satellites ---------- */
function notesLine(total, withEvidence) {
  if (!total) return "No notes yet";
  return "✦ " + total + " " + (total === 1 ? "note" : "notes") + (withEvidence ? " · " + withEvidence + " with new evidence" : "");
}
/* Q matches the title and the text, ignoring case. FILTER: {orbit, interest, archived, ids}.
   Archived notes show only when asked for. */
function filterNotes(notes, q, filter) {
  const f = filter || {}, needle = String(q || "").toLowerCase();
  return notes.filter((n) => (f.archived ? !!n.archived : !n.archived)
    && (!f.orbit || n.orbit === f.orbit) && (!f.interest || n.interest === f.interest)
    && (!f.ids || f.ids.includes(n.id))
    && (!needle || (String(n.title || "") + "\n" + String(n.body || "")).toLowerCase().includes(needle)));
}
function noteInterest(note) {
  for (const l of note.links || []) { const n = byId.get(linkNodeId(l)); if (n && (n.type === "paper" || n.type === "web")) return interestOf(n); }
  return null;
}
const NL = { open: false, q: "", filter: {}, sort: "updated", msg: "" };
MIN_CARDS.push("noteslist");
function openNotesList(filter) {
  NL.open = true; NL.filter = filter || {}; NL.q = ""; NL.msg = "";
  if (S.min.cards.noteslist) { S.min.cards.noteslist = false; applyMin(true); }
  renderNotesList();
}
function renderNotesList() {
  const card = $("#noteslist");
  if (!NL.open || (typeof editorOpen === "function" && editorOpen())) { card.hidden = true; return; }
  card.hidden = false;
  const all = [...NT.notes.values()].map((n) => ({ ...n, orbit: noteOrbit(n, noteHas), interest: noteInterest(n) }));
  const rows = filterNotes(all, NL.q, NL.filter).sort((a, b) => NL.sort === "title" ? a.title.localeCompare(b.title)
    : NL.sort === "orbit" ? ["inner", "middle", "outer"].indexOf(a.orbit) - ["inner", "middle", "outer"].indexOf(b.orbit)
      : String(b.updated || "").localeCompare(String(a.updated || "")));
  const withEv = all.filter((n) => !n.archived && (NT.evidence.get(n.id) || []).length).length;
  const chip = (label, filter) => el("button", { class: "linkbtn", "aria-pressed": String(JSON.stringify(filter) === JSON.stringify(NL.filter)),
    on: { click: () => { NL.filter = filter; renderNotesList(); } } }, label);
  const interests = [...new Set(all.map((n) => n.interest).filter(Boolean))];
  const search = el("input", { type: "search", placeholder: "Search notes", value: NL.q, "aria-label": "Search notes",
    on: { input: (e) => { NL.q = e.target.value; renderNotesList(); const s = $("#noteslist input[type=search]"); s.focus(); s.setSelectionRange(s.value.length, s.value.length); } } });
  const sort = el("select", { "aria-label": "Sort notes", on: { change: (e) => { NL.sort = e.target.value; renderNotesList(); } } },
    ...[["updated", "Recently updated"], ["title", "Title"], ["orbit", "Orbit"]].map(([v, l]) => { const o = el("option", { value: v }, l); if (NL.sort === v) o.selected = true; return o; }));
  const body = [
    el("p", { class: "note", style: "margin-top:0" }, notesLine(all.filter((n) => !n.archived).length, withEv) + ". ",
      el("button", { class: "linkbtn", on: { click: () => openEditor(null) } }, "＋ New note")),
    NL.msg ? el("p", { class: "note warn", role: "alert" }, NL.msg) : null,
    search, el("div", { class: "actions" }, sort),
    el("div", { class: "nl-chips" }, chip("All", {}), chip("In a report", { orbit: "inner" }), chip("Backed by papers", { orbit: "middle" }),
      chip("Ideas", { orbit: "outer" }), ...interests.map((i) => chip(i, { interest: i })), chip("Archived", { archived: true })),
    rows.length ? null : el("p", { class: "note" }, NT.notes.size ? "No notes match." : "No notes yet. ＋ New note starts one."),
    ...rows.map((n) => el("div", { class: "nl-row" },
      el("button", { class: "linkbtn nl-title", on: { click: () => { NL.open = false; openEditor(n.id); } } }, n.title),
      el("div", { class: "note muted" }, ({ inner: "In a report", middle: "Backed by papers", outer: "Idea" })[n.orbit] + " · " + (n.links || []).length + " linked · updated "
        + (n.updated ? shortDate(n.updated.slice(0, 10)) : "never") + ((NT.evidence.get(n.id) || []).length ? " · new evidence" : "")),
      NT.serving ? el("button", { class: "linkbtn", on: { click: () => archiveFromList(n) } }, n.archived ? "Restore" : "Archive") : null)),
  ];
  cardFrame("noteslist", "Notes", cardChip("Notes", all.filter((n) => !n.archived).length, withEv ? withEv + " with new evidence" : ""), body);
  if (cardOpen("noteslist")) card.firstChild.append(el("button", { title: "Close", "aria-label": "Close the notes list", on: { click: () => { NL.open = false; renderNotesList(); } } }, "×"));
}
/* Archive or restore N from the list. A failure says why, on the list. */
async function archiveFromList(n) {
  const r = await noteApi("/api/note/archive", { id: n.id, archived: !n.archived, version: n.version });
  const cur = NT.notes.get(n.id) || n, verb = n.archived ? "Not restored: " : "Not archived: ";
  NL.msg = "";
  if (r.status === 200) NT.notes.set(n.id, { ...cur, ...r.data.note, version: r.data.version });
  else if (r.status === 409 && r.data.conflict) {
    NT.notes.set(n.id, { ...cur, ...r.data.disk, version: r.data.diskVersion });
    NL.msg = verb + n.title + " changed in its file since the list was loaded. The list now shows the file's version; try again.";
  } else if (r.status === 409 && r.data.deleted) { NT.notes.delete(n.id); NL.msg = verb + n.title + " was deleted elsewhere."; }
  else NL.msg = verb + ((r.data && r.data.error) || "the helper refused it.");
  notesChanged();
}
NT.onChange.push(() => { if (NL.open) renderNotesList(); });
