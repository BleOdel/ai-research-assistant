/* The note editor and its guide: prompts, checks, suggested papers, new evidence.

   The guide never invents anything: every prompt is a line the researcher writes, every
   check says what it is based on, and every suggestion names the words or sub-area it
   rests on. Saving goes through the local helper; without it the editor still works,
   says plainly that saving is off, and offers Export so nothing typed is lost. */

const PRESETS = [["Claim", "What are you saying, in one sentence?"], ["Evidence", "Which papers or results back it up?"],
  ["Against", "What disagrees, or could?"], ["Gap", "What is missing or untested?"], ["Next step", "What would you do next?"]];
/* Whether the body has a line that starts with the prompt's name and a colon. */
function promptDone(body, name) {
  const safe = String(name).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp("(^|\\n)[ \\t]*" + safe + "[ \\t]*:", "i").test(String(body || ""));
}
function addPromptLine(body, name) {
  const text = String(body || "").replace(/\s+$/, "");
  return (text ? text + "\n\n" : "") + name + ": ";
}
function customPromptError(name, existing) {
  const n = String(name || "").trim();
  if (!n) return "Give the prompt a name.";
  if (n.length > 24) return "Keep the name to 24 characters or fewer.";
  const taken = PRESETS.map((p) => p[0]).concat((existing || []).map((p) => p.name)).map((x) => x.toLowerCase());
  return taken.includes(n.toLowerCase()) ? "That prompt already exists." : "";
}
/* The guide's checks, each with what it is based on. CTX: kind(link), lab(link) -> lab id
   or null, labName(id), newEvidence(note) -> [{id, title, why}]. */
function checksFor(note, ctx) {
  const out = [], links = note.links || [], body = String(note.body || "");
  if (!links.length) {
    const seen = [];
    for (const m of body.matchAll(/(\d+(?:\.\d+)?\s?%|\d+(?:\.\d+)?|\b(?:only|every|never|none|first|proves?)\b)/gi)) if (!seen.includes(m[0])) seen.push(m[0]);
    if (seen.length) out.push({ kind: "claim", text: "Reads like a factual claim, and nothing is linked.", basis: "the words " + seen.map((w) => '"' + w + '"').join(", ") });
  }
  const papers = links.filter((l) => ctx.kind(l) === "paper");
  const labs = papers.map((l) => ctx.lab(l));
  if (papers.length >= 2 && labs[0] && labs.every((x) => x === labs[0])) {
    out.push({ kind: "onegroup", text: "Every linked paper comes from one research group.",
      basis: (papers.length === 2 ? "both linked papers are" : "all " + papers.length + " linked papers are") + " from " + ctx.labName(labs[0]) });
  }
  if (links.length && links.every((l) => ctx.kind(l) === "web")) {
    out.push({ kind: "webonly", text: "Only web sources are linked.", basis: "every linked item is a web source (not peer-reviewed)" });
  }
  if (papers.length >= 2 && !promptDone(body, "Against")) {
    out.push({ kind: "noagainst", text: "Nothing against it yet.", basis: papers.length + ' linked papers, no "Against:" line' });
  }
  for (const ev of ctx.newEvidence(note)) out.push({ kind: "newevidence", text: "New evidence: " + ev.title, basis: ev.why, id: ev.id });
  return out;
}

/* New-evidence rows in the editor: the first three, and a count of the rest until asked. */
function evidenceRows(list, showAll) {
  return showAll || list.length <= 3 ? { shown: list.slice(), more: 0 } : { shown: list.slice(0, 3), more: list.length - 3 };
}

/* ---------- the editor ---------- */
const ED = { open: false, id: null, draft: null, version: null, state: "saved", msg: "", timer: null, conflict: null,
  addingPrompt: false, promptError: "", els: null, allEvidence: false };
MIN_CARDS.push("noteeditor");
function editorOpen() { return ED.open; }
function blankDraft(links) { return { title: "", body: "", links: links.slice(), in_report: null, dismissed: [] }; }
function draftOf(note) {
  return { title: note.title || "", body: note.body || "", links: (note.links || []).slice(), in_report: note.in_report || null,
    dismissed: (note.dismissed || []).slice() };
}
/* PUSH false: following the address (Back, Forward, opening the page at #note=), so
   it is left as it is. */
