#!/usr/bin/env python3
"""The report verification checklist, as code.

Run from anywhere:  python3 tools/check_report.py <report-dir-or-.tex> [options]

CLAUDE.md's Verification Checklist used to be checked only by reading the
compiled PDF. Most defects found that way were mechanical - a required section
missing, `note` used where `evidencebasis` belongs, a bibliography style that
no longer matched the profile, a `[H]` float without the float package. This
script catches that class without anyone having to notice it. It does not
judge prose, and does not replace the reviewer agent or the PDF read.

Options:
  --style NAME   Citation style to check against (IEEE, APA, Harvard, Plain,
                 Author-year). Default: the profile's `Citation style`.
  --compile      Also build a copy in a temp directory with the 4-pass
                 pdflatex -> bibtex -> pdflatex -> pdflatex sequence and check
                 the logs. Works on reports whose build artifacts were already
                 cleaned up, and never leaves files in the report directory.
  --claims       Instead of linting, list every sentence that makes an
                 exclusive, ordinal or counting claim about the corpus ("the
                 only defense", "the first source", "every figure", "six
                 defenses in this corpus"). A source added later can make such
                 a sentence false without touching it, so /update sends the
                 hits to its reviewer. Review prompts, not findings: false
                 positives are expected and the exit code is always 0.
  --json         Machine-readable output.

Errors fail the check (exit 1); warnings are reported but do not.

The style table below mirrors 04-citation-rules.md; tests/test_check_report.py
parses that file and fails if the two disagree.

Stdlib only.
"""

import argparse
import bisect
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROFILE = ROOT / ".claude" / "skills" / "research-assistant" / "01-researcher-profile.md"

# Profile value -> (\bibliographystyle, numbered?). Mirrors 04-citation-rules.md.
STYLES = {
    "IEEE": ("ieeetr", True),
    "APA": ("apalike", False),
    "Harvard": ("agsm", False),
    "Plain/numbered": ("plain", True),
    "Author-year": ("plainnat", False),
}
ALIASES = {"plain": "Plain/numbered", "numbered": "Plain/numbered", "authoryear": "Author-year"}

# A note that reads like evidence-basis commentary belongs in `evidencebasis`
# (04-citation-rules.md): every stock .bst prints `note` inline.
NOTE_COMMENTARY = re.compile(r"evidence.basis|abstract.only|full.text|disclosure:|"
                             r"self-evaluating|read (directly|via)", re.I)
NOTE_MAX = 100
OVERFULL_ERROR_PT = 3.0  # below this an overfull box is invisible in practice

# agsm.bst prints each URL as \harvardurl{...}, which natbib defines as plain
# \textit{#1}: an `_` in any URL is "Missing $ inserted" and the build fails.
# The override must take no argument, so \url reads the URL itself with its own
# catcodes - a [1]-argument \url{#1} fixes `_` but still fails on `%` and `#`.
# 04-citation-rules.md quotes this line; tests/test_check_report.py keeps the two
# in step.
HARVARD_URL_FIX = r"\renewcommand{\harvardurl}{\textbf{URL:} \url}"
# agsm separates author and year with a space, "(Liu et al. 2023)"; UK Harvard
# guides (Cite Them Right among them) put a comma there, "(Liu et al., 2023)", and
# a semicolon between citations, which natbib applies once this line is set.
# Quoted in 03-report-templates.md and 04-citation-rules.md.
HARVARD_CITE_STYLE = r"\setcitestyle{aysep={,}}"
HARVARD_COMMA = re.compile(r"\\setcitestyle\s*\{[^}\n]*aysep\s*=\s*\{,\}")
HARVARDURL_OVERRIDE = re.compile(r"\\renewcommand\s*\{?\\harvardurl\}?\s*(\[\d\])?\s*\{([^\n]*)\}")

DATE_PARAGRAPH = re.compile(r"\\paragraph\{\d{4}-\d{2}-\d{2}\}")


