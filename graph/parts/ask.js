/* The Ask tab: plain questions turned into exact filters and steps. No AI.

   A question is read against a fixed set of patterns over what the data holds, and
   becomes the same steps a person could take by hand, so the same question always
   gives the same answer, and the answer says how it was reached. A question the
   patterns do not cover says so, rather than guessing. */

function parseQuestion(q, ctx) {
  const raw = String(q || ""), text = raw.toLowerCase().replace(/[?!.,;:]/g, " ").replace(/\s+/g, " ").trim();
  const items = ctx.items, byIdLocal = new Map(items.map((it) => [it.id, it]));
  const citesOf = ctx.citesOf || ((it) => it.citesOut || []);
  const STOP = new Set(["the", "and", "for", "paper", "papers", "what", "does", "cite", "cites", "from", "same", "lab",
    "with", "that", "this", "group", "research"]);
  const words = (s) => (String(s).toLowerCase().match(/[a-z0-9]+/g) || []).filter((w) => w.length >= 3 && !STOP.has(w));
  /* The item whose title shares the most words with PHRASE, or why there is none. */
  const titleMatch = (phrase) => {
    const want = new Set(words(phrase));
    let best = [], top = 0;
    for (const it of items) {
      const n = [...new Set(words(it.title))].filter((w) => want.has(w)).length;
      if (n > top) { top = n; best = [it]; } else if (n === top && n > 0) best.push(it);
    }
    if (!top) return { error: "No title in your library shares a word with \"" + phrase.trim() + "\"." };
    if (best.length > 1) return { error: "Several titles match: " + best.slice(0, 3).map((it) => "\"" + it.title + "\"").join(", ") + ". Add a word or two." };
    return { item: best[0] };
  };
  const finish = (ids, steps) => {
    const shown = ids.filter((id) => byIdLocal.has(id) && passes(byIdLocal.get(id)));
    const hidden = ids.length - shown.length;
    if (hidden) steps.push(hidden + " more " + (hidden === 1 ? "is" : "are") + " hidden by the current filters");
    return { ok: true, ids: shown, steps };
  };
  const examples = ctx.examples || askExamples(ctx);
  const nope = (message) => {
    const want = new Set(words(text));
    const closest = examples.slice().sort((a, b) => words(b).filter((w) => want.has(w)).length - words(a).filter((w) => want.has(w)).length)[0] || examples[0];
    return { ok: false, message, closest };
  };
  let m;
  if ((m = text.match(/same (?:lab|research group) as (.+)$/))) {
    const t = titleMatch(m[1]);
    if (t.error) return nope(t.error);
    const lab = ctx.labs.find((l) => l.id === t.item.primaryLab);
    if (!lab) return nope("\"" + t.item.title + "\" has no research group in your library.");
    return finish(lab.papers.slice(), ["Paper: " + t.item.title, "Its research group: " + (lab.name || lab.id)]);
  }
  if ((m = text.match(/^what does (.+) cite$/))) {
    const t = titleMatch(m[1]);
    if (t.error) return nope(t.error);
    return finish(citesOf(t.item).slice(), ["Paper: " + t.item.title, "The papers in your library it cites"]);
  }
  if ((m = text.match(/^(?:what|which papers?) cites? (.+)$/))) {
    const t = titleMatch(m[1]);
    if (t.error) return nope(t.error);
    return finish(items.filter((it) => citesOf(it).includes(t.item.id)).map((it) => it.id), ["Paper: " + t.item.title, "The papers in your library that cite it"]);
  }
  if (/\bthin sub-?areas?\b/.test(text)) {
    const thin = ctx.gaps.filter((g) => g.kind === "thin");
    const keys = new Set(thin.map((g) => g.interest + "::" + g.subarea));
    return finish(items.filter((it) => (it.subareas || []).some((s) => keys.has(it.interest + "::" + s))).map((it) => it.id),
      ["Sub-areas the gap rules call thin: " + (thin.map((g) => g.subarea).join(", ") || "none")]);
  }
  if (/\bscored but (?:never|not) used in (?:a |any )?reports?\b/.test(text)) {
    return finish(items.filter((it) => it.statusLabel === "Scored, not yet used in a report").map((it) => it.id), ["Status: scored, not yet used in a report"]);
  }
  /* Everything else is read as filter words. */
  const steps = [], tests = [];
  let rest = text;
  if (/\bwith(?:out| no) (?:a )?defen[cs]es?\b/.test(rest)) {
    rest = rest.replace(/\bwith(?:out| no) (?:a )?defen[cs]es?\b/, " ");
    const defended = new Set(items.filter((it) => it.contribution === "defence").flatMap((it) => (it.subareas || []).map((s) => it.interest + "::" + s)));
    tests.push((it) => it.contribution === "attack" && !(it.subareas || []).some((s) => defended.has(it.interest + "::" + s)));
    steps.push("Only sub-areas with no defence paper");
  }
  if (/\bnew\b/.test(rest)) { tests.push((it) => isNew(it)); steps.push("New since your last search (" + ctx.since + ")"); }
  if (/\bweb(?: sources?| pages?)?\b/.test(rest)) { tests.push((it) => it.type === "web"); steps.push("Only web sources"); }
  else if (/\bpapers?\b/.test(rest)) { tests.push((it) => it.type === "paper"); steps.push("Only papers"); }
  const contributions = [["attack", /\battacks?\b/], ["defence", /\bdefen[cs]es?\b/], ["survey", /\bsurveys?\b/],
    ["measurement", /\bmeasurements?\b/], ["user-study", /\buser stud(?:y|ies)\b/], ["tool", /\btools?\b/], ["position", /\bposition\b/]];
  for (const [c, re] of contributions) if (re.test(rest)) { tests.push((it) => it.contribution === c); steps.push("Contribution: " + c); }
  if ((m = rest.match(/\bbetween (\d{4}) and (\d{4})\b/))) { const a = +m[1], b = +m[2]; tests.push((it) => it.year != null && it.year >= a && it.year <= b); steps.push("Year: " + a + " to " + b); }
  else {
    if ((m = rest.match(/\b(?:since|from|after) (\d{4})\b/))) { const a = +m[1]; tests.push((it) => it.year != null && it.year >= a); steps.push("Year: " + a + " or later"); }
    if ((m = rest.match(/\bbefore (\d{4})\b/))) { const b = +m[1]; tests.push((it) => it.year != null && it.year < b); steps.push("Year: before " + b); }
    if ((m = rest.match(/\bin (\d{4})\b/))) { const y = +m[1]; tests.push((it) => it.year === y); steps.push("Year: " + y); }
  }
  /* An interest is named by a word that belongs to exactly one interest's name: a word of
     four letters or more, or an acronym written in capitals (XR, AI). */
  const names = ctx.interests.map((i) => i.name);
  const tokens = names.map((n) => (n.match(/[A-Za-z0-9]+/g) || []).map((w) => w.toLowerCase()));
  for (const w of raw.match(/[A-Za-z0-9]+/g) || []) {
    if (!(w.length >= 4 || (w.length >= 2 && w === w.toUpperCase() && /[A-Z]/.test(w)))) continue;
    const hits = names.filter((n, k) => tokens[k].includes(w.toLowerCase()));
    if (hits.length === 1 && !steps.includes("Interest: " + hits[0])) { const name = hits[0]; tests.push((it) => it.interest === name); steps.push("Interest: " + name); }
  }
  if (!tests.length) return nope("That question is not one the map can answer exactly.");
  /* Every word must be one the patterns read: dropping an unknown word would quietly
     answer a different, broader question. */
  const KNOWN = new Set(["a", "an", "the", "of", "in", "on", "about", "with", "without", "no", "all", "any", "my", "me", "show",
    "list", "find", "which", "what", "are", "is", "there", "that", "and", "or", "since", "from", "after", "before", "between",
    "last", "search", "searches", "items", "item", "sources", "source", "pages", "page", "web", "paper", "papers", "new",
    "defence", "defense", "defences", "defenses", "attack", "attacks", "survey", "surveys", "measurement", "measurements",
    "user", "study", "studies", "tool", "tools", "position", "to"]);
  const named = new Set(steps.filter((x) => x.startsWith("Interest: ")).flatMap((x) => (x.slice(10).match(/[A-Za-z0-9]+/g) || []).map((w) => w.toLowerCase())));
  const unread = (text.match(/[a-z0-9-]+/g) || []).filter((w) => !KNOWN.has(w) && !named.has(w) && !/^\d{4}$/.test(w));
  if (unread.length) return nope("The map could not read: " + unread.join(", ") + ".");
  return finish(items.filter((it) => tests.every((t) => t(it))).map((it) => it.id), steps);
}
/* Example questions, written from the library itself, and each one checked against the
   patterns: an example that does not parse is never offered. */