function openEditor(id, links, push) {
  if (ED.open && NT.dirty && ED.id !== id && !window.confirm("Your note has unsaved changes. Open another anyway?")) return;
  const note = id ? NT.notes.get(id) : null;
  ED.open = true; ED.id = note ? id : null; ED.version = note ? note.version : null;
  ED.draft = note ? draftOf(note) : blankDraft(links || []);
  ED.conflict = null; ED.msg = ""; ED.allEvidence = false; NT.dirty = !note && (links || []).length > 0;
  ED.state = NT.serving ? (NT.dirty ? "unsaved" : "saved") : "readonly";
  S.note = ED.id; writeHash(push !== false);
  if (S.min.cards.noteeditor) { S.min.cards.noteeditor = false; applyMin(true); }
  renderEditor();
  if (typeof renderSelCard === "function") renderSelCard();
  globeRequestDraw();
}
function closeEditor(push) {
  if (NT.dirty && !window.confirm("Your note has unsaved changes. Close it anyway? Export keeps a copy.")) return;
  ED.open = false; ED.id = null; NT.dirty = false; S.note = null; writeHash(push !== false);
  $("#noteeditor").hidden = true;
  if (typeof renderSelCard === "function") renderSelCard();
  globeRequestDraw();
}
function markDirty() {
  NT.dirty = true;
  if (!NT.serving) { ED.state = "readonly"; renderEditorParts(); return; }
  ED.state = "unsaved"; renderEditorParts();
  clearTimeout(ED.timer);
  ED.timer = setTimeout(() => saveDraft(), 1500);
}
/* Save the draft. A failure never touches the text: it says why and offers Export. */
async function saveDraft(opts) {
  if (!NT.serving) { ED.state = "readonly"; renderEditorParts(); return; }
  /* One save at a time: a second one would carry the old version (a conflict with itself)
     or, for a new note, create a second file. It runs when this one is done. */
  if (ED.inFlight) { ED.pending = opts || {}; return; }
  if (!ED.draft.title.trim()) { ED.state = "unsaved"; ED.msg = "Give the note a title to save it."; renderEditorParts(); return; }
  const sent = JSON.stringify(ED.draft), before = ED.id ? noteOrbit(NT.notes.get(ED.id), noteHas) : null;
  ED.state = "saving"; ED.msg = ""; renderEditorParts();
  ED.inFlight = true;
  const r = await noteApi("/api/note", { note: { ...ED.draft, id: ED.id }, version: ED.version, keepUpdated: !!(opts && opts.keepUpdated) });
  ED.inFlight = false;
  if (r.status === 200) {
    const note = r.data.note;
    NT.notes.set(note.id, note);
    ED.id = note.id; ED.version = r.data.version; S.note = note.id; writeHash(false);
    NT.dirty = JSON.stringify(ED.draft) !== sent;   /* typed on while it saved */
    ED.state = NT.dirty ? "unsaved" : "saved";
    if (ED.pending) { const again = ED.pending; ED.pending = null; if (NT.dirty || again.keepUpdated) { saveDraft(again); return; } }
    if (NT.dirty) { clearTimeout(ED.timer); ED.timer = setTimeout(() => saveDraft(), 1500); }
    satMove(note.id, before || "outer", noteOrbit(note, noteHas));
    notesChanged();
  } else if (r.status === 409 && r.data.deleted) {
    ED.pending = null; ED.state = "failed";
    ED.msg = "this note was deleted elsewhere since you opened it. Export keeps a copy; Save as new keeps it as a new note.";
  } else if (r.status === 409 && r.data.conflict) {
    ED.pending = null;
    ED.state = "conflict"; ED.conflict = { disk: r.data.disk, diskVersion: r.data.diskVersion };
  } else {
    ED.pending = null; ED.state = "failed"; ED.msg = (r.data && r.data.error) || "The helper refused the save.";
  }
  renderEditorParts();
}
/* A conflict settled with the file's version: in the editor, and in the notes everywhere else. */
function useFileVersion() {
  const { disk, diskVersion } = ED.conflict;
  ED.draft = draftOf(disk); ED.version = diskVersion; ED.conflict = null; NT.dirty = false; ED.state = "saved";
  if (ED.id) NT.notes.set(ED.id, { ...NT.notes.get(ED.id), ...disk, version: diskVersion });
  notesChanged(); renderEditor();
}
/* The address names the open note (#note=<id>). Opening the page at one, or going Back or
   Forward to one, opens it; an address without one closes the editor (a new note not yet
   saved has no id, so it stays). If the researcher keeps unsaved text instead, or the note
   is not in this page, the address goes back to what is on screen. */
