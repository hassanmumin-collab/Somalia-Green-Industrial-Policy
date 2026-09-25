#!/usr/bin/env python3
"""Build report/template/reference.docx: the Word styles for the policy document (CLAUDE.md section 12A).

Starts from pandoc's default reference document and rewrites its styles in an IMF-publication register:
Arial body text at 10.5 pt with 1.15 line spacing, navy headings, left-aligned bold figure and table titles,
8 pt notes and footnotes, and 2.5 cm margins on A4.

Usage: python tools/make_reference_docx.py
"""
from __future__ import annotations

import re
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from build import find_pandoc  # noqa: E402

NAVY = "0B3C5D"
BLUE = "328CC1"
FONT = "Arial"


def rpr(size_half_pts, bold=False, color=None, italic=False):
    parts = [f'<w:rFonts w:ascii="{FONT}" w:hAnsi="{FONT}" w:cs="{FONT}" w:eastAsia="{FONT}"/>']
    if bold:
        parts.append("<w:b/><w:bCs/>")
    if italic:
        parts.append("<w:i/><w:iCs/>")
    if color:
        parts.append(f'<w:color w:val="{color}"/>')
    parts.append(f'<w:sz w:val="{size_half_pts}"/><w:szCs w:val="{size_half_pts}"/>')
    return "<w:rPr>" + "".join(parts) + "</w:rPr>"


def set_style(xml: str, style_id: str, ppr: str, rpr_xml: str) -> str:
    """Replace the pPr and rPr of a style, keeping its name, basedOn and links."""
    m = re.search(rf'(<w:style [^>]*w:styleId="{style_id}"[^>]*>)(.*?)(</w:style>)', xml, re.S)
    if not m:
        return xml
    body = re.sub(r"<w:pPr>.*?</w:pPr>|<w:pPr/>", "", m.group(2), flags=re.S)
    body = re.sub(r"<w:rPr>.*?</w:rPr>|<w:rPr/>", "", body, flags=re.S)
    return xml[:m.start()] + m.group(1) + body + ppr + rpr_xml + m.group(3) + xml[m.end():]


def main() -> int:
    pandoc = find_pandoc()
    if not pandoc:
        print("pandoc not found", file=sys.stderr)
        return 1
    out = ROOT / "report" / "template" / "reference.docx"
    out.parent.mkdir(parents=True, exist_ok=True)
    base = out.with_name("pandoc_default_reference.docx")
    subprocess.run([pandoc, "-o", str(base), "--print-default-data-file", "reference.docx"], check=True)
    zin = zipfile.ZipFile(base)
    styles = zin.read("word/styles.xml").decode("utf-8")
    styles = re.sub(r"<w:rPrDefault>.*?</w:rPrDefault>",
                    "<w:rPrDefault>" + rpr(21) + "</w:rPrDefault>", styles, flags=re.S)
    styles = re.sub(r"<w:pPrDefault>.*?</w:pPrDefault>",
                    '<w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="276" w:lineRule="auto"/></w:pPr></w:pPrDefault>',
                    styles, flags=re.S)
    body_ppr = '<w:pPr><w:spacing w:before="0" w:after="140" w:line="276" w:lineRule="auto"/><w:jc w:val="both"/></w:pPr>'
    for sid in ("BodyText", "FirstParagraph"):
        styles = set_style(styles, sid, body_ppr, rpr(21))
    styles = set_style(styles, "Compact", '<w:pPr><w:spacing w:before="0" w:after="60"/></w:pPr>', rpr(21))
    heads = {"Heading1": (32, NAVY, 360, 160), "Heading2": (25, NAVY, 280, 120), "Heading3": (22, BLUE, 220, 80),
             "Heading4": (21, NAVY, 180, 60)}
    for sid, (sz, col, before, after) in heads.items():
        lvl = int(sid[-1]) - 1
        ppr = (f'<w:pPr><w:keepNext/><w:keepLines/><w:spacing w:before="{before}" w:after="{after}"/>'
               f'<w:outlineLvl w:val="{lvl}"/></w:pPr>')
        styles = set_style(styles, sid, ppr, rpr(sz, bold=True, color=col))
    if "Heading1" in heads:  # each Part starts on a new page
        styles = styles.replace('<w:outlineLvl w:val="0"/></w:pPr>', '<w:pageBreakBefore/><w:outlineLvl w:val="0"/></w:pPr>', 1)
    styles = set_style(styles, "Title", '<w:pPr><w:spacing w:before="2400" w:after="240"/></w:pPr>', rpr(48, bold=True, color=NAVY))
    styles = set_style(styles, "Subtitle", '<w:pPr><w:spacing w:after="240"/></w:pPr>', rpr(26, color=BLUE))
    styles = set_style(styles, "Date", '<w:pPr><w:spacing w:after="240"/></w:pPr>', rpr(22, color="595959"))
    styles = set_style(styles, "FootnoteText", '<w:pPr><w:spacing w:after="40" w:line="220" w:lineRule="auto"/></w:pPr>', rpr(15))
    styles = set_style(styles, "Caption", '<w:pPr><w:spacing w:before="60" w:after="160"/></w:pPr>', rpr(16, italic=True))
    styles = set_style(styles, "ImageCaption", '<w:pPr><w:spacing w:before="60" w:after="160"/></w:pPr>', rpr(16, italic=True))
    styles = set_style(styles, "TableCaption", '<w:pPr><w:keepNext/><w:spacing w:before="200" w:after="80"/></w:pPr>', rpr(20, bold=True, color=NAVY))
    fig_title = ('<w:style w:type="paragraph" w:customStyle="1" w:styleId="FigureTitle"><w:name w:val="Figure Title"/>'
                 '<w:basedOn w:val="Normal"/><w:next w:val="Figure"/><w:qFormat/>'
                 '<w:pPr><w:keepNext/><w:keepLines/><w:spacing w:before="240" w:after="80"/></w:pPr>'
                 + rpr(20, bold=True, color=NAVY) + "</w:style>")
    styles = styles.replace("</w:styles>", fig_title + "</w:styles>")
    styles = set_style(styles, "Figure", '<w:pPr><w:keepNext/><w:keepLines/><w:spacing w:before="0" w:after="60"/></w:pPr>', rpr(21))
    styles = set_style(styles, "Hyperlink", "", '<w:rPr><w:color w:val="' + BLUE + '"/></w:rPr>')
    styles = set_style(styles, "BlockText", '<w:pPr><w:shd w:val="clear" w:color="auto" w:fill="EAF2F8"/>'
                       '<w:spacing w:before="120" w:after="120"/><w:ind w:left="200" w:right="200"/></w:pPr>', rpr(20))
    document = zin.read("word/document.xml").decode("utf-8")
    document = re.sub(r"<w:pgSz[^>]*/>", '<w:pgSz w:w="11906" w:h="16838"/>', document)
    document = re.sub(r"<w:pgMar[^>]*/>", '<w:pgMar w:top="1418" w:right="1418" w:bottom="1418" w:left="1418" '
                      'w:header="709" w:footer="709" w:gutter="0"/>', document)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "word/styles.xml":
                data = styles.encode("utf-8")
            elif item.filename == "word/document.xml":
                data = document.encode("utf-8")
            zout.writestr(item, data)
    zin.close()
    base.unlink()
    print(f"wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
