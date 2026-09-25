"""UN Comtrade public preview pull, third set: (1) fresh or chilled beef (HS 0201) imported by the six GCC states in 2023,
by supplying country, to benchmark the market share proximate suppliers achieve; (2) natural gums and resins (HS 1301)
and essential oils (HS 3301) imported from Somalia in 2023 by twelve main partner countries (frankincense and myrrh).
Rows are appended to OUT.csv as each call returns, so a slow or interrupted run keeps what it has.
Usage: comtrade_pull_3.py OUT.csv"""
import csv, json, sys, time, urllib.request, urllib.error
from pathlib import Path

OUT = Path(sys.argv[1])
BASE = "https://comtradeapi.un.org/public/v1/preview/C/A/HS"
GCC = {682: "Saudi Arabia", 784: "United Arab Emirates", 512: "Oman", 634: "Qatar", 414: "Kuwait", 48: "Bahrain"}
RESIN_PARTNERS = {784: "United Arab Emirates", 682: "Saudi Arabia", 512: "Oman", 156: "China", 699: "India", 251: "France",
                  276: "Germany", 842: "USA", 826: "United Kingdom", 380: "Italy", 818: "Egypt", 887: "Yemen"}
FIELDS = ["reporterCode", "flowCode", "partnerCode", "cmdCode", "refYear", "primaryValue", "fobvalue", "cifvalue",
          "netWgt", "qty", "qtyUnitCode", "classificationCode", "isReported", "isAggregate"]


def get(params):
    url = BASE + "?" + "&".join(f"{k}={v}" for k, v in params.items())
    for attempt in range(8):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=120) as r:
                d = json.loads(r.read().decode("utf-8"))
            if d.get("error"):
                print("API error", d["error"], url, file=sys.stderr)
            return d.get("data") or [], url
        except urllib.error.HTTPError as e:
            if e.code == 400:
                print(f"HTTP 400 skipped: {e.read()[:200]} {url}", file=sys.stderr)
                return [], url + " [HTTP 400]"
            print(f"HTTP {e.code}, waiting 60s: {url}", file=sys.stderr, flush=True)
            time.sleep(60)
        except Exception as e:
            print(f"error {e}, waiting 60s: {url}", file=sys.stderr, flush=True)
            time.sleep(60)
    raise SystemExit(f"failed: {url}")


jobs = [dict(reporterCode=rc, period=2023, cmdCode="0201", flowCode="M") for rc in GCC]
jobs += [dict(reporterCode=rc, period=y, partnerCode=706, cmdCode="1301,3301", flowCode="M")
         for rc in RESIN_PARTNERS for y in (2023,)]
n = 0
with OUT.open("w", newline="", encoding="utf-8") as f, OUT.with_suffix(".log").open("w", encoding="utf-8") as lg:
    w = csv.DictWriter(f, fieldnames=FIELDS)
    w.writeheader()
    for j in jobs:
        data, url = get(j)
        lg.write(f"{url}\t{len(data)} rows\n")
        lg.flush()
        print(f"{len(data):4d} rows  {url[len(BASE):][:110]}", flush=True)
        for d in data:
            if d.get("partner2Code", 0) != 0 or d.get("customsCode") != "C00" or str(d.get("motCode")) != "0":
                continue
            w.writerow({k: d.get(k) for k in FIELDS})
            n += 1
        f.flush()
        time.sleep(2.5)
print(n, "rows written")
