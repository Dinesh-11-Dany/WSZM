#!/usr/bin/env python3
"""
Bengaluru Official Crime Data Pipeline (Steps 1-5)
==================================================
Collects, extracts, cleans, and cross-verifies Bengaluru crime statistics from:
  Step 1-2: NCRB (ncrb.gov.in) Crime in India Metropolitan City PDF chapters
  Step 3:   PDF table extraction (tabula-py / camelot / pure-Python pdfplumber)
  Step 4:   OpenCity (data.opencity.in CKAN API), Dataful (dataful.in), & data.gov.in CSVs
  Step 5:   Bengaluru City Police (bcp.karnataka.gov.in) cross-verification

Outputs:
  - data/dataset_manifest.json              (every source URL + download timestamp)
  - data/extracted/bengaluru_extracted_table_*.csv
  - data/bengaluru_crime_summary.csv        (multi-year cross-verified metrics)
  - data/bengaluru_crime_summary.json       (ready to load into bangalore_map.html)
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

try:
    # Load dynamically so static checkers don't error when optional truststore isn't in .venv
    _truststore = importlib.import_module("truststore")
    _truststore.inject_into_ssl()
except Exception:
    pass

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
BENGALURU_REGEX = re.compile(r"\b(?:bengaluru|bangalore)\b", re.IGNORECASE)

# Approximate Bengaluru Urban / Metro population (in thousands) for per-1,000 rate calc
BENGALURU_METRO_POP_THOUSANDS = 13193.0


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_session() -> requests.Session:
    sess = requests.Session()
    sess.headers.update({"User-Agent": USER_AGENT})
    return sess


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def record_manifest(
    manifest: List[Dict[str, Any]],
    step: str,
    source: str,
    url: str,
    local_path: Optional[Path] = None,
    notes: str = "",
) -> None:
    entry: Dict[str, Any] = {
        "step": step,
        "source": source,
        "url": url,
        "downloaded_at_utc": utc_now_iso(),
        "local_file": str(local_path) if local_path else None,
        "notes": notes,
    }
    if local_path and local_path.exists():
        entry["sha256"] = sha256_file(local_path)
        entry["size_bytes"] = local_path.stat().st_size
    manifest.append(entry)


# ---------------------------------------------------------------------------
# STEP 1 & 2: Discover & download NCRB "Crime in India" City-wise PDFs
# ---------------------------------------------------------------------------
def _enable_ncrb_english(sess: requests.Session) -> None:
    """Switch NCRB session cookie to English via /api/language/set."""
    try:
        r0 = sess.get("https://www.ncrb.gov.in/", timeout=25)
        if not r0.ok:
            return
        soup0 = BeautifulSoup(r0.text, "html.parser")
        meta = soup0.find("meta", {"name": "csrf-token"})
        if meta and meta.get("content"):
            sess.post(
                "https://www.ncrb.gov.in/api/language/set",
                data={"lang": "en", "slug": "", "_csrf": meta["content"]},
                headers={"Referer": "https://www.ncrb.gov.in/", "X-Requested-With": "XMLHttpRequest"},
                timeout=20,
            )
    except requests.RequestException:
        pass


def fetch_ncrb_pdfs(
    sess: requests.Session,
    pdf_dir: Path,
    manifest: List[Dict[str, Any]],
    max_pdfs: int = 3,
) -> List[Path]:
    """Visit ncrb.gov.in Crime in India pages (English) and download metropolitan/city PDFs."""
    pdf_dir.mkdir(parents=True, exist_ok=True)
    _enable_ncrb_english(sess)

    candidate_pages = [
        "https://www.ncrb.gov.in/crime-in-india-year-wise.html?year=2023&keyword=",
        "https://www.ncrb.gov.in/crime-in-india-year-wise.html?year=2022&keyword=",
    ]
    include_kw = ("megacities", "metropolitan", "volume", "crimeinindia", "partii", "parti", "city", "cyber", "women")
    exclude_kw = ("icc-women", "internship", "hackathon", "newsletter", "aiberesult", "trainingcalendar", "feedback")
    discovered_pdfs: List[str] = []

    for page_url in candidate_pages:
        try:
            resp = sess.get(page_url, timeout=40)
            if not resp.ok:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                text = (a.get_text(" ", strip=True) or "").lower()
                full_url = urljoin(page_url, href)
                low = (full_url + " " + text).lower()
                if ".pdf" in full_url.lower():
                    if any(ex in low for ex in exclude_kw):
                        continue
                    if any(k in low for k in include_kw) and full_url not in discovered_pdfs:
                        discovered_pdfs.append(full_url)
        except requests.RequestException as exc:
            print(f"[Step 1-2] Could not query {page_url}: {exc}")

    # Prioritize Metropolitan Snapshots & Volume I/II first
    discovered_pdfs.sort(key=lambda u: (0 if "megacities" in u.lower() else 1 if "partii" in u.lower() else 2))

    downloaded: List[Path] = []
    for pdf_url in discovered_pdfs[:max_pdfs]:
        fname = Path(urlparse(pdf_url).path).name or "ncrb_chapter.pdf"
        out_path = pdf_dir / fname
        try:
            if not out_path.exists():
                print(f"[Step 2] Downloading {pdf_url} -> {out_path}")
                r = sess.get(pdf_url, timeout=90, stream=True)
                r.raise_for_status()
                with out_path.open("wb") as f:
                    for chunk in r.iter_content(chunk_size=65536):
                        if chunk:
                            f.write(chunk)
            record_manifest(manifest, "step_1_2", "NCRB Crime in India PDF", pdf_url, out_path)
            downloaded.append(out_path)
        except requests.RequestException as exc:
            print(f"[Step 2] Failed to download {pdf_url}: {exc}")

    return downloaded


# ---------------------------------------------------------------------------
# STEP 3: Extract Bengaluru rows from PDFs (tabula-py / camelot / pdfplumber)
# ---------------------------------------------------------------------------
def _filter_bengaluru_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    mask = df.astype(str).apply(lambda col: col.str.contains(BENGALURU_REGEX, na=False)).any(axis=1)
    return df[mask].copy()


def _extract_with_tabula(pdf_path: Path) -> List[pd.DataFrame]:
    import tabula  # type: ignore

    return tabula.read_pdf(str(pdf_path), pages="all", multiple_tables=True) or []


def _extract_with_camelot(pdf_path: Path) -> List[pd.DataFrame]:
    import camelot  # type: ignore

    tables = camelot.read_pdf(str(pdf_path), pages="all", flavor="stream")
    return [t.df for t in tables]


def _extract_with_pdfplumber(pdf_path: Path) -> List[pd.DataFrame]:
    import pdfplumber  # type: ignore

    dfs: List[pd.DataFrame] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            page_tables = page.extract_tables() or []
            for raw_tbl in page_tables:
                cleaned = [[(c or "").replace("\n", " ").strip() for c in row] for row in raw_tbl if row]
                if len(cleaned) >= 2:
                    headers = cleaned[0]
                    df = pd.DataFrame(cleaned[1:], columns=headers)
                    df["_page"] = page_num
                    dfs.append(df)
            # Line-based fallback if borderless NCRB layout yielded no table
            if not page_tables:
                text = page.extract_text() or ""
                lines = [ln.strip() for ln in text.splitlines() if BENGALURU_REGEX.search(ln)]
                if lines:
                    dfs.append(pd.DataFrame({"_page": page_num, "raw_line": lines}))
    return dfs


def extract_bengaluru_from_pdf(
    pdf_path: Path,
    extracted_dir: Path,
    preferred_engine: str = "auto",
) -> List[Path]:
    """Extract Bengaluru crime rows from an NCRB/BCP PDF using tabula, camelot, or pdfplumber."""
    extracted_dir.mkdir(parents=True, exist_ok=True)
    engines = (
        [preferred_engine]
        if preferred_engine in ("tabula", "camelot", "pdfplumber")
        else ["tabula", "camelot", "pdfplumber"]
    )

    tables: List[pd.DataFrame] = []
    used_engine = None
    for eng in engines:
        try:
            if eng == "tabula":
                tables = _extract_with_tabula(pdf_path)
            elif eng == "camelot":
                tables = _extract_with_camelot(pdf_path)
            else:
                tables = _extract_with_pdfplumber(pdf_path)
            used_engine = eng
            if tables:
                break
        except Exception as exc:
            print(f"[Step 3] {eng} unavailable/failed on {pdf_path.name}: {exc}")

    saved_csvs: List[Path] = []
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", pdf_path.stem)
    for i, table in enumerate(tables):
        bengaluru_rows = _filter_bengaluru_df(table)
        if not bengaluru_rows.empty:
            bengaluru_rows["_source_pdf"] = pdf_path.name
            bengaluru_rows["_extractor"] = used_engine
            out_csv = extracted_dir / f"bengaluru_{stem}_table_{i}.csv"
            bengaluru_rows.to_csv(out_csv, index=False)
            print(f"[Step 3] Found Bengaluru data in {pdf_path.name} table {i} -> {out_csv.name}")
            saved_csvs.append(out_csv)

    return saved_csvs


# ---------------------------------------------------------------------------
# STEP 4: OpenCity (data.opencity.in) & Pre-compiled CSVs (Dataful / data.gov.in)
# ---------------------------------------------------------------------------
def fetch_opencity_datasets(
    sess: requests.Session,
    raw_csv_dir: Path,
    manifest: List[Dict[str, Any]],
    limit: int = 8,
) -> List[Path]:
    """Query OpenCity CKAN API for Bengaluru Crime & NCRB datasets and download CSVs."""
    raw_csv_dir.mkdir(parents=True, exist_ok=True)
    api_url = "https://data.opencity.in/api/3/action/package_search"
    downloaded: List[Path] = []

    for query in ("Bengaluru crime", "Bengaluru cyber crime", "NCRB"):
        try:
            resp = sess.get(api_url, params={"q": query, "rows": 10}, timeout=45)
            if not resp.ok:
                continue
            payload = resp.json()
            for pkg in payload.get("result", {}).get("results", []):
                pkg_title = pkg.get("title", "")
                for res in pkg.get("resources", []):
                    fmt = (res.get("format") or "").upper()
                    res_url = res.get("url") or ""
                    if fmt == "CSV" or res_url.lower().endswith(".csv"):
                        if len(downloaded) >= limit:
                            break
                        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(urlparse(res_url).path).name or "opencity.csv")
                        out_path = raw_csv_dir / safe_name
                        if not out_path.exists():
                            r = sess.get(res_url, timeout=30)
                            if not r.ok:
                                continue
                            out_path.write_bytes(r.content)
                        record_manifest(
                            manifest,
                            "step_4",
                            f"OpenCity: {pkg_title}",
                            res_url,
                            out_path,
                            notes=f"Query={query}",
                        )
                        downloaded.append(out_path)
        except requests.RequestException as exc:
            print(f"[Step 4] OpenCity API error ({query}): {exc}")

    return downloaded


def inspect_csv_sources(csv_paths: List[Path], extracted_dir: Path) -> List[Dict[str, Any]]:
    """Parse OpenCity / Dataful / data.gov.in CSVs and collect Bengaluru metrics."""
    findings: List[Dict[str, Any]] = []
    extracted_dir.mkdir(parents=True, exist_ok=True)

    for csv_path in csv_paths:
        try:
            df = pd.read_csv(csv_path)
        except Exception as exc:
            print(f"[Step 4] Could not parse CSV {csv_path.name}: {exc}")
            continue

        # If statewide/all-India CSV, filter rows mentioning Bengaluru/Bangalore
        if any(df.astype(str).apply(lambda col: col.str.contains(BENGALURU_REGEX, na=False)).any()):
            sub = _filter_bengaluru_df(df)
            if not sub.empty:
                out_filtered = extracted_dir / f"filtered_{csv_path.name}"
                sub.to_csv(out_filtered, index=False)
                df_use = sub
            else:
                df_use = df
        else:
            # Dataset already scoped to Bengaluru (e.g., OpenCity BCP annual CSV)
            df_use = df

        findings.append(
            {
                "file": csv_path.name,
                "rows": int(len(df_use)),
                "columns": list(df_use.columns.astype(str)),
                "sample": df_use.head(5).to_dict(orient="records"),
            }
        )
    return findings


# ---------------------------------------------------------------------------
# STEP 5: Cross-verify with Bengaluru City Police (bcp.karnataka.gov.in)
# ---------------------------------------------------------------------------
def fetch_bcp_press_links(sess: requests.Session, manifest: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Check Bengaluru City Police portal for annual crime statistics / press releases."""
    urls = [
        "https://bcp.karnataka.gov.in/english",
        "https://bcp.karnataka.gov.in/",
    ]
    found_links: List[Dict[str, str]] = []
    for url in urls:
        try:
            resp = sess.get(url, timeout=20)
            if not resp.ok:
                continue
            record_manifest(manifest, "step_5", "Bengaluru City Police Portal", url, notes="Checked live portal")
            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.find_all("a", href=True):
                txt = a.get_text(" ", strip=True)
                href = urljoin(url, a["href"])
                if any(w in (txt + " " + href).lower() for w in ("crime", "statistic", "annual", "women", "cyber")):
                    found_links.append({"title": txt or href, "url": href})
            if found_links:
                break
        except requests.RequestException as exc:
            print(f"[Step 5] Could not reach {url}: {exc}")
    return found_links[:25]