function askExamples(ctx) {
  const names = ctx.interests.map((i) => i.name);
  const tokens = names.map((n) => (n.match(/[A-Za-z0-9]+/g) || []).map((w) => w.toLowerCase()));
  /* A word that names exactly one interest, by the parser's own rule. */
  let interestWord = "";
  for (const n of names) {
    for (const w of n.match(/[A-Za-z0-9]+/g) || []) {
      const usable = w.length >= 4 || (w.length >= 2 && w === w.toUpperCase() && /[A-Z]/.test(w));
      if (usable && tokens.filter((t) => t.includes(w.toLowerCase())).length === 1) { interestWord = w; break; }
    }
    if (interestWord) break;
  }
  const years = ctx.items.map((it) => it.year).filter((y) => y != null);
  const recent = years.length ? Math.max(...years) - 2 : null;
  const short = (t) => (String(t).match(/[A-Za-z0-9]+/g) || []).filter((w) => w.length >= 4).slice(0, 3).join(" ");
  const citesOf = ctx.citesOf || ((it) => it.citesOut || []);
  const cited = new Map();
  for (const it of ctx.items) for (const id of citesOf(it)) cited.set(id, (cited.get(id) || 0) + 1);
  const generic = ["thin sub-areas", "new since my last search", "scored but never used in a report"];
  const check = { ...ctx, examples: generic };
  const answers = (q) => parseQuestion(q, check).ok;
  const first = (candidates) => candidates.find(answers);
  const out = [];
  const attack = first(["attack papers" + (interestWord ? " in " + interestWord : "") + (recent ? " since " + recent : "") + " with no defence",
    "attack papers" + (recent ? " since " + recent : "")]);
  if (attack) out.push(attack);
  const lab = first(ctx.items.filter((it) => it.primaryLab && ctx.labs.some((l) => l.id === it.primaryLab && l.papers.length > 1))
    .slice(0, 20).map((it) => "papers from the same lab as " + short(it.title)));
  if (lab) out.push(lab);
  const cites = first([...cited.entries()].sort((a, b) => b[1] - a[1]).slice(0, 10)
    .map(([id]) => ctx.items.find((it) => it.id === id)).filter(Boolean).map((it) => "what cites " + short(it.title) + "?"));
  if (cites) out.push(cites);
  return out.concat(generic.filter(answers));
}
const ASK = { q: "", result: null };
let ASK_CITES = null;
function askContext() {
  if (!ASK_CITES) {
    ASK_CITES = new Map();
    for (const e of D.edges) if (e.type === "cites") { if (!ASK_CITES.has(e.source)) ASK_CITES.set(e.source, []); ASK_CITES.get(e.source).push(e.target); }
  }
  return { items: ITEMS, interests: D.interests, labs: D.labs, gaps: D.gaps, since: S.since, citesOf: (it) => ASK_CITES.get(it.id) || [] };
}
function runAsk(q) {
  ASK.q = q;
  ASK.result = q.trim() ? parseQuestion(q, askContext()) : null;
  renderAsk();
}
function renderAsk() {
  const ctx = askContext(), examples = askExamples(ctx), r = ASK.result;
  const input = el("input", { type: "search", class: "ask", value: ASK.q, placeholder: examples[0], "aria-label": "Ask about your library",
    on: { keydown: (e) => { if (e.key === "Enter") runAsk(e.target.value); } } });
  const out = [];
  if (r && r.ok) {
    out.push(el("p", {}, el("strong", {}, plural(r.ids.length, "item")), " answer \"", ASK.q, "\":"),
      el("ol", { class: "small" }, ...r.steps.map((s) => el("li", {}, s))),
      el("div", { class: "actions" },
        el("button", { on: { click: () => { highlightSet(r.ids, ASK.q); setTab("overview", true); } } }, "Show on the map"),
        el("button", { on: { click: () => { setTab("explore", true); openList(r.ids, "Ask: " + ASK.q); } } }, "Open as a list"),
        el("button", { on: { click: () => runAsk("") } }, "Clear")));
  } else if (r) {
    out.push(el("p", { class: "warn", style: "border-left:3px solid var(--gap);padding-left:8px" }, r.message),
      el("div", { class: "actions" }, "Try: ", el("button", { class: "linkbtn", on: { click: () => runAsk(r.closest) } }, r.closest)),
      el("div", { class: "actions" }, el("button", { class: "linkbtn", on: { click: () => setTab("explore", true) } }, "Or filter by hand in Explore")));
  }
  $("#tab-ask").replaceChildren(el("h2", {}, "Ask"),
    el("p", { class: "lede" }, "Questions become the same filters and steps you could do by hand, so every answer is exact and repeatable. No AI is used."),
    el("div", { class: "actions", style: "max-width:760px" }, input, el("button", { on: { click: () => runAsk(input.value) } }, "Ask")),
    el("p", { class: "small muted", style: "margin:12px 0 4px" }, "Try one of these:"),
    el("div", { class: "actions" }, ...examples.map((x) => el("button", { on: { click: () => runAsk(x) } }, x))),
    el("div", { style: "max-width:760px;margin-top:10px" }, ...out));
}
TAB_HOOKS.ask = renderAsk;
ON_FILTERS.push(() => { if (S.tab === "ask" && ASK.q) runAsk(ASK.q); });
