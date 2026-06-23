# Seed Synthetic Data

Generate and insert deterministic synthetic PE data (companies, financials, contracts, risks, milestones, comps, market signals, LP contacts).

## Run

```bash
# Full seed (40 synthetic companies + all related data + RAG documents)
python -m synthetic.generate --seed 42

# Truncate and re-seed (preserves chat history)
python -m synthetic.generate --seed 42 --fresh

# OLTP only (skip RAG embedding — faster)
python -m synthetic.generate --skip-rag

# Small subset for fast iteration
python -m synthetic.generate --limit 5
```

## What gets seeded

- ~40 companies across 6 sectors (software, healthcare, industrials, consumer, business services, financial services)
- Cap tables, monthly financials (36 months), customer MSAs + supplier contracts
- Deal risks (3-6 per company, P×I scored) and milestones (4-7 per active deal)
- Transaction comps and trading comps
- Market signals (M&A, fundraising, executive moves)
- 60 LP contacts
- RAG documents (company memos, industry reports)
- Triage scores (weighted priority model) on all companies

## Notes

- Data is deterministic given `--seed` — same seed always produces same data
- Smoke tests depend on seed 42 anchors (Northwind Systems, Meridian Healthcare)
- Scraped real companies (EE/LT/LV) are separate — use `scripts/load_*_data` for those
- Run `python -m db.migrate` first if tables don't exist yet
