/* The Overview tab: the "On your map" card, the selection card, keys, hover and minimising.

   Every mark on the globe is explained where it appears: the ring key shows while
   ringed items are in view, the selection card says in words what each line colour
   means, and the notice says when the dot cap is trimming what is drawn. */

const KIND_PAPER = "Paper", KIND_WEB = "Web source (not peer-reviewed)";
function shortDate(iso) {
  const [, m, d] = String(iso).split("-").map(Number);
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return d && m >= 1 && m <= 12 ? d + " " + months[m - 1] : String(iso);
}
function ringKey(newInView, since) {
  return "○ ring = new since your last search (" + shortDate(since) + ") · " + newInView.toLocaleString() + " in view";
}
/* One plain sentence per line colour, with a separate sentence when a count is zero. */
function lineSentences(outN, inN) {
  return [outN ? "Amber, going out: this paper cites " + outN + " " + (outN === 1 ? "paper" : "papers") + " in your library."
    : "Amber, going out: none, because none of this paper's references are in your library.",
  inN ? "Blue, coming in: " + inN + " " + (inN === 1 ? "paper" : "papers") + " in your library " + (inN === 1 ? "cites" : "cite") + " this one."
    : "Blue, coming in: none, because no paper in your library cites this one yet."];
}
function hiddenLinesNote(hidden) {
  return hidden ? hidden + " more " + (hidden === 1 ? "is" : "are") + " hidden by the current filters." : "";
}
/* What a minimised card still says: what it is, and its key number or name. */
function cardChip(name, count, extra) {
  let tail = "";
  if (extra) {
    let t = String(extra);
    if (t.length > 28) { t = t.slice(0, 28); t = (t.lastIndexOf(" ") > 10 ? t.slice(0, t.lastIndexOf(" ")) : t).replace(/[\s,;:.-]+$/, "") + "…"; }
    tail = ": " + t;
  }
  return "▸ " + name + (count != null ? " · " + count.toLocaleString() : "") + tail;
}
/* The highlight's count is what the map shows; anything the filters hide is named. */
function highlightChipText(why, ids, visible) {
  const shown = ids.filter((id) => visible.has(id)).length, hidden = ids.length - shown;
  return "Highlighted: " + why + " · " + shown.toLocaleString() + (hidden ? " shown, " + hidden.toLocaleString() + " hidden by the filters" : "");
}
function libraryLine(groups, gaps) {
  return groups.toLocaleString() + " research group" + (groups === 1 ? "" : "s") + " · " + gaps.toLocaleString() + " gap" + (gaps === 1 ? "" : "s");
}
/* Items per interest that PASS lets through, in one pass over the library. */
function interestCounts(items, pass) {
  const out = {};
  for (const n of items) if (pass(n)) out[interestOf(n)] = (out[interestOf(n)] || 0) + 1;
  return out;
}
/* Counts for the Papers / Web switch, under every other filter (PASS ignores the kind). */
function kindCounts(items, pass) {
  const out = { both: 0, paper: 0, web: 0 };
  for (const n of items) {
    if (!pass(n)) continue;
    out.both++;
    if (n.type === "web") out.web++; else out.paper++;
  }
  return out;
}