class Findings:
    """Errors and warnings. A finding may carry the list of keys it applies to,
    so one problem across 28 bibliography entries is one line, not 28."""

    SHOW_KEYS = 6

    def __init__(self):
        self.errors: list[tuple[str, list[str]]] = []
        self.warnings: list[tuple[str, list[str]]] = []

    def error(self, area: str, msg: str, keys: list[str] | None = None):
        self.errors.append((f"{area}: {msg}", keys or []))

    def warn(self, area: str, msg: str, keys: list[str] | None = None):
        self.warnings.append((f"{area}: {msg}", keys or []))

    @staticmethod
    def render(item, full: bool) -> str:
        msg, keys = item
        if not keys:
            return msg
        shown = keys if full else keys[:Findings.SHOW_KEYS]
        more = "" if full or len(keys) <= Findings.SHOW_KEYS else \
            f" +{len(keys) - Findings.SHOW_KEYS} more (--json for all)"
        return f"{msg} [{len(keys)}]: {', '.join(shown)}{more}"


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def strip_comments(tex: str) -> str:
    return "\n".join(re.sub(r"(?<!\\)%.*$", "", line) for line in tex.splitlines())


def _balanced(text: str, start: int) -> tuple[str, int]:
    """Contents of the brace group opening at text[start] == '{'."""
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1:i], i + 1
    raise ValueError("unbalanced braces")


def parse_bib(text: str) -> tuple[dict[str, dict[str, str]], list[str]]:
    """{key: {field: value}} for every entry, plus parse problems."""
    entries, problems = {}, []
    for match in re.finditer(r"@(\w+)\s*\{", text):
        kind = match.group(1).lower()
        if kind in ("comment", "string", "preamble"):
            continue
        try:
            body, _ = _balanced(text, match.end() - 1)
        except ValueError:
            problems.append(f"unbalanced braces in @{kind} entry")
            continue
        key, _, rest = body.partition(",")
        fields, pos = {}, 0
        for field in re.finditer(r"(\w+)\s*=\s*", rest):
            if field.start() < pos:
                continue
            value_start = field.end()
            if value_start < len(rest) and rest[value_start] == "{":
                try:
                    value, pos = _balanced(rest, value_start)
                except ValueError:
                    problems.append(f"{key.strip()}: unbalanced braces in field {field.group(1)}")
                    break
            elif value_start < len(rest) and rest[value_start] == '"':
                end = rest.find('"', value_start + 1)
                value, pos = rest[value_start + 1:end], end + 1
            else:
                bare = re.match(r"[^,\n]*", rest[value_start:]).group(0)
                value, pos = bare.strip(), value_start + len(bare)
            fields[field.group(1).lower()] = " ".join(value.split())
        entries[key.strip()] = fields
    return entries, problems


def cited_keys(tex: str) -> tuple[set[str], bool]:
    keys, nocite_all = set(), False
    for match in re.finditer(r"\\(no)?cite[a-zA-Z]*\*?\s*(?:\[[^\]]*\]\s*){0,2}\{([^}]*)\}", tex):
        for key in match.group(2).split(","):
            key = key.strip()
            if key == "*" and match.group(1):
                nocite_all = True
            elif key:
                keys.add(key)
    return keys, nocite_all


def profile_style() -> str | None:
    if not PROFILE.exists():
        return None
    match = re.search(r"\*\*Citation style:\*\*\s*([^\s(`]+)", PROFILE.read_text(encoding="utf-8"))
    return match.group(1) if match else None


def canonical_style(name: str) -> str | None:
    for style in STYLES:
        if name.lower() == style.lower():
            return style
    return ALIASES.get(name.lower().replace("-", ""))


