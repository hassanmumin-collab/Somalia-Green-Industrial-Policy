#!/usr/bin/env python3
"""Accuracy and data verifier for the Somalia Green Industrial Policy.

Implements CLAUDE.md section 7. Modes:
  --all          full check of registers, chapters and model
  --claim ID     check one claim (C-, D- or M- id)
  --hook         fast check: registers plus changed chapters (used by hooks)
  --final        strictest mode, run before any build

Exit code 0 on pass (warnings allowed), 2 on failure. Every run writes
reports/verification_report.md. Failures are printed to stderr.

Conventions (see tools/README.md):
  * Extracted text files mark pages with lines "=== PAGE n ===".
    A claim's `page` is the physical page index of the stored file (1-based),
    an int or a range string such as "4-5".
  * Claim ids: C-0001 (source claim), D-0001 (derived), M-0001 (model output).
  * Assumption ids: A-001.
"""
from __future__ import annotations

import argparse
import ast
import datetime as dt
import hashlib
import importlib.util
import math
import re
import subprocess
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import yaml

CHECK_NAMES = {
    1: "Source register fields",
    2: "Stored file exists and SHA-256 matches",
    3: "Extracted text file exists",
    4: "Claim fields and source reference",
    5: "Quote found in source text (on the cited page)",
    6: "Claim value appears in the quote",
    7: "Period and unit consistent with the quote",
    8: "Derived claims recompute",
    9: "Duplicate ids and unregistered conflicts",
    10: "Claim tags resolve (and final-mode status rules)",
    11: "Every number in a sentence is tagged or allowlisted",
    12: "Numbers in tagged sentences match a tagged claim",
    13: "Estimate / illustrative claims labelled as such",
    14: "Projection / target claims labelled as such",
    15: "Tier 4 and 5 claims attributed",
    16: "Executive summary uses Tier 1 or 2 sources only",
    17: "Data older than five years (warning)",
    18: "Style lint",
    19: "Model inputs are claims or assumptions; no hard-coded numbers",
    20: "Model outputs recompute from the model",
    21: "Model outputs depend only on approved assumptions (final)",
    22: "Model outputs labelled as modelled estimate or scenario",
    23: "Figures registered, traceable and referenced correctly",
}

SOURCE_REQUIRED = ["id", "title", "publisher", "date_published", "url", "accessed",
                   "local_path", "text_path", "sha256", "tier", "language",
                   "coverage", "extraction", "notes"]
SOURCE_NULLABLE_IF_NOT_OBTAINED = {"local_path", "text_path", "sha256", "extraction", "accessed"}
CLAIM_REQUIRED = ["id", "statement", "value", "unit", "period", "measure", "basis",
                  "source_id", "page", "quote", "status", "verified_at", "fact_checked"]
CLAIM_NULLABLE_IF_OPEN = {"source_id", "page", "quote", "verified_at", "value"}
DERIVED_REQUIRED = ["id", "statement", "formula", "value", "unit", "rounding", "status"]
MODEL_REQUIRED = ["id", "statement", "output_key", "scenario", "value", "unit",
                  "rounding", "status"]
ASSUMPTION_REQUIRED = ["id", "parameter", "value", "unit", "range", "basis_claim",
                       "comparator", "rationale", "approved_by_hassan"]
BASES = {"actual", "projection", "target", "estimate"}
STATUSES = {"verified", "estimate", "illustrative", "pending", "unconfirmed", "superseded"}
OPEN_STATUSES = {"pending", "unconfirmed"}
SCENARIOS = {"low", "base", "high"}

TAG_RE = re.compile(r"\{\{\s*([CDM]-\d+)\s*\}\}")
ANY_TAG_RE = re.compile(r"\{\{([^{}]*)\}\}")
FIG_RE = re.compile(r"^\{\{\s*FIG\s+(\d+\.\d+)\s*\}\}$")  # a figure marker on its own line; build.py expands it
ID_REF_RE = re.compile(r"\b([CDA])-(\d+)\b")
PAGE_RE = re.compile(r"^=== PAGE (\d+) ===\s*$", re.M)
YEAR_RE = re.compile(r"(?<!\d)((?:19|20)\d{2})(?:\s*/\s*(\d{2})(?!\d))?(?!\d)")
NUM_RE = re.compile(
    r"(?<![\w.,])(?P<sign>[-−])?"
    r"(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"(?P<suf>bn|Bn|mn|Mn|tn|m|M|k|K|%)?(?P<unitsuf>ha|kg|km2|km|kWh|MWh|GWh|kWp|MWp|kW|MW|GW|mm|cm|m2|m3|t)?(?!\w)")
SCALE_WORDS = {"trillion": 1e12, "tn": 1e12, "billion": 1e9, "bn": 1e9,
               "million": 1e6, "mn": 1e6, "m": 1e6, "thousand": 1e3, "k": 1e3}
SCALE_AFTER_RE = re.compile(r"^\s*(trillion|billion|million|thousand|bn|mn|tn)\b", re.I)
PCT_AFTER_RE = re.compile(r"^\s*(%|per\s?cent\b|percent\b|percentage points?\b|pp\b)", re.I)
CURRENCY_BEFORE_RE = re.compile(r"(US\$|\$|USD|€|£|SOS|KES|ETB|EUR)\s*$")
UNIT_NOUN_AFTER_RE = re.compile(
    r"^\s*(tonnes?|tons?|t\b|head\b|heads\b|jobs|workers|people|persons|households|hectares|"
    r"ha\b|km|MW|kW|GW|litres?|liters?|units|metric|kg)", re.I)
CURRENCIES = {
    "USD": r"US\$|\bUSD\b|US dollars?|U\.S\. dollars?|(?<![A-Za-z])\$",
    "SOS": r"\bSOS\b|Somali shillings?|\bSh\.So\b",
    "KES": r"\bKES\b|Kenyan? shillings?|\bKSh\b",
    "EUR": r"€|\bEUR\b|\beuros?\b",
    "ETB": r"\bETB\b|\bbirr\b",
    "GBP": r"£|\bGBP\b|pounds sterling",
}
UNIT_FAMILIES = {
    "mass": r"\b(tonnes?|tons?|MT|kg|kilograms?|quintals?)\b",
    "volume": r"\b(litres?|liters?|m3|cubic met(re|er)s?)\b",
    "head": r"\bheads?\b",
    "energy": r"\b(MWh|kWh|GWh|TWh)\b",
    "power": r"\b(MW|kW|GW|MWp|kWp)\b",
    "area": r"\b(hectares?|ha|km2|square kilomet(re|er)s?)\b",
    "persons": r"\b(people|persons|jobs|workers|employees|individuals)\b",
    "households": r"\bhouseholds?\b",
    "emissions": r"\b(tCO2e?|MtCO2e?|GgCO2e?|tonnes? of CO2)\b",
}
PERCENT_UNIT_RE = re.compile(r"%|per\s?cent|percent|percentage", re.I)
AUTO_LABEL_RE = re.compile(
    r"\b(Parts?|Clusters?|Phases?|Annex(?:es)?|Tables?|Figures?|Box(?:es)?|Sections?|"
    r"Chapters?|Steps?|Tiers?|Checks?)\s+(?:\d+[a-z]?|[IVX]+\b)"
    r"(?:\s*(?:,|and|to|or|-)\s*(?:\d+[a-z]?|[IVX]+\b))*")
YEAR_RANGE_RE = re.compile(r"(?<!\d)(?:19|20)\d{2}\s*(?:/|-|–|to)\s*(?:(?:19|20)\d{2}|\d{2})(?!\d)")
ABBREVIATIONS = ["e.g.", "i.e.", "No.", "Nos.", "Art.", "Mr.", "Ms.", "Dr.", "St.",
                 "Vol.", "p.", "pp.", "Fig.", "etc.", "approx.", "U.S.", "U.N.", "cf.", "vs."]
FORMULAIC = [r"\bnot only\b.{0,120}?\bbut also\b", r"\bit is worth noting\b",
             r"\bit is important to note\b", r"\bin conclusion\b", r"\bin today's\b",
             r"\bplays? an? (crucial|pivotal|vital|key) role\b", r"\bdelve\b",
             r"\ba testament to\b", r"\bever-evolving\b", r"\bnavigat\w+ the complexities\b",
             r"\blast but not least\b", r"\bgame[- ]changer\b", r"\bunlock(ing)? the (full )?potential\b"]
ATTRIBUTION_RE = re.compile(
    r"according to|reported by|as reported|estimates? (?:by|from)|industry estimates?|"
    r"cited by|data from|figures from", re.I)
ESTIMATE_RE = re.compile(r"\bestimat", re.I)
ILLUSTRATIVE_RE = re.compile(r"\billustrative\b", re.I)
PROJECTION_RE = re.compile(r"\b(projected|projection|projections|forecast|forecasts|forecasted)\b", re.I)
TARGET_RE = re.compile(r"\b(targets?|targeted)\b", re.I)
MODEL_LABEL_RE = re.compile(r"modell?ed estimate|\bscenario\b", re.I)
CANNOT_CONFIRM = "I cannot confirm this"


@dataclass
class Issue:
    check: int
    level: str  # "fail" or "warn"
    where: str
    msg: str

    def line(self) -> str:
        return f"[{self.level.upper()}] check {self.check} ({CHECK_NAMES.get(self.check, '')}): {self.where}: {self.msg}"


# --------------------------------------------------------------------------- helpers

class UniqueKeyLoader(yaml.SafeLoader):
    """SafeLoader that rejects duplicate keys inside a mapping."""


def _construct_mapping(loader, node, deep=False):
    keys = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in keys:
            raise yaml.constructor.ConstructorError(
                None, None, f"duplicate key '{key}'", key_node.start_mark)
        keys.add(key)
    return yaml.SafeLoader.construct_mapping(loader, node, deep)


UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping)


