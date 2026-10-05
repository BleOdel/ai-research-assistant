#!/usr/bin/env python3
"""Generate a report's Evidence Basis section from its references.bib.

    python3 tools/evidence_table.py <report-dir|report.tex> [--write] [--json]

Prints the LaTeX section by default. --write puts it into report.tex in place of the
existing Evidence Basis section (from its heading to the next \\section,
\\bibliographystyle or \\bibliography), or before \\bibliographystyle when there is
none. The table is a transcription of each entry's `evidencebasis` field
(04-citation-rules.md), so the field is the thing to edit and this script the thing
to re-run - a hand-maintained table drifts from the .bib, which is how it was done
until a report's table and bibliography disagreed.

Each row comes from one field:
- Evidence Basis: "Full text" when the field starts with "Primary PDF", otherwise
  "Abstract", plus the route named after the first "via ".
- Disclosure: the label after "Disclosure:" (02-source-evaluation.md's labels).
- Caveat: the text after "Caveat:".
Missing parts render as "--". The caveat is copied verbatim, so an unescaped %, &,
# or _ in it is refused (it would comment out or split the table row) - the same
check check_report.py applies.

Exit status: 0 on success, 1 when the .bib or report cannot be used.
"""
import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_report import STYLES, copied_text, parse_bib, unescaped_specials  # noqa: E402
from state import DISCLOSURE  # noqa: E402

HEADING = re.compile(r"\\section\*?\{Evidence Basis\}")
SECTION_END = re.compile(r"\\section\*?\{|\\bibliographystyle\{|\\bibliography\{|\\end\{document\}")
NUMBERED_BST = {bst for bst, numbered in STYLES.values() if numbered}
COLUMNS = r"@{}" + "".join(r">{\raggedright\arraybackslash}p{%s}" % w
                            for w in ("3.3cm", "2.9cm", "2.1cm", "6.8cm")) + "@{}"
HEADER = r"\textbf{Source} & \textbf{Evidence Basis} & \textbf{Disclosure} & \textbf{Caveat} \\"


class TableError(Exception):
    def __init__(self, problems):
        super().__init__("; ".join(problems))
        self.problems = problems


def locate(target: Path) -> tuple[Path, Path]:
    tex = target / "report.tex" if target.is_dir() else target
    bib = tex.parent / "references.bib"
    missing = [p.name for p in (tex, bib) if not p.is_file()]
    if missing:
        raise TableError([f"{tex.parent}: no {' or '.join(missing)}"])
    return tex, bib


def plain(text: str) -> str:
    """Text without braces or LaTeX accent macros, for sorting and surnames."""
    text = re.sub(r"\\[`'^\"~=.uvHcdbtr]\s*\{?([A-Za-z])\}?", r"\1", text)
    text = text.replace("{", "").replace("}", "").replace("\\", "")
    return " ".join(text.split())


def surname(author: str) -> str:
    author = plain(author)
    return author.split(",")[0].strip() if "," in author else author.split()[-1]


def sort_key(key: str, fields: dict) -> tuple:
    first = (fields.get("author") or "").split(" and ")[0]
    name = unicodedata.normalize("NFKD", surname(first) if first else key)
    return ("".join(c for c in name if not unicodedata.combining(c)).lower(),
            fields.get("year", ""), key)


def source_cell(key: str, fields: dict, numbered: bool) -> str:
    if not numbered:
        return rf"\citet{{{key}}}"
    authors = (fields.get("author") or "").split(" and ")
    name = surname(authors[0]) if authors[0] else key
    return name + (" et al." if len(authors) > 1 else "") + rf"~\citep{{{key}}}"


def row(key: str, fields: dict, numbered: bool) -> tuple[str, list[str]]:
    basis = fields.get("evidencebasis", "")
    problems = []
    kind = "Full text" if basis.lstrip().startswith("Primary PDF") else "Abstract"
    route = re.search(r"\bvia ([\w.-]+)", basis)
    disclosure = re.search(r"Disclosure:\s*([A-Za-z-]+)", basis)
    caveat = re.search(r"Caveat:\s*(.*?)\s*$", basis)
    label = disclosure.group(1) if disclosure else "--"
    if disclosure and label not in DISCLOSURE:
        problems.append(f"{key}: disclosure {label!r} is not one of {', '.join(DISCLOSURE)}")
    note = caveat.group(1).rstrip(".") if caveat else "--"
    cells = [source_cell(key, fields, numbered),
             kind + (f" ({route.group(1)})" if route else ""), label, note]
    return " & ".join(cells) + r" \\", problems