def locate(target: Path) -> tuple[Path, Path | None, list[str]]:
    """(tex, bib) for a report directory or a .tex path."""
    if target.is_file():
        tex = target
    else:
        candidates = [target / "report.tex"] if (target / "report.tex").exists() \
            else sorted(target.glob("*.tex"))
        if len(candidates) != 1:
            raise SystemExit(json.dumps({"error": f"expected one .tex in {target}, found "
                                         f"{len(candidates)}", "code": "BAD_ARG"}))
        tex = candidates[0]
    match = re.search(r"\\bibliography\{([^}]+)\}", strip_comments(tex.read_text(encoding="utf-8")))
    bib = tex.parent / (match.group(1).split(",")[0].strip() + ".bib") if match else None
    return tex, bib, []


# ---------------------------------------------------------------------------
# Static checks
# ---------------------------------------------------------------------------

def check_structure(tex: str, f: Findings):
    sections = [t.strip() for t in re.findall(r"\\section\*?\{([^}]*)\}", tex)]

    def has(word):
        return any(word.lower() in s.lower() for s in sections)

    if not re.search(r"search scope", tex, re.I):
        f.error("structure", "no search-scope note (03-report-templates.md, Section 1)")
    elif not re.search(r"\b(core|supporting|peripheral)\b", tex.split("\\begin{abstract}")[0], re.I):
        f.warn("structure", "search-scope note does not state the Core/Supporting/Peripheral "
                            "composition of the sources")
    if "\\begin{abstract}" not in tex:
        f.error("structure", "no abstract")
    if not has("Revision History"):
        f.error("structure", "no Revision History section - seeded at first synthesis "
                             "(03-report-templates.md, Section 2b)")
    elif not DATE_PARAGRAPH.search(tex):
        f.error("structure", "Revision History has no dated \\paragraph{YYYY-MM-DD} entry")
    if not has("Technical Findings"):
        f.warn("structure", "no Technical Findings (Plain Language) section - standard unless "
                            "the topic is already non-technical")
    if not has("Open Questions"):
        f.error("structure", "no Open Questions section")
    if not has("Evidence Basis"):
        f.error("structure", "no Evidence Basis section (03-report-templates.md, Section 8)")
    if not re.search(r"\\bibliography\{", tex):
        f.error("structure", "no \\bibliography{...}")


def check_style(tex: str, style: str | None, f: Findings):
    used = re.search(r"\\bibliographystyle\{([^}]+)\}", tex)
    natbib = re.search(r"\\usepackage(?:\[([^\]]*)\])?\{natbib\}", tex)
    if not natbib:
        f.error("style", "natbib is not loaded - every report needs it (04-citation-rules.md)")
    if not used:
        f.error("style", "no \\bibliographystyle")
        return
    bst = used.group(1).strip()
    known = {b: (name, numbered) for name, (b, numbered) in STYLES.items()}

    if style is None:
        f.warn("style", "no citation style in profile and no --style given; only "
                        "internal consistency was checked")
    else:
        expected, _ = STYLES[style]
        if bst != expected:
            f.error("style", f"\\bibliographystyle{{{bst}}} but the citation style is {style}, "
                             f"which is \\bibliographystyle{{{expected}}} (04-citation-rules.md)")
    if bst not in known:
        f.warn("style", f"\\bibliographystyle{{{bst}}} is not one of the supported styles")
        return
    numbered = known[bst][1]
    if natbib:
        options = [o.strip() for o in (natbib.group(1) or "").split(",")]
        if numbered and "numbers" not in options:
            f.error("style", f"{bst} is a numbered style - natbib needs the [numbers] option "
                             "or the compile fails")
        if not numbered and "numbers" in options:
            f.error("style", f"{bst} is author-year - natbib must not have [numbers]")
    if numbered and re.search(r"\\citet\b", tex):
        f.error("style", f"\\citet with numbered style {bst} renders as (author?) - write the "
                         "author in prose and use \\citep")
    if bst == "agsm":
        check_harvardurl(tex, natbib, f)
        if not HARVARD_COMMA.search(tex):
            f.warn("style", "agsm prints citations as (Liu et al. 2023); UK Harvard guides want "
                            f"(Liu et al., 2023) - add {HARVARD_CITE_STYLE} after the "
                            "\\harvardurl override (04-citation-rules.md)")