def load_yaml_list(path: Path, issues: list, check: int) -> list:
    if not path.exists():
        return []
    try:
        data = yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueKeyLoader)
    except yaml.YAMLError as exc:
        issues.append(Issue(check, "fail", str(path.name), f"YAML error: {exc}"))
        return []
    if data is None:
        return []
    if not isinstance(data, list):
        issues.append(Issue(check, "fail", str(path.name), "register must be a YAML list"))
        return []
    return [d for d in data if isinstance(d, dict)]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def normalise(text: str, join_hyphens: bool = True) -> str:
    """Normalise whitespace, ligatures, curly quotes, dashes and line-end hyphenation."""
    text = unicodedata.normalize("NFKC", str(text))
    text = text.replace("­", "")
    for ch in "‘’‚‛′":
        text = text.replace(ch, "'")
    for ch in "“”„‟″":
        text = text.replace(ch, '"')
    for ch in "‐‑‒–—―−":
        text = text.replace(ch, "-")
    text = PAGE_RE.sub(" ", text)
    if join_hyphens:
        text = re.sub(r"(?<=[A-Za-z])-[ \t]*\r?\n\s*(?=[a-z])", "", text)
    else:
        text = re.sub(r"-[ \t]*\r?\n\s*", "-", text)
    return re.sub(r"\s+", " ", text).strip()


def quote_in(quote: str, raw_text: str) -> bool:
    q = normalise(quote)
    q_nows = re.sub(r"\s", "", q)
    for join in (True, False):
        t = normalise(raw_text, join_hyphens=join)
        if q in t or q_nows in re.sub(r"\s", "", t):
            return True
    return False


def split_pages(text: str) -> dict:
    parts = PAGE_RE.split(text)
    if len(parts) == 1:
        return {1: text}
    pages = {}
    for i in range(1, len(parts), 2):
        pages[int(parts[i])] = parts[i + 1]
    return pages


def parse_page_spec(page) -> list | None:
    if page is None or page == "":
        return None
    if isinstance(page, int) and not isinstance(page, bool):
        return [page]
    m = re.fullmatch(r"\s*(\d+)\s*(?:-\s*(\d+))?\s*", str(page))
    if not m:
        raise ValueError(f"unreadable page '{page}'")
    a = int(m.group(1))
    b = int(m.group(2)) if m.group(2) else a
    return list(range(a, b + 1))


def years_in(text) -> set:
    years = set()
    for m in YEAR_RE.finditer(str(text or "")):
        y = int(m.group(1))
        years.add(y)
        if m.group(2):
            years.add(int(str(y)[:2] + m.group(2)))
    return years


def unit_scale(unit) -> float:
    u = str(unit or "").lower()
    for word in ("trillion", "billion", "million", "thousand", "bn", "mn", "tn"):
        if re.search(rf"\b{word}\b", u):
            return SCALE_WORDS[word]
    if "'000" in u or "000s" in u:
        return 1e3
    return 1.0


def unit_is_percent(unit) -> bool:
    return bool(PERCENT_UNIT_RE.search(str(unit or "")))


def currencies_in(text: str) -> set:
    return {code for code, pat in CURRENCIES.items() if re.search(pat, text)}


def families_in(text: str) -> set:
    return {fam for fam, pat in UNIT_FAMILIES.items() if re.search(pat, text)}


@dataclass
class Num:
    text: str
    value: float
    scale: float
    percent: bool
    negative: bool
    is_year: bool
    start: int
    end: int


def find_numbers(text: str) -> list:
    out = []
    for m in NUM_RE.finditer(text):
        raw = m.group("num")
        value = float(raw.replace(",", ""))
        suf = m.group("suf") or ""
        after = text[m.end():m.end() + 40]
        before = text[max(0, m.start() - 12):m.start()]
        scale = 1.0
        percent = suf == "%"
        if suf and suf != "%":
            scale = SCALE_WORDS[suf.lower()]
        else:
            sm = SCALE_AFTER_RE.match(after)
            if sm:
                scale = SCALE_WORDS[sm.group(1).lower()]
            if PCT_AFTER_RE.match(after):
                percent = True
        is_year = (re.fullmatch(r"\d{4}", raw) is not None and 1900 <= value <= 2100
                   and not suf and scale == 1.0 and not percent and not m.group("sign")
                   and not CURRENCY_BEFORE_RE.search(before)
                   and not UNIT_NOUN_AFTER_RE.match(after))
        sign = bool(m.group("sign"))
        if sign and m.start() > 0 and not (text[m.start() - 1].isspace() or text[m.start() - 1] in "([:="):
            sign = False  # a hyphen straight after another token is a range ("17%-59%"), not a minus
        out.append(Num(raw, value, scale, percent, sign, is_year, m.start(), m.end()))
    return out


