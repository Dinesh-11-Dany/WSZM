# Bengaluru Crime Data Pipeline (Steps 1–5)

Python pipeline to fetch, extract, and cross-verify official Bengaluru crime data from **NCRB (`ncrb.gov.in`)**, **OpenCity (`data.opencity.in`)**, **Dataful (`dataful.in`)**, **`data.gov.in`**, and **Bengaluru City Police (`bcp.karnataka.gov.in`)**.

## 1. Prerequisites
- **Python 3.9+** (`python --version`)
- **Java JRE** (only required if using `tabula-py`; `pdfplumber` works in pure Python without Java)

Install dependencies:
```bash
pip install -r scripts/requirements.txt
```

## 2. Usage

### Run full online pipeline (Steps 1–5):
```bash
python scripts/bengaluru_crime_extractor.py
```

### Extract from manually downloaded NCRB PDFs or Dataful / `data.gov.in` CSVs:
```bash
python scripts/bengaluru_crime_extractor.py --offline --pdf path/to/crime_in_india_metropolitan_cities.pdf --csv path/to/dataful_bengaluru.csv
```

### Force `tabula-py` specifically (Step 3 snippet):
```bash
python scripts/bengaluru_crime_extractor.py --offline --engine tabula --pdf crime_in_india_metropolitan_cities.pdf
```

## 3. Outputs (`data/`)
- `data/extracted/bengaluru_*_table_*.csv` — Filtered rows matching `Bengaluru|Bangalore` from each NCRB PDF table
- `data/bengaluru_crime_summary.json` — Compiled metrics, methodology notes, and BCP cross-check links
- `data/bengaluru_dataset_sources.csv` & `data/dataset_manifest.json` — Exact source URLs, SHA-256 hashes, and UTC download dates