def check_harvardurl(tex: str, natbib, f: Findings):
    """agsm needs \\harvardurl redefined to use \\url (see HARVARD_URL_FIX)."""
    fix = f"add {HARVARD_URL_FIX} right after \\usepackage{{natbib}} (04-citation-rules.md)"
    override = HARVARDURL_OVERRIDE.search(tex)
    if not override or "\\url" not in override.group(2):
        f.error("style", "agsm prints URLs with natbib's \\harvardurl, which breaks the build on "
                         f"any URL containing _ % or # - {fix}")
        return
    if natbib and override.start() < natbib.start():
        f.error("style", "the \\harvardurl override comes before \\usepackage{natbib}, which "
                         f"defines it - {fix}")
    if not re.search(r"\\usepackage(?:\[[^\]]*\])?\{[^}]*\b(hyperref|url)\b[^}]*\}", tex):
        f.error("style", "the \\harvardurl override uses \\url, but neither hyperref nor url "
                         "is loaded")
    if override.group(1):
        f.warn("style", "\\harvardurl takes the URL as an argument, which fixes _ but still "
                        f"fails on % and # - use {HARVARD_URL_FIX}")


def check_floats(tex: str, f: Findings):
    uses_h = re.search(r"\\begin\{(table|figure)\*?\}\[[^\]]*H[^\]]*\]", tex)
    loads_float = re.search(r"\\usepackage(?:\[[^\]]*\])?\{[^}]*\bfloat\b[^}]*\}", tex)
    if uses_h and not loads_float:
        f.error("floats", "[H] placement without \\usepackage{float} - fails to compile")


def unprotected_caps(title: str) -> list[str]:
    """Words in a title that BibTeX will lower-case but are acronyms or names.

    Every supported .bst sentence-cases titles, so LLM renders as "Llm" and
    AgentDojo as "Agentdojo" unless braced. Only text outside braces is at
    risk. A hyphenated Title-Case compound (Rule-Based) is ordinary prose that
    sentence case is meant to lower, so it is not flagged.
    """
    plain, depth = [], 0
    for ch in title:
        if ch == "{":
            depth += 1
            plain.append(" ")
        elif ch == "}":
            depth = max(depth - 1, 0)
            plain.append(" ")
        else:
            plain.append(ch if depth == 0 else " ")
    flagged = []
    for word in re.findall(r"[A-Za-z0-9][A-Za-z0-9.\-]*", "".join(plain)):
        parts = [p for p in word.split("-") if p]
        if any((len(p) >= 2 and p.isupper()) or any(c.isupper() for c in p[1:])
               for p in parts):
            flagged.append(word)
    return flagged


def check_bib(tex: str, bib_path: Path | None, f: Findings):
    if bib_path is None:
        return
    if not bib_path.exists():
        f.error("bib", f"{bib_path.name} not found")
        return
    entries, problems = parse_bib(bib_path.read_text(encoding="utf-8"))
    for problem in problems:
        f.error("bib", problem)
    no_basis = [k for k, v in entries.items() if not v.get("evidencebasis")]
    commentary = [k for k, v in entries.items() if NOTE_COMMENTARY.search(v.get("note", ""))]
    long_notes = [k for k, v in entries.items()
                  if k not in commentary and len(v.get("note", "")) > NOTE_MAX]
    if no_basis:
        f.error("bib", "entries with no evidencebasis field (04-citation-rules.md)", no_basis)
    if commentary:
        f.error("bib", "note fields holding evidence-basis commentary, which prints inline in "
                       "the bibliography - move it to evidencebasis", commentary)
    if long_notes:
        f.warn("bib", f"note fields over {NOTE_MAX} characters - notes print inline, so "
                      "commentary belongs in evidencebasis", long_notes)
    lowered = [k for k, v in entries.items() if unprotected_caps(v.get("title", ""))]
    if lowered:
        f.warn("bib", "titles with acronyms or mixed-case names outside braces - every "
                      "supported style lower-cases title words, so LLM renders as \"Llm\"; "
                      "brace them, e.g. {LLM}, {AgentDojo} (04-citation-rules.md)", lowered)
    cited, nocite_all = cited_keys(tex)
    missing = sorted(cited - set(entries))
    if missing:
        f.error("citations", f"cited but not in {bib_path.name}", missing)
    unused = sorted(set(entries) - cited)
    if unused and not nocite_all:
        f.error("citations", f"in {bib_path.name} but never cited", unused)


