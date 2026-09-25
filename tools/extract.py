#!/usr/bin/env python3
"""Text extraction for stored sources (CLAUDE.md section 6, step 3).

Usage:
  extract.py S-001 [S-002 ...]      extract registered sources to their text_path
  extract.py --all                  extract every obtained source that has no text file yet
  extract.py --all --force          re-extract every obtained source
  extract.py --file IN --out OUT    extract one file without touching the register
  extract.py --hash FILE            print the SHA-256 of a file
  add --update-register to write sha256, text_path and extraction back to data/sources.yaml

Output format: plain UTF-8 text with a line "=== PAGE n ===" before each page.
  * PDF: one marker per physical page (1-based page index of the file, which may
    differ from the page number printed on the page).
  * DOCX: pages follow Word's last rendered page breaks and explicit page breaks,
    so page numbers are approximate. Prefer the PDF version of a document if both exist.
  * HTML, TXT, MD, CSV: a single page 1.

OCR: a PDF page with almost no text layer is sent to Tesseract if installed, otherwise to the
Windows built-in OCR engine (tools/winocr.py). Images of OCR'd pages are saved to
sources/text/<ID>_pages/ so the fact-checker can confirm figures against the page. Pages that needed OCR but could not get it are
listed on stderr and the exit code is 3, so they are never silently empty.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import re
import sys
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
MIN_PAGE_CHARS = 25  # allow-literal: threshold below which a PDF page is treated as image-only


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


OCR_DPI = 300  # allow-literal: rendering resolution for OCR and page images


def ocr_available():
    """Return the OCR engine to use: 'tesseract', 'windows', or False."""
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return "tesseract"
    except Exception:  # noqa: BLE001
        pass
    try:
        import winocr
        if winocr.available():
            return "windows"
    except Exception:  # noqa: BLE001
        pass
    return False


def ocr_pixmap(pix, engine: str) -> str:
    if engine == "tesseract":
        import pytesseract
        from PIL import Image
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        return pytesseract.image_to_string(img)
    import winocr
    return winocr.ocr_png(pix.tobytes("png"))


def save_page_images(pdf: Path, pages: list, out_dir: Path):
    """Save page images so OCR figures can be confirmed against the page itself."""
    import pymupdf
    out_dir.mkdir(parents=True, exist_ok=True)
    with pymupdf.open(pdf) as doc:
        for n in pages:
            doc[n - 1].get_pixmap(dpi=OCR_DPI // 2).save(str(out_dir / f"p{n:03d}.png"))


def extract_pdf(path: Path):
    import pymupdf
    pages, ocr_pages, missing = [], [], []
    can_ocr = None
    with pymupdf.open(path) as doc:
        for i, page in enumerate(doc, 1):
            text = page.get_text("text")
            if len(text.strip()) < MIN_PAGE_CHARS and page.get_images():
                if can_ocr is None:
                    can_ocr = ocr_available()
                if can_ocr:
                    pix = page.get_pixmap(dpi=OCR_DPI)
                    text = ocr_pixmap(pix, can_ocr)
                    ocr_pages.append(i)
                else:
                    missing.append(i)
            pages.append(text)
    return pages, ocr_pages, missing


W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def extract_docx(path: Path):
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    pages, cur = [], []

    def para_text(p):
        out = []
        for el in p.iter():
            if el.tag == W + "t":
                out.append(el.text or "")
            elif el.tag == W + "tab":
                out.append("\t")
            elif el.tag in (W + "br", W + "cr"):
                if el.get(W + "type") == "page":
                    out.append("\f")
                else:
                    out.append("\n")
            elif el.tag == W + "lastRenderedPageBreak":
                out.append("\f")
        return "".join(out)

    body = root.find(W + "body")
    for block in list(body):
        if block.tag == W + "p":
            chunks = para_text(block).split("\f")
        elif block.tag == W + "tbl":
            rows = []
            for tr in block.iter(W + "tr"):
                cells = [" ".join(para_text(p) for p in tc.iter(W + "p")).strip() for tc in tr.findall(W + "tc")]
                rows.append(" | ".join(cells))
            chunks = "\n".join(rows).split("\f")
        else:
            continue
        for j, chunk in enumerate(chunks):
            if j > 0:
                pages.append("\n".join(cur))
                cur = []
            cur.append(chunk)
    pages.append("\n".join(cur))
    return pages


class _HTMLText(HTMLParser):
    BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section",
             "article", "table", "ul", "ol", "header", "footer", "blockquote"}
    SKIP = {"script", "style", "noscript", "svg"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag in self.BLOCK:
            self.out.append("\n")
        elif tag in ("td", "th"):
            self.out.append(" | ")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def extract_html(path: Path):
    raw = path.read_bytes().decode("utf-8", errors="replace")
    p = _HTMLText()
    p.feed(raw)
    text = html.unescape("".join(p.out))
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return [text.strip()]


def extract_xlsx(path: Path):
    """One page per worksheet; each non-empty row becomes one line of cell values joined by ' | '.
    Values are written as stored in the file (no number formatting), so quotes match the data."""
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    pages = []
    for ws in wb.worksheets:
        lines = [f"# Sheet: {ws.title}"]
        for row in ws.iter_rows(values_only=True):
            cells = ["" if v is None else str(v).strip() for v in row]
            while cells and cells[-1] == "":
                cells.pop()
            if any(cells):
                lines.append(" | ".join(cells))
        pages.append("\n".join(lines))
    wb.close()
    return pages


def extract_file(path: Path):
    """Return (pages, method, missing_ocr_pages). OCR'd page numbers are in extract_file.last_ocr_pages."""
    extract_file.last_ocr_pages = []
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        pages, ocr_pages, missing = extract_pdf(path)
        extract_file.last_ocr_pages = ocr_pages
        return pages, ("ocr" if ocr_pages else "text"), missing
    if suffix == ".docx":
        return extract_docx(path), "text", []
    if suffix in (".html", ".htm"):
        return extract_html(path), "text", []
    if suffix == ".xlsx":
        return extract_xlsx(path), "text", []
    if suffix in (".txt", ".md", ".csv", ".tsv", ".json", ".geojson"):
        return [path.read_text(encoding="utf-8", errors="replace")], "text", []
    raise ValueError(f"unsupported file type: {suffix}")


