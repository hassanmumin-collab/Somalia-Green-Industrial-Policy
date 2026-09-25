#!/usr/bin/env python3
"""Download a source into sources/raw/, hash it, extract its text, and show its opening text.

Usage: fetch.py S-001 short-name URL [--head N] [--ext pdf]

  * Saves to sources/raw/S-001_short-name.<ext>. Never overwrites an existing file.
  * Retries once on failure (CLAUDE.md: slow government sites), then reports "not obtained".
  * Writes sources/text/S-001.txt and prints SHA-256, page count and the first N lines,
    so the exact title, publisher and date can be recorded as printed.
The register entry in data/sources.yaml is written separately, after reading the document.
"""
from __future__ import annotations

import argparse
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import extract  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
TYPES = {"application/pdf": "pdf", "text/html": "html",
         "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx"}


def download(url: str, timeout: int):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), r.headers.get_content_type(), r.geturl()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sid")
    ap.add_argument("name")
    ap.add_argument("url")
    ap.add_argument("--head", type=int, default=40)
    ap.add_argument("--ext")
    ap.add_argument("--timeout", type=int, default=180)
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    data = ctype = final = None
    for attempt in (1, 2):
        try:
            data, ctype, final = download(a.url, a.timeout)
            break
        except Exception as exc:  # noqa: BLE001
            print(f"attempt {attempt} failed: {exc}", file=sys.stderr)
            if attempt == 1:
                time.sleep(5)
    if data is None:
        print("NOT OBTAINED", file=sys.stderr)
        return 1
    ext = a.ext or TYPES.get(ctype) or Path(final.split("?")[0]).suffix.lstrip(".").lower() or "bin"
    if data[:4] == b"%PDF":
        ext = "pdf"
    elif ext == "pdf":
        print(f"WARNING: expected a PDF but got {ctype}; saving as html", file=sys.stderr)
        ext = "html"
    raw = ROOT / "sources" / "raw" / f"{a.sid}_{a.name}.{ext}"
    if raw.exists():
        print(f"refusing to overwrite {raw}", file=sys.stderr)
        return 2
    raw.write_bytes(data)
    pages, method, missing = extract.extract_file(raw)
    out = ROOT / "sources" / "text" / f"{a.sid}.txt"
    extract.write_text(pages, out)
    if extract.extract_file.last_ocr_pages:
        extract.save_page_images(raw, extract.extract_file.last_ocr_pages, out.parent / f"{a.sid}_pages")
        print(f"OCR used on pages {extract.extract_file.last_ocr_pages[:30]}; page images in sources/text/{a.sid}_pages/")
    print(f"saved {raw.relative_to(ROOT).as_posix()}  ({len(data)} bytes, {ctype}, final URL {final})")
    print(f"sha256 {extract.sha256_file(raw)}")
    print(f"pages {len(pages)}, characters {sum(len(p.strip()) for p in pages)}, extraction {method}")
    if missing:
        print(f"PAGES WITHOUT TEXT LAYER (need OCR): {missing[:30]}{' ...' if len(missing) > 30 else ''}")
    head = "\n".join(l for l in "\n".join(pages[:4]).splitlines() if l.strip())
    print("----- opening text -----")
    print("\n".join(head.splitlines()[:a.head]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