# ---------------------------------------------------------------------------
# Compile check
# ---------------------------------------------------------------------------

def check_compile(tex_path: Path, f: Findings):
    for tool in ("pdflatex", "bibtex"):
        if not shutil.which(tool):
            f.error("compile", f"{tool} not found on PATH - see SETUP.md")
            return
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "build"
        shutil.copytree(tex_path.parent, work,
                        ignore=shutil.ignore_patterns("*.aux", "*.log", "*.bbl", "*.blg",
                                                      "*.out", "*.pdf", "*.md"))
        stem = tex_path.stem
        latex = ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", f"{stem}.tex"]
        steps = [latex, ["bibtex", stem], latex, latex]
        for step in steps:
            subprocess.run(step, cwd=work, capture_output=True, text=True)
        log = (work / f"{stem}.log").read_text(encoding="utf-8", errors="replace") \
            if (work / f"{stem}.log").exists() else ""
        blg = (work / f"{stem}.blg").read_text(encoding="utf-8", errors="replace") \
            if (work / f"{stem}.blg").exists() else ""

        if "couldn't open style file" in blg:
            style = re.search(r"couldn't open style file (\S+)", blg).group(1)
            hint = " - run: tlmgr --usermode install harvard (SETUP.md)" \
                if style.startswith("agsm") else ""
            f.error("compile", f"bibtex could not find {style}{hint}")
        for line in re.findall(r"^! .*$", log, re.M)[:5]:
            f.error("compile", f"pdflatex: {line[2:]}")
        if not (work / f"{stem}.pdf").exists() and not f.errors:
            f.error("compile", "no PDF produced")
        for cite in sorted(set(re.findall(r"Citation `([^']+)'[^\n]*undefined", log))):
            f.error("compile", f"citation {cite} undefined in the PDF (renders as ?)")
        for ref in sorted(set(re.findall(r"Reference `([^']+)'[^\n]*undefined", log))):
            f.error("compile", f"\\ref{{{ref}}} undefined in the PDF (renders as ??)")
        if re.search(r"Author undefined for citation", log):
            f.error("compile", "natbib could not find author data - \\citet with a numbered "
                               "style renders as (author?)")
        for amount, where in re.findall(r"Overfull \\hbox \(([\d.]+)pt too wide\) (.*)$", log, re.M):
            msg = f"overfull box {amount}pt {where.strip()}"
            (f.error if float(amount) > OVERFULL_ERROR_PT else f.warn)("compile", msg)
        # A float taller than the page runs off the bottom of it. An [H] float
        # logs an overfull \vbox "while \output is active"; any other placement
        # logs "Float too large for page". Long tables belong in longtable, which
        # breaks across pages (03-report-templates.md).
        tall = " - a float taller than the page; use longtable for long tables"
        for amount, where in re.findall(r"Overfull \\vbox \(([\d.]+)pt too high\) (.*)$", log, re.M):
            hint = tall if "\\output is active" in where else f" {where.strip()}"
            msg = f"overfull vbox {amount}pt too high, content runs off the page{hint}"
            (f.error if float(amount) > OVERFULL_ERROR_PT else f.warn)("compile", msg)
        for amount, line in re.findall(r"Float too large for page by ([\d.]+)pt(?: on input line (\d+))?",
                                       log):
            where = f" (input line {line})" if line else ""
            msg = f"float too large for page by {amount}pt{where}, content runs off the page{tall}"
            (f.error if float(amount) > OVERFULL_ERROR_PT else f.warn)("compile", msg)
        for line in re.findall(r"^Warning--(.*)$", blg, re.M)[:10]:
            f.warn("bibtex", line.strip())


