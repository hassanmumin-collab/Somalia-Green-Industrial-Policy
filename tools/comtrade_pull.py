"""UN Comtrade public preview pull: partner (mirror) data for Somalia (code 706)."""
import csv, json, sys, time, urllib.request, urllib.error
from pathlib import Path

OUT = Path(sys.argv[1])
BASE = "https://comtradeapi.un.org/public/v1/preview/C/A/HS"
REPORTERS = {784: "United Arab Emirates", 156: "China", 699: "India", 792: "Turkiye", 512: "Oman",
             404: "Kenya", 231: "Ethiopia", 682: "Saudi Arabia", 586: "Pakistan", 458: "Malaysia",
             360: "Indonesia", 76: "Brazil", 818: "Egypt", 262: "Djibouti", 764: "Thailand",
             704: "Viet Nam", 380: "Italy", 842: "USA", 528: "Netherlands", 702: "Singapore",
             634: "Qatar", 414: "Kuwait", 48: "Bahrain", 400: "Jordan", 276: "Germany", 826: "United Kingdom",
             724: "Spain", 250: "France", 410: "Rep. of Korea", 392: "Japan", 400: "Jordan", 887: "Yemen",
             716: "Zimbabwe", 710: "South Africa", 800: "Uganda", 834: "Tanzania"}
EXPORT_CMDS = ["3401", "3402", "9619", "1507", "1508", "1509", "1510", "1511", "1512", "1513", "1514",
               "1515", "1516", "1517", "0402", "1101", "1006", "1701", "1902", "61", "62"]
GULF = {682: "Saudi Arabia", 784: "United Arab Emirates", 512: "Oman", 634: "Qatar", 414: "Kuwait", 48: "Bahrain", 887: "Yemen"}
MEAT = ["0201", "0202", "0204", "0208", "0102", "0104", "0106", "1207", "4101", "4102", "4103"]
YEARS = "2021,2022,2023,2024"
FIELDS = ["reporterCode", "flowCode", "partnerCode", "cmdCode", "refYear", "primaryValue", "fobvalue", "cifvalue",
          "netWgt", "qty", "qtyUnitCode", "classificationCode", "isReported", "isAggregate"]


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
for rc in REPORTERS:
    for flow in ("X", "RX"):
        jobs.append(dict(reporterCode=rc, period=YEARS, partnerCode=706, cmdCode=",".join(EXPORT_CMDS), flowCode=flow))
for rc in GULF:
    jobs.append(dict(reporterCode=rc, period=YEARS, partnerCode=706, cmdCode=",".join(MEAT), flowCode="M"))
    jobs.append(dict(reporterCode=rc, period=YEARS, partnerCode=0, cmdCode="0201,0202,0204,0208", flowCode="M"))
jobs = [dict(j, period=y) for j in jobs for y in YEARS.split(",")]
for j in jobs:
    data, url = get(j)
    log.append(f"{url}\t{len(data)} rows")
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
