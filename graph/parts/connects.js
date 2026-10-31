/* The How it connects tab: the kinds of thing in the library and how they link.

   A type-level map before the items: each kind with its exact count, each link with
   what it means. Counts are the whole library, before filters, so they match what
   the build reports. */

/* The eight kinds' relations, as the build makes them: [from, to, what it means]. */
const SCHEMA_LINKS = [
  ["papers", "subareas", "labelled with"], ["web", "subareas", "labelled with"],
  ["subareas", "interests", "part of"], ["papers", "papers", "cites"],
  ["papers", "groups", "from"], ["papers", "reports", "used in"],
  ["gaps", "subareas", "about"], ["gaps", "reports", "open question in"],
];
const SCHEMA_KINDS = [
  ["interests", "Research interests", 360, 40], ["subareas", "Sub-areas", 360, 140],
  ["papers", "Papers", 230, 255], ["web", "Web sources", 570, 255],
  ["groups", "Research groups", 95, 375], ["reports", "Your reports", 285, 375], ["gaps", "Gaps", 555, 375],
];
function schemaCounts(data) {
  const by = (t) => data.nodes.filter((n) => n.type === t).length;
  /* "Uncategorized" and the "no sub-area" hubs hold items, but are not interests or sub-areas. */
  return { interests: data.nodes.filter((n) => n.type === "interest" && n.label !== "Uncategorized").length,
    subareas: data.nodes.filter((n) => n.type === "subarea" && !/__(unlabelled|unassigned|stale)$/.test(String(n.id))).length,
    papers: by("paper"), web: by("web"),
    groups: data.labs.filter((l) => l.papers.length > 1).length, reports: by("report"), gaps: by("gap"),
    cites: data.edges.filter((e) => e.type === "cites").length };
}
const CN = { on: null };
function renderConnects() {
  const pane = $("#tab-connects"), counts = schemaCounts(D);
  const pos = Object.fromEntries(SCHEMA_KINDS.map(([k, , x, y]) => [k, [x, y]]));
  const name = Object.fromEntries(SCHEMA_KINDS.map(([k, label]) => [k, label]));
  const svg = svgEl("svg", { id: "schema", viewBox: "0 0 720 420", role: "img", "aria-label": "The kinds of thing in your library and how they link" });
  for (const [from, to, label] of SCHEMA_LINKS) {
    const [x1, y1] = pos[from], [x2, y2] = pos[to];
    if (from === to) {
      svg.append(svgEl("path", { class: "link", d: `M ${x1 - 85} ${y1 - 8} C ${x1 - 150} ${y1 - 60}, ${x1 - 150} ${y1 + 50}, ${x1 - 85} ${y1 + 8}` }),
        svgEl("text", { class: "lbl", x: x1 - 118, y: y1 - 44, "text-anchor": "middle" }, label + " (" + counts.cites.toLocaleString() + ")"));
      continue;
    }
    svg.append(svgEl("line", { class: "link", x1, y1, x2, y2 }),
      svgEl("text", { class: "lbl", x: (x1 + x2) / 2, y: (y1 + y2) / 2 - 6, "text-anchor": "middle" }, label));
  }
  for (const [key, label, x, y] of SCHEMA_KINDS) {
    const g = svgEl("g", { class: "kind" + (CN.on === key ? " on" : ""), tabindex: "0", role: "button",
      "aria-label": label + ": " + counts[key], on: { click: () => { CN.on = key; renderConnects(); },
        keydown: (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); CN.on = key; renderConnects(); } } } },
    svgEl("rect", { x: x - 85, y: y - 23, width: 170, height: 46, rx: 8 }),
    svgEl("text", { x, y: y - 3, "text-anchor": "middle" }, label),
    svgEl("text", { class: "n", x, y: y + 14, "text-anchor": "middle" }, counts[key].toLocaleString()));
    svg.append(g);
  }
  const detail = el("div", { id: "schema-detail" });
  if (!CN.on) detail.append(el("h3", {}, "Click a kind"), el("p", { class: "muted" }, "Its count, what it connects to, and where to see all of them."));
  else {
    const key = CN.on, links = SCHEMA_LINKS.filter(([a, b]) => a === key || b === key);
    const action = {
      papers: ["Show all " + counts.papers.toLocaleString() + " on the map", () => { S.filters.sets.type = new Set([KIND_PAPER]); refreshData(); setTab("overview", true); }],
      web: ["Show all " + counts.web.toLocaleString() + " on the map", () => { S.filters.sets.type = new Set([KIND_WEB]); refreshData(); setTab("overview", true); }],
      interests: ["See them on the globe", () => { GL.zoom = 1; setTab("overview", true); }],
      subareas: ["See them on the globe", () => { GL.zoom = 1; setTab("overview", true); }],
      groups: ["Open the Research groups view", () => { setTab("explore", true); setView("groups"); }],
      reports: ["Open the Library view", () => { setTab("explore", true); setView("library"); }],
      gaps: ["Open the Gaps view", () => { setTab("explore", true); setView("gaps"); }],
    }[key];
    detail.append(el("h3", {}, name[key] + " · " + counts[key].toLocaleString()),
      el("p", { class: "small muted", style: "margin:0 0 4px" }, "Connects to:"),
      el("ul", { class: "small", style: "margin:0 0 10px;padding-left:18px" }, ...links.map(([a, b, label]) =>
        el("li", {}, a === b ? "Papers " + label + " papers (" + counts.cites.toLocaleString() + " links)" : name[a] + " " + label + " " + name[b].toLowerCase()))),
      el("button", { on: { click: action[1] } }, action[0]));
  }
  pane.replaceChildren(el("h2", {}, "How your library connects"),
    el("p", { class: "lede" }, "The kinds of thing in your library, how many there are, and how they link. Counts are the whole library, before filters."),
    el("div", { class: "schema-wrap" }, svg, detail));
}
TAB_HOOKS.connects = renderConnects;