function syncEditorToHash() {
  if (S.note && !NT.notes.has(S.note)) { S.note = ED.open ? ED.id : null; writeHash(false); return; }
  if (S.note && !(ED.open && ED.id === S.note)) openEditor(S.note, undefined, false);
  else if (!S.note && ED.open && ED.id) closeEditor(false);
  else return;
  const shown = ED.open ? ED.id : null;
  if (shown !== S.note) { S.note = shown; writeHash(false); }
}
window.addEventListener("popstate", () => syncEditorToHash());   /* after restoreFromHash has read the address */
function linkLabel(link) {
  const id = linkNodeId(link), p = parseLink(link);
  if (p && p.kind === "group") { const lab = labOf(id); return lab ? lab.name + " (research group)" : link; }
  const n = id ? byId.get(id) : null;
  return n ? (n.title || n.label) + (p.kind === "subarea" ? " (sub-area)" : p.kind === "web" ? " (web source)" : "") : link;
}
function noteMarkdown(id, d) {
  const n = { id: id || null, title: d.title, links: d.links, in_report: d.in_report, dismissed: d.dismissed, created: null, updated: null, archived: null };
  const note = id ? NT.notes.get(id) : null;
  if (note) { n.created = note.created; n.updated = note.updated; n.archived = note.archived; }
  return ["---"].concat(Object.entries(n).map(([k, v]) => k + ": " + JSON.stringify(v)), ["---", d.body]).join("\n");
}
function exportDraft() {
  download((ED.id || "new-note") + ".md", "text/markdown", noteMarkdown(ED.id, ED.draft));
}
function renderEditor() {
  const card = $("#noteeditor");
  card.hidden = false;
  const title = el("input", { type: "text", class: "ed-title", maxlength: "200", placeholder: "Title", value: ED.draft.title, "aria-label": "Note title",
    on: { input: (e) => { ED.draft.title = e.target.value; markDirty(); } } });
  const body = el("textarea", { class: "ed-body", rows: "9", placeholder: "Write your idea. The prompts below help you shape it.", "aria-label": "Note",
    on: { input: (e) => { ED.draft.body = e.target.value; markDirty(); } } });
  body.value = ED.draft.body;
  ED.els = { title, body, state: el("p", { class: "note ed-state", "aria-live": "polite" }), orbit: el("div", { class: "note" }),
    chips: el("div", { class: "ed-chips" }), checks: el("div"), suggest: el("div"), links: el("div"), report: el("div"), actions: el("div", { class: "actions" }),
    conflict: el("div") };
  cardFrame("noteeditor", "Note", cardChip("Note", null, ED.draft.title || "new note"), [ED.els.orbit, title, body, ED.els.state, ED.els.conflict,
    el("div", { class: "note", style: "margin-top:8px" }, "Guide: click a prompt to add it; hover for its question."), ED.els.chips,
    ED.els.checks, ED.els.suggest, ED.els.links, ED.els.report, ED.els.actions]);
  if (cardOpen("noteeditor")) card.firstChild.append(el("button", { title: "Close (Esc)", "aria-label": "Close the note", on: { click: closeEditor } }, "×"));
  renderEditorParts();
}
function renderEditorParts() {
  if (!ED.open || !ED.els || !cardOpen("noteeditor")) { if (ED.open && !cardOpen("noteeditor")) renderEditor(); return; }
  const E = ED.els, d = ED.draft, saving = NT.serving;
  E.orbit.textContent = orbitWords({ links: d.links, in_report: d.in_report }, noteHas, reportTitleOf);
  /* the save state, in words */
  const words = { saved: "Saved.", saving: "Saving…", unsaved: ED.msg || "Not saved yet: it saves a moment after you stop typing.",
    readonly: "Saving is off: run python3 tools/knowledge_graph.py --serve to save. Export keeps a copy.",
    failed: "Not saved: " + ED.msg + " Your text is still here; Export keeps a copy.", conflict: "This note changed somewhere else since you opened it." };
  E.state.textContent = words[ED.state] || "";
  E.state.classList.toggle("warn", ["failed", "conflict", "readonly"].includes(ED.state));
  /* a conflict: both versions, and the researcher chooses */
  E.conflict.replaceChildren();
  if (ED.state === "conflict" && ED.conflict) {
    const disk = ED.conflict.disk;
    E.conflict.append(el("div", { class: "ed-conflict" },
      el("div", {}, el("strong", {}, "In the file now"), el("div", { class: "muted" }, disk.title), el("pre", {}, disk.body)),
      el("div", {}, el("strong", {}, "Yours"), el("div", { class: "muted" }, d.title), el("pre", {}, d.body))),
    el("div", { class: "actions" },
      el("button", { on: { click: () => { ED.version = ED.conflict.diskVersion; ED.conflict = null; saveDraft(); } } }, "Keep mine"),
      el("button", { on: { click: useFileVersion } }, "Use the file's")));
  }
  /* prompts: presets, then the researcher's own */
  E.chips.replaceChildren(...PRESETS.map(([name, q]) => [name, q, false]).concat(NT.prompts.map((p) => [p.name, p.question, true])).map(([name, q, mine]) => {
    const done = promptDone(d.body, name);
    return el("span", { class: "ed-chip" + (done ? " done" : "") }, el("button", { class: "linkbtn", title: q || name, on: { click: () => {
      d.body = addPromptLine(d.body, name); E.body.value = d.body; E.body.focus(); E.body.setSelectionRange(d.body.length, d.body.length); markDirty(); } } },
    (done ? "✓ " : "+ ") + name), mine ? el("button", { class: "linkbtn", title: "Remove this prompt", "aria-label": "Remove the prompt " + name,
      on: { click: () => savePrompts(NT.prompts.filter((p) => p.name !== name)) } }, "×") : null);
  }), ED.addingPrompt ? promptForm() : el("button", { class: "linkbtn", on: { click: () => { ED.addingPrompt = true; ED.promptError = ""; renderEditorParts(); } } }, "＋ Custom"));
  /* checks */
  const checks = checksFor(d, { kind: (l) => (parseLink(l) || {}).kind, lab: (l) => { const n = byId.get(linkNodeId(l)); return n ? n.primaryLab || null : null; },
    labName: (id) => (labById.get(id) || {}).name || id, newEvidence: () => (typeof noteEvidence === "function" ? noteEvidence(ED.id, d) : []) });
  const rows = evidenceRows(checks.filter((c) => c.kind === "newevidence"), ED.allEvidence);
  const visibleChecks = checks.filter((c) => c.kind !== "newevidence").concat(rows.shown);
  E.checks.replaceChildren(...(checks.length ? [el("div", { class: "note", style: "margin-top:8px" }, "Checks")] : []), ...visibleChecks.map((c) => el("div", { class: "ed-check" },
    el("div", {}, c.text), el("div", { class: "note muted" }, "Why: " + c.basis),
    c.kind === "newevidence" ? el("div", { class: "actions" },
      el("button", { disabled: !saving, on: { click: () => { d.links.push(c.id); E.body.focus(); markDirty(); renderEditorParts(); } } }, "Link it"),
      el("button", { disabled: !saving, on: { click: () => { d.dismissed.push(c.id); saveDraft({ keepUpdated: true }); } } }, "Dismiss")) : null)),
  rows.more ? el("button", { class: "linkbtn", on: { click: () => { ED.allEvidence = true; renderEditorParts(); } } },
    "Show all " + (rows.more + rows.shown.length) + " new papers that look related") : null);
  /* suggested papers (Task 7 fills suggestionsFor) */
  const sug = typeof suggestionsFor === "function" ? suggestionsFor(d) : [];
  E.suggest.replaceChildren(...(sug.length ? [el("div", { class: "note", style: "margin-top:8px" }, "Suggested papers")] : []), ...sug.map((s) => el("div", { class: "ed-row" },
    el("span", {}, byId.get(s.id).title, el("span", { class: "note muted" }, " · shares " + s.words.join(", "))),
    el("button", { class: "linkbtn", on: { click: () => { d.links.push(s.id); markDirty(); renderEditorParts(); } } }, "link"))));
  /* what it links to */
  const resolved = resolveLinks(d, noteHas), hidden = resolved.filter((l) => !l.missing && (l.kind === "paper" || l.kind === "web") && !VISIBLE.has(l.id)).length;
  E.links.replaceChildren(el("div", { class: "note", style: "margin-top:8px" }, resolved.length ? "Linked" : "Nothing linked yet."), ...resolved.map((l) => el("div", { class: "ed-row" },
    el("span", { class: l.missing ? "warn" : "" }, l.missing ? "missing: " + l.link : linkLabel(l.link)),
    el("button", { class: "linkbtn", on: { click: () => { d.links = d.links.filter((x) => x !== l.link); markDirty(); renderEditorParts(); } } }, "remove"))),
  hidden ? el("p", { class: "note" }, hidden + " linked " + (hidden === 1 ? "source is" : "sources are") + " hidden by the current filters.") : null);
  /* written into a report */
  const reports = D.nodes.filter((n) => n.type === "report");
  E.report.replaceChildren(el("label", { class: "note" }, "Written into a report: ", el("select", { on: { change: (e) => { d.in_report = e.target.value || null; markDirty(); renderEditorParts(); } } },
    el("option", { value: "" }, "not yet"), ...reports.map((r) => { const o = el("option", { value: r.slug }, r.title); if (d.in_report === r.slug) o.selected = true; return o; }))));
  /* actions */
  const note = ED.id ? NT.notes.get(ED.id) : null;
  E.actions.replaceChildren(
    ED.state === "failed" && /deleted elsewhere/.test(ED.msg) ? el("button", { on: { click: () => { ED.id = null; ED.version = null; saveDraft(); } } }, "Save as new") : null,
    note ? el("button", { disabled: !saving, on: { click: () => archiveNote(note) } }, note.archived ? "Restore" : "Archive") : null,
    el("button", { on: { click: exportDraft } }, "Export"), el("button", { on: { click: closeEditor } }, "Close"));
}
function promptForm() {
  const name = el("input", { type: "text", maxlength: "40", placeholder: "Name (24 characters)", "aria-label": "Prompt name" });
  const q = el("input", { type: "text", maxlength: "200", placeholder: "Guiding question (optional)", "aria-label": "Guiding question" });
  return el("div", { class: "ed-form" }, name, q, ED.promptError ? el("div", { class: "note warn" }, ED.promptError) : null,
    el("div", { class: "actions" }, el("button", { on: { click: () => {
      if (!NT.serving) { ED.promptError = "Custom prompts are saved by the helper; run python3 tools/knowledge_graph.py --serve"; renderEditorParts(); return; }
      const err = customPromptError(name.value, NT.prompts);
      if (err) { ED.promptError = err; renderEditorParts(); return; }
      savePrompts(NT.prompts.concat([{ name: name.value.trim(), question: q.value.trim() }]));
    } } }, "Add"), el("button", { on: { click: () => { ED.addingPrompt = false; renderEditorParts(); } } }, "Cancel")));
}
async function savePrompts(list) {
  const r = await noteApi("/api/prompts", { prompts: list });
  if (r.status === 200) { NT.prompts = r.data.prompts; ED.addingPrompt = false; ED.promptError = ""; }
  else ED.promptError = (r.data && r.data.error) || "Not saved: the helper is not answering.";
  renderEditorParts();
}
async function archiveNote(note) {
  const r = await noteApi("/api/note/archive", { id: note.id, archived: !note.archived, version: ED.version });
  if (r.status === 200) { NT.notes.set(note.id, r.data.note); ED.version = r.data.version; notesChanged(); }
  else if (r.status === 409 && r.data.conflict) { ED.state = "conflict"; ED.conflict = { disk: r.data.disk, diskVersion: r.data.diskVersion }; }
  else { ED.state = "failed"; ED.msg = (r.data && r.data.error) || "The helper is not answering."; }
  renderEditorParts();
}