def fulltext_dates(entries: dict) -> list[str]:
    dates = set()
    for fields in entries.values():
        basis = fields.get("evidencebasis", "")
        if basis.lstrip().startswith("Primary PDF"):
            dates.update(re.findall(r"\b(\d{4}-\d{2}-\d{2})\b", basis.split(";")[0]))
    return sorted(dates)


def build(tex: str, bib_text: str) -> tuple[str, int]:
    """The Evidence Basis section for this report, and its row count."""
    entries, problems = parse_bib(bib_text)
    if not entries:
        problems.append("references.bib has no entries")
    for key, fields in entries.items():
        if not fields.get("evidencebasis"):
            problems.append(f"{key}: no evidencebasis field (04-citation-rules.md)")
        elif unescaped_specials(copied_text(fields["evidencebasis"])):
            chars = " ".join(sorted(unescaped_specials(copied_text(fields["evidencebasis"]))))
            problems.append(f"{key}: unescaped {chars} in the evidencebasis caveat - escape as "
                            "\\% \\& \\# \\_")
    style = re.search(r"\\bibliographystyle\{([^}]+)\}", tex)
    numbered = bool(style) and style.group(1).strip() in NUMBERED_BST
    rows = []
    for key in sorted(entries, key=lambda k: sort_key(k, entries[k])):
        line, row_problems = row(key, entries[key], numbered)
        problems += row_problems
        rows.append(line)
    if problems:
        raise TableError(problems)

    dates = fulltext_dates(entries)
    when = ("" if not dates else f" on {dates[0]}" if len(dates) == 1
            else f" between {dates[0]} and {dates[-1]}")
    heading = HEADING.search(tex)
    head = heading.group(0) if heading else r"\section{Evidence Basis}"
    section = "\n".join([
        head,
        "% Generated by tools/evidence_table.py from references.bib: edit the",
        "% evidencebasis fields there and re-run it, rather than editing this table.",
        "Per source, how its content was obtained and what a reader should weigh when relying",
        "on it, alphabetically by first author.",
        "``Full text'' means the PDF was read" + when + ";",
        "``Abstract'' means only the abstract could be read, and claims from that source go",
        "no further than its abstract.",
        "",
        r"{\small",
        r"\begin{longtable}{" + COLUMNS + "}",
        r"\caption{Evidence basis per source, alphabetically by first author.}\\",
        r"\toprule", HEADER, r"\midrule", r"\endfirsthead",
        r"\toprule", HEADER, r"\midrule", r"\endhead",
        *rows,
        r"\bottomrule",
        r"\end{longtable}",
        "}",
        "",
    ])
    return section + "\n", len(rows)


def write(tex: str, section: str) -> str:
    heading = HEADING.search(tex)
    if heading:
        end = SECTION_END.search(tex, heading.end())
        stop = end.start() if end else len(tex)
        return tex[:heading.start()] + section + tex[stop:]
    anchor = re.search(r"\\bibliographystyle\{|\\bibliography\{", tex)
    if not anchor:
        raise TableError(["report.tex has neither an Evidence Basis section nor a "
                          "\\bibliographystyle to place one before"])
    return tex[:anchor.start()] + section + tex[anchor.start():]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("target")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        tex_path, bib_path = locate(Path(args.target))
        tex = tex_path.read_text(encoding="utf-8")
        if not re.search(r"\\usepackage(?:\[[^\]]*\])?\{[^}]*\blongtable\b", tex):
            raise TableError(["report.tex does not load longtable - add \\usepackage{longtable}"])
        section, count = build(tex, bib_path.read_text(encoding="utf-8"))
        changed = False
        if args.write:
            new = write(tex, section)
            changed = new != tex
            if changed:
                tex_path.write_text(new, encoding="utf-8")
    except TableError as err:
        if args.json:
            print(json.dumps({"ok": False, "problems": err.problems}))
        else:
            print("evidence_table: cannot build the table:", file=sys.stderr)
            for problem in err.problems:
                print(f"  {problem}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps({"ok": True, "rows": count, "written": args.write,
                          "changed": changed, **({} if args.write else {"section": section})}))
    elif args.write:
        print(f"evidence_table: {count} rows, {tex_path} "
              + ("updated" if changed else "already current"))
    else:
        print(section, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
