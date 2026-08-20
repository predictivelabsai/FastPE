---
name: sector-taxonomy
description: Map national industry classification codes (EMTAK for Estonia, NACE for Lithuania/Latvia) to PEHero's internal sector/sub_sector taxonomy and to named clinical/business "verticals" (dental, dermatology, general medical, …). Use whenever a task screens, classifies, or filters companies by industry — building a sourcing screen, translating a scraped EMTAK/NACE code, deciding which sub_sector labels a vertical covers, or excluding non-clinical adjacencies (pharmacy, medical devices, veterinary). Backed by tools/sector_codes.py.
---

# Sector-code taxonomy

`tools/sector_codes.py` is the single source of truth that maps industry
classification **codes** to PEHero's internal **`(sector, sub_sector)`** taxonomy
and to named **verticals** a screen can request by name. Reach for it instead of
hand-writing `ILIKE '%dental%'` fragments — those drift, miss multilingual names,
and silently re-admit noise (a wine company mislabelled "Healthcare" in the LV
registry data).

## Code systems

- **EMTAK** — Estonia's 5-digit classification (Äriregister / Statistics Estonia),
  a national extension of NACE Rev.2. E.g. `86230` = dental practice.
- **NACE Rev.2** — the EU standard. Lithuania's **EVRK** and Latvia's classifier
  are national versions. Dotted, e.g. `86.23` = dental practice.

The `companies` table stores a free-text `sub_sector` (not a code column), so the
taxonomy resolves each vertical to three things: the internal **sub_sector labels**
it wears, its **EMTAK/NACE codes**, and multilingual **name/description keywords**
(ET/LT/LV/EN). Screens match on labels + keywords; the codes document provenance
and feed the scrapers.

## Verticals (healthcare branch)

| Vertical | Sub_sector label(s) | EMTAK | NACE | Clinical? |
|---|---|---|---|---|
| `dental` | Dental practice / Dental clinics | 86230 | 86.23 | ✅ |
| `dermatology` | Specialist medical practice (＋ skin keywords) | 86220 | 86.22 | ✅ |
| `general_medical` | General medical practice | 86210 | 86.21 | ✅ |
| `specialist_medical` | Specialist medical practice | 86220 | 86.22 | ✅ |
| `health_clinic` | Health care institutions / Ambulance & emergency | 86901 | 86.90 | ✅ |
| `veterinary` | Veterinary clinics | 75001 | 75.00 | animal — excluded from human-health screens |
| `pharmacy` | Pharmacy & medical materials | 47730/47740 | 47.73 | ❌ non-clinical |
| `medical_devices` | Medical devices wholesale | 46462 | 46.46 | ❌ non-clinical |

**Dermatology has no code of its own** — it sits under *specialist medical
practice* (EMTAK 86220 / NACE 86.22), disambiguated by keyword (`dermatolog`,
`skin`, `naha`, `odos`, `ādas`, …). That is why a dermatology screen must go
through the taxonomy rather than a sub_sector match alone.

## How to use it

**Resolve a vertical or a code:**
```python
from tools.sector_codes import resolve_vertical, code_to_sector

resolve_vertical("dermatology")   # Vertical(key='dermatology', label='Dermatology & skin clinics', …)
resolve_vertical("skin")          # same — synonym/keyword resolution
code_to_sector("86230")           # ('healthcare', 'Dental practice')   — EMTAK
code_to_sector("86.22")           # ('healthcare', 'Specialist medical practice')  — NACE
code_to_sector("86.221")          # rolls up to the nearest known NACE level
```

**Build a screen** — the main entry point. Pass vertical keys (or free-text names);
get back a parameterised SQL fragment + params. By default it excludes veterinary,
pharmacy, devices, wholesale and spa noise:
```python
from tools.sector_codes import build_screen_sql
from db import fetch_all

frag, p = build_screen_sql(["dental", "dermatology", "health_clinic"])
rows = fetch_all(
    f"""SELECT slug, name, country, sub_sector, revenue_ltm, ownership
        FROM pehero.companies
        WHERE sector = 'healthcare'
          AND {frag}
          AND revenue_ltm BETWEEN %(rmin)s AND %(rmax)s""",
    {"rmin": 3_000_000, "rmax": 10_000_000, **p},
)
```
Pass `exclude_non_clinical=False` to keep the adjacencies, or `sub_col`/`name_col`
to target different columns.

## Worked example

`evals/run_screen_eval.py` uses this to screen Baltic health/dental/dermatology
clinics with non-institutional ownership and €3–10M revenue:
```python
SCREEN_VERTICALS = ("dental", "dermatology", "general_medical",
                    "specialist_medical", "health_clinic")
tax_frag, tax_params = build_screen_sql(SCREEN_VERTICALS)
```
Run `python -m evals.run_screen_eval --no-llm` to see the deterministic universe.

## Extending it

- **New vertical:** add a `Vertical(...)` to `VERTICALS` with its sub_sector
  labels, EMTAK + NACE codes, and multilingual keywords. The `EMTAK`/`NACE`
  lookup maps and `build_screen_sql` pick it up automatically.
- **Non-clinical adjacency:** set `clinical=False` and, if it should never count
  as care, add its key to `NON_HUMAN_HEALTH` so `build_screen_sql` excludes it.
- **Keep it aligned with the scrapers:** `scripts/scrape_ee.py` (EMTAK map) and
  `scripts/scrape_lv.py` (NACE map) are the upstream code sources — when they gain
  a code, mirror it here so classification stays consistent end to end.
- **Data caveat:** the LV loader tags many firms with the generic `sub_sector =
  "Healthcare"`, including non-clinical ones. The taxonomy deliberately does **not**
  treat that bare label as a clinic — LV rows qualify only when the company **name**
  carries a clinic keyword (`klinik`, `slimnīc`, `dental`, …).