/* ---------- suggested papers and new evidence ---------- */
/* One matcher for both, so the editor's suggestions and the satellites' new-evidence ring
   never disagree. A note and an item match on the words they share, each word weighted by
   how rare it is in this library: a rare shared word counts more than a common one. The
   word list is plain English only; the library's own common words are discounted by
   rarity, so nothing here is specific to one researcher's topics. */
const STOPWORDS = new Set(("about which their there these those would could should where while being between because other under " +
  "after before through during again against within without paper papers study using based towards toward claim evidence next step " +
  "with from that this when what have does been into were will your them than then they more also only some such each most over same " +
  "both very much many data").split(" "));
const SUGGEST_AT = 5;
function stem(w) {
  return w.length > 5 ? w.replace(/(ing|ed|es|s)$/, "") : w;
}
function tokens(text) {
  return (String(text || "").toLowerCase().match(/[a-z]{4,}/g) || []).filter((w) => !STOPWORDS.has(w)).map(stem);
}
function buildIndex(items) {
  const docs = new Map(), df = new Map();
  for (const it of items) {
    const set = new Set(tokens(it.title + " " + (it.subareas || []).join(" ")));
    docs.set(it.id, set);
    for (const w of set) df.set(w, (df.get(w) || 0) + 1);
  }
  return { n: items.length, df, docs };
}
function matchScore(noteTokens, id, idx) {
  const doc = idx.docs.get(id), words = [];
  let score = 0;
  if (!doc) return { score, words };
  for (const w of new Set(noteTokens)) if (doc.has(w)) { score += Math.log(idx.n / idx.df.get(w)); words.push(w); }
  words.sort((a, b) => idx.df.get(a) - idx.df.get(b));   /* the rarest first */
  return { score, words };
}
function suggestPapers(note, idx, linked, limit = 8) {
  const nt = tokens(note.title + " " + note.body), out = [];
  for (const id of idx.docs.keys()) {
    if (linked.has(id)) continue;
    const m = matchScore(nt, id, idx);
    if (m.score >= SUGGEST_AT) out.push({ id, score: m.score, words: m.words.slice(0, 3) });
  }
  return out.sort((a, b) => b.score - a.score || (a.id < b.id ? -1 : 1)).slice(0, limit);
}
/* Papers first seen after the note was last updated that look related: they share a
   sub-area with a linked paper, or the note's text matches them strongly. Never one the
   note links or has dismissed; nothing for a note not yet saved. */
