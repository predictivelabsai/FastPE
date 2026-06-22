"""Synthetic PE company catalog — ~40 portfolio / pipeline companies across
6 sectors + North America / Europe.

Deterministic given the seed. Returns a list of dicts ready for bulk insert
into pehero.companies.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

HQs = [
    ("Austin", "TX", "USA"),
    ("Atlanta", "GA", "USA"),
    ("Boston", "MA", "USA"),
    ("Chicago", "IL", "USA"),
    ("Dallas", "TX", "USA"),
    ("Denver", "CO", "USA"),
    ("Minneapolis", "MN", "USA"),
    ("Nashville", "TN", "USA"),
    ("Charlotte", "NC", "USA"),
    ("New York", "NY", "USA"),
    ("Columbus", "OH", "USA"),
    ("San Francisco", "CA", "USA"),
    ("Seattle", "WA", "USA"),
    ("Toronto", "ON", "CAN"),
    ("London", "", "GBR"),
    ("Amsterdam", "", "NLD"),
]

# (sector, count_target, sub_sector_choices, rev_range, ebitda_margin_range, growth_range)
SECTOR_MIX = [
    ("software",            10,
     ["Vertical SaaS", "Data & Analytics", "Cybersecurity", "DevOps", "FinTech SaaS",
      "HR Tech", "LegalTech"],
     (10_000_000, 140_000_000), (15, 35), (8, 35)),
    ("healthcare",           7,
     ["Healthcare Services", "Specialty Physician Practices", "HCIT", "Medical Devices",
      "Behavioral Health", "Home Care"],
     (25_000_000, 260_000_000), (10, 22), (6, 18)),
    ("industrials",          8,
     ["Specialty Manufacturing", "Distribution", "Industrial Services", "Aerospace & Defense",
      "Test & Measurement", "Electrical Products"],
     (40_000_000, 420_000_000), (9, 20), (2, 10)),
    ("consumer",             5,
     ["Consumer Products", "Pet", "Consumer Health", "Food & Beverage", "E-commerce"],
     (30_000_000, 180_000_000), (8, 18), (3, 14)),
    ("business_services",    6,
     ["Staffing", "Testing Inspection & Certification", "Route-Based Services",
      "Marketing Services", "Residential Services"],
     (25_000_000, 220_000_000), (12, 24), (5, 15)),
    ("financial_services",   4,
     ["Insurance Brokerage", "Specialty Lending", "Wealth Management", "Payments"],
     (20_000_000, 180_000_000), (20, 35), (4, 14)),
]

OWNERSHIPS = ["founder", "founder", "family", "pe_backed", "pe_backed", "vc_backed", "corporate_carve_out"]
DEAL_STAGES = ["sourced", "screened", "loi", "diligence", "ic", "signed", "closed", "held", "exited", "passed"]
DEAL_TYPES = ["platform", "platform", "add_on", "carve_out", "minority", "recap", "secondary"]
SELLER_INTENT = ["cold", "cold", "warm", "warm", "hot"]

# Synthetic name generators by sector
SOFTWARE_PREFIXES = ["Northwind", "Axiom", "Lumen", "Meridian", "Cascade", "Orbital", "Arcadia",
                     "Sentinel", "Verdant", "Parallax", "Pinnacle", "Quantum", "Vertex"]
SOFTWARE_SUFFIXES = ["Systems", "Analytics", "Labs", "Cloud", "Platform", "Works", "IO", "Logic"]
HEALTH_PREFIXES = ["Meridian", "Evergreen", "Keystone", "Beacon", "Cornerstone", "Summit", "Elevate", "Pinecrest"]
HEALTH_SUFFIXES = ["Health", "Medical", "Care", "Clinics", "Partners", "Physicians"]
INDUSTRIAL_PREFIXES = ["Atlas", "Ironwood", "Reliant", "Precision", "Frontier", "Anvil", "Sterling", "Hudson"]
INDUSTRIAL_SUFFIXES = ["Industries", "Manufacturing", "Services", "Group", "Technologies", "Corp"]
CONSUMER_PREFIXES = ["Wildroot", "Harbor", "Hearth", "Ember", "Fieldhouse", "Maple", "Tidewater", "Coastwise"]
CONSUMER_SUFFIXES = ["Brands", "Co", "Goods", "Kitchen", "Pet", "Provisions"]
BIZ_PREFIXES = ["Summit", "Pacific", "Stride", "Corbin", "Apex", "Stonebridge", "Gateway"]
BIZ_SUFFIXES = ["Services", "Solutions", "Partners", "Group", "Inc"]
FIN_PREFIXES = ["Ridgeline", "Keystone", "Granite", "Navigator", "Anchor"]
FIN_SUFFIXES = ["Financial", "Capital", "Insurance", "Wealth", "Payments"]

PREFIX_BY_SECTOR = {
    "software": (SOFTWARE_PREFIXES, SOFTWARE_SUFFIXES),
    "healthcare": (HEALTH_PREFIXES, HEALTH_SUFFIXES),
    "industrials": (INDUSTRIAL_PREFIXES, INDUSTRIAL_SUFFIXES),
    "consumer": (CONSUMER_PREFIXES, CONSUMER_SUFFIXES),
    "business_services": (BIZ_PREFIXES, BIZ_SUFFIXES),
    "financial_services": (FIN_PREFIXES, FIN_SUFFIXES),
}


@dataclass
class CompanySpec:
    slug: str
    name: str
    hq_city: str
    hq_state: str
    country: str
    sector: str
    sub_sector: str
    website: str
    founded_year: int
    employees: int
    revenue_ltm: float
    ebitda_ltm: float
    ebitda_margin: float
    growth_rate: float
    ownership: str
    deal_stage: str
    deal_type: str
    enterprise_value: float | None
    ask_multiple: float | None
    description: str
    seller_intent: str
    triage_score: float | None
    triage_priority: str | None


def _name_for(sector: str, rng: random.Random) -> str:
    prefixes, suffixes = PREFIX_BY_SECTOR[sector]
    p = rng.choice(prefixes)
    s = rng.choice(suffixes)
    return f"{p} {s}"


def _triage(revenue: float, margin: float, growth: float,
            sector: str, intent: str, stage: str) -> tuple[float, str]:
    from utils.scoring import triage_score
    return triage_score(revenue=revenue, ebitda_margin=margin, growth_rate=growth,
                        sector=sector, seller_intent=intent, deal_stage=stage)


def _ask_multiple(sector: str, growth: float, margin: float, rng: random.Random) -> float:
    base = {
        "software": 13.0,
        "healthcare": 11.0,
        "industrials": 9.0,
        "consumer": 10.0,
        "business_services": 10.0,
        "financial_services": 11.0,
    }[sector]
    growth_premium = max(0, (growth - 8) * 0.15)
    margin_premium = max(0, (margin - 18) * 0.05)
    noise = rng.uniform(-1.2, 1.2)
    return round(max(5.0, base + growth_premium + margin_premium + noise), 2)


ANCHORS = [
    # (slug, name, sector, sub_sector, revenue, margin, growth, ownership, deal_stage, deal_type, hq_city, hq_state, country, founded, employees)
    ("northwind-systems",   "Northwind Systems",   "software",   "Vertical SaaS",
     62_000_000, 26.0, 22.0, "founder", "diligence", "platform",
     "Austin", "TX", "USA", 2011, 280),
    ("meridian-healthcare", "Meridian Healthcare", "healthcare", "Specialty Physician Practices",
     128_000_000, 17.0, 11.0, "family",  "ic",        "platform",
     "Nashville", "TN", "USA", 2004, 640),
]


def generate(seed: int = 42) -> list[dict]:
    rng = random.Random(seed)
    specs: list[CompanySpec] = []
    slug_counter: dict[str, int] = {}
    reserved_names: set[str] = set()

    def next_slug(base: str) -> str:
        slug_counter[base] = slug_counter.get(base, 0) + 1
        n = slug_counter[base]
        return base if n == 1 else f"{base}-{n}"

    # ── Deterministic anchors first — example prompts in registry.py
    # reference "Meridian Healthcare" / "Northwind Systems" by name. Without
    # these two rows the IC memo / triage agents fail to resolve the company
    # when a user runs the canned prompt. ────────────────────────────────
    for (slug, name, sector, sub_sector, revenue, margin, growth,
         ownership, deal_stage, deal_type,
         city, state, country, founded, employees) in ANCHORS:
        ebitda = round(revenue * margin / 100, 0)
        ask_mult = _ask_multiple(sector, growth, margin, rng)
        ev = round(ebitda * ask_mult, 0)
        descr = (
            f"{name} is a {sub_sector.lower()} business headquartered in {city}"
            + (f", {state}" if state else "")
            + f", founded in {founded}. LTM revenue €{revenue/1_000_000:.0f}M, "
            f"{margin:.0f}% EBITDA margin, growing {growth:.0f}% YoY. "
            f"{ownership.replace('_', ' ')}-owned; currently {deal_stage}."
        )
        ts, tp = _triage(revenue, margin, growth, sector, "warm", deal_stage)
        specs.append(CompanySpec(
            slug=slug, name=name, hq_city=city, hq_state=state, country=country,
            sector=sector, sub_sector=sub_sector,
            website=slug.replace("-", "") + ".com",
            founded_year=founded, employees=employees,
            revenue_ltm=revenue, ebitda_ltm=ebitda, ebitda_margin=margin,
            growth_rate=growth, ownership=ownership, deal_stage=deal_stage,
            deal_type=deal_type, enterprise_value=ev, ask_multiple=ask_mult,
            description=descr, seller_intent="warm",
            triage_score=ts, triage_priority=tp,
        ))
        slug_counter[slug] = 1
        reserved_names.add(name)

    for sector, count, sub_sectors, rev_range, margin_range, growth_range in SECTOR_MIX:
        for _ in range(count):
            city, state, country = rng.choice(HQs)
            sub = rng.choice(sub_sectors)
            name = _name_for(sector, rng)
            founded = rng.randint(1992, 2018)
            revenue = round(rng.uniform(*rev_range), 0)
            margin = round(rng.uniform(*margin_range), 2)
            ebitda = round(revenue * margin / 100, 0)
            growth = round(rng.uniform(*growth_range), 2)
            employees = int(revenue / rng.uniform(180_000, 350_000))

            ownership = rng.choice(OWNERSHIPS)
            deal_stage = rng.choice(DEAL_STAGES)
            deal_type = rng.choice(DEAL_TYPES)
            ask_mult = _ask_multiple(sector, growth, margin, rng)
            ev = round(ebitda * ask_mult, 0)
            intent = rng.choice(SELLER_INTENT)

            descr = (
                f"{name} is a {sub.lower()} business headquartered in {city}"
                + (f", {state}" if state else "")
                + f", founded in {founded}. LTM revenue ${revenue/1_000_000:.0f}M, "
                f"{margin:.0f}% EBITDA margin, growing {growth:.0f}% YoY. "
                f"{ownership.replace('_', ' ')}-owned; currently {deal_stage}."
            )
            website = name.lower().replace(" ", "") + ".com"

            slug_base = name.lower().replace(" ", "-").replace(",", "").replace("'", "")
            slug_base = "".join(c for c in slug_base if c.isalnum() or c == "-")
            slug = next_slug(slug_base[:50])

            ts, tp = _triage(revenue, margin, growth, sector, intent, deal_stage)
            specs.append(CompanySpec(
                slug=slug,
                name=name,
                hq_city=city,
                hq_state=state,
                country=country,
                sector=sector,
                sub_sector=sub,
                website=website,
                founded_year=founded,
                employees=employees,
                revenue_ltm=revenue,
                ebitda_ltm=ebitda,
                ebitda_margin=margin,
                growth_rate=growth,
                ownership=ownership,
                deal_stage=deal_stage,
                deal_type=deal_type,
                enterprise_value=ev if deal_stage not in {"exited", "passed"} else None,
                ask_multiple=ask_mult if deal_stage not in {"exited", "passed"} else None,
                description=descr,
                seller_intent=intent,
                triage_score=ts,
                triage_priority=tp,
            ))

    return [s.__dict__ for s in specs]