def close(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-9)


def number_matches_value(n: Num, value: float, unit, rounding=None, abs_value=False) -> bool:
    """True if a number in text is a declared-equivalent form of a claim value.

    Equivalent forms: thousands separators (1,000 / 1000) and scale words that
    give the same magnitude ("13.2 billion" / "13,200 million"). When `rounding`
    is given (derived and model claims), the value rounded to that many decimals
    is also accepted. A claim whose unit is a share or fraction (0.369) may be
    written as a percentage (36.9 percent), to the claim's rounding less two places.
    """
    v = abs(value) if abs_value else value
    cand = n.value if (abs_value or not n.negative) else -n.value
    uscale = unit_scale(unit)
    targets = [v]
    if rounding is not None:
        targets.append(round(v, int(rounding)))
    if n.percent and str(unit or "").lower().startswith(("share", "fraction")):
        pct = [v * 100]
        if rounding is not None:
            pct.append(round(v * 100, max(0, int(rounding) - 2)))
        if any(close(cand, t) for t in pct):
            return True
    for t in targets:
        if n.scale == 1.0:
            if close(cand, t):
                return True
        elif close(cand * n.scale, t * uscale):
            return True
    return False


def numeric(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    # Space as thousands separator, as printed in IPCC tables ("74 100"); strict three-digit groups only.
    if isinstance(value, str) and re.fullmatch(r"\d{1,3}(?: \d{3})+(?:\.\d+)?", value.strip()):
        return float(value.replace(" ", ""))
    return None


# --------------------------------------------------------------------------- chapter parsing

@dataclass
class Unit:
    chapter: str
    line: int
    text: str       # sentence or table cell, tags included
    context: str    # text used for label checks (sentence, or cell + header + caption)


def strip_comments(text: str) -> str:
    return re.sub(r"<!--.*?-->", lambda m: "\n" * m.group().count("\n"), text, flags=re.S)


def split_sentences(paragraph: str) -> list:
    protected = paragraph
    for ab in ABBREVIATIONS:
        protected = protected.replace(ab + " ", ab.replace(".", "\x00") + " ")
    parts = re.split(r"(?<=[.!?])\s+(?=[\"'(\[]?[A-Z0-9{])", protected)
    sentences = []
    for p in parts:
        p = p.replace("\x00", ".")
        lead = re.match(r"^((?:\{\{[^{}]*\}\}\s*)+)(.*)$", p, re.S)
        if lead and sentences:
            sentences[-1] = sentences[-1] + " " + lead.group(1).strip()
            p = lead.group(2)
        if p.strip():
            sentences.append(p.strip())
    return sentences


def parse_chapter(name: str, text: str) -> list:
    text = strip_comments(text)
    lines = text.splitlines()
    units = []
    in_code = False
    para, para_start = [], 0
    last_para_text = ""

    def flush():
        nonlocal para, last_para_text
        if para:
            joined = " ".join(para)
            for s in split_sentences(joined):
                units.append(Unit(name, para_start, s, s))
            last_para_text = joined
        para = []

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("```") or line.startswith("~~~"):
            flush()
            in_code = not in_code
            i += 1
            continue
        if in_code:
            i += 1
            continue
        if not line:
            flush()
            i += 1
            continue
        if line.startswith("#") or FIG_RE.match(line):
            flush()
            last_para_text = ""
            i += 1
            continue
        if line.startswith("|"):
            flush()
            caption = last_para_text if re.match(r"^\**Table\b", last_para_text) else ""
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append((i + 1, lines[i].strip()))
                i += 1
            header = ""
            for idx, (ln, row) in enumerate(rows):
                cells = [c.strip() for c in row.strip("|").split("|")]
                if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                    continue
                if idx == 0:
                    header = " ".join(cells)
                for c in cells:
                    if c:
                        units.append(Unit(name, ln, c, f"{c} {header} {caption}"))
            last_para_text = ""
            continue
        m = re.match(r"^(?:>\s*)?(?:[-*+]\s+|\d+[.)]\s+)(.*)$", line)
        if m:
            flush()
            para_start = i + 1
            para = [m.group(1)]
            i += 1
            continue
        if not para:
            para_start = i + 1
        para.append(re.sub(r"^>\s*", "", line))
        i += 1
    flush()
    return units


def mask_for_numbers(text: str, allow_phrases: list) -> str:
    def blank(m):
        return " " * len(m.group())
    t = ANY_TAG_RE.sub(blank, text)
    t = re.sub(r"\]\([^)]*\)", blank, t)
    t = re.sub(r"https?://\S+", blank, t)
    for phrase in allow_phrases:
        t = t.replace(phrase, " " * len(phrase))
    t = AUTO_LABEL_RE.sub(blank, t)
    t = YEAR_RANGE_RE.sub(blank, t)
    t = re.sub(r"\b[QH][1-4]\b", blank, t)
    return t


# --------------------------------------------------------------------------- project

class Project:
    def __init__(self, root: Path, today: dt.date | None = None):
        self.root = root
        self.today = today or dt.date.today()
        self.issues: list[Issue] = []
        d = root / "data"
        self.sources = load_yaml_list(d / "sources.yaml", self.issues, 1)
        self.claims = load_yaml_list(d / "claims.yaml", self.issues, 4)
        self.conflicts = load_yaml_list(d / "conflicts.yaml", self.issues, 9)
        self.allowlist = load_yaml_list(d / "allowlist.yaml", self.issues, 11)
        self.assumptions = load_yaml_list(d / "assumptions.yaml", self.issues, 19)
        self.source_by_id = {}
        for s in self.sources:
            self.source_by_id.setdefault(s.get("id"), s)
        self.claim_by_id = {}
        for c in self.claims:
            self.claim_by_id.setdefault(c.get("id"), c)
        self.assumption_by_id = {a.get("id"): a for a in self.assumptions}
        self._texts = {}
        self._model_cache = {}

    # ---- utilities
    def add(self, check, level, where, msg):
        self.issues.append(Issue(check, level, str(where), msg))

    def text_for(self, source):
        sid = source.get("id")
        if sid not in self._texts:
            tp = source.get("text_path")
            p = self.root / tp if tp else None
            self._texts[sid] = p.read_text(encoding="utf-8", errors="replace") if p and p.exists() else None
        return self._texts[sid]

    @staticmethod
    def kind(cid) -> str:
        return str(cid)[:1]

    @staticmethod
    def formula_refs(c) -> list:
        return [f"{k}-{n}" for k, n in ID_REF_RE.findall(str(c.get("formula", "")))]

    def claim_tier(self, cid, seen=None):
        c = self.claim_by_id.get(cid)
        if not c:
            return None
        k = self.kind(cid)
        if k == "C":
            s = self.source_by_id.get(c.get("source_id"))
            return s.get("tier") if s else None
        if k == "D":
            seen = seen if seen is not None else set()
            if cid in seen:
                return None
            seen.add(cid)
            tiers = [5 if r.startswith("A-") else (self.claim_tier(r, seen) or 5) for r in self.formula_refs(c)]
            return max(tiers) if tiers else None
        return None

    def claim_basis(self, cid, seen=None) -> set:
        c = self.claim_by_id.get(cid)
        if not c:
            return set()
        if c.get("basis"):
            return {c["basis"]}
        if self.kind(cid) == "D":
            seen = seen if seen is not None else set()
            if cid in seen:
                return set()
            seen.add(cid)
            out = set()
            for ref in self.formula_refs(c):
                if not ref.startswith("A-"):
                    out |= self.claim_basis(ref, seen)
            return out - {"actual"}
        return set()

    def base_claims(self, cid, seen=None) -> set:
        """C-claims that a claim ultimately rests on."""
        seen = seen if seen is not None else set()
        if cid in seen:
            return set()
        seen.add(cid)
        c = self.claim_by_id.get(cid)
        if not c:
            return set()
        if self.kind(cid) == "C":
            return {cid}
        out = set()
        if self.kind(cid) == "D":
            for ref in self.formula_refs(c):
                if not ref.startswith("A-"):
                    out |= self.base_claims(ref, seen)
        return out

    # ---- source integrity (1-3)
    def check_sources(self, only: set | None = None):
        seen = set()
        for s in self.sources:
            sid = s.get("id", "<no id>")
            if only is not None and sid not in only:
                continue
            if sid in seen:
                self.add(1, "fail", sid, "duplicate source id")
            seen.add(sid)
            if not re.fullmatch(r"S-\d{3,}", str(sid)):
                self.add(1, "fail", sid, "source id must look like S-001")
            obtained = s.get("local_path") not in (None, "")
            for f in SOURCE_REQUIRED:
                if f not in s:
                    self.add(1, "fail", sid, f"missing field '{f}'")
                elif s[f] in (None, "") and f != "notes" and not (
                        not obtained and f in SOURCE_NULLABLE_IF_NOT_OBTAINED):
                    self.add(1, "fail", sid, f"field '{f}' is empty")
            if s.get("tier") not in (1, 2, 3, 4, 5):
                self.add(1, "fail", sid, f"tier must be 1 to 5, got {s.get('tier')!r}")
            if obtained and s.get("extraction") not in ("text", "ocr"):
                self.add(1, "fail", sid, "extraction must be 'text' or 'ocr'")
            if not obtained:
                continue
            p = self.root / s["local_path"]
            if not p.exists():
                self.add(2, "fail", sid, f"stored file missing: {s['local_path']}")
            elif not s.get("sha256") or sha256_file(p) != str(s["sha256"]).lower():
                self.add(2, "fail", sid, "SHA-256 of stored file does not match the register")
            tp = s.get("text_path")
            if not tp or not (self.root / tp).exists():
                self.add(3, "fail", sid, f"extracted text file missing: {tp}")

    # ---- claim integrity (4-9)
    def check_claim(self, c):
        cid = str(c.get("id", "<no id>"))
        k = self.kind(cid)
        if not re.fullmatch(r"[CDM]-\d{4,}", cid):
            self.add(4, "fail", cid, "claim id must look like C-0001, D-0001 or M-0001")
            return
        status = c.get("status")
        if status not in STATUSES:
            self.add(4, "fail", cid, f"status must be one of {sorted(STATUSES)}")
        if status == "superseded":
            if not c.get("superseded_by") or c.get("superseded_by") not in self.claim_by_id:
                self.add(4, "fail", cid, "superseded claim needs superseded_by pointing to an existing claim")
            return
        if k == "D":
            self.check_derived(c)
            return
        if k == "M":
            for f in MODEL_REQUIRED:
                if f not in c or (c[f] in (None, "") and not (f == "rounding" and c.get(f) == 0)):
                    self.add(4, "fail", cid, f"missing field '{f}'")
            if c.get("scenario") not in SCENARIOS:
                self.add(4, "fail", cid, "scenario must be low, base or high")
            if status != "illustrative":
                self.add(4, "fail", cid, "model outputs must have status 'illustrative'")
            return
        open_ = status in OPEN_STATUSES
        for f in CLAIM_REQUIRED:
            if f not in c:
                self.add(4, "fail", cid, f"missing field '{f}'")
            elif c[f] in (None, "") and not (open_ and f in CLAIM_NULLABLE_IF_OPEN):
                self.add(4, "fail", cid, f"field '{f}' is empty")
        if c.get("basis") not in BASES:
            self.add(4, "fail", cid, f"basis must be one of {sorted(BASES)}")
        if not isinstance(c.get("fact_checked"), bool):
            self.add(4, "fail", cid, "fact_checked must be true or false")
        if open_:
            return
        src = self.source_by_id.get(c.get("source_id"))
        if not src:
            self.add(4, "fail", cid, f"source {c.get('source_id')} not in source register")
            return
        if not src.get("local_path"):
            self.add(4, "fail", cid, f"source {src.get('id')} has not been obtained; its figures cannot be used")
            return
        text = self.text_for(src)
        if text is None:
            return  # reported by check 3
        # ---- check 5: quote on page
        try:
            pages = parse_page_spec(c.get("page"))
        except ValueError as exc:
            self.add(5, "fail", cid, str(exc))
            return
        quote = str(c.get("quote") or "")
        if len(normalise(quote)) < 12:
            self.add(5, "fail", cid, "quote too short to be unambiguous (minimum 12 characters)")
            return
        page_map = split_pages(text)
        if pages is None:
            haystack = text
            if len(page_map) > 1:
                self.add(5, "warn", cid, "no page given for a multi-page source")
        else:
            missing = [p for p in pages if p not in page_map]
            if missing:
                self.add(5, "fail", cid, f"page {c.get('page')} not in extracted text (it has {len(page_map)} pages)")
                return
            haystack = "\n".join(page_map[p] for p in pages)
        context = str(c.get("quote_context") or "")
        if context and not quote_in(context, haystack):
            self.add(5, "fail", cid, f"quote_context not found on page {c.get('page')} of {src.get('id')}")
            return
        if not quote_in(quote, haystack):
            elsewhere = [p for p, t in page_map.items() if quote_in(quote, t)] if pages else []
            hint = f"; it does appear on page(s) {elsewhere}" if elsewhere else ""
            self.add(5, "fail", cid, f"quote not found in {src.get('id')} on page {c.get('page')}{hint}")
            return
        ocr_pages = src.get("ocr_pages")
        on_ocr_page = src.get("extraction") == "ocr" and (
            not ocr_pages or pages is None or any(p in ocr_pages for p in pages))
        if on_ocr_page and not c.get("fact_checked"):
            self.add(5, "warn", cid, "cited page is OCR text: the fact-checker must confirm the figure "
                     f"against the page image in sources/text/{src.get('id')}_pages/")
        # ---- check 6: value in quote
        nq = normalise(quote)
        if str(src.get("local_path", "")).lower().endswith((".csv", ".zip")):
            # tabular sources: commas separate fields, never thousands
            nq = nq.replace(",", " | ")
        value = c.get("value")
        nv = numeric(value)
        matched = None
        if nv is not None and isinstance(value, str):
            # space-grouped value such as "74 100": must appear verbatim, not inside a longer number
            if not re.search(rf"(?<![\d.,]){re.escape(normalise(value))}(?![\d]|[.,]\d)", nq):
                self.add(6, "fail", cid, f"value '{value}' does not appear in the quote")
                return
        elif nv is None:
            if value in (None, ""):
                self.add(6, "fail", cid, "claim has no value")
                return
            if normalise(str(value)).casefold() not in nq.casefold():
                self.add(6, "fail", cid, f"value '{value}' does not appear in the quote")
                return
        else:
            nums = find_numbers(nq)
            matched = next((n for n in nums if number_matches_value(n, nv, c.get("unit"))), None)
            if matched is None and nv < 0 and c.get("sign_in_words"):
                matched = next((n for n in nums if number_matches_value(n, nv, c.get("unit"), abs_value=True)), None)
            if matched is None:
                shown = ", ".join(n.text + ("%" if n.percent else "") for n in nums[:8]) or "none"
                self.add(6, "fail", cid, f"value {value} {c.get('unit')} not found in the quote (numbers in quote: {shown})")
                return
        # ---- check 7: period and unit
        qyears = years_in(nq)
        cyears = years_in(c.get("period", ""))
        if qyears and cyears and not (qyears & cyears):
            self.add(7, "fail", cid, f"period '{c.get('period')}' not consistent with years in quote {sorted(qyears)}")
        if matched is not None:
            unit = str(c.get("unit") or "")
            window = nq[max(0, matched.start - 16):matched.end + 30]
            ctx_norm = normalise(context) if context else ""
            qc, uc = currencies_in(window + " " + ctx_norm), currencies_in(unit)
            if qc and uc and not (qc & uc):
                self.add(7, "fail", cid, f"unit '{unit}' conflicts with currency in quote {sorted(qc)}")
            if unit_is_percent(unit) and not matched.percent and not PERCENT_UNIT_RE.search(nq + " " + ctx_norm):
                self.add(7, "fail", cid, f"unit '{unit}' is a percentage but the quote states no percentage")
            if matched.percent and not unit_is_percent(unit):
                self.add(7, "fail", cid, f"quote states a percentage but unit is '{unit}'")
            qf = families_in(nq[matched.end:matched.end + 30])
            uf = families_in(unit)
            if qf and uf and not (qf & uf):
                self.add(7, "fail", cid, f"unit '{unit}' conflicts with unit in quote ({', '.join(sorted(qf))})")
            elif qf and not uf and uc:
                self.add(7, "fail", cid, f"quote gives a physical unit ({', '.join(sorted(qf))}) but unit is '{unit}'")

    def eval_ref(self, ref, stack=()):
        if ref in stack:
            raise ValueError(f"circular formula through {ref}")
        if ref.startswith("A-"):
            a = self.assumption_by_id.get(ref)
            v = numeric(a.get("value")) if a else None
            if v is None:
                raise ValueError(f"assumption {ref} missing or not numeric")
            return v
        c = self.claim_by_id.get(ref)
        if not c:
            raise ValueError(f"unknown claim {ref}")
        if self.kind(ref) == "D":
            return self.eval_formula(c.get("formula", ""), stack + (ref,))
        v = numeric(c.get("value"))
        if v is None:
            raise ValueError(f"claim {ref} has no numeric value")
        return v

    def eval_formula(self, formula: str, stack=()):
        expr = ID_REF_RE.sub(lambda m: f"__{m.group(1)}_{m.group(2)}", str(formula))
        tree = ast.parse(expr, mode="eval")
        funcs = {"sum": sum, "min": min, "max": max, "abs": abs}

        def ev(node):
            if isinstance(node, ast.Expression):
                return ev(node.body)
            if isinstance(node, ast.BinOp):
                a, b = ev(node.left), ev(node.right)
                if isinstance(node.op, ast.Add):
                    return a + b
                if isinstance(node.op, ast.Sub):
                    return a - b
                if isinstance(node.op, ast.Mult):
                    return a * b
                if isinstance(node.op, ast.Div):
                    return a / b
                if isinstance(node.op, ast.Pow):
                    return a ** b
                raise ValueError("operator not allowed")
            if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
                v = ev(node.operand)
                return -v if isinstance(node.op, ast.USub) else v
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
                return float(node.value)
            if isinstance(node, ast.Name) and node.id.startswith("__"):
                kind, _, num = node.id[2:].partition("_")
                return self.eval_ref(f"{kind}-{num}", stack)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in funcs:
                args = [ev(a) for a in node.args]
                if len(args) == 1 and isinstance(args[0], list):
                    args = args[0]
                return float(funcs[node.func.id](args) if node.func.id != "abs" else abs(args[0]))
            if isinstance(node, (ast.List, ast.Tuple)):
                return [ev(e) for e in node.elts]
            raise ValueError(f"formula element not allowed: {type(node).__name__}")
        return ev(tree)

    def check_derived(self, c):
        cid = c["id"]
        for f in DERIVED_REQUIRED:
            if f not in c or (c[f] in (None, "") and not (f == "rounding" and c.get(f) == 0)):
                self.add(4, "fail", cid, f"missing field '{f}'")
        refs = self.formula_refs(c)
        if not refs:
            self.add(8, "fail", cid, "formula references no claims")
            return
        for r in refs:
            known = self.assumption_by_id if r.startswith("A-") else self.claim_by_id
            if r not in known:
                self.add(8, "fail", cid, f"formula references unknown {'assumption' if r.startswith('A-') else 'claim'} {r}")
                return
        try:
            computed = self.eval_formula(c.get("formula", ""), (cid,))
        except (ValueError, SyntaxError, ZeroDivisionError, TypeError) as exc:
            self.add(8, "fail", cid, f"cannot evaluate formula: {exc}")
            return
        v = numeric(c.get("value"))
        r = c.get("rounding", 0)
        if v is None or not isinstance(r, int) or isinstance(r, bool):
            self.add(8, "fail", cid, "value must be numeric and rounding an integer number of decimals")
            return
        if abs(computed - v) > 0.5 * 10 ** (-r) + 1e-9:
            self.add(8, "fail", cid, f"formula gives {computed:.6g}, register states {v} (rounding {r})")
        statuses = {"assumption" if ref.startswith("A-") else self.claim_by_id[ref].get("status") for ref in refs}
        if c.get("status") == "verified" and statuses - {"verified"}:
            self.add(8, "fail", cid, f"status 'verified' but inputs include {sorted(str(s) for s in statuses - {'verified'})}")

    def check_duplicates(self):
        seen = set()
        for c in self.claims:
            cid = c.get("id")
            if cid in seen:
                self.add(9, "fail", cid, "duplicate claim id")
            seen.add(cid)
        allowed_pairs = set()
        for x in self.conflicts:
            xid = x.get("id", "<no id>")
            ids = x.get("claims") or []
            for f in ("id", "claims", "used", "resolution"):
                if not x.get(f):
                    self.add(9, "fail", xid, f"conflict entry missing '{f}'")
            for i in ids:
                if i not in self.claim_by_id:
                    self.add(9, "fail", xid, f"conflict lists unknown claim {i}")
            if x.get("used") and x.get("used") not in ids:
                self.add(9, "fail", xid, "'used' must be one of the listed claims")
            allowed_pairs |= {(a, b) for a in ids for b in ids}
        groups = {}
        for c in self.claims:
            if self.kind(c.get("id")) != "C" or c.get("status") in OPEN_STATUSES | {"superseded"}:
                continue
            nv = numeric(c.get("value"))
            key = (re.sub(r"\s+", " ", str(c.get("measure", ""))).strip().lower(),
                   str(c.get("period", "")).strip().lower())
            val = nv * unit_scale(c.get("unit")) if nv is not None else c.get("value")
            groups.setdefault(key, []).append((c["id"], val))
        for (measure, period), items in groups.items():
            for i in range(len(items)):
                for j in range(i + 1, len(items)):
                    (a, va), (b, vb) = items[i], items[j]
                    same = close(va, vb) if isinstance(va, float) and isinstance(vb, float) else va == vb
                    if not same and (a, b) not in allowed_pairs:
                        self.add(9, "fail", f"{a}/{b}", f"same measure '{measure}' and period '{period}' "
                                 "with different values; record in data/conflicts.yaml")

    # ---- report integrity (10-18, 22)
    def chapter_files(self, only: list | None = None) -> list:
        d = self.root / "report" / "chapters"
        files = sorted(d.glob("*.md")) if d.exists() else []
        if only is not None:
            wanted = {str(Path(p).resolve()).lower() for p in only}
            files = [f for f in files if str(f.resolve()).lower() in wanted]
        return files

    def allow_phrases(self) -> list:
        phrases = []
        for a in self.allowlist:
            if not a.get("phrase") or not a.get("reason"):
                self.add(11, "fail", "allowlist.yaml", f"entry {a} needs 'phrase' and 'reason'")
            else:
                phrases.append(str(a["phrase"]))
        return sorted(phrases, key=len, reverse=True)

    def check_chapters(self, files: list, final: bool) -> set:
        phrases = self.allow_phrases()
        used = set()
        for f in files:
            raw = f.read_text(encoding="utf-8")
            name = f.name
            self.lint(name, raw)
            if CANNOT_CONFIRM in raw:
                self.add(10, "fail" if final else "warn", name,
                         f"contains '{CANNOT_CONFIRM}'" + ("; not allowed in the final build" if final else ""))
            is_exec = bool(re.search(r"exec(utive)?_summary", name))
            for u in parse_chapter(name, raw):
                where = f"{name}:{u.line}"
                for m in ANY_TAG_RE.finditer(u.text):
                    if not TAG_RE.fullmatch(m.group()):
                        self.add(10, "fail", where, f"malformed claim tag '{m.group()}'")
                tags = TAG_RE.findall(u.text)
                claims = []
                for t in tags:
                    c = self.claim_by_id.get(t)
                    if not c:
                        self.add(10, "fail", where, f"tag {t} does not resolve to a claim")
                        continue
                    claims.append(c)
                    used.add(t)
                    st = c.get("status")
                    if st == "superseded":
                        self.add(10, "fail", where, f"{t} is superseded by {c.get('superseded_by')}")
                    if st in OPEN_STATUSES:
                        self.add(10, "fail" if final else "warn", where, f"{t} has status '{st}'")
                    self.label_checks(where, u, t, c)
                    if is_exec and self.kind(t) in "CD":
                        tier = self.claim_tier(t)
                        if tier not in (1, 2):
                            self.add(16, "fail", where, f"{t} rests on a Tier {tier} source; "
                                     "executive summary figures must be Tier 1 or 2")
                for n in find_numbers(mask_for_numbers(u.text, phrases)):
                    if n.is_year:
                        continue
                    if not claims:
                        self.add(11, "fail", where, f"number '{n.text}' has no claim tag and is not allowlisted: \"{u.text[:90]}\"")
                    elif not any(self.claim_covers_number(c, n) for c in claims):
                        self.add(12, "fail", where, f"number '{n.text}' matches none of the tagged claims {tags}")
        return used

    def check_figures(self, files: list, final: bool):
        """Check 23: the figure register (data/figures.yaml) and the {{FIG n.n}} markers in chapters."""
        path = self.root / "data" / "figures.yaml"
        figs = load_yaml_list(path, self.issues, 23) if path.exists() else []
        by_id = {}
        for f in figs:
            fid = str(f.get("id"))
            by_id[fid] = f
            where = f"figure {fid}"
            if not f.get("file") or not (self.root / f["file"]).exists():
                self.add(23, "fail", where, f"image file missing: {f.get('file')}")
            if not f.get("source_line"):
                self.add(23, "fail", where, "no source line")
            claims = []
            for cid in f.get("claims") or []:
                c = self.claim_by_id.get(cid)
                if not c:
                    self.add(23, "fail", where, f"uses {cid}, which is not in the claim register")
                    continue
                claims.append(c)
                if c.get("status") == "superseded":
                    self.add(23, "fail", where, f"uses superseded claim {cid}")
                if final and c.get("fact_checked") is not True and self.kind(cid) == "C":
                    self.add(23, "fail", where, f"uses {cid}, not passed by the fact-checker")
            if f.get("model_outputs"):
                if f.get("scenario") not in ("low", "base", "high"):
                    self.add(23, "fail", where, "model outputs used without a scenario name")
                else:
                    try:
                        out = self.model_compute(f["scenario"])
                        for k in f["model_outputs"]:
                            if k not in out:
                                self.add(23, "fail", where, f"model output '{k}' not produced by the model")
                    except Exception as exc:  # noqa: BLE001
                        self.add(23, "fail", where, f"model could not be run: {exc}")
            for field in ("title", "note"):
                for n in find_numbers(mask_for_numbers(str(f.get(field) or ""), self.allow_phrases())):
                    if n.is_year:
                        continue
                    if not any(self.claim_covers_number(c, n) for c in claims):
                        self.add(23, "fail", where, f"number '{n.text}' in the {field} matches none of the figure's claims")
        for ch in files:
            for ln, line in enumerate(ch.read_text(encoding="utf-8").splitlines(), 1):
                m = FIG_RE.match(line.strip())
                if m and m.group(1) not in by_id:
                    self.add(23, "fail", f"{ch.name}:{ln}", f"figure {m.group(1)} is not in data/figures.yaml")
                elif "{{" in line and "FIG" in line and not m:
                    self.add(23, "fail", f"{ch.name}:{ln}", "figure marker must stand alone on its line as {{FIG n.n}}")

    def claim_covers_number(self, c, n: Num) -> bool:
        rounding = c.get("rounding") if self.kind(c.get("id")) in ("D", "M") else None
        nv = numeric(c.get("value"))
        if nv is not None and number_matches_value(
                n, nv, c.get("unit"), rounding, abs_value=bool(c.get("sign_in_words"))):
            return True
        forms = c.get("display") or []
        forms = [forms] if isinstance(forms, str) else list(forms)
        if nv is None and c.get("value") not in (None, ""):
            forms.append(str(c.get("value")))
        for form in forms:
            for fn in find_numbers(str(form)):
                if close(fn.value * fn.scale, n.value * n.scale):
                    return True
        return False

    def label_checks(self, where, u: Unit, t, c):
        ctx = u.context
        st = c.get("status")
        if st == "estimate" and not ESTIMATE_RE.search(ctx):
            self.add(13, "fail", where, f"{t} is an estimate; the sentence must say 'estimated'")
        if st == "illustrative" and not ILLUSTRATIVE_RE.search(ctx):
            self.add(13, "fail", where, f"{t} is illustrative; the sentence must say 'illustrative'")
        basis = self.claim_basis(t)
        if "projection" in basis and not PROJECTION_RE.search(ctx):
            self.add(14, "fail", where, f"{t} is a projection; the sentence must say 'projected' or 'projection'")
        if "target" in basis and not TARGET_RE.search(ctx):
            self.add(14, "fail", where, f"{t} is a target; the sentence must say 'target'")
        if "estimate" in basis and st != "estimate" and not ESTIMATE_RE.search(ctx):
            self.add(14, "fail", where, f"{t} has basis 'estimate'; the sentence must say 'estimated'")
        if self.kind(t) in ("C", "D"):
            tier = self.claim_tier(t)
            if tier in (4, 5):
                pubs = [str(self.source_by_id.get(self.claim_by_id[b].get("source_id"), {}).get("publisher", ""))
                        for b in self.base_claims(t)]
                if not ATTRIBUTION_RE.search(ctx) and not any(p and p.lower() in ctx.lower() for p in pubs):
                    self.add(15, "fail", where, f"{t} is Tier {tier}; the sentence must attribute it "
                             "(for example 'according to industry estimates')")
            for b in self.base_claims(t):
                ys = years_in(self.claim_by_id[b].get("period", ""))
                if ys and max(ys) < self.today.year - 5:
                    self.add(17, "warn", where, f"{b} is data for {self.claim_by_id[b].get('period')}, more than five years old")
        if self.kind(t) == "M":
            if not MODEL_LABEL_RE.search(ctx):
                self.add(22, "fail", where, f"{t} is a model output; label it 'modelled estimate' or 'scenario'")
            sc = str(c.get("scenario", ""))
            if not re.search(rf"\b{re.escape(sc)}\b", ctx, re.I):
                self.add(22, "fail", where, f"{t} must name its scenario ('{sc}')")

    def lint(self, name, raw):
        text = strip_comments(raw)
        text = re.sub(r"```.*?```", lambda m: "\n" * m.group().count("\n"), text, flags=re.S)
        for i, line in enumerate(text.splitlines(), 1):
            where = f"{name}:{i}"
            body = ANY_TAG_RE.sub("", line)
            if "—" in body:
                self.add(18, "fail", where, "em-dash; rewrite the sentence")
            for m in re.finditer("–", body):
                prev, nxt = body[m.start() - 1:m.start()], body[m.end():m.end() + 1]
                if not (prev.isdigit() and nxt.isdigit()):
                    self.add(18, "fail", where, "en-dash used as a dash; rewrite the sentence")
            stripped = re.sub(r"^\s*(?:[-*+]|\|)\s+", "", body)
            for m in re.finditer(r"(\S)\s+--?\s+(\S)", stripped):
                if not (m.group(1).isdigit() and m.group(2).isdigit()) and not stripped.lstrip().startswith("|"):
                    self.add(18, "fail", where, "spaced hyphen used as a dash; rewrite the sentence")
                    break
            if re.search(r"\w--\w", body):
                self.add(18, "fail", where, "double hyphen used as a dash")
        flat = re.sub(r"\s+", " ", text)
        for pat in FORMULAIC:
            for m in re.finditer(pat, flat, re.I):
                self.add(18, "warn", name, f"formulaic construction: '{m.group()[:60]}'")

    # ---- model integrity (19-21)
    def check_model_static(self):
        for a in self.assumptions:
            aid = a.get("id", "<no id>")
            for f in ASSUMPTION_REQUIRED:
                if f not in a:
                    self.add(19, "fail", aid, f"assumption missing field '{f}'")
            v = numeric(a.get("value"))
            rng = a.get("range")
            if v is None:
                self.add(19, "fail", aid, "assumption value must be numeric")
            if not (isinstance(rng, list) and len(rng) == 2 and all(numeric(x) is not None for x in rng)):
                self.add(19, "fail", aid, "range must be [low, high]")
            elif v is not None and not (rng[0] <= v <= rng[1]):
                self.add(19, "fail", aid, f"value {v} outside range {rng}")
            bc = a.get("basis_claim")
            if bc and bc not in self.claim_by_id:
                self.add(19, "fail", aid, f"basis_claim {bc} not in claim register")
            if not isinstance(a.get("approved_by_hassan"), bool):
                self.add(19, "fail", aid, "approved_by_hassan must be true or false")
        mdir = self.root / "model"
        inputs = mdir / "inputs.yaml"
        for e in load_yaml_list(inputs, self.issues, 19):
            ref, nm = e.get("ref"), e.get("name", "<no name>")
            where = f"model input {nm}"
            if not ref:
                self.add(19, "fail", where, "no ref (claim or assumption id)")
            elif str(ref).startswith("A-"):
                if ref not in self.assumption_by_id:
                    self.add(19, "fail", where, f"{ref} not in assumptions.yaml")
            elif ref in self.claim_by_id:
                if self.claim_by_id[ref].get("status") != "verified":
                    self.add(19, "fail", where, f"{ref} is not a verified claim")
            else:
                self.add(19, "fail", where, f"{ref} is neither a claim nor an assumption")
        if not mdir.exists():
            return
        for py in sorted(mdir.rglob("*.py")):
            rel = py.relative_to(self.root).as_posix()
            if "/tests/" in rel or "/outputs/" in rel:
                continue
            src = py.read_text(encoding="utf-8")
            lines = src.splitlines()
            try:
                tree = ast.parse(src)
            except SyntaxError as exc:
                self.add(19, "fail", rel, f"syntax error: {exc}")
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
                        and not isinstance(node.value, bool) and node.value not in (0, 1):
                    line = lines[node.lineno - 1] if node.lineno <= len(lines) else ""
                    if "allow-literal:" not in line:
                        self.add(19, "fail", f"{rel}:{node.lineno}",
                                 f"hard-coded number {node.value!r}; take it from a claim or assumption "
                                 "(or mark a structural constant with '# allow-literal: <reason>')")

    def model_compute(self, scenario):
        if scenario not in self._model_cache:
            engine = self.root / "model" / "engine.py"
            if not engine.exists():
                raise FileNotFoundError("model/engine.py not found")
            spec = importlib.util.spec_from_file_location(f"_gip_engine_{id(self)}", engine)
            mod = importlib.util.module_from_spec(spec)
            sys.path.insert(0, str(self.root))
            try:
                spec.loader.exec_module(mod)
                self._model_cache[scenario] = mod.compute(scenario, root=self.root)
            finally:
                sys.path.pop(0)
        return self._model_cache[scenario]

    def check_model_outputs(self, final: bool, only: set | None = None):
        for c in self.claims:
            cid = str(c.get("id"))
            if self.kind(cid) != "M" or (only is not None and cid not in only) or c.get("status") == "superseded":
                continue
            try:
                out = self.model_compute(c.get("scenario"))
            except Exception as exc:  # noqa: BLE001 - any model error is a failure
                self.add(20, "fail", cid, f"model could not be run: {exc}")
                continue
            entry = out.get(c.get("output_key"))
            if entry is None:
                self.add(20, "fail", cid, f"output '{c.get('output_key')}' not produced by the model")
                continue
            v = numeric(c.get("value"))
            r = int(c.get("rounding") or 0)
            if v is None or abs(entry["value"] - v) > 0.5 * 10 ** (-r) + 1e-9:
                self.add(20, "fail", cid, f"model gives {entry['value']:.6g}, register states {c.get('value')} (rounding {r})")
            unapproved = [a for a in entry.get("depends", [])
                          if self.assumption_by_id.get(a, {}).get("approved_by_hassan") is not True]
            if unapproved:
                self.add(21, "fail" if final else "warn", cid,
                         f"depends on assumptions not approved by Hassan: {', '.join(sorted(unapproved))}")


# --------------------------------------------------------------------------- runner

def changed_chapters(root: Path):
    try:
        out = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all", "--", "report/chapters"],
                             cwd=root, capture_output=True, text=True, timeout=20)
        if out.returncode != 0:
            return None
        files = []
        for line in out.stdout.splitlines():
            path = line[3:].strip().strip('"')
            if " -> " in path:
                path = path.split(" -> ")[1]
            if path.endswith(".md"):
                files.append(str((root / path).resolve()))
        return files
    except Exception:  # noqa: BLE001 - no git: fall back to all chapters
        return None