# ---------------------------------------------------------------------------
# Corpus-claim scan (--claims)
# ---------------------------------------------------------------------------
# An /update merges new sources and fact-checks only the prose it changed. A
# sentence it never touched - "Spotlight-Guard is distinctive among the defenses
# in this corpus in reporting an adaptive evaluation" - is falsified all the same
# when a new source does what it says no source does. These patterns find the
# sentences whose truth depends on what the corpus contains. They over-match on
# purpose: each hit is a prompt for a reviewer, never an error.

_NUM = (r"(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
        r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|"
        r"(?:twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)"
        r"(?:-(?:one|two|three|four|five|six|seven|eight|nine))?)")
# Units a corpus is counted in. Deliberately not models, tools, datasets or
# figures: "four victim models" is a fact about one paper, not about the corpus.
_NOUN = (r"(?:sources?|papers?|stud(?:y|ies)|works?|defen[cs]es?|attacks?|benchmarks?|"
         r"evaluations?|surveys?|reviews?|approach(?:es)?|methods?|replications?)")
# A count above one names a plural, so "four attack types" is not "four attacks".
_PLURAL = (r"(?:sources|papers|studies|works|defen[cs]es|attacks|benchmarks|evaluations|"
           r"surveys|reviews|approaches|methods|replications)")
# What "every" quantifies over when the claim is about the corpus or the report's
# own figures - not "every tool call", which describes a mechanism.
_EVERY = rf"(?:{_NOUN}|figures?|numbers?|results?|claims?|entry|entries|one)"
_W = r"(?:[\w-]+\s+)"  # one intervening word ("three other defenses")

# A space in a pattern matches any whitespace: LaTeX source wraps phrases across lines.
CLAIM_PATTERNS = [re.compile(p.replace(" ", r"\s+"), re.I) for p in (
    # exclusive: "the only defense", "only one source" (and a sentence that opens
    # with "Only", found per sentence in scan_claims)
    rf"\bthe only\b|\bonly\s+(?:one|two|three|{_W}?{_NOUN})\b",
    r"\bsole(?:ly)?\b",
    r"\bunique(?:ly)?\b",
    r"\bdistinctive(?:ly)?\b",
    r"\bno other\b|\bany other\b|\bnone\b",
    rf"\bno\s+{_W}?{_NOUN}\b",
    r"\bunlike (?:any|all|every|the other)\b|\balone among\b",
    # ordinal and superlative: "the first source to", "the strongest defense"
    r"\b(?:the|is|was|were|are) (?:first|earliest|last|latest)\b|"
    r"\bfirst (?:to|in|among)\b",
    rf"\bthe (?:largest|smallest|strongest|weakest|best|highest|lowest|broadest|"
    rf"most\s+[\w-]+|least\s+[\w-]+)\s+{_W}?{_NOUN}\b",
    # universal: "every figure", "all four", "all the defenses"
    rf"\bevery\s+{_W}?{_EVERY}\b|\beach of the\b",
    rf"\ball\s+(?:of\s+)?(?:the\s+)?(?:{_NUM}\b|{_W}?{_NOUN}\b)",
    # counted: "six defenses in this corpus", "one of four", "most defenses"
    rf"\bone\s+(?:{_W})?{_NOUN}\b|\b{_NUM}\s+(?:{_W}){{0,2}}{_PLURAL}\b",
    r"\b(?:one|two|three|four|five|six|seven|eight|nine|ten)\s+of\s+(?:the\s+)?"
    rf"{_NUM}\b",
    rf"\b(?:most|many|few|several|majority|minority|handful)\s+(?:of\s+)?(?:the\s+)?"
    rf"(?:{_W})?{_NOUN}\b",
    # scoped to the corpus explicitly
    r"\b(?:this|the) corpus\b|\b(?:reviewed|surveyed|covered|included) here\b",
)]

