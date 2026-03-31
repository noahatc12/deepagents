# Apartment Lead Generation Pipeline

Find apartment buildings that are likely **owner-managed or self-managed** —
not handled by a third-party property management company —
using only publicly available, lawfully accessed data.

---

## Project Purpose

This pipeline helps you build a targeted lead list of apartment building owners
in a chosen geographic market. It:

1. Pulls apartment property data from public sources (county assessors, city
   rental registries, open map data, your own CSV files)
2. Deduplicates and normalizes records across sources
3. Classifies each property as *likely third-party managed*, *likely
   owner-managed*, or *unclear*
4. Enriches owner-managed leads with entity and contact data from public
   business registries
5. Exports a clean lead table to CSV, Excel, JSON, and/or SQLite

**Target use cases:** off-market outreach, direct-to-owner marketing,
property acquisition prospecting.

---

## Architecture Overview

```
Public Sources → Collectors → Normalizer → Classifier → Enricher → Exports
                 (assessor,    (dedup,     (rule-based   (CA SOS,   (CSV/
                  registry,    address     scoring)      OpenCorp)  Excel/
                  CSV, maps)   normalize)                           JSON/DB)
```

See [docs/architecture.md](docs/architecture.md) for the full module map and
data flow diagram.

---

## Quick Start

### 1. Prerequisites

- Python 3.10+
- pip

### 2. Install

```bash
cd apartment_leads
pip install -r requirements.txt

# Optional: Overture Maps support (large DuckDB download on first run)
pip install duckdb
```

### 3. Configure

```bash
cp .env.example .env
# Edit .env to add any API keys (all optional)
```

### 4. Run with your own CSV

The fastest way to start is with a CSV of properties you already have:

```bash
python -m apartment_leads run \
  --city Oakland \
  --state CA \
  --csv data/sample_input.csv
```

### 5. Run with public data sources

```bash
# East Bay (Alameda County)
python -m apartment_leads run --config configs/east_bay.yaml

# Sacramento
python -m apartment_leads run --config configs/sacramento.yaml

# Custom city from CLI
python -m apartment_leads run --city Berkeley --state CA --min-units 5
```

### 6. View results

```bash
# Query the database
python -m apartment_leads query --status likely_owner_managed --city Oakland

# Show stats
python -m apartment_leads stats

# Output files are in data/processed/
ls data/processed/
```

### Docker

```bash
docker build -t apartment-leads .
docker run -v $(pwd)/data:/app/data -v $(pwd)/configs:/app/configs \
  apartment-leads run --config configs/east_bay.yaml
```

---

## Output Fields

| Field | Description |
|-------|-------------|
| `property_name` | Building name (if known) |
| `street_address` | Normalized street address |
| `city`, `state`, `zip`, `county` | Location |
| `apn` | Assessor Parcel Number |
| `units_estimated` | Estimated number of units |
| `website` | Property website |
| `phone` | Property phone |
| `management_status` | `likely_owner_managed` / `likely_third_party` / `unclear` |
| `management_status_confidence` | 0.0–1.0 confidence score |
| `detected_management_company` | Name of PM company if detected |
| `management_signals` | Signals that drove the classification |
| `owner_name` | Owner individual name (from assessor / enrichment) |
| `owner_entity` | Owner LLC/Corp name |
| `owner_contact_name` | Registered agent or contact person |
| `owner_email` | Contact email (from enrichment) |
| `owner_phone` | Contact phone |
| `mailing_address` | Owner mailing address |
| `source_urls` | All sources this record came from |
| `manual_review_flag` | True if this lead needs human review |
| `review_reason` | Why it was flagged |
| `notes` | Additional notes |

---

## How Management Detection Works

The classifier assigns a **signed score** to each property:

- **Positive score** → third-party managed evidence
- **Negative score** → owner-managed evidence
- **Score near zero** → unclear / needs review

Signals and their weights:

| Signal | Direction | Weight |
|--------|-----------|--------|
| Known PM company name matches | → Third-party | 0.90 |
| "managed by" text | → Third-party | 0.70 |
| Website domain = known PM | → Third-party | 0.80 |
| PM branding on site | → Third-party | 0.70 |
| "self-managed" text | → Owner | 0.80 |
| Owner is individual person | → Owner | 0.40 |
| No management name found | → Owner | 0.30 |
| Owner mailing = property addr | → Owner | 0.50 |
| On-site management text | → Owner | 0.50 |

**Classification thresholds:**
- `|score| < 0.20` → `unclear` (flagged for review)
- `score > 0.20` → `likely_third_party`
- `score < -0.20` → `likely_owner_managed`

**LLM review interface:** An optional `LLMReviewerProtocol` is available
for feeding unclear cases to an LLM (Claude, GPT-4, etc.) for
a second-pass classification. See `src/classifiers/management.py`.

---

## Adding a New Market

1. Copy the template config:
   ```bash
   cp configs/sample_market_template.yaml configs/my_city.yaml
   ```
2. Edit the `geography` section (city, county, state, ZIPs)
3. Optionally limit `sources.enabled` to collectors that cover your area
4. Run: `python -m apartment_leads run --config configs/my_city.yaml`

