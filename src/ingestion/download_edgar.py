import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

USER_AGENT = os.getenv("SEC_USER_AGENT")
if not USER_AGENT:
    raise SystemExit("Set SEC_USER_AGENT in your .env file")

HEADERS = {"User-Agent": USER_AGENT}
RAW_DIR = Path("data/raw")

TICKERS = ["NVDA", "AMD", "INTC", "MSFT"]   # TSM files 20-F, not 10-K; add later
FORMS = {"10-K", "10-Q"}
MIN_YEAR = 2022


def get(url):
    """Polite GET: SEC allows ~10 requests/sec; we stay well under."""
    time.sleep(0.2)
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r


def ticker_to_cik():
    data = get("https://www.sec.gov/files/company_tickers.json").json()
    return {v["ticker"]: str(v["cik_str"]).zfill(10) for v in data.values()}


def list_filings(cik):
    """Return recent filings of the forms we want, as a list of dicts."""
    data = get(f"https://data.sec.gov/submissions/CIK{cik}.json").json()
    recent = data["filings"]["recent"]
    out = []
    for i, form in enumerate(recent["form"]):
        year = int(recent["filingDate"][i][:4])
        if form in FORMS and year >= MIN_YEAR:
            out.append({
                "form": form,
                "filing_date": recent["filingDate"][i],
                "report_date": recent["reportDate"][i],
                "accession": recent["accessionNumber"][i],
                "primary_doc": recent["primaryDocument"][i],
            })
    return out


def download(ticker, cik, filing):
    acc_nodash = filing["accession"].replace("-", "")
    url = (f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
           f"{acc_nodash}/{filing['primary_doc']}")
    folder = RAW_DIR / ticker
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{ticker}_{filing['form']}_{filing['report_date']}.html"
    path = folder / name
    if path.exists():
        print(f"skip   {name}")
        return
    path.write_bytes(get(url).content)
    print(f"saved  {name}")


def main():
    ciks = ticker_to_cik()
    manifest = []
    for t in TICKERS:
        cik = ciks[t]
        for f in list_filings(cik):
            download(t, cik, f)
            manifest.append({"ticker": t, "cik": cik, **f})
    Path("data/manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"\nDone. {len(manifest)} filings. Manifest at data/manifest.json")


if __name__ == "__main__":
    main()