function newEvidence(note, items, idx, subOf) {
  if (!note.updated) return [];
  const since = String(note.updated).slice(0, 10), links = new Set(note.links || []), dismissed = new Set(note.dismissed || []);
  const subs = new Set((note.links || []).filter((l) => l.startsWith("paper:")).flatMap((l) => subOf(l)));
  const nt = tokens(note.title + " " + note.body), out = [];
  for (const it of items) {
    if (it.type !== "paper" || links.has(it.id) || dismissed.has(it.id) || !(String(it.firstSeen || "") > since)) continue;
    const shared = subOf(it.id).find((s) => subs.has(s));
    if (shared) { out.push({ id: it.id, why: "shares the sub-area " + shared }); continue; }
    const m = matchScore(nt, it.id, idx);
    if (m.score >= SUGGEST_AT) out.push({ id: it.id, why: "shares the words " + m.words.slice(0, 3).join(", ") });
  }
  return out;
}
const MATCH = { idx: null, items: null };
function matchData() {
  if (!MATCH.idx) {
    MATCH.items = ITEMS.map((n) => ({ id: n.id, type: n.type, title: n.title, subareas: n.subareas || [], firstSeen: n.firstSeen }));
    MATCH.idx = buildIndex(MATCH.items);
  }
  return MATCH;
}
function subOfItem(id) { const n = byId.get(id); return (n && n.subareas) || []; }
/* For the editor's check rows: what is new for the open note, with titles. */
function noteEvidence(id, draft) {
  const note = id ? NT.notes.get(id) : null;
  if (!note) return [];
  const m = matchData();
  return newEvidence({ ...note, ...draft, updated: note.updated }, m.items, m.idx, subOfItem)
    .map((e) => ({ ...e, title: (byId.get(e.id) || {}).title || e.id }));
}
function suggestionsFor(draft) {
  if (!(draft.title + draft.body).trim()) return [];
  return suggestPapers(draft, matchData().idx, new Set(draft.links));
}
/* Every note's new evidence, for the satellites' ring and the notes list. */
function computeAllEvidence() {
  const m = matchData();
  NT.evidence = new Map();
  for (const n of NT.notes.values()) if (!n.archived) {
    const ev = newEvidence(n, m.items, m.idx, subOfItem);
    if (ev.length) NT.evidence.set(n.id, ev);
  }
}
NT.onChange.unshift(computeAllEvidence);   /* before the redraws that read it */
