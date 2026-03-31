# Architecture Overview

## Data Flow

```
Geography Target (city / county / ZIPs)
          │
          ▼
┌─────────────────────────────────┐
│          Collectors             │
│  ┌──────────┐  ┌─────────────┐ │
│  │ Assessor │  │  Rental     │ │
│  │  (APIs)  │  │  Registry   │ │
│  └──────────┘  └─────────────┘ │
│  ┌──────────┐  ┌─────────────┐ │
│  │Overture  │  │  CSV Import │ │
│  │  Maps    │  │  (manual)   │ │
│  └──────────┘  └─────────────┘ │
└──────────────┬──────────────────┘
               │ SourceRecord[]
               ▼
┌──────────────────────────────────┐
│   Normalization + Deduplication  │
│   • Address normalization         │
│   • Entity name normalization     │
│   • Fingerprint-based dedup       │
│   • Field merge (source priority) │
└──────────────┬───────────────────┘
               │ PropertyLead[]
               ▼
┌──────────────────────────────────┐
│     Management Classifier        │
│   • Rule-based signal scoring    │
│   • Known PM company matching    │
│   • Website/domain analysis      │
│   • Owner name analysis          │
│   • Optional LLM review pass     │
└──────────────┬───────────────────┘
               │ Classified PropertyLead[]
               ▼
┌──────────────────────────────────┐
│    Enrichment (owner-managed)    │
│   • CA SOS business entity data  │
│   • OpenCorporates company search│
│   • (future: phone/email lookup) │
└──────────────┬───────────────────┘
               │ Enriched PropertyLead[]
               ▼
┌──────────────────────────────────┐
│           Exports                │
│   CSV  │  Excel  │  JSON  │  DB  │
│             Review Queue         │
└──────────────────────────────────┘
```

## Module Map

| Path | Purpose |
|------|---------|
| `src/models.py` | Core data models: SourceRecord, PropertyLead, EnrichedField |
| `src/pipeline.py` | Pipeline orchestrator |
| `src/cli.py` | CLI entry point |
| `src/config_loader.py` | YAML config → PipelineConfig |
| `src/collectors/base.py` | BaseCollector + GeographyTarget |
| `src/collectors/csv_import.py` | CSV file collector |
| `src/collectors/assessor.py` | County assessor Socrata adapters |
| `src/collectors/rental_registry.py` | City rental registry adapters |
| `src/collectors/overture_maps.py` | Overture Maps Places (via DuckDB) |
| `src/collectors/registry.py` | Collector selection logic |
| `src/normalizers/pipeline.py` | Normalization + deduplication |
| `src/classifiers/management.py` | Management status classifier |
| `src/enrichment/base.py` | BaseEnricher |
| `src/enrichment/ca_sos.py` | CA SOS entity enricher |
| `src/enrichment/opencorporates.py` | OpenCorporates enricher |
| `src/enrichment/pipeline.py` | Enrichment runner |
| `src/exports/csv_export.py` | CSV / Excel / JSON export |
| `src/exports/database.py` | SQLite persistence |
| `src/utils/address.py` | Address normalization |
| `src/utils/cache.py` | SQLite HTTP response cache |
| `src/utils/entity.py` | Entity name normalization |
| `src/utils/http.py` | PoliteSession (robots.txt + rate limiting) |
| `src/utils/logging.py` | Logging setup |
| `src/utils/rate_limiter.py` | Token-bucket rate limiter + retry decorator |

## Key Design Decisions

### Pluggable Collector Pattern
Each data source is an independent class that inherits from `BaseCollector`.
To add a new source, subclass `BaseCollector`, implement `collect()`, and
register the class in `src/collectors/registry.py`.

### Address Fingerprinting for Deduplication
Properties from multiple sources are deduplicated by a canonical fingerprint
of `(street, city, state, zip)`. This handles abbreviation variations
(`St` vs `Street`), direction differences, etc.

### Signal-Based Classification
The management classifier works on a signed score: positive = third-party
signals, negative = owner-managed signals. The magnitude determines
confidence. A low-magnitude score results in `unclear` and triggers
a manual review flag.

### Source Attribution
Every enriched field carries its source name, URL, fetch timestamp, and
a confidence score (0–1). This allows downstream users to understand
where each piece of data came from and how reliable it is.

### HTTP Compliance
- `robots.txt` is checked for every domain before fetching
- A descriptive User-Agent is sent on every request
- A token-bucket rate limiter prevents hammering any single domain
- A disk cache avoids re-fetching the same URL within a configurable TTL
- Retry logic uses exponential back-off with jitter

## Adding a New Market

1. Copy `configs/sample_market_template.yaml` to `configs/<city>.yaml`
2. Fill in `geography` section (city, county, state, ZIPs)
3. Check which collectors work for your jurisdiction:
   - If the county uses Socrata open data → subclass `BaseAssessorCollector`
   - If the city has a rental registry CSV → use `CsvImportCollector`
4. Run: `python -m apartment_leads run --config configs/<city>.yaml`

## Adding a New Source Adapter

1. Create `src/collectors/<source_name>.py`
2. Subclass `BaseCollector`
3. Set `source_name` class attribute
4. Implement `collect(target)` → `Iterator[SourceRecord]`
5. Optionally override `is_available(target)` to limit to specific geographies
6. Register in `src/collectors/registry.py`

```python
# Example skeleton
from .base import BaseCollector, GeographyTarget
from ..models import SourceRecord

class MyNewCollector(BaseCollector):
    source_name = "my_source"

    def collect(self, target: GeographyTarget):
        # Fetch and parse data
        for row in self._fetch_rows(target):
            yield SourceRecord(
                source_name=self.source_name,
                source_url="https://...",
                raw_address=row["address"],
                raw_city=row["city"],
                ...
            )
```
