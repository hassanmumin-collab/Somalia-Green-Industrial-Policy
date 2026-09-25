#!/usr/bin/env python3
"""Helpers for the sourcing protocol (CLAUDE.md section 6, steps 4 and 5).

  claimkit.py find S-040 "regex" [--ctx 160]   search a source's text; prints page and context
  claimkit.py page S-040 7                      print one page of a source's text
  claimkit.py register new_sources.yaml         register fetched sources (hash, pages, OCR filled in)
  claimkit.py factcheck verdicts.txt           apply fact-checker verdicts (PASS sets fact_checked: true)
  claimkit.py add drafts.yaml                   add draft claims, one at a time, only if each passes
                                                verify.py --claim; failures are reported and not added

A draft is a claim without an id (the next free C-/D- id is assigned). Defaults filled in
when absent: status 'verified', verified_at today, fact_checked false. Drafts that fail are
written to <drafts>.rejected.yaml with the verifier's reasons, for correction.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CLAIMS = ROOT / "data" / "claims.yaml"


def pages_of(sid: str) -> dict:
    text = (ROOT / "sources" / "text" / f"{sid}.txt").read_text(encoding="utf-8")
    return verify.split_pages(text)


def cmd_find(sid, pattern, ctx):
    rx = re.compile(pattern, re.I)
    hits = 0
    for n, t in pages_of(sid).items():
        flat = re.sub(r"\s+", " ", t)
        for m in rx.finditer(flat):
            a, b = max(0, m.start() - ctx), min(len(flat), m.end() + ctx)
            print(f"[{sid} p.{n}] ...{flat[a:b]}...")
            hits += 1
            if hits >= 40:
                print("(stopped at 40 hits)")
                return
    if not hits:
        print("no match")


def next_id(existing, prefix):
    nums = [int(c["id"][2:]) for c in existing if str(c.get("id", "")).startswith(prefix + "-")]
    return f"{prefix}-{(max(nums) + 1 if nums else 1):04d}"


def cmd_add(path):
    drafts = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or []
    raw = CLAIMS.read_text(encoding="utf-8") if CLAIMS.exists() else ""
    existing = yaml.safe_load(raw) or []
    rejected, added = [], []
    for d in drafts:
        d = dict(d)
        prefix = "D" if "formula" in d else "C"
        d.setdefault("status", "verified")
        d.setdefault("verified_at", dt.date.today().isoformat())
        if prefix == "C":
            d.setdefault("fact_checked", False)
        cid = next_id(existing, prefix)
        entry = {"id": cid, **{k: v for k, v in d.items() if k != "id"}}
        trial = existing + [entry]
        CLAIMS.write_text(yaml.safe_dump(trial, sort_keys=False, allow_unicode=True, width=1000), encoding="utf-8")
        p = verify.run(ROOT, "claim", claim_id=cid, write=False)
        dup = verify.Project(ROOT)
        dup.check_duplicates()
        fails = [i for i in p.issues + dup.issues if i.level == "fail" and (i.where == cid or cid in i.where)]
        if fails:
            d["_rejected"] = [f"check {i.check}: {i.msg}" for i in fails]
            rejected.append(d)
            CLAIMS.write_text(raw, encoding="utf-8")
            print(f"REJECTED ({d.get('statement', '')[:70]}): " + "; ".join(d["_rejected"]))
        else:
            existing = trial
            raw = CLAIMS.read_text(encoding="utf-8")
            added.append(cid)
            print(f"added {cid}: {d.get('statement', '')[:90]}")
    header = "# Claim register (CLAUDE.md section 5.2 and 5.3). Add claims with tools/claimkit.py add.\n"
    body = CLAIMS.read_text(encoding="utf-8")
    if not body.startswith("#"):
        CLAIMS.write_text(header + body, encoding="utf-8")
    if rejected:
        out = Path(path).with_suffix(".rejected.yaml")
        out.write_text(yaml.safe_dump(rejected, sort_keys=False, allow_unicode=True, width=1000), encoding="utf-8")
        print(f"{len(rejected)} rejected -> {out}")
    print(f"{len(added)} added")


def cmd_register(path):
    """Append new sources (already fetched into sources/raw with text extracted) to the register.

    Each entry needs: id, title, publisher, date_published, url, tier, language, coverage, notes.
    local_path, text_path, sha256, extraction, ocr_pages and pages are filled in from the files.
    """
    import hashlib
    reg = ROOT / "data" / "sources.yaml"
    raw = reg.read_text(encoding="utf-8")
    existing = {s["id"] for s in (yaml.safe_load(raw) or [])}
    new = []
    for e in yaml.safe_load(Path(path).read_text(encoding="utf-8")):
        sid = e["id"]
        if sid in existing:
            print(f"{sid} already registered; skipped")
            continue
        files = sorted((ROOT / "sources" / "raw").glob(f"{sid}_*"))
        if len(files) != 1:
            print(f"{sid}: expected one stored file, found {len(files)}; skipped")
            continue
        f = files[0]
        text = (ROOT / "sources" / "text" / f"{sid}.txt").read_text(encoding="utf-8")
        pages = len(verify.PAGE_RE.findall(text))
        pdir = ROOT / "sources" / "text" / f"{sid}_pages"
        ocr = sorted(int(p.stem[1:]) for p in pdir.glob("p*.png")) if pdir.exists() else []
        entry = {k: e[k] for k in ("id", "title", "publisher", "date_published", "url")}
        entry.update(accessed=e.get("accessed", dt.date.today().isoformat()),
                     local_path=f.relative_to(ROOT).as_posix(), text_path=f"sources/text/{sid}.txt",
                     sha256=hashlib.sha256(f.read_bytes()).hexdigest(), tier=e["tier"],
                     language=e["language"], coverage=e["coverage"], extraction="ocr" if ocr else "text")
        if ocr and len(ocr) < pages:
            entry["ocr_pages"] = ocr
        entry["pages"] = pages
        entry["notes"] = e.get("notes", "")
        new.append(entry)
        print(f"registered {sid}: {entry['title'][:80]}")
    if new:
        reg.write_text(raw.rstrip("\n") + "\n" + yaml.safe_dump(new, sort_keys=False, allow_unicode=True, width=1000),
                       encoding="utf-8")


def cmd_factcheck(path):
    """Apply fact-checker verdicts from a text file of blocks like 'C-0001: PASS' followed by indented lines.

    PASS sets fact_checked: true. FAIL and QUERY leave it false and store the reason in fact_check_note.
    """
    text = Path(path).read_text(encoding="utf-8")
    blocks = re.findall(r"^\s*\**([CD]-\d{4})\**\s*:\s*\**(PASS|FAIL|QUERY)\**(.*?)(?=^\s*\**[CD]-\d{4}\**\s*:|^Summary|\Z)",
                        text, re.M | re.S)
    raw = CLAIMS.read_text(encoding="utf-8")
    header = "".join(l for l in raw.splitlines(keepends=True) if l.startswith("#"))
    claims = yaml.safe_load(raw)
    by_id = {c["id"]: c for c in claims}
    counts = {"PASS": 0, "FAIL": 0, "QUERY": 0}
    for cid, verdict, body in blocks:
        c = by_id.get(cid)
        if not c:
            print(f"{cid}: not in register")
            continue
        counts[verdict] += 1
        note = re.sub(r"\s+", " ", body).strip()
        if verdict == "PASS":
            c["fact_checked"] = True
            c.pop("fact_check_note", None)
        else:
            c["fact_checked"] = False
            c["fact_check_note"] = f"{verdict} ({dt.date.today().isoformat()}): {note}"
    CLAIMS.write_text(header + yaml.safe_dump(claims, sort_keys=False, allow_unicode=True, width=1000), encoding="utf-8")
    print(counts)


def main(argv=None):
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("find"); f.add_argument("sid"); f.add_argument("pattern"); f.add_argument("--ctx", type=int, default=160)
    g = sub.add_parser("page"); g.add_argument("sid"); g.add_argument("n", type=int)
    a = sub.add_parser("add"); a.add_argument("path")
    r = sub.add_parser("register"); r.add_argument("path")
    fc = sub.add_parser("factcheck"); fc.add_argument("path")
    x = ap.parse_args(argv)
    if x.cmd == "find":
        cmd_find(x.sid, x.pattern, x.ctx)
    elif x.cmd == "page":
        print(pages_of(x.sid).get(x.n, "no such page"))
    elif x.cmd == "factcheck":
        cmd_factcheck(x.path)
    elif x.cmd == "register":
        cmd_register(x.path)
    else:
        cmd_add(x.path)


if __name__ == "__main__":
    main()
