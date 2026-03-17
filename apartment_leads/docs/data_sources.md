# Public Data Sources Reference

## Currently Implemented

| Source | Type | Coverage | Notes |
|--------|------|----------|-------|
| CSV Import | File | Any | User-supplied property list |
| Alameda County Assessor | Socrata API | Alameda Co., CA | Parcel + owner data |
| Sacramento County Assessor | Socrata API | Sacramento Co., CA | Stub – needs dataset ID |
| Oakland Rental Registry | Socrata API | Oakland, CA | Stub – needs dataset ID |
| Berkeley Rental Registry | N/A | Berkeley, CA | No automated endpoint; use CSV |
| Overture Maps Places | DuckDB / S3 | Global | Free; needs duckdb |

---

## Planned / Future Sources

### County Assessor Open Data (Socrata pattern)
Most California counties publish parcel data on Socrata-based portals.
The `BaseAssessorCollector` pattern works for all of them.

| County | Portal | Notes |
|--------|--------|-------|
| Alameda | data.acgov.org | Implemented (needs dataset ID) |
| Sacramento | data.saccounty.gov | Stub implemented |
| Contra Costa | data.contracostacounty.gov | TODO |
| San Francisco | data.sfgov.org | TODO |
| Santa Clara | data.sccgov.org | TODO |
| Los Angeles | assessor.lacounty.gov | TODO; different API structure |
| San Diego | data.sandiegocounty.gov | TODO |

### City Rental Registries
| City | URL | Format | Notes |
|------|-----|--------|-------|
| Oakland | data.oaklandca.gov | Socrata | Stub implemented |
| Berkeley | rentboard.cityofberkeley.info | Web only | PRA request recommended |
| Los Angeles | zimas.lacity.org | Web | LAHD data; check ToS |
| San Jose | www.sanjoseca.gov | Web | RSO list; check ToS |
| San Francisco | sfrb.org | Web | Check bulk download |

### Business Entity Data
| Source | URL | Format | Notes |
|--------|-----|--------|-------|
| CA Secretary of State | bizfileonline.sos.ca.gov | CSV bulk | Monthly free download |
| OpenCorporates | api.opencorporates.com | REST API | Free tier; implemented |
| EDGAR (SEC) | efts.sec.gov | REST API | For large public entities |

### Public Property Listing Sites
> **Note**: These sources require careful ToS review before automated access.
> Many prohibit scraping. Use only where explicitly permitted.

| Site | ToS Status | Notes |
|------|------------|-------|
| Apartments.com | Check ToS | Check robots.txt; may prohibit scraping |
| Zillow | Prohibits scraping | Do not use |
| Craigslist | Prohibits scraping | Do not use |
| HUD Multifamily | Public | HUD-assisted properties only |
| LIHTC database | Public | Low-income housing only |

### Geographic / Map Data
| Source | License | Notes |
|--------|---------|-------|
| Overture Maps Places | CDLA Permissive 2.0 | Implemented; needs duckdb |
| OpenStreetMap | ODbL | Building footprints |
| TIGER/Line | Public domain | Census geographic data |

### HUD / Federal Sources
| Source | URL | Notes |
|--------|-----|-------|
| HUD Multifamily Housing | hudgis-hud.opendata.arcgis.com | Assisted housing only |
| LIHTC Database | huduser.gov | Tax credit properties |
| HMDA | consumerfinance.gov | Mortgage origination data |

---

## How to Evaluate a New Source

Before adding a new data source, verify:

1. **Legal basis**: Is the data public record or explicitly licensed for reuse?
2. **Terms of Service**: Does the ToS permit automated access?
3. **robots.txt**: Does the site's robots.txt block our user agent?
4. **Rate limits**: What are the API rate limits or request policies?
5. **Data quality**: Does the data include address + owner + unit count?
6. **Update frequency**: How often is the data refreshed?
7. **Attribution requirements**: Do we need to credit the source?

Only add sources that pass all checks.
