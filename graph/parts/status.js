/* The Status tab: when the map was built, what it covers, and what to fix.

   Every problem sits next to the command that fixes it. */

function statusRows(data, counts) {
  const m = data.meta, cov = m.coverage || {}, lab = m.labels || {}, warn = m.warnings || [];
  const n = (v) => (v || 0).toLocaleString();
  const missing = (cov.notFound || 0) + (cov.mismatch || 0) + (cov.noId || 0) + (cov.notFetched || 0);
  return [
    { label: "Last built", value: m.built, problem: false, fix: "" },
    { label: "Items", value: n(counts.shown) + " shown · hidden: " + n(counts.shortlist) + " by the shortlist, "
      + n(counts.offTopic) + " judged off-topic, " + n(counts.other) + " by other filters", problem: false, fix: "" },
    { label: "New items counted from", value: m.newSince + " (your most recent search)", problem: false, fix: "" },
    { label: "OpenAlex coverage", value: n(cov.found) + " found · " + n(cov.notFound) + " not found · " + n(cov.mismatch)
      + " rejected (OpenAlex returned a different title) · " + n(cov.noId) + " without an id · " + n(cov.notFetched) + " not yet fetched",
    problem: missing > 0, fix: "Run python3 tools/knowledge_graph.py --enrich to fetch what is missing. A paper OpenAlex does not have, or matched to a different title, has no citation lines or research group." },
    { label: "Sub-area labels", value: n(lab.notLabelled) + " not yet labelled · " + n(lab.fitsNone) + " fit no listed sub-area · "
      + n(lab.stale) + " use a sub-area the profile no longer lists", problem: (lab.notLabelled || 0) + (lab.stale || 0) > 0,
    fix: "Run /rank, which labels what it scores, or label papers with python3 tools/state.py subareas (see graph/README.md)." },
    { label: "Contribution labels", value: n(lab.noContribution) + " papers without one", problem: (lab.noContribution || 0) > 0,
      fix: "Run /rank, which labels what it scores." },
    { label: "Citation links", value: n(data.edges.filter((e) => e.type === "cites").length), problem: false, fix: "" },
    { label: "When it next refreshes", value: "After your next /research, /rank, /synthesize, /update or /websearch, or when you run /graph.", problem: false, fix: "" },
    { label: "Warnings from the build", value: warn.length ? warn.join("; ") : "None", problem: warn.length > 0,
      fix: "The rest of the map was built; fix the file the warning names and run /graph again." },
  ];
}
function statusCounts() {
  const shown = ITEMS.filter((x) => VISIBLE.has(x.id)).length;
  const offTopic = ITEMS.filter((x) => x.hiddenByDefault && !S.filters.offTopic).length;
  const shortlist = ITEMS.filter((x) => !VISIBLE.has(x.id) && !shortlisted(x) && passes(x, "shortlist")).length;
  return { shown, shortlist, offTopic, other: Math.max(0, ITEMS.length - shown - shortlist - offTopic) };
}
function renderStatus() {
  const rows = statusRows(D, statusCounts());
  const fixCell = (text) => {
    const td = el("td", { class: "fix" });
    /* Commands in a fix read as code, so they can be copied exactly. */
    for (const part of text.split(/(python3 tools\/[\w.]+\.py(?: (?:--?[\w-]+|subareas))*)/)) td.append(/^python3 /.test(part) ? el("code", {}, part) : part);
    return td;
  };
  $("#tab-status").replaceChildren(el("h2", {}, "Status"),
    el("p", { class: "lede" }, "When this map was built, what it covers, and what to fix. A red edge marks a row with something to fix."),
    el("table", { class: "status-table" }, el("thead", {}, el("tr", {}, el("th", {}, "What"), el("th", {}, "Now"), el("th", {}, "To fix"))),
      el("tbody", {}, ...rows.map((r) => el("tr", { class: r.problem ? "problem" : "" }, el("td", {}, r.label), el("td", {}, r.value), r.problem ? fixCell(r.fix) : el("td", { class: "fix" }, ""))))));
}
TAB_HOOKS.status = renderStatus;
ON_FILTERS.push(() => { if (S.tab === "status") renderStatus(); });