def build_summary(
    pdf_csvs: List[Path],
    csv_findings: List[Dict[str, Any]],
    bcp_links: List[Dict[str, str]],
    manifest: List[Dict[str, Any]],
    out_dir: Path,
) -> Path:
    """Compile extracted metrics and provenance into JSON + CSV ready for bangalore_map.html."""
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "city": "Bengaluru",
        "generated_at_utc": utc_now_iso(),
        "metro_population_thousands": BENGALURU_METRO_POP_THOUSANDS,
        "methodology_notes": [
            "NCRB tracks Bengaluru among 19 metropolitan cities (>2 million population); street/locality crime is not publicly released.",
            "NCRB follows the Principal Offence Rule (counting the single most severe offence per FIR).",
            "Per NCRB guidance, cities should not be compared purely on raw crime totals due to varying e-FIR and registration practices.",
        ],
        "extracted_pdf_tables": [str(p.name) for p in pdf_csvs],
        "csv_sources_parsed": csv_findings,
        "bcp_portal_links": bcp_links,
        "manifest": manifest,
    }

    summary_json = out_dir / "bengaluru_crime_summary.json"
    summary_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    # Export flat manifest CSV for reporting
    manifest_csv = out_dir / "bengaluru_dataset_sources.csv"
    with manifest_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["step", "source", "url", "downloaded_at_utc", "local_file", "size_bytes", "notes"],
        )
        writer.writeheader()
        for row in manifest:
            writer.writerow({k: row.get(k, "") for k in writer.fieldnames})

    return summary_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract & cross-verify Bengaluru NCRB/OpenCity/BCP crime data.")
    parser.add_argument("--data-dir", type=Path, default=Path("data"), help="Output directory (default: ./data)")
    parser.add_argument("--pdf", type=Path, nargs="*", default=[], help="Local NCRB/BCP PDF files to parse in Step 3")
    parser.add_argument("--csv", type=Path, nargs="*", default=[], help="Local Dataful/data.gov.in CSV files to ingest in Step 4")
    parser.add_argument("--engine", choices=["auto", "tabula", "camelot", "pdfplumber"], default="auto")
    parser.add_argument("--offline", action="store_true", help="Skip web downloads and parse only --pdf / --csv / existing files")
    args = parser.parse_args()

    data_dir: Path = args.data_dir
    pdf_dir = data_dir / "ncrb_pdfs"
    raw_csv_dir = data_dir / "opencity_csvs"
    manual_csv_dir = data_dir / "manual_csvs"
    extracted_dir = data_dir / "extracted"
    manifest: List[Dict[str, Any]] = []

    sess = make_session()

    pdf_files: List[Path] = list(args.pdf)
    if pdf_dir.exists():
        pdf_files.extend(p for p in pdf_dir.glob("*.pdf") if p not in pdf_files)

    csv_files: List[Path] = list(args.csv)
    for d in (raw_csv_dir, manual_csv_dir):
        if d.exists():
            csv_files.extend(p for p in d.glob("*.csv") if p not in csv_files)

    if not args.offline:
        downloaded_pdfs = fetch_ncrb_pdfs(sess, pdf_dir, manifest)
        for p in downloaded_pdfs:
            if p not in pdf_files:
                pdf_files.append(p)

        downloaded_csvs = fetch_opencity_datasets(sess, raw_csv_dir, manifest)
        for c in downloaded_csvs:
            if c not in csv_files:
                csv_files.append(c)

        bcp_links = fetch_bcp_press_links(sess, manifest)
    else:
        bcp_links = []

    all_extracted_csvs: List[Path] = []
    for pdf_path in pdf_files:
        if pdf_path.exists():
            all_extracted_csvs.extend(extract_bengaluru_from_pdf(pdf_path, extracted_dir, args.engine))

    csv_findings = inspect_csv_sources(csv_files, extracted_dir)
    summary_json = build_summary(all_extracted_csvs, csv_findings, bcp_links, manifest, data_dir)

    manifest_path = data_dir / "dataset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\nPipeline complete.")
    print(f"  Summary JSON : {summary_json}")
    print(f"  Extracted CSVs from PDFs: {len(all_extracted_csvs)}")
    print(f"  Parsed CSV files        : {len(csv_findings)}")
    print(f"  BCP links discovered    : {len(bcp_links)}")


if __name__ == "__main__":
    main()

