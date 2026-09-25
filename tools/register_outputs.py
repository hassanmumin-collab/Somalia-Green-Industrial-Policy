#!/usr/bin/env python3
"""Register model outputs used in the report as M- claims (model/README.md; CLAUDE.md sections 5.3 and 7.2 check 20).

The spec file data/model_outputs.yaml lists each output the report quotes:
    - output_key: climate.minigrid.lcoe_usd_per_kwh
      scenario: base
      unit: USD per kWh
      rounding: 3
      statement: "Levelised cost of the park solar-plus-storage supply ({scenario} scenario, modelled estimate)"
      measure: "..."            (optional)
      period: "2032"            (optional; default taken from the key's last part or 'model horizon')

This tool computes each value from model/engine.py, rounds it, and adds or updates the matching M- claim (matched on
output_key and scenario, so ids stay stable). Values are recomputed, never typed. Status is always 'illustrative'.

Usage: python tools/register_outputs.py
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from model import engine  # noqa: E402


def main() -> int:
    spec = yaml.safe_load((ROOT / "data" / "model_outputs.yaml").read_text(encoding="utf-8")) or []
    claims_path = ROOT / "data" / "claims.yaml"
    text = claims_path.read_text(encoding="utf-8")
    claims = yaml.safe_load(text) or []
    by_key = {(c.get("output_key"), c.get("scenario")): c for c in claims if str(c.get("id", "")).startswith("M-")}
    next_n = max([int(c["id"][2:]) for c in claims if str(c["id"]).startswith("M-")] or [0]) + 1
    results = {}
    added, updated = [], []
    today = dt.date.today().isoformat()
    for s in spec:
        sc = s.get("scenario", "base")
        if sc not in results:
            results[sc] = engine.compute(sc, ROOT)
        key = s["output_key"]
        if key not in results[sc]:
            raise SystemExit(f"model output '{key}' not produced by the model")
        r = int(s.get("rounding", 1))
        value = round(results[sc][key]["value"], r)
        if r <= 0:
            value = int(round(value))
        last = key.rsplit(".", 1)[-1]
        period = str(s.get("period") or (last if last.isdigit() else "model horizon 2028 to 2032"))
        fields = dict(statement=s["statement"].format(scenario=sc), output_key=key, scenario=sc, value=value,
                      unit=s["unit"], rounding=r, period=period, measure=s.get("measure", key), basis="projection",
                      status="illustrative", verified_at=today)
        c = by_key.get((key, sc))
        if c is None:
            c = {"id": f"M-{next_n:04d}", **fields}
            next_n += 1
            claims.append(c)
            added.append(c["id"])
        else:
            if c.get("value") != value:
                updated.append(f"{c['id']} {c.get('value')} -> {value}")
            c.update(fields)
    header = text.split("\n- id:", 1)[0] if text.lstrip().startswith("#") else ""
    body = yaml.safe_dump(claims, sort_keys=False, allow_unicode=True, width=1000)
    claims_path.write_text((header.rstrip() + "\n" if header else "") + body, encoding="utf-8")
    print(f"{len(added)} added {added}; {len(updated)} updated {updated}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