# Command arguments that are never prose: masked so a key like zhan2024first or
# a URL cannot trigger a hit or end a sentence.
_NON_PROSE_ARG = re.compile(r"\\(?:no)?cite[a-zA-Z]*\*?\s*(?:\[[^\]]*\]\s*){0,2}\{[^}]*\}|"
                            r"\\(?:ref|eqref|autoref|cref|Cref|label|url|input|include|"
                            r"bibliography|bibliographystyle|usepackage|documentclass|"
                            r"begin|end)\*?(?:\[[^\]]*\])?\{[^}]*\}|"
                            r"\\href\{[^}]*\}|\\[a-zA-Z]+")
_ABBREVIATIONS = {"al", "e.g", "i.e", "etc", "vs", "cf", "fig", "figs", "sec", "secs",
                  "eq", "no", "nos", "approx", "resp", "et"}
# "Only RETA reports ..." - "only" opening a sentence, after any \textbf{ etc.
_BEFORE_OPENING_ONLY = re.compile(r"[\s{]*(?=only\b)", re.I)
_ONLY = re.compile(r"only\b", re.I)
_HEADING = re.compile(r"\\(?:sub)*section\*?\{([^}]*)\}|\\paragraph\*?\{([^}]*)\}")


def _spaces(text: str) -> str:
    return re.sub(r"[^\n]", " ", text)


def _blank(text: str, start: int, end: int) -> str:
    return text[:start] + _spaces(text[start:end]) + text[end:]


def _mask(tex: str) -> str:
    """tex with everything that is not body prose replaced by spaces, offsets kept."""
    begin = tex.find("\\begin{document}")
    masked = _blank(tex, 0, begin) if begin > 0 else tex
    # The Revision History is an append-only record of past states: a line saying
    # what an earlier version claimed is history, not a claim about the corpus.
    history = re.search(r"\\section\*?\{Revision History\}", masked)
    if history:
        rest = re.search(r"\\section\*?\{|\\bibliography\{|\\end\{document\}",
                         masked[history.end():])
        stop = history.end() + rest.start() if rest else len(masked)
        masked = _blank(masked, history.start(), stop)
    return _NON_PROSE_ARG.sub(lambda m: _spaces(m.group(0)), masked)


def _sentence_spans(tex: str, masked: str) -> list[tuple[int, int]]:
    """Split points: sentence-final punctuation before a capital or a command,
    blank lines, table cells and rows, and structural commands."""
    cuts = {0, len(tex)}
    for match in re.finditer(r"[.?!]['\")}]*", masked):
        if not re.match(r"\s+[A-Z\\]", tex[match.end():match.end() + 80]):
            continue
        word = re.search(r"([\w.]+)$", masked[max(match.start() - 20, 0):match.start()])
        word = word.group(1).lower() if word else ""
        if word in _ABBREVIATIONS or (len(word) == 1 and word.isalpha()):
            continue
        cuts.add(match.end())
    for match in re.finditer(r"\n[ \t]*\n|(?<!\\)&|\\\\", tex):
        cuts.update((match.start(), match.end()))
    for match in re.finditer(r"\\(?:item|caption)\b", tex):
        cuts.add(match.start())
    for match in _HEADING.finditer(tex):
        cuts.update((match.start(), match.end()))
    for match in re.finditer(r"\\(?:begin|end)\{[^}]*\}", tex):
        cuts.update((match.start(), match.end()))
    ordered = sorted(cuts)
    return list(zip(ordered, ordered[1:]))


