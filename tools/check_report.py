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
  --json         Machine-readable output.

Errors fail the check (exit 1); warnings are reported but do not.

The style table below mirrors 04-citation-rules.md; tests/test_check_report.py
parses that file and fails if the two disagree.

Stdlib only.
"""

import argparse
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


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("target")
    parser.add_argument("--style")
    parser.add_argument("--compile", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    target = Path(args.target)
    if not target.exists():
        print(json.dumps({"error": f"{target} not found", "code": "NOT_FOUND"}), file=sys.stderr)
        return 1
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
