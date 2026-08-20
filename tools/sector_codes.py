"""Industry sector-code taxonomy — one source of truth for classification codes.

Maps national industry classification codes to PEHero's internal
``(sector, sub_sector)`` taxonomy and to clinical/business "verticals" that a
screen can name directly (``dental``, ``dermatology``, …) instead of
hand-writing ``ILIKE`` fragments.

Code systems covered:

- **EMTAK** — Estonia's 5-digit classification (Äriregister / Statistics Estonia),
  a national extension of NACE Rev.2. Codes like ``86230`` (dental practice).
- **NACE Rev.2** — the EU standard; Lithuania's EVRK and Latvia's NACE are
  national versions of it. Dotted codes like ``86.23`` (dental practice).

The company table stores free-text ``sub_sector`` (and sometimes a code), so the
resolver exposes, per vertical: the internal sub_sector labels, the EMTAK / NACE
codes, and multilingual name/description keywords (ET/LT/LV/EN). ``build_screen_sql``
turns a set of verticals into a parameterised SQL fragment usable anywhere a
``fetch_all`` screen runs.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Vertical:
    key: str
    label: str
    sector: str
    sub_sectors: tuple[str, ...]   # internal sub_sector labels this vertical wears
    emtak: tuple[str, ...]         # Estonia EMTAK 5-digit codes
    nace: tuple[str, ...]          # NACE Rev.2 / EVRK / LV codes (dotted)
    keywords: tuple[str, ...]      # ET/LT/LV/EN name & description keywords
    clinical: bool = True          # True = direct care provider (vs. adjacency)


# ── The taxonomy ─────────────────────────────────────────────────────────
# Healthcare is the worked-out branch (this codebase's focus); other sectors
# are stubs to extend the same way.

VERTICALS: dict[str, Vertical] = {
    "dental": Vertical(
        key="dental", label="Dental practices & clinics", sector="healthcare",
        sub_sectors=("Dental practice", "Dental clinics"),
        emtak=("86230",), nace=("86.23",),
        keywords=("dental", "dentist", "dental", "dantų", "odontolog",
                  "hambaravi", "hambaarst", "zobārst"),
    ),
    "dermatology": Vertical(
        key="dermatology", label="Dermatology & skin clinics", sector="healthcare",
        # Dermatology is not its own code — it sits under specialist medical
        # practice (EMTAK 86220 / NACE 86.22); disambiguated by keyword.
        sub_sectors=("Specialist medical practice",),
        emtak=("86220",), nace=("86.22",),
        keywords=("dermatolog", "skin clinic", "skin care", "aesthetic",
                  "cosmetolog", "naha", "nahaarst", "odos", "ādas", "āda"),
    ),
    "general_medical": Vertical(
        key="general_medical", label="General medical practice", sector="healthcare",
        sub_sectors=("General medical practice",),
        emtak=("86210",), nace=("86.21",),
        keywords=("general practice", "family medicine", "gp clinic",
                  "perearst", "šeimos", "ģimenes ārsts"),
    ),
    "specialist_medical": Vertical(
        key="specialist_medical", label="Specialist medical practice", sector="healthcare",
        sub_sectors=("Specialist medical practice",),
        emtak=("86220",), nace=("86.22",),
        keywords=("specialist medical", "eriarst", "specialist clinic"),
    ),
    "health_clinic": Vertical(
        key="health_clinic", label="Health & medical clinics", sector="healthcare",
        # Only the specific clinical label (LT loader) triggers on sub_sector.
        # The generic "Healthcare" label (LV loader) is deliberately excluded —
        # it is over-applied to non-clinical firms — so LV rows qualify only when
        # the NAME carries a clinic keyword below.
        sub_sectors=("Health care institutions", "Ambulance & emergency services"),
        emtak=("86901",), nace=("86.90",),
        keywords=("clinic", "klinik", "klinika", "slimnīc", "slimnic",
                  "sveikatos", "medicinos", "ārstniec"),
    ),
    "veterinary": Vertical(
        key="veterinary", label="Veterinary clinics (animal health)", sector="healthcare",
        sub_sectors=("Veterinary clinics",),
        emtak=("75001",), nace=("75.00", "75.0", "75"),
        keywords=("veterinar", "vet clinic", "loomaarst", "veterinarij"),
        clinical=True,  # clinical, but animal — usually excluded from human-health screens
    ),
    # Non-clinical healthcare adjacencies — deliberately NOT care providers.
    "pharmacy": Vertical(
        key="pharmacy", label="Pharmacy & medical materials", sector="healthcare",
        sub_sectors=("Pharmacy & medical materials",),
        emtak=("47730", "47740"), nace=("47.73", "47.74"),
        keywords=("pharmac", "apteek", "vaistin", "aptiek", "medical materials"),
        clinical=False,
    ),
    "medical_devices": Vertical(
        key="medical_devices", label="Medical devices wholesale", sector="healthcare",
        sub_sectors=("Medical devices wholesale",),
        emtak=("46462",), nace=("46.46",),
        keywords=("medical device", "device wholesale", "medical wholesale"),
        clinical=False,
    ),
}

# Verticals that must never count as a human-health care provider.
NON_HUMAN_HEALTH = ("veterinary", "pharmacy", "medical_devices")

# Consolidated code → (sector, sub_sector), rebuilt from the verticals above so
# the scrapers and any future code column share one map.
EMTAK: dict[str, tuple[str, str]] = {
    code: (v.sector, v.sub_sectors[0])
    for v in VERTICALS.values() for code in v.emtak
}
NACE: dict[str, tuple[str, str]] = {
    code: (v.sector, v.sub_sectors[0])
    for v in VERTICALS.values() for code in v.nace
}

# Free-text synonyms → vertical key, for resolve_vertical.
_SYNONYMS = {
    "derma": "dermatology", "dermatological": "dermatology", "skin": "dermatology",
    "dentistry": "dental", "odontology": "dental",
    "gp": "general_medical", "family medicine": "general_medical",
    "vet": "veterinary",
    "health": "health_clinic", "medical": "health_clinic", "clinic": "health_clinic",
}


def resolve_vertical(name: str) -> Vertical | None:
    """Resolve a free-text vertical name to a Vertical (key, label, synonym or keyword)."""
    if not name:
        return None
    n = name.strip().lower()
    if n in VERTICALS:
        return VERTICALS[n]
    if n in _SYNONYMS:
        return VERTICALS[_SYNONYMS[n]]
    for v in VERTICALS.values():
        if n == v.label.lower() or any(n == kw or n in kw for kw in v.keywords):
            return v
    return None


def code_to_sector(code: str) -> tuple[str, str] | None:
    """Map an EMTAK (5-digit) or NACE (dotted) code to (sector, sub_sector)."""
    code = (code or "").strip()
    if code in EMTAK:
        return EMTAK[code]
    if code in NACE:
        return NACE[code]
    # NACE codes roll up: 86.221 → 86.22 → 86; EMTAK 86230 → 86.23.
    if "." in code:
        while "." in code and code:
            if code in NACE:
                return NACE[code]
            code = code.rsplit(".", 1)[0] if code.count(".") else code[:-1]
    elif code.isdigit() and len(code) >= 4:
        dotted = f"{code[:2]}.{code[2:4]}"
        if dotted in NACE:
            return NACE[dotted]
    return None


def _ilike_patterns(values) -> list[str]:
    seen, out = set(), []
    for v in values:
        p = f"%{v.lower()}%"
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def build_screen_sql(
    verticals,
    *,
    exclude_non_clinical: bool = True,
    sub_col: str = "sub_sector",
    name_col: str = "name",
    prefix: str = "tax",
) -> tuple[str, dict]:
    """Build a parameterised SQL fragment matching the given verticals.

    Matches on sub_sector labels + name/description keywords, and (by default)
    excludes the non-human-health adjacencies (veterinary, pharmacy, devices)
    plus wholesale/spa noise. Returns (sql_fragment, params) — merge params into
    your query's param dict and drop the fragment into a WHERE clause.

        frag, p = build_screen_sql(["dental", "dermatology", "health_clinic"])
        rows = fetch_all(f"SELECT ... WHERE ... AND {frag}", {**other_params, **p})
    """
    resolved = [v if isinstance(v, Vertical) else resolve_vertical(v) for v in verticals]
    resolved = [v for v in resolved if v is not None]

    sub_terms = [s for v in resolved for s in v.sub_sectors] + \
                [kw for v in resolved for kw in v.keywords]
    name_terms = [kw for v in resolved for kw in v.keywords]

    p_sub, p_name = f"{prefix}_sub", f"{prefix}_name"
    params: dict = {p_sub: _ilike_patterns(sub_terms), p_name: _ilike_patterns(name_terms)}
    frag = f"( {sub_col} ILIKE ANY(%({p_sub})s) OR {name_col} ILIKE ANY(%({p_name})s) )"

    if exclude_non_clinical:
        excl_terms = [s for k in NON_HUMAN_HEALTH for s in VERTICALS[k].sub_sectors]
        excl_terms += ["wholesale", "spa", "device"]
        excl_names = ["veterinar", "spa "]  # trailing space: "SPA <resort>", not "hospal" etc.
        p_xsub, p_xname = f"{prefix}_xsub", f"{prefix}_xname"
        params[p_xsub] = _ilike_patterns(excl_terms)
        params[p_xname] = _ilike_patterns(excl_names)
        frag += (f" AND NOT (COALESCE({sub_col}, '') ILIKE ANY(%({p_xsub})s))"
                 f" AND NOT (COALESCE({name_col}, '') ILIKE ANY(%({p_xname})s))")

    return frag, params