def scan_claims(tex: str) -> list[dict]:
    """Sentences of the report body that make a claim about the corpus as a whole,
    in document order: {line, section, triggers, sentence}."""
    masked = _mask(tex)
    spans = _sentence_spans(tex, masked)
    starts = [s for s, _ in spans]
    hits: dict[int, list[re.Match]] = {}
    for pattern in CLAIM_PATTERNS:
        for match in pattern.finditer(masked):
            index = bisect.bisect_right(starts, match.start()) - 1
            hits.setdefault(index, []).append(match)
    for index, (start, end) in enumerate(spans):
        lead = _BEFORE_OPENING_ONLY.match(masked, start, end)
        if lead:
            hits.setdefault(index, []).append(_ONLY.match(masked, lead.end()))
    headings = [(m.start(), next(g for g in m.groups() if g is not None))
                for m in _HEADING.finditer(tex)]
    claims = []
    for index in sorted(hits):
        start, end = spans[index]
        if len(tex[start:end].split()) < 3:
            continue  # a table cell reading "None" is not a claim
        matches = sorted(hits[index], key=lambda m: m.start())
        triggers = list(dict.fromkeys(" ".join(m.group(0).lower().split()) for m in matches))
        section = next((title for pos, title in reversed(headings) if pos <= start), "")
        claims.append({"line": tex.count("\n", 0, matches[0].start()) + 1,
                       "section": " ".join(section.split()),
                       "triggers": triggers,
                       "sentence": " ".join(tex[start:end].split())})
    return claims

# ---------------------------------------------------------------------------

def run(target: Path, style_arg: str | None, compile_: bool) -> Findings:
    f = Findings()
    tex_path, bib_path, _ = locate(target)
    tex = strip_comments(tex_path.read_text(encoding="utf-8"))

    style_name = style_arg or profile_style()
    style = canonical_style(style_name) if style_name else None
    if style_name and style is None:
        f.error("style", f"unknown citation style {style_name!r} - one of: {', '.join(STYLES)}")

    check_structure(tex, f)
    check_style(tex, style, f)
    check_floats(tex, f)
    check_bib(tex, bib_path, f)
    if compile_:
        check_compile(tex_path, f)
    return f


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("target")
    parser.add_argument("--style")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--compile", action="store_true")
    mode.add_argument("--claims", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def print_claims(target: Path, as_json: bool) -> int:
    tex_path, _, _ = locate(target)
    claims = scan_claims(strip_comments(tex_path.read_text(encoding="utf-8")))
    if as_json:
        print(json.dumps({"target": str(target), "claims": claims}, indent=2))
        return 0
    print(f"CLAIMS  {target}  ({len(claims)} sentences with exclusive, ordinal or counting "
          "claims - review prompts, not errors)")
    for claim in claims:
        where = f"  {claim['section']}" if claim["section"] else ""
        print(f"  L{claim['line']}{where}  [{', '.join(claim['triggers'])}]")
        print(f"      {claim['sentence']}")
    return 0


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)

    target = Path(args.target)
    if not target.exists():
        print(json.dumps({"error": f"{target} not found", "code": "NOT_FOUND"}), file=sys.stderr)
        return 1
    if args.claims:
        return print_claims(target, args.json)
    f = run(target, args.style, args.compile)
    if args.json:
        print(json.dumps({"target": str(target),
                          "errors": [Findings.render(e, True) for e in f.errors],
                          "warnings": [Findings.render(w, True) for w in f.warnings]},
                         indent=2))
    else:
        verdict = "FAIL" if f.errors else "PASS"
        print(f"{verdict}  {target}  ({len(f.errors)} errors, {len(f.warnings)} warnings)")
        for item in f.errors:
            print(f"  ERROR  {Findings.render(item, False)}")
        for item in f.warnings:
            print(f"  warn   {Findings.render(item, False)}")
    return 1 if f.errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