def write_report(p: Project, mode: str, used: set):
    rep = p.root / "reports" / "verification_report.md"
    rep.parent.mkdir(parents=True, exist_ok=True)
    fails = [i for i in p.issues if i.level == "fail"]
    warns = [i for i in p.issues if i.level == "warn"]
    by_status, by_tier = {}, {}
    for c in p.claims:
        by_status[str(c.get("status"))] = by_status.get(str(c.get("status")), 0) + 1
    for s in p.sources:
        by_tier[str(s.get("tier"))] = by_tier.get(str(s.get("tier")), 0) + 1
    obtained = sum(1 for s in p.sources if s.get("local_path"))
    lines = [
        "# Verification report", "",
        f"- Run: {dt.datetime.now().isoformat(timespec='seconds')}",
        f"- Mode: {mode}",
        f"- Result: {'PASS' if not fails else 'FAIL'}",
        f"- Failures: {len(fails)}",
        f"- Warnings: {len(warns)}",
        f"- Sources registered: {len(p.sources)} (obtained: {obtained})",
        "- Sources by tier: " + (", ".join(f"Tier {k}: {v}" for k, v in sorted(by_tier.items())) or "none"),
        f"- Claims registered: {len(p.claims)}",
        "- Claims by status: " + (", ".join(f"{k}: {v}" for k, v in sorted(by_status.items())) or "none"),
        f"- Claims used in checked chapters: {len(used)}",
        f"- Assumptions: {len(p.assumptions)} (approved by Hassan: "
        f"{sum(1 for a in p.assumptions if a.get('approved_by_hassan') is True)})",
        "",
        "Scope: the verifier proves traceability, meaning each figure appears in the cited source as reported. "
        "It does not prove that the source is correct or was interpreted correctly. That is the role of the "
        "fact-checker subagent and of Hassan's review.",
        "",
    ]
    for title, items in (("Failures", fails), ("Warnings", warns)):
        lines += [f"## {title}", ""]
        if not items:
            lines.append("None.")
        for i in sorted(items, key=lambda x: (x.check, x.where)):
            lines.append(f"- Check {i.check} ({CHECK_NAMES.get(i.check, '')}): `{i.where}`: {i.msg}")
        lines.append("")
    rep.write_text("\n".join(lines), encoding="utf-8")


