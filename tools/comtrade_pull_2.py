"""UN Comtrade public preview pull, second set: partners' imports from Somalia (fish, fruit, sesame, skins)
and world export prices of tanned sheep and goat leather. Usage: comtrade_pull_2.py OUT.csv"""
import csv, json, sys, time, urllib.request, urllib.error
from pathlib import Path

OUT = Path(sys.argv[1])
BASE = "https://comtradeapi.un.org/public/v1/preview/C/A/HS"
PARTNERS_OF_SOMALIA = {512: "Oman", 784: "United Arab Emirates", 682: "Saudi Arabia", 887: "Yemen", 404: "Kenya",
    156: "China", 704: "Viet Nam", 764: "Thailand", 380: "Italy", 818: "Egypt", 634: "Qatar", 414: "Kuwait", 48: "Bahrain",
    400: "Jordan", 262: "Djibouti", 231: "Ethiopia", 699: "India", 586: "Pakistan", 792: "Turkiye", 724: "Spain",
    410: "Rep. of Korea", 392: "Japan", 458: "Malaysia", 360: "Indonesia", 702: "Singapore", 344: "China, Hong Kong SAR",
    144: "Sri Lanka", 842: "USA", 276: "Germany", 528: "Netherlands"}
FROM_SOMALIA_CMDS = ["0302", "0303", "0304", "0305", "0306", "0307", "0803", "0804", "0805", "1207", "1515", "4102", "4103"]
LEATHER_EXPORTERS = {231: "Ethiopia", 404: "Kenya", 586: "Pakistan", 566: "Nigeria"}
LEATHER_CMDS = ["4105", "4106"]
YEARS = "2022,2023,2024"
FIELDS = ["reporterCode", "flowCode", "partnerCode", "cmdCode", "refYear", "primaryValue", "fobvalue", "cifvalue",
          "netWgt", "qty", "qtyUnitCode", "classificationCode", "isReported", "isAggregate"]
REPORTERS = {**PARTNERS_OF_SOMALIA, **LEATHER_EXPORTERS}


def get(params):
    url = BASE + "?" + "&".join(f"{k}={v}" for k, v in params.items())
    for attempt in range(6):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=90) as r:
                d = json.loads(r.read().decode("utf-8"))
            if d.get("error"):
                print("API error", d["error"], url, file=sys.stderr)
            return d.get("data") or [], url
        except urllib.error.HTTPError as e:
            if e.code == 400:
                print(f"HTTP 400 skipped: {e.read()[:200]} {url}", file=sys.stderr)
                return [], url + " [HTTP 400]"
            wait = 30 if e.code == 429 else 10
            print(f"HTTP {e.code}, waiting {wait}s: {url}", file=sys.stderr)
            time.sleep(wait)
        except Exception as e:
            print(f"error {e}, retrying: {url}", file=sys.stderr)
            time.sleep(10)
    raise SystemExit(f"failed: {url}")


rows, log = [], []
jobs = []
for rc in PARTNERS_OF_SOMALIA:
    jobs.append(dict(reporterCode=rc, partnerCode=706, cmdCode=",".join(FROM_SOMALIA_CMDS), flowCode="M"))
for rc in LEATHER_EXPORTERS:
    jobs.append(dict(reporterCode=rc, partnerCode=0, cmdCode=",".join(LEATHER_CMDS), flowCode="X"))
jobs = [dict(j, period=y) for j in jobs for y in YEARS.split(",")]
for j in jobs:
    data, url = get(j)
    log.append(f"{url}	{len(data)} rows")
    print(f"{len(data):4d} rows  {url[len(BASE):][:110]}", flush=True)
    for d in data:
        if d.get("partner2Code", 0) != 0 or d.get("customsCode") != "C00" or str(d.get("motCode")) != "0":
            continue
        rows.append({k: d.get(k) for k in FIELDS})
    time.sleep(2.5)
with OUT.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=FIELDS)
    w.writeheader()
    w.writerows(rows)
OUT.with_suffix(".log").write_text("\n".join(log), encoding="utf-8")
print(len(rows), "rows written")
