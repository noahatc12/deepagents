# Roadmap

## Phase 1: MVP (Current)

**Goal**: Run a complete pipeline from public data sources to a clean lead CSV on a laptop.

- [x] Pluggable collector architecture
- [x] CSV import collector (user-supplied property list)
- [x] County assessor collector (Alameda, Sacramento stubs)
- [x] City rental registry collector (Oakland, Berkeley stubs)
- [x] Overture Maps Places collector
- [x] Address normalization + deduplication
- [x] Rule-based management classifier
- [x] Known PM company entity matching
- [x] CA SOS entity enricher (bulk CSV)
- [x] OpenCorporates entity enricher
- [x] CSV / Excel / JSON / SQLite export
- [x] Manual review queue export
- [x] CLI entry point (`python -m apartment_leads run`)
- [x] YAML config files per market
- [x] robots.txt compliance + rate limiting + retry logic
- [x] Disk-based HTTP cache (avoids re-fetching)
- [x] Docker support
- [x] Test suite

---

## Phase 2: Better Enrichment

**Goal**: Improve owner contact data quality.

- [ ] Validate CA SOS bulk CSV column mapping against live file
- [ ] Implement full Sacramento assessor Socrata mapping
- [ ] Add Contra Costa County assessor adapter
- [ ] Add San Francisco assessor adapter (data.sfgov.org)
- [ ] Add LA County assessor adapter (different API structure)
- [ ] Add USPS address validation (via SmartyStreets free tier or similar)
- [ ] Add phone number validation / carrier lookup
- [ ] Add email format validation
- [ ] Add "same-entity different name" fuzzy matching for deduplication
- [ ] Improve unit count extraction (use parcel land use codes)
- [ ] Add assessor-recorded year built as filter
- [ ] Add Overture Maps to fetch building footprint area as proxy for unit count

---

## Phase 3: LLM-Assisted Review

**Goal**: Reduce the manual review queue with AI assistance.

- [ ] Implement `OpenAIReviewer` (LLMReviewerProtocol)
- [ ] Add Claude API reviewer option
- [ ] Prompt engineering for management classification
- [ ] Batch LLM calls with cost estimation
- [ ] Store LLM review rationale in `notes` field
- [ ] Add confidence calibration based on LLM agreement rate

---

## Phase 4: Review Dashboard

**Goal**: Simple web UI for reviewing the leads queue.

- [ ] Flask/FastAPI backend serving SQLite data
- [ ] Table view with sort/filter by status, city, units
- [ ] One-click approve / reject / flag for follow-up
- [ ] Notes field for reviewer comments
- [ ] Export filtered subset from UI

---

## Phase 5: CRM Export

**Goal**: Push leads directly to outreach tools.

- [ ] HubSpot CRM export (via API)
- [ ] Salesforce export (via API or CSV)
- [ ] Airtable export
- [ ] Google Sheets export
- [ ] Mailchimp / email list export

---

## Phase 6: Scheduled Recurring Runs

**Goal**: Automated weekly refresh of lead data.

- [ ] GitHub Actions workflow for scheduled runs
- [ ] Docker Compose with cron
- [ ] Delta detection: flag newly appeared / disappeared properties
- [ ] Owner change detection (assessor records)
- [ ] Email / Slack notification of new leads
- [ ] Incremental database upserts (not full re-run)