def run(root: Path, mode: str, claim_id: str | None = None, files: list | None = None,
        today: dt.date | None = None, write: bool = True) -> Project:
    p = Project(root, today=today)
    final = mode == "final"
    used = set()
    if mode == "claim":
        c = p.claim_by_id.get(claim_id)
        if not c:
            p.add(4, "fail", claim_id, "claim not in register")
        else:
            if p.kind(claim_id) == "C" and c.get("source_id"):
                p.check_sources(only={c.get("source_id")})
            p.check_claim(c)
            if p.kind(claim_id) == "M":
                p.check_model_outputs(final=False, only={claim_id})
    else:
        p.check_sources()
        for c in p.claims:
            p.check_claim(c)
        p.check_duplicates()
        p.check_model_static()
        if mode == "hook":
            chosen = changed_chapters(root)
            if chosen is None:
                chosen = [str(f) for f in p.chapter_files()]
            chosen += [str(Path(f).resolve()) for f in (files or [])]
            used = p.check_chapters(p.chapter_files(only=chosen), final=False)
            p.check_figures(p.chapter_files(only=chosen), final=False)
        else:
            used = p.check_chapters(p.chapter_files(), final=final)
            p.check_figures(p.chapter_files(), final=final)
            p.check_model_outputs(final=final)
        if final:
            for cid in sorted(used):
                c = p.claim_by_id.get(cid, {})
                if p.kind(cid) == "C" and c.get("fact_checked") is not True:
                    p.add(10, "fail", cid, "used in the report but not passed by the fact-checker")
                for b in p.base_claims(cid) - {cid}:
                    if p.claim_by_id[b].get("fact_checked") is not True:
                        p.add(10, "fail", cid, f"input {b} not passed by the fact-checker")
    if write:
        write_report(p, mode if mode != "claim" else f"claim {claim_id}", used)
    return p


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--all", action="store_true")
    g.add_argument("--claim", metavar="ID")
    g.add_argument("--hook", action="store_true")
    g.add_argument("--final", action="store_true")
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--files", nargs="*", help="extra chapter files to check in --hook mode")
    ap.add_argument("--today", help="override today's date (YYYY-MM-DD), for tests")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    mode = "all" if a.all else "claim" if a.claim else "hook" if a.hook else "final"
    today = dt.date.fromisoformat(a.today) if a.today else None
    p = run(Path(a.root).resolve(), mode, claim_id=a.claim, files=a.files, today=today)
    fails = [i for i in p.issues if i.level == "fail"]
    warns = [i for i in p.issues if i.level == "warn"]
    if fails:
        print(f"VERIFY FAILED ({mode}): {len(fails)} failure(s), {len(warns)} warning(s). "
              "Full list in reports/verification_report.md", file=sys.stderr)
        for i in fails[:60]:
            print("  " + i.line(), file=sys.stderr)
        if len(fails) > 60:
            print(f"  ... and {len(fails) - 60} more", file=sys.stderr)
        return 2
    if not a.quiet:
        print(f"VERIFY PASSED ({mode}): 0 failures, {len(warns)} warning(s).")
        for i in warns[:30]:
            print("  " + i.line())
    return 0


if __name__ == "__main__":
    sys.exit(main())
