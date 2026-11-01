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

/* ---------- the editor ---------- */
const ED = { open: false, id: null, draft: null, version: null, state: "saved", msg: "", timer: null, conflict: null,
  addingPrompt: false, promptError: "", els: null };
MIN_CARDS.push("noteeditor");
function editorOpen() { return ED.open; }
function blankDraft(links) { return { title: "", body: "", links: links.slice(), in_report: null, dismissed: [] }; }
function draftOf(note) {
  return { title: note.title || "", body: note.body || "", links: (note.links || []).slice(), in_report: note.in_report || null,
    dismissed: (note.dismissed || []).slice() };
}
function openEditor(id, links) {
  if (ED.open && NT.dirty && ED.id !== id && !window.confirm("Your note has unsaved changes. Open another anyway?")) return;
  const note = id ? NT.notes.get(id) : null;
  ED.open = true; ED.id = note ? id : null; ED.version = note ? note.version : null;
  ED.draft = note ? draftOf(note) : blankDraft(links || []);
  ED.conflict = null; ED.msg = ""; NT.dirty = !note && (links || []).length > 0;
  ED.state = NT.serving ? (NT.dirty ? "unsaved" : "saved") : "readonly";
  S.note = ED.id; writeHash(true);
  if (S.min.cards.noteeditor) { S.min.cards.noteeditor = false; applyMin(true); }
  renderEditor();
  if (typeof renderSelCard === "function") renderSelCard();
  globeRequestDraw();
}
function closeEditor() {
  if (NT.dirty && !window.confirm("Your note has unsaved changes. Close it anyway? Export keeps a copy.")) return;
  ED.open = false; ED.id = null; NT.dirty = false; S.note = null; writeHash(true);
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
  if (!ED.draft.title.trim()) { ED.state = "unsaved"; ED.msg = "Give the note a title to save it."; renderEditorParts(); return; }
  const sent = JSON.stringify(ED.draft), before = ED.id ? noteOrbit(NT.notes.get(ED.id), noteHas) : null;
  ED.state = "saving"; ED.msg = ""; renderEditorParts();
  const r = await noteApi("/api/note", { note: { ...ED.draft, id: ED.id }, version: ED.version, keepUpdated: !!(opts && opts.keepUpdated) });
  if (r.status === 200) {
    const note = r.data.note;
    NT.notes.set(note.id, note);
    ED.id = note.id; ED.version = r.data.version; S.note = note.id; writeHash(false);
    NT.dirty = JSON.stringify(ED.draft) !== sent;   /* typed on while it saved */
    ED.state = NT.dirty ? "unsaved" : "saved";
    if (NT.dirty) { clearTimeout(ED.timer); ED.timer = setTimeout(() => saveDraft(), 1500); }
    satMove(note.id, before || "outer", noteOrbit(note, noteHas));
    notesChanged();
  } else if (r.status === 409 && r.data.conflict) {
    ED.state = "conflict"; ED.conflict = { disk: r.data.disk, diskVersion: r.data.diskVersion };
  } else {
    ED.state = "failed"; ED.msg = (r.data && r.data.error) || "The helper refused the save.";
  }
  renderEditorParts();
}
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
      el("button", { on: { click: () => { ED.draft = draftOf(disk); ED.version = ED.conflict.diskVersion; ED.conflict = null; NT.dirty = false; ED.state = "saved"; renderEditor(); } } }, "Use the file's")));
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
  E.checks.replaceChildren(...(checks.length ? [el("div", { class: "note", style: "margin-top:8px" }, "Checks")] : []), ...checks.map((c) => el("div", { class: "ed-check" },
    el("div", {}, c.text), el("div", { class: "note muted" }, "Why: " + c.basis),
    c.kind === "newevidence" ? el("div", { class: "actions" },
      el("button", { disabled: !saving, on: { click: () => { d.links.push(c.id); E.body.focus(); markDirty(); renderEditorParts(); } } }, "Link it"),
      el("button", { disabled: !saving, on: { click: () => { d.dismissed.push(c.id); saveDraft({ keepUpdated: true }); } } }, "Dismiss")) : null)));
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
