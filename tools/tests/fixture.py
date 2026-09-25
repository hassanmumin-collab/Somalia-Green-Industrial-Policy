"""Builds a small, self-contained project that passes every verifier check.

Each test copies this baseline, breaks exactly one thing, and checks that the
right check fails. The baseline itself is the passing fixture for every check.
All source text here is invented test data, not real statistics.
"""
from __future__ import annotations

import copy
import hashlib
import shutil
import tempfile
from pathlib import Path

import yaml

TEXT_S001 = """=== PAGE 1 ===
Somalia National Bureau of Statistics
Test release
=== PAGE 2 ===
Nominal GDP at current prices reached US$13.2 billion in 2025, according to the rebased es-
timates. Livestock exports were 5.4 million head in 2024.
The inflation rate was 4.2 percent in 2025.
=== PAGE 3 ===
The ﬁnal “official” ﬁgures show sesame exports of 45,000 tonnes in 2023.
"""
TEXT_S002 = """=== PAGE 1 ===
Industry sources estimate diesel generation costs of USD 0.35 per kWh in Mogadishu in 2025.
"""
TEXT_S003 = """=== PAGE 1 ===
Real GDP growth is projected at 4.0 percent in 2026.
"""


def source(sid, title, publisher, tier, text_name):
    return {
        "id": sid, "title": title, "publisher": publisher, "date_published": "2026",
        "url": f"https://example.org/{sid}", "accessed": "2026-09-23",
        "local_path": f"sources/raw/{sid}.txt", "text_path": f"sources/text/{text_name}",
        "sha256": None, "tier": tier, "language": "en", "coverage": "national",
        "extraction": "text", "notes": "",
    }


def claim(cid, statement, value, unit, period, measure, basis, sid, page, quote, status="verified"):
    return {
        "id": cid, "statement": statement, "value": value, "unit": unit, "period": period,
        "measure": measure, "basis": basis, "source_id": sid, "page": page, "quote": quote,
        "status": status, "verified_at": "2026-09-23", "fact_checked": True,
    }


BASE = {
    "texts": {"S-001.txt": TEXT_S001, "S-002.txt": TEXT_S002, "S-003.txt": TEXT_S003},
    "sources": [
        source("S-001", "Test GDP Release", "Test Bureau of Statistics", 1, "S-001.txt"),
        source("S-002", "Test Industry Note", "Test Industry Association", 4, "S-002.txt"),
        source("S-003", "Test Staff Report", "Test Fund", 2, "S-003.txt"),
    ],
    "claims": [
        claim("C-0001", "Nominal GDP 2025", 13.2, "USD billion", "2025", "GDP at current prices",
              "actual", "S-001", 2, "Nominal GDP at current prices reached US$13.2 billion in 2025"),
        claim("C-0002", "Livestock exports 2024", 5.4, "million head", "2024", "livestock exports, head",
              "actual", "S-001", 2, "Livestock exports were 5.4 million head in 2024"),
        claim("C-0003", "Sesame exports 2023", 45000, "tonnes", "2023", "sesame exports, volume",
              "actual", "S-001", 3, "The final \"official\" figures show sesame exports of 45,000 tonnes in 2023"),
        claim("C-0004", "Diesel generation cost", 0.35, "USD per kWh", "2025", "diesel generation cost",
              "estimate", "S-002", 1, "Industry sources estimate diesel generation costs of USD 0.35 per kWh",
              status="estimate"),
        claim("C-0005", "Real GDP growth 2026", 4.0, "percent", "2026", "real GDP growth",
              "projection", "S-003", 1, "Real GDP growth is projected at 4.0 percent in 2026"),
        claim("C-0006", "Inflation 2025", 4.2, "percent", "2025", "CPI inflation",
              "actual", "S-001", 2, "The inflation rate was 4.2 percent in 2025"),
        {"id": "D-0001", "statement": "GDP 2025 in USD million", "formula": "C-0001 * 1000",
         "value": 13200, "unit": "USD million", "rounding": 0, "status": "verified"},
        {"id": "M-0001", "statement": "Value added 2032, base", "output_key": "base/total/value_added/2032",
         "scenario": "base", "value": 2.5, "unit": "USD million", "rounding": 1, "status": "illustrative"},
    ],
    "assumptions": [
        {"id": "A-001", "parameter": "Value-added ratio", "value": 0.25, "unit": "share",
         "range": [0.2, 0.3], "basis_claim": None, "comparator": "Test country, 2020",
         "rationale": "test", "approved_by_hassan": True},
        {"id": "A-002", "parameter": "Gross output", "value": 10, "unit": "USD million",
         "range": [8, 12], "basis_claim": None, "comparator": "Test", "rationale": "test",
         "approved_by_hassan": True},
    ],
    "conflicts": [],
    "allowlist": [{"phrase": "Article 6", "reason": "Name of a Paris Agreement article, not a figure"}],
    "model_inputs": [
        {"name": "va_ratio", "ref": "A-001"},
        {"name": "gross_output", "ref": "A-002"},
        {"name": "gdp_2025", "ref": "C-0001"},
    ],
    "engine": '''"""Test model engine."""
from pathlib import Path
import yaml


def compute(scenario, root):
    a = {x["id"]: x for x in yaml.safe_load((Path(root) / "data" / "assumptions.yaml").read_text())}
    value = a["A-002"]["value"] * a["A-001"]["value"]
    return {f"{scenario}/total/value_added/2032": {"value": value, "depends": ["A-001", "A-002"]}}
''',
    "chapters": {
        "00_executive_summary.md": """# Executive summary

Somalia's nominal GDP reached USD 13.2 billion in 2025 {{C-0001}}.
""",
        "01_part1.md": """# Part 1: Why Somalia needs a green industrial policy

## 1.1 Baseline

Somalia's nominal GDP reached USD 13.2 billion in 2025 {{C-0001}}. Expressed in millions, this is USD 13,200 million {{D-0001}}. Livestock exports were 5.4 million head in 2024 {{C-0002}}. Sesame exports were 45,000 tonnes in 2023 {{C-0003}}. Inflation was 4.2 percent in 2025 {{C-0006}}.

Real GDP growth is projected at 4.0 percent in 2026 {{C-0005}}. According to industry estimates, diesel generation is estimated to cost USD 0.35 per kWh in Mogadishu {{C-0004}}.

Finance under Article 6 depends on the Carbon Markets Act. The policy runs from 2028 to 2032, as set out in Part 3.

{{FIG 1.1}}

Table 1: Value added, modelled estimate, base scenario (illustrative, not a forecast)

| Indicator | 2032 |
|---|---|
| Value added (USD million) | 2.5 {{M-0001}} |
""",
    },
}


