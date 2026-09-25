#!/usr/bin/env python3
"""Assemble the policy document and build DOCX and PDF (CLAUDE.md sections 4 and 7).

Steps:
  1. Run `verify.py --final`. Refuse to build if it fails.
  2. Concatenate report/chapters/*.md in file-name order (00_, 01_, ... prefixes).
  3. Replace each claim tag {{C-0001}} / {{D-0001}} / {{M-0001}} with a footnote
     giving publisher, title, date, page, URL and accessed date.
  4. Append a verification statement annex generated from the registers.
  5. Run pandoc with report/template/reference.docx to produce the Word file.
  6. Convert the Word file to PDF through Microsoft Word (Windows), unless --no-pdf.

Usage: build.py [--no-pdf] [--root DIR] [--out NAME]
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
TAG_RE = re.compile(r"\s*\{\{\s*([CDM]-\d+)\s*\}\}")
TITLE = "Green Industrial Policy of the Federal Republic of Somalia, 2028 to 2032"


def find_pandoc() -> str | None:
    p = shutil.which("pandoc")
    if p:
        return p
    for cand in (Path(os.environ.get("LOCALAPPDATA", "")) / "Pandoc" / "pandoc.exe",
                 Path(os.environ.get("ProgramFiles", "")) / "Pandoc" / "pandoc.exe"):
        if cand.exists():
            return str(cand)
    return None


def load(root: Path, name: str) -> list:
    p = root / "data" / name
    return (yaml.safe_load(p.read_text(encoding="utf-8")) or []) if p.exists() else []


def md_escape(s: str) -> str:
    return str(s).replace("*", r"\*").replace("_", r"\_").replace("[", r"\[").replace("]", r"\]")


class Citer:
    """Turns claim tags into footnotes (CLAUDE.md 5.5). The first citation of a source gives publisher, title, date,
    page, URL and accessed date; later citations of the same source use a short form (publisher, title, date, page).
    Derived figures name each underlying source once, with its pages. Every source cited is listed in full in the
    References section."""

    def __init__(self, root: Path):
        self.sources = {s["id"]: s for s in load(root, "sources.yaml")}
        self.claims = {c["id"]: c for c in load(root, "claims.yaml")}
        self.figs = {str(f["id"]): f for f in load(root, "figures.yaml")}
        self.cited = []  # source ids in order of first citation

    def _short(self, sid, pages) -> str:
        s = self.sources[sid]
        cite = f"{md_escape(s['publisher'])}, *{md_escape(s['title'])}*, {s['date_published']}"
        pages = list(dict.fromkeys(str(p) for p in pages if p not in (None, "")))
        if pages:
            cite += (", p. " if len(pages) == 1 else ", pp. ") + ", ".join(pages)
        return cite

    def link(self, sid, pages=()) -> str:
        """URL of the source; for a PDF, opened at the first cited page (#page=N)."""
        s = self.sources[sid]
        url = s.get("url") or ""
        pages = [p for p in pages if p not in (None, "")]
        if url and pages and str(s.get("local_path") or "").lower().endswith(".pdf") and "#" not in url:
            url += f"#page={pages[0]}"
        return url

    def _cite(self, sid, pages) -> str:
        """Every footnote carries a clickable link to the source (Hassan Mumin, 2026-09-25); the first citation of a
        source also gives the accessed date."""
        s = self.sources[sid]
        cite = self._short(sid, pages)
        url = self.link(sid, pages)
        if url:
            cite += f". <{url}>"
        if sid not in self.cited:
            self.cited.append(sid)
            if s.get("accessed"):
                cite += f" (accessed {s['accessed']})"
        return cite + "."

    def figure_sources_note(self, fig: dict) -> str:
        """Footnote for a figure's source line: each underlying source once, with the pages its claims cite."""
        by_src = {}
        for cid in fig.get("claims") or []:
            for sid, page in self._inputs(cid, set()):
                if sid != "A":
                    by_src.setdefault(sid, []).append(page)
        for sid in fig.get("sources") or []:
            by_src.setdefault(sid, [])
        parts = [self._cite(sid, pages).rstrip(".") for sid, pages in by_src.items() if sid in self.sources]
        if fig.get("model_outputs"):
            parts.append(f"model outputs, {fig.get('scenario')} scenario (illustrative, not a forecast; see the annex on "
                         "model methodology and assumptions)")
        return "; ".join(parts) + "." if parts else ""

    def _inputs(self, cid, seen) -> list:
        """(source id, page) pairs and assumption ids behind a claim, following derived formulas."""
        if cid in seen:
            return []
        seen.add(cid)
        c = self.claims[cid]
        if cid.startswith("C-"):
            return [(c["source_id"], c.get("printed_page") or c.get("page"))]
        out = []
        for k, n in re.findall(r"\b([CDA])-(\d+)\b", str(c.get("formula", ""))):
            r = f"{k}-{n}"
            out += [("A", r)] if k == "A" else self._inputs(r, seen)
        return out

    def footnote_for(self, ids) -> str:
        """One footnote for one or more consecutive tags. Source claims are merged by source (pages combined);
        derived claims are introduced as calculations; model outputs are labelled as modelled estimates."""
        direct, derived, assumptions, models = {}, {}, [], []
        for cid in dict.fromkeys(ids):
            c = self.claims[cid]
            if cid.startswith("C-"):
                direct.setdefault(c["source_id"], []).append(c.get("printed_page") or c.get("page"))
            elif cid.startswith("D-"):
                for sid, page in self._inputs(cid, set()):
                    if sid == "A":
                        assumptions.append(page)
                    else:
                        derived.setdefault(sid, []).append(page)
            elif cid.startswith("M-"):
                models.append(c.get("scenario"))
            else:
                raise KeyError(cid)
        parts = [self._cite(sid, pages).rstrip(".") for sid, pages in direct.items()]
        calc = [self._cite(sid, pages).rstrip(".") for sid, pages in derived.items() if sid not in direct]
        calc += [f"model assumption {a} (Annex: model methodology and assumptions)" for a in dict.fromkeys(assumptions)]
        if calc:
            parts.append("calculated from " + "; ".join(calc) if parts else "Calculated from " + "; ".join(calc))
        for sc in dict.fromkeys(models):
            parts.append(f"Modelled estimate, {sc} scenario (illustrative, not a forecast); see the annex on model "
                         "methodology and assumptions")
        return "; ".join(parts) + "."

    def footnote(self, cid: str) -> str:
        return self.footnote_for([cid])

    def replace_tags(self, text: str) -> str:
        """Consecutive tags (separated only by spaces) become one footnote, so markers never run together."""
        group_re = re.compile(r"(?:\s*\{\{\s*[CDM]-\d+\s*\}\})+|\s*\{\{FIGSRC (\d+\.\d+)\}\}")

        def sub(m):
            if m.group(1):  # a figure's source line: one footnote listing its sources, with links
                note = self.figure_sources_note(self.figs[m.group(1)])
                return f"^[{note}]" if note else ""
            return f"^[{self.footnote_for(re.findall(r'[CDM]-[0-9]+', m.group()))}]"
        return group_re.sub(sub, text)

    def references(self) -> str:
        rows = ["# References", ""]
        for sid in sorted(self.cited, key=lambda i: (self.sources[i]["publisher"].lower(), str(self.sources[i]["date_published"]))):
            s = self.sources[sid]
            line = f"{md_escape(s['publisher'])}. {s['date_published']}. *{md_escape(s['title'])}*."
            if s.get("url"):
                line += f" <{s['url']}> (accessed {s.get('accessed')})."
            rows += [line, ""]
        return "\n".join(rows)


def verification_annex(root: Path, used: set) -> str:
    sources = load(root, "sources.yaml")
    claims = load(root, "claims.yaml")
    obtained = [s for s in sources if s.get("local_path")]
    cited_sources = {claims_by_id(claims)[c].get("source_id") for c in used if c.startswith("C-") and c in claims_by_id(claims)}
    tiers = {}
    for s in obtained:
        if s["id"] in cited_sources:
            tiers[s.get("tier")] = tiers.get(s.get("tier"), 0) + 1
    kinds = {"C": 0, "D": 0, "M": 0}
    for c in used:
        kinds[c[0]] = kinds.get(c[0], 0) + 1
    checked = sum(1 for c in used if c.startswith("C-") and claims_by_id(claims)[c].get("fact_checked") is True)
    today = dt.date.today().isoformat()
    rows = "\n".join(f"| Tier {t} | {n} |" for t, n in sorted(tiers.items()))
    return f"""
# Annex: Verification statement

This document is fully sourced and verified against the cited documents. Every factual statement carries a reference to a stored copy of its source, at a specific page, supported by a verbatim quotation that an automated verifier matched against the text of that document. An independent fact-checking review then confirmed that each quotation supports the statement as written, including its period, measure, geographic scope and currency.

Verification establishes that each figure appears in the cited source as reported. It does not establish that the source itself is correct.

| Item | Count |
|---|---|
| Sources cited | {len(cited_sources)} |
| Source claims cited | {kinds['C']} |
| Derived figures cited | {kinds['D']} |
| Modelled estimates cited | {kinds['M']} |
| Source claims passed by the independent fact-checker | {checked} |

| Source tier | Sources cited |
|---|---|
{rows or '| None | 0 |'}

Date of final verification: {today}.
"""


_cache = {}


def claims_by_id(claims):
    key = id(claims)
    if key not in _cache:
        _cache[key] = {c["id"]: c for c in claims}
    return _cache[key]


FIG_LINE_RE = re.compile(r"^\{\{\s*FIG\s+(\d+\.\d+)\s*\}\}\s*$", re.M)


def expand_figures(text: str, root: Path) -> str:
    """Replace each {{FIG n.n}} line with the numbered title, image, note and source line from data/figures.yaml
    (IMF convention: title above, notes and sources below)."""
    path = root / "data" / "figures.yaml"
    figs = {str(f["id"]): f for f in (yaml.safe_load(path.read_text(encoding="utf-8")) or [])} if path.exists() else {}

    def sub(m):
        f = figs[m.group(1)]
        img = (root / f["file"]).resolve().as_posix()
        out = ['::: {custom-style="Figure Title"}', f"Figure {f['id']}. {md_escape(f['title'])}", ":::", "",
               '::: {custom-style="Figure"}', f"![]({img}){{width=100%}}", ":::", ""]
        if f.get("note"):
            out += [f"*Note:* {md_escape(f['note'])}", ""]
        out += [f"*Source:* {md_escape(f['source_line'])} {{{{FIGSRC {f['id']}}}}}", ""]
        return "\n".join(out)
    return FIG_LINE_RE.sub(sub, text)


def word_to_pdf(docx: Path, pdf: Path) -> bool:
    ps = (
        "$ErrorActionPreference='Stop';"
        "$w=New-Object -ComObject Word.Application;$w.Visible=$false;"
        f"$d=$w.Documents.Open('{docx}',$false,$true);"
        "$d.Fields.Update()|Out-Null;"
        f"$d.SaveAs([ref]'{pdf}',[ref]17);$d.Close([ref]0);$w.Quit()"
    )
    r = subprocess.run(["powershell.exe", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        print("PDF export through Word failed:\n" + r.stderr, file=sys.stderr)
        return False
    return pdf.exists()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=str(HERE.parent))
    ap.add_argument("--no-pdf", action="store_true")
    ap.add_argument("--draft", action="store_true",
                    help="review draft: run verify.py --all instead of --final and mark the document DRAFT")
    ap.add_argument("--out", default="Somalia_Green_Industrial_Policy_2028-2032")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve()

    mode = "--all" if a.draft else "--final"
    r = subprocess.run([sys.executable, str(HERE / "verify.py"), mode, "--root", str(root)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write(r.stderr)
        print(f"BUILD REFUSED: verify.py {mode} failed. Fix every failure before building.", file=sys.stderr)
        return 2

    chapters = sorted((root / "report" / "chapters").glob("*.md"))
    if not chapters:
        print("BUILD REFUSED: no chapters in report/chapters.", file=sys.stderr)
        return 2
    citer = Citer(root)
    used = set()
    parts = []
    for ch in chapters:
        text = re.sub(r"<!--.*?-->", "", ch.read_text(encoding="utf-8"), flags=re.S)
        used |= set(re.findall(r"\{\{\s*([CDM]-\d+)\s*\}\}", text))
        parts.append(citer.replace_tags(expand_figures(text, root)).strip())
    for sid in {fs for f in (yaml.safe_load((root / "data" / "figures.yaml").read_text(encoding="utf-8")) or []
                           if (root / "data" / "figures.yaml").exists() else []) for fs in f.get("sources") or []}:
        if sid in citer.sources and sid not in citer.cited:
            citer.cited.append(sid)
    parts.append(citer.references().strip())
    if not a.draft:
        parts.append(verification_annex(root, used).strip())
    subtitle = ("\nsubtitle: \"DRAFT for review. Not for circulation. Some figures await independent fact-checking.\""
                if a.draft else "")
    header = f"---\ntitle: \"{TITLE}\"{subtitle}\ndate: \"{dt.date.today():%d %B %Y}\"\nlang: en-GB\n---\n\n"
    build = root / "report" / "build"
    build.mkdir(parents=True, exist_ok=True)
    combined = build / f"{a.out}.md"
    combined.write_text(header + "\n\n".join(parts) + "\n", encoding="utf-8")

    pandoc = find_pandoc()
    if not pandoc:
        print("BUILD FAILED: pandoc not found.", file=sys.stderr)
        return 1
    ref = root / "report" / "template" / "reference.docx"
    if not ref.exists():
        ref.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([pandoc, "-o", str(ref), "--print-default-data-file", "reference.docx"], check=True)
    docx = build / f"{a.out}.docx"
    cmd = [pandoc, str(combined), "-f", "markdown", "-t", "docx", "--reference-doc", str(ref),
           "--toc", "--toc-depth=2", "-o", str(docx)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("pandoc failed:\n" + r.stderr, file=sys.stderr)
        return 1
    print(f"Built {docx}")
    if not a.no_pdf:
        pdf = build / f"{a.out}.pdf"
        if word_to_pdf(docx, pdf):
            print(f"Built {pdf}")
        else:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