const OV = { q: "", colourMsg: "", defaultsDone: false };
MIN_CARDS.push("mapcard", "selcard", "globe-legend");
function cardOpen(id) { return !S.min.cards[id]; }
function setCardMin(id, on) { S.min.cards[id] = on; applyMin(true); }
/* A card's frame: a chip when minimised, else a header with a minimise control. */
function cardFrame(id, title, chip, body) {
  const card = document.getElementById(id);
  card.classList.toggle("min", !cardOpen(id));
  if (!cardOpen(id)) {
    card.replaceChildren(el("button", { class: "chip", title: "Show " + title, on: { click: () => setCardMin(id, false) } }, chip));
    return;
  }
  card.replaceChildren(el("div", { class: "hd" }, el("span", { class: "t" }, title),
    el("button", { title: "Minimise (M minimises everything)", "aria-label": "Minimise " + title, on: { click: () => setCardMin(id, true) } }, "–")), ...body.filter((x) => x != null));
}
function kindChoice() {
  const s = S.filters.sets.type;
  if (!s || !s.size) return "both";
  return s.has(KIND_PAPER) && !s.has(KIND_WEB) ? "paper" : s.has(KIND_WEB) && !s.has(KIND_PAPER) ? "web" : "both";
}
function setKind(choice) {
  if (choice === "both") delete S.filters.sets.type;
  else S.filters.sets.type = new Set([choice === "paper" ? KIND_PAPER : KIND_WEB]);
  refreshData();
}
function toggleColour(name) {
  const chosen = S.colours ? S.colours.slice()
    : Object.entries(COLOUR_SLOTS).filter(([, k]) => k).sort((a, b) => a[1] - b[1]).map(([n]) => n);
  OV.colourMsg = "";
  if (chosen.includes(name)) chosen.splice(chosen.indexOf(name), 1);
  else if (chosen.length >= 6) OV.colourMsg = "Six interests are coloured; uncolour one first.";
  else chosen.push(name);
  store.set("kg-colours", JSON.stringify(chosen));
  refreshColourSlots();
  if (!deferExplore()) { refreshObjects(); renderLegend(); }
  renderMapCard(); globeRequestDraw();
}
function renderMapCard() {
  const shownIds = ITEMS.filter((n) => VISIBLE.has(n.id));
  if (!ITEMS.length) {
    cardFrame("mapcard", "On your map", cardChip("On your map", 0), [el("p", {}, "Nothing in your library yet. Run /research to start.")]);
    return;
  }
  const k = kindCounts(ITEMS, (n) => passes(n, "type")), choice = kindChoice();
  const seg = el("div", { class: "seg", role: "group", "aria-label": "Show" },
    ...[["both", "Both", k.both], ["paper", "Papers only", k.paper], ["web", "Web only", k.web]].map(([c, label, count]) =>
      el("button", { "aria-pressed": String(choice === c), on: { click: () => setKind(c) } }, label, el("span", { class: "n" }, count.toLocaleString()))));
  const kindNote = choice === "paper" ? "Papers only means peer-reviewed sources: no web pages."
    : choice === "web" ? "Web sources are not peer-reviewed and have no citation lines." : null;
  const more = ITEMS.filter((n) => !shortlisted(n) && passes(n, "shortlist")).length;
  const shortlist = el("label", { class: "irow", style: "align-items:flex-start;margin-top:10px" },
    el("input", { type: "checkbox", checked: S.filters.all, on: { change: (e) => { S.filters.all = e.target.checked; refreshData(); } } }),
    el("span", {}, "Include peripheral and excluded", el("br"), el("span", { class: "note" },
      S.filters.all ? "Showing everything." : more.toLocaleString() + " more are hidden · the map starts with Core, Supporting and not yet scored")));
  const fresh = shownIds.filter((n) => isNew(n)).length;
  const newLine = el("p", { class: "note" }, el("button", { class: "linkbtn", "aria-pressed": String(S.filters.newOnly),
    title: S.filters.newOnly ? "Show everything again" : "Show only these", on: { click: () => { S.filters.newOnly = !S.filters.newOnly; refreshData(); } } },
  "○ " + fresh.toLocaleString() + " new since " + shortDate(S.since)), S.filters.newOnly ? " · showing only these" : "");
  const names = INTERESTS.concat(ITEMS.some((n) => interestOf(n) === "Uncategorized") ? ["Uncategorized"] : []);
  const on = ticked("interest", names), perInterest = interestCounts(ITEMS, (n) => passes(n, "interest"));
  const rows = [];
  for (const name of names) {
    if (OV.q && !name.toLowerCase().includes(OV.q.toLowerCase())) continue;
    const count = perInterest[name] || 0;
    const coloured = !!COLOUR_SLOTS[name], uncat = name === "Uncategorized";
    rows.push(el("div", { class: "irow" + (on.has(name) ? "" : " off") },
      el("button", { class: "dotbtn", style: "background:" + interestColor(name), disabled: uncat,
        title: uncat ? "Uncategorized items are always grey" : coloured ? "Remove its colour" : "Colour this interest",
        "aria-label": (coloured ? "Remove the colour of " : "Colour ") + name, on: { click: () => toggleColour(name) } }),
      el("button", { class: "name", title: on.has(name) ? "Hide this interest" : "Show this interest",
        on: { click: () => toggleFacet("interest", names, name, !on.has(name)) } }, name),
      el("span", { class: "n" }, count.toLocaleString())));
  }
  const search = names.length > 8 ? el("input", { type: "search", placeholder: "Search " + names.length + " interests", value: OV.q,
    "aria-label": "Search research interests", on: { input: (e) => { OV.q = e.target.value; renderMapCard(); const q = $("#mapcard input[type=search]"); q.focus(); q.setSelectionRange(q.value.length, q.value.length); } } }) : null;
  const extra = exploreOnlyFilters(S.filters);
  const body = [
    el("div", { class: "big" }, shownIds.length.toLocaleString(), el("span", { class: "note", style: "font-size:14px;font-weight:400" }, " items shown")),
    el("div", { class: "note", style: "margin-top:2px" }, "of " + ITEMS.length.toLocaleString() + " in the library, across " + plural(INTERESTS.length, "research interest")),
    el("div", { class: "note", style: "margin-top:10px" }, "Show"), seg, kindNote ? el("p", { class: "note" }, kindNote) : null,
    shortlist, newLine,
    el("p", { class: "note" }, "In the library: " + libraryLine(D.labs.filter((l) => l.papers.length > 1).length, D.gaps.length) + " · ",
      el("button", { class: "linkbtn", on: { click: () => { setTab("explore", true); setView("groups"); } } }, "groups"), " ",
      el("button", { class: "linkbtn", on: { click: () => { setTab("explore", true); setView("gaps"); } } }, "gaps")),
    el("div", { class: "note", style: "margin-top:10px" }, "Research interests: click a name to hide it, its dot to colour it"),
    search, ...rows,
    OV.colourMsg ? el("p", { class: "note warn" }, OV.colourMsg) : null,
    el("p", { class: "note" }, "The six largest are coloured by default, the rest grey, so no colour repeats."),
    extra.length ? el("p", { class: "note warn" }, "Also filtered in Explore: " + extra.join(", ") + ". ",
      el("button", { class: "linkbtn", on: { click: () => {
        const f = S.filters;
        S.filters = { sets: Object.fromEntries(["interest", "type"].filter((x) => f.sets[x]).map((x) => [x, f.sets[x]])),
          yearMin: null, yearMax: null, undated: true, newOnly: f.newOnly, offTopic: false, all: f.all };
        refreshData();
      } } }, "Clear those")) : null,
    el("p", { class: "note" }, el("button", { class: "linkbtn", on: { click: () => setTab("connects", true) } }, "See how your library connects →")),
  ];
  cardFrame("mapcard", "On your map", cardChip("On your map", shownIds.length), body);
}
function renderSelCard() {
  const card = $("#selcard"), id = S.current, n = id ? byId.get(id) : null;
  if (!n || (n.type !== "paper" && n.type !== "web")) { card.hidden = true; card.replaceChildren(); return; }
  card.hidden = false;
  const i = GL.index ? GL.index.get(id) : undefined;
  const near = (list) => (i == null ? [] : list[i].map((j) => GL.model.ids[j]));
  const cites = near(GL.out || []), citedBy = near(GL.inn || []);
  const grade = (n.type === "web" ? n.tier : n.verdict) || "Not yet scored";
  const body = [el("h3", {}, n.title),
    el("div", { class: "tags" }, el("span", { class: "tag", style: "border-color:" + interestColor(interestOf(n)) }, interestOf(n)),
      el("span", { class: "tag" }, subareaText(n)), el("span", { class: "tag" }, n.year == null ? "Undated" : String(n.year)),
      el("span", { class: "tag" }, grade), el("span", { class: "tag" }, n.type === "web" ? "Web source, not peer-reviewed" : "Paper"))];
  if (!VISIBLE.has(id)) body.push(el("p", { class: "note warn" }, "Hidden by the current filters."));
  if (n.type === "web") {
    body.push(el("p", { class: "note" }, "Web sources are not peer-reviewed and have no citation lines, so nothing is drawn from this one."));
  } else {
    const [amber, blue] = lineSentences(cites.length, citedBy.length);
    const hidden = cites.concat(citedBy).filter((x) => !VISIBLE.has(x)).length;
    body.push(el("div", { class: "note" }, "Cites " + cites.length + " · cited by " + citedBy.length + " (within the library)"),
      el("p", { class: "note" }, el("span", { class: "key", style: "color:var(--cites)" }, "━▶ "), amber),
      el("p", { class: "note", style: "margin-top:2px" }, el("span", { class: "key", style: "color:var(--citedby)" }, "━▶ "), blue),
      el("p", { class: "note muted" }, "The arrowhead points at the paper being cited. A line only appears when both papers are in your library. This paper may cite others you have not collected. " + hiddenLinesNote(hidden)));
  }
  const short = shortLabel(n.title, 40), steps = [];
  const step = (label, ids, why) => steps.push(el("button", { class: "linkbtn", on: { click: () => { highlightSet(ids, why); renderOverview(); globeRequestDraw(); } } }, label));
  if (n.type === "paper") {
    step("Show what it cites", [id].concat(cites), "what " + short + " cites");
    step("Show what cites it", [id].concat(citedBy), "what cites " + short);
  }
  const lab = n.primaryLab ? labById.get(n.primaryLab) : null;
  if (lab) step("Show its research group's other papers", lab.papers.concat(lab.bridges || []), lab.name);
  if (i != null) {
    const c = GL.model.clusters[GL.model.cluster[i]];
    step("Show the same sub-area", c.members.map((j) => GL.model.ids[j]), c.name);
  }
  steps.push(el("button", { class: "linkbtn", on: { click: () => { setTab("explore", true); select(id); } } }, "Open full details"));
  body.push(el("div", { class: "steps" }, ...steps));
  cardFrame("selcard", "Selected", cardChip("Selected", null, n.title), body);
  if (cardOpen("selcard")) card.firstChild.append(el("button", { title: "Close (Esc)", "aria-label": "Close", on: { click: globeClear } }, "×"));
}
function renderHighlightChip() {
  const chip = $("#highlight-chip");
  if (!S.highlight) { chip.hidden = true; return; }
  chip.hidden = false;
  chip.replaceChildren(highlightChipText(S.highlightWhy, [...S.highlight], VISIBLE) + " · ",
    el("button", { class: "linkbtn", on: { click: () => { S.highlight = null; S.highlightWhy = ""; refreshObjects(); renderOverview(); globeRequestDraw(); } } }, "Clear"));
}
/* Whether citation lines are on the globe right now (the legend explains them if so). */
function legendHasLines() {
  const sel = globeSelectedIndex();
  return sel != null ? GL.model.items[sel].type === "paper" : GL.zoom > 1.15 && GL.zoom < 4 && GL.strong.length > 0;
}
function renderGlobeLegend() {
  const lines = GL.model ? legendHasLines() : false;
  OV.legendLines = lines;
  const body = [el("p", { class: "note", style: "margin:0" }, "Each glow is a sub-area, sized by its items. Zoom in to see the items: ● paper, ■ web source. North = newer, south = older; undated at the south pole. Ring = new since your last search."),
    lines ? el("p", { class: "note" }, "Lines are citations between papers in your library: click a paper to see them, amber for what it cites, blue for what cites it.") : null];
  cardFrame("globe-legend", "How to read the globe", cardChip("How to read the globe"), body);
}
/* After every draw: the dot-cap notice and the ring key, which depend on the view. */
function afterGlobeDraw() {
  const notice = $("#globe-notice"), dots = zoomBlend(GL.zoom).dots;
  notice.textContent = dots < 0.05 ? "Zoomed out: showing sub-area totals. Zoom in to see items."
    : GL.counts.drawn < GL.counts.inView ? GL.counts.drawn.toLocaleString() + " of " + GL.counts.inView.toLocaleString() + " items in view drawn, highest scored first. Zoom in or filter to see more."
      : GL.counts.inView.toLocaleString() + " items in view, all drawn.";
  let fresh = 0;
  if (dots >= 0.05) {
    const { W, H, cx, cy, R } = globeGeometry(), rot = rotation(GL.yaw, GL.pitch), m = GL.model;
    for (let i = 0; i < m.n; i++) {
      if (!GL.fresh[i] || !GL.mask[i]) continue;
      const p = project(rot, m.vx[i], m.vy[i], m.vz[i]), sx = cx + p[0] * R, sy = cy - p[1] * R;
      if (p[2] > 0.02 && sx > 0 && sx < W && sy > 0 && sy < H) fresh++;
    }
  }
  const key = $("#ringkey");
  key.hidden = !fresh;
  key.textContent = fresh ? ringKey(fresh, S.since) : "";
  if (OV.legendLines !== legendHasLines()) renderGlobeLegend();
}
function globeTip(info, x, y) {
  const tip = $("#globe-tip");
  if (!info) { tip.hidden = true; return; }
  if (info.kind === "note") {
    const n = NT.notes.get(info.id);
    if (!n) { tip.hidden = true; return; }
    tip.replaceChildren(el("strong", {}, n.title), el("div", { class: "muted" }, orbitWords(n, noteHas, reportTitleOf)));
  } else if (info.kind === "item") {
    const n = byId.get(info.id);
    tip.replaceChildren(el("strong", {}, n.title), el("div", { class: "muted" }, (n.year == null ? "Undated" : n.year) + " · " + (n.type === "web" ? "web source, not peer-reviewed" : "paper")));
    if (isNew(n)) tip.append(el("div", {}, "○ New since your last search (" + shortDate(S.since) + ")"));
  } else {
    tip.replaceChildren(el("strong", {}, byId.get(info.from).title), " cites ", el("strong", {}, byId.get(info.to).title));
  }
  tip.hidden = false;
  tip.style.left = Math.min(x + 14, window.innerWidth - tip.offsetWidth - 8) + "px";
  tip.style.top = Math.min(y + 14, window.innerHeight - tip.offsetHeight - 8) + "px";
}
function renderOverview() {
  if (!OV.defaultsDone) {
    OV.defaultsDone = true;
    /* On a phone-width screen the cards start as chips, so the globe is visible. */
    if (store.get("kg-min") == null && window.matchMedia("(max-width: 600px)").matches) for (const id of MIN_CARDS) S.min.cards[id] = true;
    /* Below 900 px the legend starts as a chip, so it never sits under the card's list. */
    else if (store.get("kg-min") == null && window.matchMedia("(max-width: 900px)").matches) S.min.cards["globe-legend"] = true;
  }
  renderMapCard(); renderSelCard(); renderHighlightChip(); renderGlobeLegend();
}
/* The globe makes room for the "On your map" card. The selection card floats over it
   instead: moving the globe on every click would move what was just clicked. */
GL.insets = () => ({ left: $("#globe").clientWidth > 900 && cardOpen("mapcard") ? 324 : 0, right: 0 });
GL.onSelect = (id) => { if (id) select(id); renderOverview(); };
GL.onHover = globeTip;
GL.afterDraw = afterGlobeDraw;
{
  const globeHook = TAB_HOOKS.overview;
  TAB_HOOKS.overview = () => { globeEnsure(); renderOverview(); globeHook(); };
}
ON_FILTERS.push(() => { if (S.tab === "overview") renderOverview(); });