For counties not yet implemented, see [docs/architecture.md](docs/architecture.md#adding-a-new-source-adapter) for how to add a new assessor adapter in ~50 lines of Python.

---

## Adding a New Source Adapter

1. Create `src/collectors/<source_name>.py`
2. Subclass `BaseCollector`, implement `collect(target) -> Iterator[SourceRecord]`
3. Register in `src/collectors/registry.py`

Skeleton:
```python
from .base import BaseCollector, GeographyTarget
from ..models import SourceRecord

class MyCollector(BaseCollector):
    source_name = "my_source"

    def collect(self, target: GeographyTarget):
        for row in self._fetch(target):
            yield SourceRecord(
                source_name=self.source_name,
                source_url="https://...",
                raw_address=row["address"],
                raw_city=row["city"],
                raw_state=row["state"],
                raw_zip=row["zip"],
            )
```

---

## Data Sources

See [docs/data_sources.md](docs/data_sources.md) for the full reference of
current and planned sources, ToS status, and evaluation criteria.

**Currently implemented (stubs ready for your jurisdiction):**
- County assessor open data (Socrata API pattern)
- City rental registries (Socrata or CSV)
- Overture Maps Places (free, open license, via DuckDB)
- CSV file import (your own data)

**Enrichment sources:**
- California SOS entity bulk CSV (free monthly download)
- OpenCorporates public company API (free tier)

---

## Legal & Compliance Notes

- **Only public data**: This pipeline accesses data that is legally public —
  county assessor records (public property records), city rental registries,
  open data portals, and business registration records.
- **robots.txt respected**: The HTTP client checks and honors `robots.txt`
  before fetching any URL.
- **No login bypass, no CAPTCHA bypass, no ToS violations.**
- **Rate limiting**: Requests are throttled to ≤ 0.5 req/s per domain by default.
- **Source attribution**: Every field in the output is tagged with its source.
- **Fair use of APIs**: Socrata and OpenCorporates provide public APIs
  explicitly intended for this kind of access.
- **CA SOS data**: The California Secretary of State provides bulk entity
  data files explicitly for public download.

**Limitations and false-positive risks:**
- Owner name from assessor records may be an LLC, trust, or stale name.
- Management company detection is heuristic-based and will miss novel
  company names not in the known-company list.
- "Unclear" properties require human review before outreach.
- Contact data from business registries may be outdated.
- Always verify contact information before outreach.

---

## Running Tests

```bash
cd apartment_leads
pip install -r requirements.txt
pytest tests/ -v

# With coverage
pytest tests/ --cov=src --cov-report=term-missing
```

---

## Project Structure

```
apartment_leads/
├── src/
│   ├── models.py               # SourceRecord, PropertyLead, EnrichedField
│   ├── pipeline.py             # Pipeline orchestrator
│   ├── cli.py                  # CLI entry point
│   ├── config_loader.py        # YAML → PipelineConfig
│   ├── collectors/
│   │   ├── base.py             # BaseCollector, GeographyTarget
│   │   ├── csv_import.py       # CSV file import
│   │   ├── assessor.py         # County assessor adapters
│   │   ├── rental_registry.py  # City rental registry adapters
│   │   ├── overture_maps.py    # Overture Maps Places
│   │   └── registry.py         # Collector selection
│   ├── normalizers/
│   │   └── pipeline.py         # Normalization + deduplication
│   ├── classifiers/
│   │   └── management.py       # Management status classifier
│   ├── enrichment/
│   │   ├── base.py             # BaseEnricher
│   │   ├── ca_sos.py           # CA SOS enricher
│   │   ├── opencorporates.py   # OpenCorporates enricher
│   │   └── pipeline.py         # Enrichment runner
│   ├── exports/
│   │   ├── csv_export.py       # CSV / Excel / JSON export
│   │   └── database.py         # SQLite persistence
│   └── utils/
│       ├── address.py          # Address normalization
│       ├── cache.py            # HTTP response cache
│       ├── entity.py           # Entity name normalization
│       ├── http.py             # PoliteSession (robots.txt + rate limit)
│       ├── logging.py          # Logging setup
│       └── rate_limiter.py     # Token bucket + retry decorator
├── tests/                      # pytest test suite
├── configs/                    # Per-market YAML configs
├── data/
│   ├── sample_input.csv        # Example input CSV
│   ├── sample_output.csv       # Example output CSV
│   ├── cache/                  # HTTP response cache (auto-created)
│   └── processed/              # Output files (auto-created)
├── docs/
│   ├── architecture.md         # Architecture deep-dive
│   ├── data_sources.md         # Source reference
│   └── roadmap.md              # Feature roadmap
├── __main__.py                 # python -m apartment_leads entry point
├── .env.example                # Environment variable template
├── requirements.txt
├── pyproject.toml
├── Dockerfile
└── docker-compose.yml
```

---

## MVP Scope

The current implementation covers:

1. **CSV import** of your own property list → immediate value with zero API setup
2. **Assessor adapter pattern** → add any Socrata county in ~50 lines
3. **Overture Maps** → free global building data (requires `pip install duckdb`)
4. **Rule-based classifier** → works without any API keys
5. **CA SOS + OpenCorporates enrichment** → owner entity data
6. **Full export suite** → CSV, Excel, JSON, SQLite, review queue
7. **CLI** → one command to run end-to-end

**What requires jurisdiction-specific setup:**
- Each county assessor Socrata dataset ID must be confirmed and column names mapped
- Each city rental registry endpoint must be confirmed

See [docs/roadmap.md](docs/roadmap.md) for Phase 2+ plans.
