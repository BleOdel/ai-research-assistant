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
    return { status: 0, data: { error: "The helper is not answering, so this was not saved." } };
  }
}
function setNotes(list) {
  NT.notes = new Map(list.map((n) => [n.id, n]));
}
async function notesInit() {
  setNotes(D.notes || []); NT.unreadable = D.notesUnreadable || []; NT.prompts = D.prompts || [];
  if (location.protocol === "http:" || location.protocol === "https:") {
    const url = new URL(location.href), t = url.searchParams.get("t");
    if (t) {
      NT.token = t;
      /* The token leaves the address at once, so no bookmark or screenshot carries it. */
      url.searchParams.delete("t");
      history.replaceState(null, "", url.pathname + url.search + location.hash);
    } else {
      const s = await noteApi("/api/session");   /* after a reload: the cookie gets it back */
      if (s.status === 200) NT.token = s.data.token;
    }
  }
  if (NT.token) {
    const st = await noteApi("/api/state");
    if (st.status === 200) {
      NT.serving = true; NT.built = st.data.built;
      setNotes(st.data.notes); NT.unreadable = st.data.unreadable; NT.prompts = st.data.prompts;
      setInterval(beatAndCheck, 60000);
    }
  }
  notesChanged();
}
/* Every minute: keep the helper awake, and notice a rebuild made by another command. */
async function beatAndCheck() {
  const r = await noteApi("/api/heartbeat", {});
  if (r.status !== 200) { NT.serving = false; notesChanged(); return; }
  if (NT.built != null && r.data.built != null && r.data.built !== NT.built) showRebuilt();
}
function showRebuilt() {
  const b = $("#rebuilt");
  b.hidden = false;
  b.replaceChildren("The library was rebuilt. ", NT.dirty ? "Save or export your note first. " : "",
    el("button", { on: { click: () => { if (!NT.dirty || window.confirm("Your note has unsaved changes. Reload anyway?")) location.reload(); } } }, "Reload"));
}
window.addEventListener("beforeunload", (e) => { if (NT.dirty) { e.preventDefault(); e.returnValue = ""; } });