def write_text(pages, out: Path):
    out.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(f"=== PAGE {i} ===\n{t.rstrip()}\n" for i, t in enumerate(pages, 1))
    out.write_text(body, encoding="utf-8")


def load_register():
    import yaml
    path = ROOT / "data" / "sources.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else []
    return path, data or []


def save_register(path, data):
    """Rewrite the register, keeping any leading comment lines."""
    import yaml
    header = ""
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines(keepends=True):
            if not line.startswith("#"):
                break
            header += line
    path.write_text(header + yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=1000), encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--file")
    ap.add_argument("--out")
    ap.add_argument("--hash")
    ap.add_argument("--update-register", action="store_true")
    a = ap.parse_args(argv)

    if a.hash:
        print(sha256_file(Path(a.hash)))
        return 0
    if a.file:
        pages, method, missing = extract_file(Path(a.file))
        write_text(pages, Path(a.out))
        print(f"{a.file}: {len(pages)} page(s), extraction={method}")
        if missing:
            print(f"  pages needing OCR but OCR unavailable: {missing}", file=sys.stderr)
            return 3
        return 0

    reg_path, sources = load_register()
    status = 0
    changed = False
    for s in sources:
        sid = s.get("id")
        if not s.get("local_path"):
            continue
        if a.ids and sid not in a.ids:
            continue
        if not a.ids and not a.all:
            continue
        text_path = s.get("text_path") or f"sources/text/{sid}.txt"
        out = ROOT / text_path
        if a.all and not a.force and not a.ids and out.exists():
            continue
        src = ROOT / s["local_path"]
        if not src.exists():
            print(f"{sid}: stored file missing: {s['local_path']}", file=sys.stderr)
            status = 2
            continue
        pages, method, missing = extract_file(src)
        write_text(pages, out)
        if extract_file.last_ocr_pages:
            save_page_images(src, extract_file.last_ocr_pages, out.parent / f"{sid}_pages")
        digest = sha256_file(src)
        chars = sum(len(p.strip()) for p in pages)
        print(f"{sid}: {len(pages)} page(s), {chars} characters, extraction={method}, sha256={digest}")
        if missing:
            print(f"  {sid}: pages with no text layer and no OCR available: {missing}", file=sys.stderr)
            status = max(status, 3)
        if a.update_register:
            if s.get("sha256") and s["sha256"] != digest:
                print(f"  {sid}: WARNING register hash differs from file; register updated. "
                      "Check the file has not been replaced.", file=sys.stderr)
            s["sha256"], s["text_path"], s["extraction"] = digest, text_path, method
            ocr_pages = extract_file.last_ocr_pages
            if ocr_pages and len(ocr_pages) < len(pages):
                s["ocr_pages"] = ocr_pages
            else:
                s.pop("ocr_pages", None)
            changed = True
    if changed:
        save_register(reg_path, sources)
    return status


if __name__ == "__main__":
    sys.exit(main())