BASE["figures"] = [{"id": "1.1", "title": "GDP in 2025", "file": "report/figures/fig_1_1.png", "claims": ["C-0001"],
                    "model_outputs": [], "scenario": None, "sources": ["S-001"], "source_line": "Test Bureau of Statistics.",
                    "note": "GDP of USD 13.2 billion."}]


def spec():
    return copy.deepcopy(BASE)


def build(s: dict, root: Path | None = None) -> Path:
    root = Path(root or tempfile.mkdtemp(prefix="gip_fixture_"))
    for d in ("sources/raw", "sources/text", "data", "report/chapters", "reports", "model"):
        (root / d).mkdir(parents=True, exist_ok=True)
    for name, text in s["texts"].items():
        (root / "sources" / "text" / name).write_text(text, encoding="utf-8")
    for src in s["sources"]:
        if src.get("local_path"):
            raw = root / src["local_path"]
            raw.write_text("raw file for " + src["id"], encoding="utf-8")
            if src.get("sha256") is None:
                src["sha256"] = hashlib.sha256(raw.read_bytes()).hexdigest()
    dump = lambda name, data: (root / "data" / name).write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    dump("sources.yaml", s["sources"])
    dump("claims.yaml", s["claims"])
    dump("assumptions.yaml", s["assumptions"])
    dump("conflicts.yaml", s["conflicts"])
    dump("allowlist.yaml", s["allowlist"])
    (root / "model" / "inputs.yaml").write_text(yaml.safe_dump(s["model_inputs"], sort_keys=False), encoding="utf-8")
    (root / "model" / "engine.py").write_text(s["engine"], encoding="utf-8")
    for name, text in s["chapters"].items():
        (root / "report" / "chapters" / name).write_text(text, encoding="utf-8")
    (root / "report" / "figures").mkdir(parents=True, exist_ok=True)
    for f in s.get("figures", []):
        (root / f["file"]).write_bytes(b"png")
    dump("figures.yaml", s.get("figures", []))
    return root


def get(s, kind, id_):
    return next(x for x in s[kind] if x["id"] == id_)


def cleanup(root: Path):
    shutil.rmtree(root, ignore_errors=True)
