# Scrape & Load Regional Data

Scrape Baltic company data from registries and load into the database.

## Estonia

```bash
python -m scripts.scrape_ee                      # scrape companies → data/ee_companies.json
python -m scripts.load_ee_data                   # load JSON into DB
python -m scripts.scrape_ee_owners               # scrape ownership data
python -m scripts.scrape_ee_owners --dry-run     # preview without writing
python -m scripts.load_ee_persons                # load persons into DB
python -m scripts.load_ee_persons --fresh        # truncate + reload
python -m scripts.scrape_ee_rich                 # scrape wealth rankings → data/ee_rich.json
python -m scripts.load_ee_persons --rich data/ee_rich.json  # merge wealth data
```

## Lithuania

```bash
python -m scripts.scrape_lt                      # scrape companies
python -m scripts.load_lt_data                   # load into DB
```

## Latvia, Poland, Romania

```bash
python -m scripts.scrape_lv                      # Latvia
python -m scripts.load_lv_data
python -m scripts.scrape_pl                      # Poland
python -m scripts.load_pl_data
python -m scripts.scrape_ro                      # Romania
python -m scripts.load_ro_data
```

## Notes

- All scrapers support `--dry-run` and `--limit N` flags
- JSON files are saved to `data/` directory
- Loaders are idempotent (upsert on slug/reg_code)
- Persons data includes ownership stakes, wealth rankings, company links
