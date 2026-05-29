"""Internationalisation — English + Estonian + Lithuanian.

Translation catalog, session language helpers, and the `t()` / `agent_t()` lookup
functions used by every UI module.
"""

from __future__ import annotations

from typing import Any

LANGUAGES: dict[str, dict[str, str]] = {
    "en": {"name": "English", "flag": "\U0001f1ec\U0001f1e7", "native": "English"},
    "et": {"name": "Estonian", "flag": "\U0001f1ea\U0001f1ea", "native": "Eesti"},
    "lt": {"name": "Lithuanian", "flag": "\U0001f1f1\U0001f1f9", "native": "Lietuvių"},
    "fi": {"name": "Finnish", "flag": "\U0001f1eb\U0001f1ee", "native": "Suomi"},
    "sv": {"name": "Swedish", "flag": "\U0001f1f8\U0001f1ea", "native": "Svenska"},
}

DEFAULT_LANG = "en"
SUPPORTED_LANGS = tuple(LANGUAGES.keys())

# ── IP-based detection ─────────────────────────────────────────────────
_ESTONIAN_IP_PREFIXES = (
    "85.253.", "90.190.", "90.191.", "80.235.",    # Telia EE
    "213.168.", "195.50.", "217.159.",              # Elisa / Starman
    "84.50.", "84.51.",                             # Tele2 EE
    "86.40.", "86.41.",                             # Levikom
    "194.126.",                                     # EENet / academic
)

_LITHUANIAN_IP_PREFIXES = (
    "78.56.", "78.57.", "78.58.", "78.59.",         # Telia LT
    "82.135.", "84.15.", "86.38.", "86.100.",       # Tele2 LT
    "88.118.", "88.119.",                           # Bite
    "90.131.", "91.204.", "91.211.",                # Various LT ISPs
    "193.219.", "195.14.", "212.52.", "213.252.",   # TEO / academic
)


def detect_language(request) -> str:
    """Detect language from IP address."""
    ip = _get_client_ip(request)
    if ip:
        if any(ip.startswith(p) for p in _ESTONIAN_IP_PREFIXES):
            return "et"
        if any(ip.startswith(p) for p in _LITHUANIAN_IP_PREFIXES):
            return "lt"
    return DEFAULT_LANG


def _get_client_ip(request) -> str | None:
    if not request:
        return None
    for header in ("x-forwarded-for", "x-real-ip"):
        val = request.headers.get(header) if hasattr(request, "headers") else None
        if val:
            return val.split(",")[0].strip()
    client = getattr(request, "client", None)
    if client:
        return client.host
    return None


# ── Session helpers ────────────────────────────────────────────────────

def get_lang(sess: dict[str, Any], request=None) -> str:
    lang = (sess.get("lang") or "").lower()
    if lang in SUPPORTED_LANGS:
        return lang
    if request:
        detected = detect_language(request)
        sess["lang"] = detected
        return detected
    return DEFAULT_LANG


def set_lang(sess: dict[str, Any], lang: str) -> str:
    code = (lang or "").lower()
    if code in SUPPORTED_LANGS:
        sess["lang"] = code
    return get_lang(sess)


# ── Translation catalog ───────────────────────────────────────────────

TRANSLATIONS: dict[str, dict[str, str]] = {

    # ── Navigation ─────────────────────────────────────────────────
    "nav_platform":      {"en": "Platform",      "et": "Platvorm",       "lt": "Platforma",
                          "fi": "Alusta", "sv": "Plattform"},
    "nav_agents":        {"en": "Agents",         "et": "Agendid",        "lt": "Agentai",
                          "fi": "Agentit", "sv": "Agenter"},
    "nav_how":           {"en": "How it works",   "et": "Kuidas toimib",  "lt": "Kaip tai veikia",
                          "fi": "Miten toimii", "sv": "Hur det fungerar"},
    "nav_pricing":       {"en": "Pricing",        "et": "Hinnakiri",      "lt": "Kainos",
                          "fi": "Hinnoittelu", "sv": "Prissättning"},
    "nav_contact":       {"en": "Contact",        "et": "Kontakt",        "lt": "Kontaktai",
                          "fi": "Yhteystiedot", "sv": "Kontakt"},
    "nav_book_demo":     {"en": "Book a demo",    "et": "Broneeri demo",  "lt": "Rezervuoti demo",
                          "fi": "Varaa demo", "sv": "Boka demo"},
    "nav_open_app":      {"en": "Open app",       "et": "Ava rakendus",   "lt": "Atidaryti",
                          "fi": "Avaa sovellus", "sv": "Öppna app"},

    # ── Hero section ──────────────────────────────────────────────
    "hero_eyebrow":      {"en": "Agentic AI for private equity",
                          "et": "Agentne AI erakapitalile",
                          "lt": "Agentinė AI privataus kapitalo komandai",
                          "fi": "Agenttitekoäly pääomasijoittamiseen", "sv": "Agentbaserad AI för private equity"},
    "hero_h1_1":         {"en": "Your Private Equity ",       "et": "Teie erakapitali ",          "lt": "Jūsų privataus kapitalo ",
                          "fi": "Teidän pääomasijoitus ", "sv": "Ert private equity "},
    "hero_h1_2":         {"en": "AI Agent Squad",             "et": "AI agentide meeskond",       "lt": "AI agentų komanda",
                          "fi": "AI-agenttitiimi", "sv": "AI-agentteam"},
    "hero_h1_3":         {"en": " — ",                        "et": " — ",                        "lt": " — ",
                          "fi": " — ", "sv": " — "},
    "hero_h1_4":         {"en": "sourcing, ",                 "et": "otsib, ",                    "lt": "ieško, ",
                          "fi": "etsii, ", "sv": "söker, "},
    "hero_h1_5":         {"en": "underwriting, ",             "et": "hindab, ",                   "lt": "vertina, ",
                          "fi": "arvioi, ", "sv": "bedömer, "},
    "hero_h1_6":         {"en": "and closing ",               "et": "ja sulgeb ",                 "lt": "ir uždaro ",
                          "fi": "ja sulkee ", "sv": "och stänger "},
    "hero_h1_7":         {"en": "your next platform.",        "et": "teie järgmise platvormi.",   "lt": "jūsų kitą platformą.",
                          "fi": "seuraavan alustanne.", "sv": "er nästa plattform."},
    "hero_lede":         {"en": "Not a prompt pack. Not a build-it-yourself kit. PEHero is a full agentic system "
                                "already wired into your deal flow — scanning targets, running QoE, building LBO "
                                "models, and drafting IC memos while your team focuses on the call.",
                          "et": "Mitte promptide kogum. Mitte 'ehita ise' komplekt. PEHero on täielik agentne süsteem, "
                                "mis on juba ühendatud teie tehingute voogu — skaneerib sihtmärke, teeb QoE-d, ehitab LBO "
                                "mudeleid ja koostab IC memosid, kuni teie meeskond keskendub kõnele.",
                          "lt": "Ne promptų rinkinys. Ne 'pasidaryk pats'. PEHero — pilna agentinė sistema, "
                                "jau integruota į jūsų sandorių srautą: skentuoja įmones, atlieka QoE, stato LBO "
                                "modelius ir rašo IC memo, kol jūsų komanda kalba telefonu.",
                          "fi": "Ei promptipakettia. Ei tee-se-itse-pakettia. PEHero on täysi agenttijärjestelmä, joka on jo kytketty kauppavirtoihinne — skannaa kohteita, tekee QoE:n, rakentaa LBO-malleja ja laatii IC-muistioita tiimienne keskittyessä puheluun.", "sv": "Inte ett prompt-paket. Inte ett bygg-det-själv-kit. PEHero är ett komplett agentsystem redan kopplat till ert deal flow — skannar mål, kör QoE, bygger LBO-modeller och skriver IC-memon medan ert team fokuserar på samtalet."},
    "hero_cta_open":     {"en": "Open the app",   "et": "Ava rakendus",   "lt": "Atidaryti programą",
                          "fi": "Avaa sovellus", "sv": "Öppna appen"},
    "hero_cta_meet":     {"en": "Meet the squad",  "et": "Tutvu meeskonnaga", "lt": "Susipažinkite su komanda",
                          "fi": "Tapaa tiimi", "sv": "Träffa teamet"},

    # ── Stat cells ─────────────────────────────────────────────────
    "stat_squad":        {"en": "Squad",            "et": "Meeskond",       "lt": "Komanda",
                          "fi": "Tiimi", "sv": "Team"},
    "stat_squad_cap":    {"en": "of PE specialists, on call",
                          "et": "PE spetsialisti, alati valmis",
                          "lt": "PE specialistų, visada pasiekiamų",
                          "fi": "PE-asiantuntijaa, aina valmiina", "sv": "PE-specialister, alltid tillgängliga"},
    "stat_5":            {"en": "5",                "et": "5",              "lt": "5",
                          "fi": "5", "sv": "5"},
    "stat_5_cap":        {"en": "workflow stages, end-to-end",
                          "et": "töövoo etappi, otsast otsani",
                          "lt": "darbo etapų, nuo pradžios iki galo",
                          "fi": "työnkulun vaihetta, alusta loppuun", "sv": "arbetsflödessteg, från början till slut"},
    "stat_90s":          {"en": "<90s",             "et": "<90s",           "lt": "<90s",
                          "fi": "<90s", "sv": "<90s"},
    "stat_90s_cap":      {"en": "to a go / no-go decision",
                          "et": "jah/ei otsuseni",
                          "lt": "iki 'taip / ne' sprendimo",
                          "fi": "kyllä/ei-päätökseen", "sv": "till ja/nej-beslut"},
    "stat_byod":         {"en": "BYOD",             "et": "BYOD",           "lt": "BYOD",
                          "fi": "BYOD", "sv": "BYOD"},
    "stat_byod_cap":     {"en": "bring your own data",
                          "et": "kasutage oma andmeid",
                          "lt": "naudokite savo duomenis",
                          "fi": "tuo omat tietosi", "sv": "använd egen data"},

    # ── Product tour ──────────────────────────────────────────────
    "tour_eyebrow":      {"en": "Product tour",     "et": "Tootetutvustus",   "lt": "Produkto apžvalga",
                          "fi": "Tuotekierros", "sv": "Produkttur"},
    "tour_heading":      {"en": "See it in motion.", "et": "Vaata tegevuses.", "lt": "Pamatykite veikime.",
                          "fi": "Katso toiminnassa.", "sv": "Se det i aktion."},
    "tour_body":         {"en": "A 30-second walk through chat, the pipeline kanban, deal detail, "
                                "analytics and prompt editing — BYOD: bring your own data and "
                                "see the squad in action on your deals.",
                          "et": "30-sekundiline ülevaade: vestlus, pipeline kanban, tehingu detailid, "
                                "analüütika ja promptide redigeerimine — BYOD: kasutage oma andmeid "
                                "ja vaadake meeskonda töös teie tehingutega.",
                          "lt": "30 sekundžių apžvalga: pokalbiai, sandorių kanban, sandorių detalės, "
                                "analitika ir promptų redagavimas — BYOD: naudokite savo duomenis "
                                "ir išbandykite komandą su tikrais sandoriais.",
                          "fi": "30 sekunnin katsaus: chat, pipeline-kanban, kaupan yksityiskohdat, analytiikka ja promptien muokkaus — BYOD: tuo omat tietosi ja katso tiimi töissä kaupoillasi.", "sv": "En 30-sekunders genomgång: chatt, pipeline kanban, deal-detaljer, analys och promptredigering — BYOD: använd din egen data och se teamet i aktion på dina deals."},
    "tour_pdf":          {"en": "Product tour (PDF)",  "et": "Ülevaade (PDF)",   "lt": "Apžvalga (PDF)",
                          "fi": "Tuotekierros (PDF)", "sv": "Produkttur (PDF)"},
    "tour_pptx":         {"en": "Product tour (PPTX)", "et": "Ülevaade (PPTX)",  "lt": "Apžvalga (PPTX)",
                          "fi": "Tuotekierros (PPTX)", "sv": "Produkttur (PPTX)"},
    "tour_readme":       {"en": "View README",        "et": "Vaata README",      "lt": "Žiūrėti README",
                          "fi": "Näytä README", "sv": "Visa README"},
    "tour_open_app":     {"en": "Open the app",        "et": "Ava rakendus",      "lt": "Atidaryti programą",
                          "fi": "Avaa sovellus", "sv": "Öppna appen"},

    # ── Pillars section ───────────────────────────────────────────
    "pillars_eyebrow":   {"en": "Five stages, one system",
                          "et": "Viis etappi, üks süsteem",
                          "lt": "Penki etapai, viena sistema",
                          "fi": "Viisi vaihetta, yksi järjestelmä", "sv": "Fem steg, ett system"},
    "pillars_heading":   {"en": "Every role your deal team plays — live inside PEHero.",
                          "et": "Iga roll, mida teie tehingumeeskond täidab — elab PEHero sees.",
                          "lt": "Visos jūsų sandorių komandos rolės — veikia PEHero viduje.",
                          "fi": "Jokainen rooli kauppatiimissänne — elää PEHeron sisällä.", "sv": "Varje roll ert deal-team spelar — lever i PEHero."},
    "agents_count":      {"en": "{n} agents",       "et": "{n} agenti",     "lt": "{n} agentų",
                          "fi": "{n} agenttia", "sv": "{n} agenter"},
    "see_all":           {"en": "See all {n} → ",   "et": "Vaata kõiki {n} → ", "lt": "Žiūrėti visus {n} → ",
                          "fi": "Näytä kaikki {n} → ", "sv": "Visa alla {n} → "},

    # ── How it works (home page) ──────────────────────────────────
    "how_eyebrow":       {"en": "How it works",         "et": "Kuidas toimib",      "lt": "Kaip tai veikia",
                          "fi": "Miten toimii", "sv": "Hur det fungerar"},
    "how_heading":       {"en": "Source → Underwrite → Close → Hold.",
                          "et": "Otsi → Hinda → Sulge → Halda.",
                          "lt": "Ieškoti → Vertinti → Uždaryti → Valdyti.",
                          "fi": "Etsi → Arvioi → Sulje → Hallitse.", "sv": "Sök → Bedöm → Stäng → Förvalta."},
    "how_01_title":      {"en": "Source deals that fit your mandate",
                          "et": "Leidke tehinguid, mis vastavad teie mandaadile",
                          "lt": "Raskite sandorius pagal savo mandatą",
                          "fi": "Löydä mandaattiinne sopivat kaupat", "sv": "Hitta deals som passar ert mandat"},
    "how_01_body":       {"en": "Market Scanner watches PitchBook, Grata, banker feeds, and proprietary founder outreach. "
                                "Deal Triage returns a go/no-go on each in under 90 seconds against your fund's criteria.",
                          "et": "Market Scanner jälgib PitchBook-i, Grata-t, pankurite voogusid ja otseseid asutajate pöördumisi. "
                                "Deal Triage annab jah/ei otsuse iga tehingu kohta alla 90 sekundiga vastavalt teie fondi kriteeriumidele.",
                          "lt": "Market Scanner stebi PitchBook, Grata, bankininkų srautus ir tiesiogines įkūrėjų užklausas. "
                                "Deal Triage pateikia 'taip/ne' sprendimą per 90 sekundžių pagal jūsų fondo kriterijus.",
                          "fi": "Market Scanner seuraa PitchBookia, Grataa, pankkiirien syötteitä ja suoria perustajayhteydenottoja. Deal Triage antaa kyllä/ei alle 90 sekunnissa rahastonne kriteerien perusteella.", "sv": "Market Scanner bevakar PitchBook, Grata, bankirflöden och direkta grundarkontakter. Deal Triage ger ja/nej på under 90 sekunder mot er fonds kriterier."},
    "how_02_title":      {"en": "Model them in hours, not weeks",
                          "et": "Modeleerige tundidega, mitte nädalatega",
                          "lt": "Sumodeliuokite per valandas, ne savaites",
                          "fi": "Mallinna tunneissa, ei viikoissa", "sv": "Modellera på timmar, inte veckor"},
    "how_02_body":       {"en": "Cap Table Parser, LTM Normalizer, and LBO Model Builder take seller financials "
                                "into an IC-ready 5-year model with sensitivity and debt stack — already benchmarked "
                                "against live transaction comps.",
                          "et": "Cap Table Parser, LTM Normalizer ja LBO Model Builder teisendavad müüja finantsandmed "
                                "IC-valmis 5-aasta mudeliks koos tundlikkuse analüüsi ja võlastruktuuriga — juba võrreldud "
                                "reaalsete tehingute kordajatega.",
                          "lt": "Cap Table Parser, LTM Normalizer ir LBO Model Builder paverčia pardavėjo finansinę ataskaitą "
                                "į IC parengtą 5 metų modelį su jautrumo analize ir skolos struktūra — jau palygintą "
                                "su rinkos sandorių dauginamaisiais.",
                          "fi": "Cap Table Parser, LTM Normalizer ja LBO Model Builder muuttavat myyjän taloustiedot IC-valmiiksi 5-vuoden malliksi herkkyysanalyysillä ja velkarakenteella — jo verrattu markkinoiden kauppakertoimiin.", "sv": "Cap Table Parser, LTM Normalizer och LBO Model Builder omvandlar säljarens finansdata till en IC-redo 5-årsmodell med känslighetsanalys och skuldstruktur — redan jämförd mot marknadens transaktionsmultiplar."},
    "how_03_title":      {"en": "Close, raise, and hold with conviction",
                          "et": "Sulgege, kaasake ja haldake enesekindlalt",
                          "lt": "Uždarykite, pritraukite ir valdykite užtikrintai",
                          "fi": "Sulje, kerää ja hallitse varmuudella", "sv": "Stäng, res kapital och förvalta med övertygelse"},
    "how_03_body":       {"en": "IC Memo Writer, Teaser Designer, LP Update Generator, and Portfolio Ops agents keep "
                                "every thesis, covenant, and KPI variance in view from signing through exit.",
                          "et": "IC Memo Writer, Teaser Designer, LP Update Generator ja Portfolio Ops agendid hoiavad "
                                "iga teesi, kovenanditingimuse ja KPI kõrvalekalde silme ees allkirjastamisest kuni väljumiseni.",
                          "lt": "IC Memo Writer, Teaser Designer, LP Update Generator ir Portfolio Ops agentai išlaiko "
                                "visą tezę, kovenantas ir KPI nukrypimus matomus nuo pasirašymo iki išėjimo.",
                          "fi": "IC Memo Writer, Teaser Designer, LP Update Generator ja Portfolio Ops -agentit pitävät jokaisen teesin, kovenantin ja KPI-poikkeaman näkyvillä allekirjoituksesta exitiin.", "sv": "IC Memo Writer, Teaser Designer, LP Update Generator och Portfolio Ops-agenter håller varje tes, covenant och KPI-avvikelse synlig från signering till exit."},

    # ── Case study strip ──────────────────────────────────────────
    "case_eyebrow":      {"en": "What you get",     "et": "Mida saate",         "lt": "Ką gausite",
                          "fi": "Mitä saatte", "sv": "Vad ni får"},
    "case_heading":      {"en": "Time compressed, confidence higher.",
                          "et": "Aeg kokku pressitud, kindlus suurem.",
                          "lt": "Laikas suspaustas, pasitikėjimas didesnis.",
                          "fi": "Aika puristettu, varmuus suurempi.", "sv": "Tid komprimerad, förtroende högre."},
    "case_1_label":      {"en": "Sourcing → triage",    "et": "Otsing → sõelumine",    "lt": "Paieška → atranka",
                          "fi": "Etsintä → seulonta", "sv": "Sökning → screening"},
    "case_1_metric":     {"en": "1,240 deals",          "et": "1 240 tehingut",         "lt": "1 240 sandorių",
                          "fi": "1 240 kauppaa", "sv": "1 240 deals"},
    "case_1_caption":    {"en": "surfaced and triaged against a lower-middle-market software mandate in one week of scanning.",
                          "et": "leitud ja sõelutud alamkeskmise turu tarkvaramandaadi vastu ühe skaneerimisnädalaga.",
                          "lt": "surasta ir atrinkta pagal žemesnės vidurinės rinkos programinės įrangos mandatą per vieną skenavimo savaitę.",
                          "fi": "löydetty ja seulottu alemman keskimarkkinan ohjelmistomandaattia vasten yhdessä skannausviikossa.", "sv": "identifierade och screenade mot ett lower-middle-market mjukvarumandat under en veckas skanning."},
    "case_2_label":      {"en": "Underwriting",         "et": "Hindamine",              "lt": "Vertinimas",
                          "fi": "Arviointi", "sv": "Bedömning"},
    "case_2_metric":     {"en": "3 days → 40 min",      "et": "3 päeva → 40 min",      "lt": "3 dienos → 40 min",
                          "fi": "3 päivää → 40 min", "sv": "3 dagar → 40 min"},
    "case_2_caption":    {"en": "from seller financials + cap table to a full 5-year LBO model with sensitivity and debt stack.",
                          "et": "müüja finantsandmetest + cap table'ist täieliku 5-aasta LBO mudelini koos tundlikkuse analüüsi ja võlastruktuuriga.",
                          "lt": "nuo pardavėjo finansinių ataskaitų + cap table iki pilno 5 metų LBO modelio su jautrumo analize ir skolos struktūra.",
                          "fi": "myyjän taloustiedoista + cap tablesta täydelliseen 5-vuoden LBO-malliin herkkyysanalyysillä ja velkarakenteella.", "sv": "från säljarfinanser + cap table till en komplett 5-års LBO-modell med känslighetsanalys och skuldstruktur."},
    "case_3_label":      {"en": "Capital",               "et": "Kapital",                "lt": "Kapitalas",
                          "fi": "Pääoma", "sv": "Kapital"},
    "case_3_metric":     {"en": "60 LPs, ranked",        "et": "60 LP-d, reastatud",     "lt": "60 LP, suranguoti",
                          "fi": "60 LP:tä, järjestetty", "sv": "60 LP:er, rankade"},
    "case_3_caption":    {"en": "by fund-fit, staleness, and commitment size — with drafted re-engagement emails.",
                          "et": "fondi sobivuse, vanuse ja kohustuse suuruse järgi — koos koostatud taaskontakti kirjadega.",
                          "lt": "pagal tinkamumą fondui, senumą ir įsipareigojimo dydį — su parengtais pakartotinio kontakto laiškais.",
                          "fi": "rahastosopivuuden, vanhenemisen ja sitoutumiskoon mukaan — valmiilla uudelleenkontaktointikirjeillä.", "sv": "efter fondpassning, inaktivitet och åtagandestorlek — med färdigställda återkontakt-mejl."},

    # ── CTA section ───────────────────────────────────────────────
    "cta_eyebrow":       {"en": "Talk to us",        "et": "Võtke ühendust",      "lt": "Susisiekite",
                          "fi": "Ota yhteyttä", "sv": "Kontakta oss"},
    "cta_headline":      {"en": "Stop stitching tools. Start closing deals.",
                          "et": "Lõpetage tööriistade lappimise. Hakake tehinguid sulgema.",
                          "lt": "Nustokite lipdyti įrankius. Pradėkite uždaryti sandorius.",
                          "fi": "Lopeta työkalujen paikkaus. Ala sulkea kauppoja.", "sv": "Sluta lappa ihop verktyg. Börja stänga deals."},
    "cta_body":          {"en": "Book a 20-minute walkthrough. We'll load one of your recent deals into PEHero "
                                "and show you the full agent flow end-to-end.",
                          "et": "Broneerige 20-minutiline tutvustus. Laadime ühe teie hiljutise tehingu PEHerosse "
                                "ja näitame kogu agentide töövoogu otsast otsani.",
                          "lt": "Užsisakykite 20 minučių demonstraciją. Įkelkime vieną iš jūsų sandorių "
                                "į PEHero ir parodysime pilną agentų darbo eigą.",
                          "fi": "Varaa 20 minuutin esittely. Lataamme yhden viimeisistä kaupoistanne PEHeroon ja näytämme koko agenttivirran alusta loppuun.", "sv": "Boka en 20-minuters genomgång. Vi laddar en av era senaste deals i PEHero och visar hela agentflödet från början till slut."},
    "cta_book":          {"en": "Book a demo",       "et": "Broneeri demo",       "lt": "Rezervuoti demo",
                          "fi": "Varaa demo", "sv": "Boka demo"},
    "cta_byod":          {"en": "BYOD — bring your own data",
                          "et": "BYOD — kasutage oma andmeid",
                          "lt": "BYOD — naudokite savo duomenis",
                          "fi": "BYOD — tuo omat tietosi", "sv": "BYOD — använd egen data"},

    # ── Footer ────────────────────────────────────────────────────
    "footer_product":    {"en": "Product",           "et": "Toode",              "lt": "Produktas",
                          "fi": "Tuote", "sv": "Produkt"},
    "footer_company":    {"en": "Company",           "et": "Ettevõte",           "lt": "Įmonė",
                          "fi": "Yritys", "sv": "Företag"},
    "footer_tagline":    {"en": "Built by a small team that's sourced, underwritten, and held the phone at 2 AM the night before IC.",
                          "et": "Ehitatud väikese meeskonna poolt, kes on otsinud, hinnanud ja hoidnud telefoni kell 2 öösel enne IC-d.",
                          "lt": "Sukurta nedidelės komandos, kuri ieškojo, vertino ir laikė telefoną 2 val. nakties prieš IC.",
                          "fi": "Rakennettu pienen tiimin voimin, joka on etsinyt, arvioinut ja pitänyt puhelinta kello 2 yöllä ennen IC:tä.", "sv": "Byggt av ett litet team som har sourcat, bedömt och hållit telefonen kl 2 på natten inför IC."},
    "footer_open_app":   {"en": "Open the app",      "et": "Ava rakendus",       "lt": "Atidaryti programą",
                          "fi": "Avaa sovellus", "sv": "Öppna appen"},

    # ── Platform page ─────────────────────────────────────────────
    "platform_title":    {"en": "Platform",          "et": "Platvorm",           "lt": "Platforma",
                          "fi": "Alusta", "sv": "Plattform"},
    "platform_h1":       {"en": "One system. Every stage. All your deal data.",
                          "et": "Üks süsteem. Iga etapp. Kõik teie tehinguandmed.",
                          "lt": "Viena sistema. Visi etapai. Visi jūsų sandorių duomenys.",
                          "fi": "Yksi järjestelmä. Jokainen vaihe. Kaikki kauppatietonne.", "sv": "Ett system. Varje steg. All er deal-data."},
    "platform_body":     {"en": "PEHero lives where your deal team already works. Twenty-two specialist "
                                "agents share a single model of your pipeline, your portfolio, and your market. "
                                "Each agent has its own tools and prompts — and they pass artifacts between each "
                                "other without the associate re-keying anything.",
                          "et": "PEHero elab seal, kus teie tehingumeeskond juba töötab. Kakskümmend kaks spetsialist-agenti "
                                "jagavad ühte mudelit teie pipeline'ist, portfellist ja turust. "
                                "Igal agendil on oma tööriistad ja promptid — ning nad edastavad artefakte üksteisele "
                                "ilma et analüütik peaks midagi ümber trükkima.",
                          "lt": "PEHero veikia ten, kur jūsų sandorių komanda jau dirba. Dvidešimt du specialistų "
                                "agentai dalijasi vienu jūsų pipeline, portfelio ir rinkos modeliu. "
                                "Kiekvienas agentas turi savo įrankius ir promptus — ir jie perduoda artefaktus vieni "
                                "kitiems be pakartotinio duomenų įvedimo.",
                          "fi": "PEHero elää siellä, missä kauppatiimisi jo työskentelee. Erikoisagentit jakavat yhden mallin putkestanne, portfoliostanne ja markkinoistanne.", "sv": "PEHero lever där ert deal-team redan jobbar. Specialistagenter delar en enda modell av er pipeline, portfölj och marknad."},
    "platform_hood":     {"en": "Under the hood",    "et": "Kapoti all",         "lt": "Po dangčiu",
                          "fi": "Konepellin alla", "sv": "Under huven"},
    "platform_not_wrap": {"en": "Not a wrapper. A system.",
                          "et": "Mitte ümbris. Süsteem.",
                          "lt": "Ne apvalkalas. Sistema.",
                          "fi": "Ei kääre. Järjestelmä.", "sv": "Inte en wrapper. Ett system."},
    "platform_squad":    {"en": "A full squad of specialist agents, one per role, sharing a common tool registry and prompt library.",
                          "et": "Täielik spetsialistagentide meeskond, üks rolli kohta, ühise tööriistade registri ja promptide teegiga.",
                          "lt": "Pilna specialistų agentų komanda, po vieną kiekvienai rolei, besidalijanti bendru įrankių registru ir promptų biblioteka.",
                          "fi": "Täysi erikoisagenttitiimi, yksi roolia kohden, jaetulla työkalurekisterillä ja promptikirjastolla.", "sv": "Ett komplett team av specialistagenter, en per roll, med gemensamt verktygsregister och promptbibliotek."},
    "platform_tools":    {"en": "70+ StructuredTools that read cap tables, financials, VDR PDFs, and sector comps directly — not through copy-paste.",
                          "et": "70+ tööriista, mis loevad cap table'eid, finantsandmeid, VDR PDF-e ja sektori võrdlusi otse — mitte copy-paste kaudu.",
                          "lt": "70+ įrankių, kurie tiesiogiai skaito cap tables, finansines ataskaitas, VDR PDF ir sektoriaus lyginamuosius — ne per copy-paste.",
                          "fi": "70+ työkalua, jotka lukevat cap tableja, taloustietoja, VDR-PDF:iä ja toimialavertailuja suoraan.", "sv": "70+ verktyg som läser cap tables, finansdata, VDR-PDF:er och sektorjämförelser direkt."},
    "platform_rag":      {"en": "Postgres + pgvector index of every CIM, QoE, MSA, legal DD memo, ESG assessment, and industry report in your deal.",
                          "et": "Postgres + pgvector indeks igast CIM-ist, QoE-st, MSA-st, juriidilisest DD memosst, ESG hinnangust ja tööstusraportist teie tehingus.",
                          "lt": "Postgres + pgvector indeksas kiekvienam CIM, QoE, MSA, teisiniam DD memo, ESG vertinimui ir pramonės ataskaitai jūsų sandoryje.",
                          "fi": "Postgres + pgvector -indeksi jokaisesta CIM:stä, QoE:stä, MSA:sta ja muista dokumenteista kaupassanne.", "sv": "Postgres + pgvector-index över varje CIM, QoE, MSA och övriga dokument i er deal."},
    "platform_memory":   {"en": "Every conversation and every artifact persists, queryable across agents, so Week 3 of diligence still knows what Week 1 agreed.",
                          "et": "Iga vestlus ja iga artefakt salvestatakse, päringutega kättesaadav kõikidele agentidele — nii et DD 3. nädal teab, mida 1. nädal otsustas.",
                          "lt": "Kiekvienas pokalbis ir kiekvienas artefaktas išsaugomas, užklausomas per visus agentus — 3-ioji patikros savaitė vis dar žino, ką nutarė 1-oji.",
                          "fi": "Jokainen keskustelu ja artefakti säilyy, haettavissa kaikkien agenttien yli.", "sv": "Varje konversation och artefakt sparas, sökbar över alla agenter."},

    # ── Agents page ───────────────────────────────────────────────
    "agents_eyebrow":    {"en": "Your Private Equity AI Agent Squad",
                          "et": "Teie erakapitali AI agentide meeskond",
                          "lt": "Jūsų privataus kapitalo AI agentų komanda",
                          "fi": "Teidän pääomasijoitus-AI-agenttitiimi", "sv": "Ert private equity AI-agentteam"},
    "agents_h1":         {"en": "Every role already wired in.",
                          "et": "Iga roll on juba ühendatud.",
                          "lt": "Kiekviena rolė jau sujungta.",
                          "fi": "Jokainen rooli jo kytketty.", "sv": "Varje roll redan inkopplad."},
    "agents_body":       {"en": "Each agent has a narrow remit, deep tooling, and a prefix you can type in the chat "
                                "to call it directly. Or just ask in plain English — the router picks the right one.",
                          "et": "Igal agendil on kitsas pädevus, sügav tööriistade tugi ja prefiks, mida saate vestluses "
                                "otse sisestada. Või lihtsalt küsige — marsruuter valib õige agendi.",
                          "lt": "Kiekvienas agentas turi siaurą kompetenciją, giluminius įrankius ir prefiksą, "
                                "kurį galite įvesti pokalbyje. Arba tiesiog klauskite — maršrutizatorius parinks tinkamą.",
                          "fi": "Jokaisella agentilla on kapea vastuualue, syvät työkalut ja etuliite, jonka voit kirjoittaa chatiin. Tai kysy vain — reitittäjä valitsee oikean.", "sv": "Varje agent har ett smalt uppdrag, djupa verktyg och ett prefix du kan skriva i chatten. Eller fråga bara — routern väljer rätt."},

    # ── Agent detail page ─────────────────────────────────────────
    "agent_not_found":   {"en": "Not found",         "et": "Ei leitud",          "lt": "Nerasta",
                          "fi": "Ei löytynyt", "sv": "Hittades inte"},
    "agent_no_url":      {"en": "No agent at that URL. See the ",
                          "et": "Sellel aadressil agenti pole. Vaadake ",
                          "lt": "Nėra agento šiuo adresu. Žiūrėkite ",
                          "fi": "Tässä osoitteessa ei ole agenttia. Katso ", "sv": "Ingen agent på den adressen. Se "},
    "agent_full_squad":  {"en": "full squad",        "et": "kogu meeskonda",     "lt": "visą komandą",
                          "fi": "koko tiimi", "sv": "hela teamet"},
    "agent_all":         {"en": "← All agents",      "et": "← Kõik agendid",    "lt": "← Visi agentai",
                          "fi": "← Kaikki agentit", "sv": "← Alla agenter"},
    "agent_what":        {"en": "What it does",      "et": "Mida teeb",          "lt": "Ką daro",
                          "fi": "Mitä tekee", "sv": "Vad den gör"},
    "agent_examples":    {"en": "Example prompts",   "et": "Näidispäringud",     "lt": "Pavyzdžiai",
                          "fi": "Esimerkkipromptit", "sv": "Exempelprompts"},
    "agent_try":         {"en": "Try {name} now.",    "et": "Proovige {name} kohe.", "lt": "Išbandykite {name} dabar.",
                          "fi": "Kokeile {name} nyt.", "sv": "Prova {name} nu."},
    "agent_try_body":    {"en": "BYOD — bring your own deal data and try the example prompt above against it.",
                          "et": "BYOD — kasutage oma tehinguandmeid ja proovige ülaltoodud näidispäringut nendega.",
                          "lt": "BYOD — naudokite savo sandorių duomenis ir išbandykite aukščiau esančią užklausą.",
                          "fi": "BYOD — tuo omat kauppatietosi ja kokeile yllä olevaa esimerkkipromptia niillä.", "sv": "BYOD — använd er egen deal-data och prova exempelprompten ovan mot den."},

    # ── How-it-works page (detailed) ──────────────────────────────
    "hiw_title":         {"en": "How it works",      "et": "Kuidas toimib",      "lt": "Kaip tai veikia",
                          "fi": "Miten toimii", "sv": "Hur det fungerar"},
    "hiw_h1":            {"en": "From teaser to signed SPA — in one system.",
                          "et": "Teaserist allkirjastatud SPA-ni — ühes süsteemis.",
                          "lt": "Nuo teaserio iki pasirašyto SPA — vienoje sistemoje.",
                          "fi": "Teaserista allekirjoitettuun SPA:han — yhdessä järjestelmässä.", "sv": "Från teaser till signerat SPA — i ett system."},
    "hiw_01_num":        {"en": "01 — Source",       "et": "01 — Otsing",        "lt": "01 — Paieška",
                          "fi": "01 — Etsintä", "sv": "01 — Sökning"},
    "hiw_01_title":      {"en": "Surface the right deals faster than the next MD.",
                          "et": "Leidke õiged tehingud kiiremini kui järgmine juhtivdirektor.",
                          "lt": "Suraskite tinkamus sandorius greičiau nei kitas MD.",
                          "fi": "Löydä oikeat kaupat nopeammin kuin seuraava MD.", "sv": "Hitta rätt deals snabbare än nästa MD."},
    "hiw_01_body":       {"en": "Market Scanner watches PitchBook, Grata, banker feeds, and off-market founder-intent signals. "
                                "Deal Triage returns a go/no-go in under 90 seconds. Transaction Comps tightens multiple benchmarks before you sign an NDA.",
                          "et": "Market Scanner jälgib PitchBook-i, Grata-t, pankurite voogusid ja turuväliseid asutajate kavatsussignaale. "
                                "Deal Triage annab jah/ei otsuse alla 90 sekundiga. Transaction Comps kitsendab kordajaid enne NDA allkirjastamist.",
                          "lt": "Market Scanner stebi PitchBook, Grata, bankininkų srautus ir nešalinius įkūrėjų ketinimo signalus. "
                                "Deal Triage pateikia 'taip/ne' per 90 sekundžių. Transaction Comps sugriežtina dauginamuosius prieš pasirašant NDA.",
                          "fi": "Market Scanner seuraa PitchBookia, Grataa, pankkiirien syötteitä ja markkinoiden ulkopuolisia perustajakavatsussignaaleja. Deal Triage antaa kyllä/ei alle 90 sekunnissa.", "sv": "Market Scanner bevakar PitchBook, Grata, bankirflöden och off-market grundaravsiktssignaler. Deal Triage ger ja/nej på under 90 sekunder."},
    "hiw_02_num":        {"en": "02 — Underwrite",   "et": "02 — Hindamine",     "lt": "02 — Vertinimas",
                          "fi": "02 — Arviointi", "sv": "02 — Bedömning"},
    "hiw_02_title":      {"en": "Seller financials to IC-ready LBO in under an hour.",
                          "et": "Müüja finantsandmetest IC-valmis LBO-ni alla tunniga.",
                          "lt": "Pardavėjo finansinės ataskaitos iki IC parengt LBO per valandą.",
                          "fi": "Myyjän taloustiedoista IC-valmiiseen LBO:hon alle tunnissa.", "sv": "Säljarfinanser till IC-redo LBO på under en timme."},
    "hiw_02_body":       {"en": "Cap Table Parser and LTM Normalizer ingest whatever format the banker sends. "
                                "LBO Model Builder produces a 5-year model with sensitivity. Debt Stack Modeler sizes the capital structure. "
                                "Return Metrics outputs IRR, MOIC, and the value-creation bridge.",
                          "et": "Cap Table Parser ja LTM Normalizer töötlevad ükskõik mis formaadis pankur saadab. "
                                "LBO Model Builder koostab 5-aasta mudeli koos tundlikkuse analüüsiga. Debt Stack Modeler dimensioneerib kapitalistruktuuri. "
                                "Return Metrics väljastab IRR-i, MOIC-i ja väärtuse loomise silla.",
                          "lt": "Cap Table Parser ir LTM Normalizer apdoroja bet kokį bankininkui siųstamą formatą. "
                                "LBO Model Builder sukuria 5 metų modelį su jautrumo analize. Debt Stack Modeler sudaro kapitalo struktūrą. "
                                "Return Metrics pateikia IRR, MOIC ir vertės kūrimo tiltą.",
                          "fi": "Cap Table Parser ja LTM Normalizer käsittelevät minkä tahansa formaatin. LBO Model Builder tuottaa 5-vuoden mallin herkkyysanalyysillä.", "sv": "Cap Table Parser och LTM Normalizer hanterar oavsett format. LBO Model Builder producerar en 5-årsmodell med känslighetsanalys."},
    "hiw_03_num":        {"en": "03 — Diligence",    "et": "03 — Audit",         "lt": "03 — Patikra",
                          "fi": "03 — Due Diligence", "sv": "03 — Due Diligence"},
    "hiw_03_title":      {"en": "No surprises at signing.",
                          "et": "Üllatused allkirjastamisel puuduvad.",
                          "lt": "Jokių staigmenų pasirašant.",
                          "fi": "Ei yllätyksiä allekirjoituksessa.", "sv": "Inga överraskningar vid signering."},
    "hiw_03_body":       {"en": "VDR Auditor checks the seller data room against a 140-item PE checklist. "
                                "Contract Abstractor reads every MSA. Legal & Regulatory, Operational Diligence, "
                                "and ESG agents flag material issues with page-level citations.",
                          "et": "VDR Auditor kontrollib müüja andmeruumi 140-punktilise PE kontrollnimekirja vastu. "
                                "Contract Abstractor loeb läbi iga MSA. Legal & Regulatory, Operational Diligence "
                                "ja ESG agendid märgivad olulised probleemid koos lehekülje tasandi viidetega.",
                          "lt": "VDR Auditor patikrina pardavėjo duomenų kambarį pagal 140 punktų PE kontrolę. "
                                "Contract Abstractor perskaito kiekvieną MSA. Legal & Regulatory, Operational Diligence "
                                "ir ESG agentai pažymi esminius dalykus su puslapio lygio citatomis.",
                          "fi": "VDR Auditor tarkistaa myyjän datahuoneen 140-kohtaista PE DD-tarkistuslistaa vasten. Contract Abstractor lukee jokaisen MSA:n.", "sv": "VDR Auditor kontrollerar säljarens datarum mot en 140-punkters PE DD-checklista. Contract Abstractor läser varje MSA."},
    "hiw_04_num":        {"en": "04 — Raise",        "et": "04 — Kapital",       "lt": "04 — Kapitalas",
                          "fi": "04 — Pääoma", "sv": "04 — Kapital"},
    "hiw_04_title":      {"en": "LP material your chair will actually sign.",
                          "et": "LP materjal, mille teie esimees tegelikult allkirjastab.",
                          "lt": "LP medžiaga, kurią jūsų pirmininkas tikrai pasirašys.",
                          "fi": "LP-materiaali, jonka puheenjohtajanne todella allekirjoittaa.", "sv": "LP-material som er ordförande faktiskt signerar."},
    "hiw_04_body":       {"en": "IC Memo Writer drafts the investment-committee memo from your own data. "
                                "Teaser Designer produces a 2-page blind teaser for co-invest distribution. "
                                "LP Update Generator writes the quarterly letter. Fundraising CRM Copilot ranks prospects and drafts outreach.",
                          "et": "IC Memo Writer koostab investeerimiskomitee memo teie enda andmetest. "
                                "Teaser Designer loob 2-leheküljelise pimeda teaseri kaasinvesteeringute jaotamiseks. "
                                "LP Update Generator kirjutab kvartalse kirja. Fundraising CRM Copilot reastab prospekte ja koostab kontaktkirjad.",
                          "lt": "IC Memo Writer parengia investicijų komiteto memo iš jūsų duomenų. "
                                "Teaser Designer sukuria 2 puslapių anoniminį teaserį bendram investavimui. "
                                "LP Update Generator rašo ketvirtį laišką. Fundraising CRM Copilot ranguoja prospektus ir rengia raištinius.",
                          "fi": "IC Memo Writer laatii sijoituskomitean muistion omista tiedoistanne. Teaser Designer tuottaa 2-sivuisen teaserien. LP Update Generator kirjoittaa neljännesvuosikirjeen.", "sv": "IC Memo Writer skriver investeringskommitténs memo från er egen data. Teaser Designer producerar en 2-sidig blind teaser. LP Update Generator skriver kvartalsbrevet."},
    "hiw_05_num":        {"en": "05 — Hold & Grow",  "et": "05 — Halda ja kasva", "lt": "05 — Valdymas ir augimas",
                          "fi": "05 — Hallinta ja kasvu", "sv": "05 — Förvalta och väx"},
    "hiw_05_title":      {"en": "Post-close, the agents stay on.",
                          "et": "Pärast sulgemist jäävad agendid tööle.",
                          "lt": "Po uždarymo agentai lieka.",
                          "fi": "Sulkemisen jälkeen agentit pysyvät mukana.", "sv": "Efter stängning stannar agenterna kvar."},
    "hiw_05_body":       {"en": "Pricing Optimization recommends increases at renewal. EBITDA Variance Watcher flags monthly drift. "
                                "Value Creation Prioritizer ranks VCP initiatives by ROI. Customer Churn Predictor scores renewal risk across the ARR base.",
                          "et": "Pricing Optimization soovitab tõstmisi uuendamisel. EBITDA Variance Watcher tuvastab igakuise kõrvalekalde. "
                                "Value Creation Prioritizer reastab VCP algatusi ROI järgi. Customer Churn Predictor hindab uuendamisriski üle kogu ARR baasi.",
                          "lt": "Pricing Optimization rekomenduoja kėlimus atnaujinat. EBITDA Variance Watcher fiksuoja mėnesinį nukrypimą. "
                                "Value Creation Prioritizer ranguoja VCP iniciatyvas pagal ROI. Customer Churn Predictor vertina atsinaujinimo riziką per ARR bazę.",
                          "fi": "Pricing Optimization suosittelee korotuksia uusinnassa. EBITDA Variance Watcher havaitsee kuukausittaiset poikkeamat.", "sv": "Pricing Optimization rekommenderar höjningar vid förnyelse. EBITDA Variance Watcher flaggar månatlig avvikelse."},

    # ── Pricing page ──────────────────────────────────────────────
    "pricing_eyebrow":   {"en": "Pricing",           "et": "Hinnakiri",          "lt": "Kainos",
                          "fi": "Hinnoittelu", "sv": "Prissättning"},
    "pricing_h1":        {"en": "BYOD — bring your own data. Upgrade when it sticks.",
                          "et": "BYOD — kasutage oma andmeid. Uuendage, kui sobib.",
                          "lt": "BYOD — naudokite savo duomenis. Atnaujinkite, kai patiks.",
                          "fi": "BYOD — tuo omat tietosi. Päivitä, kun se toimii.", "sv": "BYOD — använd egen data. Uppgradera när det fastnar."},
    "pricing_sub":       {"en": "No setup fee. No per-seat tax. No prompt-token surprise.",
                          "et": "Ilma seadistustasuta. Ilma kohamaksuta. Ilma prompt-token üllatusteta.",
                          "lt": "Be pradiniamą. Be mokestis už vietą. Be prompt-token staigmenų.",
                          "fi": "Ei aloitusmaksua. Ei paikkakohtaista veroa. Ei prompt-token-yllätyksiä.", "sv": "Ingen uppstartsavgift. Ingen per-sätes-skatt. Inga prompt-token-överraskningar."},
    "pricing_pilot":     {"en": "Pilot",             "et": "Piloot",             "lt": "Pilotinis",
                          "fi": "Pilotti", "sv": "Pilot"},
    "pricing_pilot_price": {"en": "BYOD",            "et": "BYOD",               "lt": "BYOD",
                          "fi": "BYOD", "sv": "BYOD"},
    "pricing_pilot_sub": {"en": "bring your own data · 30-day pilot",
                          "et": "kasutage oma andmeid · 30-päevane piloot",
                          "lt": "naudokite savo duomenis · 30 dienų bandomasis",
                          "fi": "tuo omat tietosi · 30 päivän pilotti", "sv": "använd egen data · 30-dagars pilot"},
    "pricing_pilot_blurb": {"en": "One associate, one deal, the full squad — running against your own data.",
                            "et": "Üks analüütik, üks tehing, kogu meeskond — töötab teie enda andmetega.",
                            "lt": "Vienas asocijuotas partneris, vienas sandoris, visa komanda — su jūsų duomenimis.",
                          "fi": "Yksi analyytikko, yksi kauppa, koko tiimi — omilla tiedoillanne.", "sv": "En analytiker, en deal, hela teamet — mot er egen data."},
    "pricing_team":      {"en": "Team",              "et": "Meeskond",           "lt": "Komanda",
                          "fi": "Tiimi", "sv": "Team"},
    "pricing_team_price": {"en": "Contact us",       "et": "Võtke ühendust",     "lt": "Susisiekite",
                          "fi": "Ota yhteyttä", "sv": "Kontakta oss"},
    "pricing_team_sub":  {"en": "per fund",          "et": "fondi kohta",        "lt": "už fondą",
                          "fi": "rahastoa kohden", "sv": "per fond"},
    "pricing_team_blurb": {"en": "Fund actively deploying capital with 5-25 investment professionals.",
                           "et": "Fond, mis aktiivselt investeerib kapital 5-25 investeerimisprofessionaaliga.",
                           "lt": "Fondas, aktyviai investuojantis kapitalą su 5-25 investicijų profesionalais.",
                          "fi": "Rahasto, joka sijoittaa aktiivisesti 5-25 sijoitusammattilaisen voimin.", "sv": "Fond som aktivt investerar kapital med 5-25 investeringsproffs."},
    "pricing_platform":  {"en": "Platform",          "et": "Platvorm",           "lt": "Platforma",
                          "fi": "Alusta", "sv": "Plattform"},
    "pricing_platform_price": {"en": "Custom",       "et": "Kohandatud",         "lt": "Individuali",
                          "fi": "Räätälöity", "sv": "Anpassad"},
    "pricing_platform_sub": {"en": "for multi-fund GPs",
                             "et": "mitme fondi GP-dele",
                             "lt": "multi-fund GP",
                          "fi": "monirahasto-GP:ille", "sv": "för multi-fond-GP:er"},
    "pricing_platform_blurb": {"en": "Dedicated cluster, your brand, custom agents.",
                               "et": "Eraldatud klaster, teie bränd, kohandatud agendid.",
                               "lt": "Atskiras klasteris, jūsų prekės ženklas, individualūs agentai.",
                          "fi": "Erillinen klusteri, oma brändi, räätälöidyt agentit.", "sv": "Dedikerat kluster, ert varumärke, anpassade agenter."},
    "pricing_start_pilot": {"en": "Start pilot",     "et": "Alusta pilooti",     "lt": "Pradėti pilotą",
                          "fi": "Aloita pilotti", "sv": "Starta pilot"},
    "pricing_book_demo": {"en": "Book a demo",       "et": "Broneeri demo",      "lt": "Rezervuoti demo",
                          "fi": "Varaa demo", "sv": "Boka demo"},
    "pricing_contact":   {"en": "Contact sales",     "et": "Võtke müügiga ühendust", "lt": "Susisiekti su pardavimais",
                          "fi": "Ota yhteyttä myyntiin", "sv": "Kontakta sälj"},
    "feat_full_squad":   {"en": "Full squad of specialists",    "et": "Täielik spetsialistide meeskond",  "lt": "Visa specialistų komanda",
                          "fi": "Täysi asiantuntijatiimi", "sv": "Komplett specialistteam"},
    "feat_1_user":       {"en": "1 concurrent user",            "et": "1 kasutaja",                      "lt": "1 vartotojas",
                          "fi": "1 käyttäjä", "sv": "1 användare"},
    "feat_5_deals":      {"en": "Up to 5 live deals",           "et": "Kuni 5 aktiivset tehingut",       "lt": "Iki 5 aktyvių sandorių",
                          "fi": "Jopa 5 aktiivista kauppaa", "sv": "Upp till 5 aktiva deals"},
    "feat_byod":         {"en": "BYOD — connect your deal data on day one",
                          "et": "BYOD — ühendage oma andmed esimesel päeval",
                          "lt": "BYOD — prijunkite savo duomenis nuo pirmos dienos",
                          "fi": "BYOD — yhdistä tietosi ensimmäisenä päivänä", "sv": "BYOD — koppla in er data dag ett"},
    "feat_email":        {"en": "Email support",                "et": "E-posti tugi",                    "lt": "El. pašto palaikymas",
                          "fi": "Sähköpostituki", "sv": "E-postsupport"},
    "feat_25_seats":     {"en": "Up to 25 seats",               "et": "Kuni 25 kohta",                   "lt": "Iki 25 vietų",
                          "fi": "Jopa 25 paikkaa", "sv": "Upp till 25 platser"},
    "feat_unlimited":    {"en": "Unlimited deals + portcos",    "et": "Piiramatult tehinguid + portfelle", "lt": "Neriboti sandoriai + portfeliai",
                          "fi": "Rajattomat kaupat + portfolioyhtiöt", "sv": "Obegränsat antal deals + portföljbolag"},
    "feat_sso":          {"en": "SSO + audit log",              "et": "SSO + auditi logi",               "lt": "SSO + audito žurnalas",
                          "fi": "SSO + auditointilokit", "sv": "SSO + revisionslogg"},
    "feat_shared":       {"en": "Shared memory across team",    "et": "Jagatud mälu meeskonnale",        "lt": "Bendra atmintis komandai",
                          "fi": "Jaettu muisti tiimille", "sv": "Delat minne för teamet"},
    "feat_priority":     {"en": "Priority support",             "et": "Prioriteetne tugi",               "lt": "Prioritetinis palaikymas",
                          "fi": "Prioriteettituki", "sv": "Prioriterat stöd"},
    "feat_everything":   {"en": "Everything in Team",           "et": "Kõik, mis Team plaanis",          "lt": "Viskas, kas Team plane",
                          "fi": "Kaikki Team-paketissa", "sv": "Allt i Team-paketet"},
    "feat_unlimited_seats": {"en": "Unlimited seats",           "et": "Piiramatult kohti",               "lt": "Neribota vieta",
                          "fi": "Rajattomat paikat", "sv": "Obegränsade platser"},
    "feat_dedicated":    {"en": "Dedicated instance",           "et": "Eraldatud instants",              "lt": "Atskira instancija",
                          "fi": "Oma instanssi", "sv": "Dedicerad instans"},
    "feat_own_llm":      {"en": "Bring your own LLM provider", "et": "Kasutage oma LLM pakkujat",       "lt": "Naudokite savo LLM tiekėją",
                          "fi": "Tuo oma LLM-tarjoaja", "sv": "Använd egen LLM-leverantör"},
    "feat_custom":       {"en": "Custom agents and tools",      "et": "Kohandatud agendid ja tööriistad", "lt": "Individualūs agentai ir įrankiai",
                          "fi": "Räätälöidyt agentit ja työkalut", "sv": "Anpassade agenter och verktyg"},
    "feat_onsite":       {"en": "Onsite training",              "et": "Kohapeal koolitus",               "lt": "Mokymai vietoje",
                          "fi": "Koulutus paikan päällä", "sv": "Utbildning på plats"},

    # ── Contact page ──────────────────────────────────────────────
    "contact_eyebrow":   {"en": "Contact",           "et": "Kontakt",            "lt": "Kontaktai",
                          "fi": "Yhteystiedot", "sv": "Kontakt"},
    "contact_h1":        {"en": "Let's look at one of your deals.",
                          "et": "Vaatame ühte teie tehingut.",
                          "lt": "Pažiūrėkime vieną jūsų sandorį.",
                          "fi": "Katsotaan yhtä kaupoistanne.", "sv": "Låt oss titta på en av era deals."},
    "contact_body":      {"en": "Send us a note and we'll set up a 20-minute walkthrough. We'll load one of your "
                                "recent deals into PEHero and show you the full agent flow — live.",
                          "et": "Saatke meile kiri ja me korraldame 20-minutilise tutvustuse. Laadime ühe teie "
                                "hiljutise tehingu PEHerosse ja näitame kogu agentide töövoogu — reaalajas.",
                          "lt": "Parašykite mums ir suorganizuosime 20 minučių demonstraciją. Įkelkime vieną iš jūsų "
                                "paskutinių sandorių į PEHero ir parodysime pilną agentų darbo eigą — gyvai.",
                          "fi": "Lähetä meille viesti ja järjestämme 20 minuutin esittelyn. Lataamme yhden viimeisistä kaupoistanne PEHeroon ja näytämme koko agenttivirran — livenä.", "sv": "Skicka oss ett meddelande så sätter vi upp en 20-minuters genomgång. Vi laddar en av era senaste deals i PEHero och visar hela agentflödet — live."},
    "contact_name":      {"en": "Your name",         "et": "Teie nimi",          "lt": "Jūsų vardas",
                          "fi": "Nimenne", "sv": "Ert namn"},
    "contact_email":     {"en": "Email",             "et": "E-post",             "lt": "El. paštas",
                          "fi": "Sähköposti", "sv": "E-post"},
    "contact_firm":      {"en": "Firm (optional)",   "et": "Ettevõte (valikuline)", "lt": "Įmonė (neprivaloma)",
                          "fi": "Yritys (valinnainen)", "sv": "Företag (valfritt)"},
    "contact_pipeline":  {"en": "Tell us about your pipeline",
                          "et": "Rääkige meile oma pipeline'ist",
                          "lt": "Papasakokite apie savo pipeline",
                          "fi": "Kerro meille pipeline'stänne", "sv": "Berätta om er pipeline"},
    "contact_send":      {"en": "Send message →",    "et": "Saada sõnum →",      "lt": "Siųsti žinutę →",
                          "fi": "Lähetä viesti →", "sv": "Skicka meddelande →"},
    "contact_thanks":    {"en": "Thanks — we'll be in touch shortly.",
                          "et": "Täname — võtame peagi ühendust.",
                          "lt": "Ačiū — netrukus susisieksime.",
                          "fi": "Kiitos — otamme pian yhteyttä.", "sv": "Tack — vi hör av oss snart."},
    "contact_usually":   {"en": "Usually within one business day.",
                          "et": "Tavaliselt ühe tööpäeva jooksul.",
                          "lt": "Paprastai per vieną darbo dieną.",
                          "fi": "Yleensä yhden työpäivän kuluessa.", "sv": "Vanligtvis inom en arbetsdag."},
    "contact_meanwhile": {"en": "In the meantime, ",  "et": "Vahepeal ",          "lt": "Tuo tarpu, ",
                          "fi": "Sillä välin ", "sv": "Under tiden "},
    "contact_open_app":  {"en": "open the app",       "et": "avage rakendus",     "lt": "atidarykite programą",
                          "fi": "avaa sovellus", "sv": "öppna appen"},
    "contact_byod_post": {"en": " — BYOD: connect your deal data to see the squad on real work.",
                          "et": " — BYOD: ühendage oma tehinguandmed ja vaadake meeskonda päris tööl.",
                          "lt": " — BYOD: prijunkite savo sandorių duomenis ir pamatykite komandą tikrame darbe.",
                          "fi": " — BYOD: yhdistä kauppatietosi ja katso tiimi oikeassa työssä.", "sv": " — BYOD: koppla in er deal-data och se teamet i riktigt arbete."},

    # ── Chat UI ───────────────────────────────────────────────────
    "chat_new":          {"en": "+ New chat",        "et": "+ Uus vestlus",      "lt": "+ Naujas pokalbis",
                          "fi": "+ Uusi keskustelu", "sv": "+ Ny chatt"},
    "chat_sessions":     {"en": "Sessions",          "et": "Vestlused",          "lt": "Pokalbiai",
                          "fi": "Keskustelut", "sv": "Sessioner"},
    "chat_no_sessions":  {"en": "No sessions yet — send a message to start.",
                          "et": "Vestlused puuduvad — saatke sõnum alustamiseks.",
                          "lt": "Dar nėra pokalbių — parašykite žinutę, kad pradėtumėte.",
                          "fi": "Ei vielä keskusteluja — lähetä viesti aloittaaksesi.", "sv": "Inga sessioner ännu — skicka ett meddelande för att börja."},
    "chat_untitled":     {"en": "Untitled session",  "et": "Pealkirjata vestlus", "lt": "Be pavadinimo",
                          "fi": "Nimetön keskustelu", "sv": "Namnlös session"},
    "chat_agents":       {"en": "Agents",            "et": "Agendid",            "lt": "Agentai",
                          "fi": "Agentit", "sv": "Agenter"},
    "chat_workspace":    {"en": "Workspace",         "et": "Tööruum",            "lt": "Darbo erdvė",
                          "fi": "Työtila", "sv": "Arbetsyta"},
    "chat_config":       {"en": "Configuration",     "et": "Seaded",             "lt": "Nustatymai",
                          "fi": "Asetukset", "sv": "Inställningar"},
    "chat_pipeline":     {"en": "Pipeline",          "et": "Pipeline",           "lt": "Pipeline",
                          "fi": "Pipeline", "sv": "Pipeline"},
    "chat_instructions": {"en": "Instructions",      "et": "Juhised",            "lt": "Instrukcijos",
                          "fi": "Ohjeet", "sv": "Instruktioner"},
    "chat_analytics":    {"en": "Analytics",         "et": "Analüütika",         "lt": "Analitika",
                          "fi": "Analytiikka", "sv": "Analys"},
    "chat_companies":    {"en": "Companies",        "et": "Ettevõtted",         "lt": "Įmonės",
                          "fi": "Yritykset", "sv": "Företag"},

    # ── Company search page ──────────────────────────────────────
    "search_title":      {"en": "Company Search",   "et": "Ettevõtete otsing",  "lt": "Įmonių paieška",
                          "fi": "Yrityshaku", "sv": "Företagssökning"},
    "search_placeholder": {"en": "Search by company name...",
                          "et": "Otsi ettevõtte nime järgi...",
                          "lt": "Ieškoti pagal įmonės pavadinimą...",
                          "fi": "Hae yrityksen nimellä...",
                          "sv": "Sök på företagsnamn..."},
    "search_btn":        {"en": "Search",            "et": "Otsi",               "lt": "Ieškoti",
                          "fi": "Hae", "sv": "Sök"},
    "search_sector":     {"en": "Sector",            "et": "Sektor",             "lt": "Sektorius",
                          "fi": "Sektori", "sv": "Sektor"},
    "search_all_sectors": {"en": "All sectors",      "et": "Kõik sektorid",      "lt": "Visi sektoriai",
                          "fi": "Kaikki sektorit", "sv": "Alla sektorer"},
    "search_results":    {"en": "{n} companies found", "et": "{n} ettevõtet leitud", "lt": "{n} įmonių rasta",
                          "fi": "{n} yritystä löytyi", "sv": "{n} företag hittades"},
    "search_no_results": {"en": "No companies match your search.", "et": "Ühtegi ettevõtet ei leitud.",
                          "lt": "Nerasta įmonių pagal paiešką.",
                          "fi": "Yrityksiä ei löytynyt.", "sv": "Inga företag hittades."},
    "search_col_name":   {"en": "Company",           "et": "Ettevõte",           "lt": "Įmonė",
                          "fi": "Yritys", "sv": "Företag"},
    "search_col_city":   {"en": "City",              "et": "Linn",               "lt": "Miestas",
                          "fi": "Kaupunki", "sv": "Stad"},
    "search_col_sector": {"en": "Sector",            "et": "Sektor",             "lt": "Sektorius",
                          "fi": "Sektori", "sv": "Sektor"},
    "search_col_revenue": {"en": "Revenue (LTM)",    "et": "Käive (LTM)",        "lt": "Pajamos (LTM)",
                          "fi": "Liikevaihto (LTM)", "sv": "Omsättning (LTM)"},
    "search_col_ebitda": {"en": "EBITDA",            "et": "EBITDA",             "lt": "EBITDA",
                          "fi": "EBITDA", "sv": "EBITDA"},
    "search_col_employees": {"en": "Employees",      "et": "Töötajad",           "lt": "Darbuotojai",
                          "fi": "Työntekijät", "sv": "Anställda"},
    "search_col_stage":  {"en": "Stage",             "et": "Etapp",              "lt": "Etapas",
                          "fi": "Vaihe", "sv": "Steg"},
    "chat_sign_in":      {"en": "Sign in",           "et": "Logi sisse",         "lt": "Prisijungti",
                          "fi": "Kirjaudu", "sv": "Logga in"},
    "chat_sign_out":     {"en": "Sign out",          "et": "Logi välja",         "lt": "Atsijungti",
                          "fi": "Kirjaudu ulos", "sv": "Logga ut"},
    "chat_beta":         {"en": "Beta",              "et": "Beta",               "lt": "Beta",
                          "fi": "Beta", "sv": "Beta"},
    "chat_send":         {"en": "Send",              "et": "Saada",              "lt": "Siųsti",
                          "fi": "Lähetä", "sv": "Skicka"},
    "chat_auto_routed":  {"en": "Auto-routed",       "et": "Automaatne",         "lt": "Automatinis",
                          "fi": "Automaattinen", "sv": "Automatisk"},
    "chat_copy":         {"en": "Copy chat",         "et": "Kopeeri vestlus",    "lt": "Kopijuoti pokalbį",
                          "fi": "Kopioi chat", "sv": "Kopiera chatt"},
    "chat_share":        {"en": "Share",             "et": "Jaga",               "lt": "Dalintis",
                          "fi": "Jaa", "sv": "Dela"},
    "chat_canvas":       {"en": "Canvas",            "et": "Lõuend",             "lt": "Drobė",
                          "fi": "Piirtoalusta", "sv": "Arbetsyta"},
    "chat_back":         {"en": "Back to chat",      "et": "Tagasi vestlusse",   "lt": "Grįžti į pokalbį",
                          "fi": "Takaisin chattiin", "sv": "Tillbaka till chatten"},
    "chat_placeholder":  {"en": "Ask anything — or type a prefix like `triage:`, `memo:`, `pf:`",
                          "et": "Küsige mida iganes — või sisestage prefiks nagu `triage:`, `memo:`, `pf:`",
                          "lt": "Klauskite bet ko — arba įveskite prefiksą kaip `triage:`, `memo:`, `pf:`",
                          "fi": "Kysy mitä vain — tai kirjoita etuliite kuten 'triage:', 'memo:', 'pf:'", "sv": "Fråga vad som helst — eller skriv ett prefix som 'triage:', 'memo:', 'pf:'"},
    "chat_welcome_title": {"en": "PEHero",           "et": "PEHero",             "lt": "PEHero",
                          "fi": "PEHero", "sv": "PEHero"},
    "chat_welcome_sub":  {"en": "Your Private Equity AI Agent Squad. Type a prompt — the router picks the right specialist.",
                          "et": "Teie erakapitali AI agentide meeskond. Sisestage päring — marsruuter valib õige spetsialisti.",
                          "lt": "Jūsų privataus kapitalo AI agentų komanda. Įveskite užklausą — maršrutizatorius parinks tinkamą specialistą.",
                          "fi": "Teidän pääomasijoitus-AI-agenttitiimi. Kirjoita prompti — reitittäjä valitsee oikean asiantuntijan.", "sv": "Ert private equity AI-agentteam. Skriv en prompt — routern väljer rätt specialist."},
    "chat_canvas_empty": {"en": "Canvas renders here as agents produce them — company briefs, LBO models, comps tables, IC memo previews, RAG citations.",
                          "et": "Lõuend kuvatakse siin, kui agendid neid loovad — ettevõtte ülevaated, LBO mudelid, võrdlustabelid, IC memo eelvaated, RAG viited.",
                          "lt": "Drobė rodoma, kai agentai sukuria artefaktus — įmonių aprašymus, LBO modelius, lyginimuosius, IC memo peržiūras, RAG citatas.",
                          "fi": "Piirtoalusta näyttää agenttien tuotokset — yritystiivistelmät, LBO-mallit, vertailutaulukot, IC-muistion esikatselut, RAG-viittaukset.", "sv": "Arbetsytan visar agenternas resultat — företagsöversikter, LBO-modeller, jämförelsetabeller, IC-memo-förhandsgranskning, RAG-citat."},
    "chat_signin_title": {"en": "Sign in to PEHero", "et": "Logige PEHerosse sisse", "lt": "Prisijungti prie PEHero",
                          "fi": "Kirjaudu PEHeroon", "sv": "Logga in på PEHero"},
    "chat_signin_sub":   {"en": "Email only — we'll send a confirmation later.",
                          "et": "Ainult e-post — saadame kinnituse hiljem.",
                          "lt": "Tik el. paštu — patvirtinimas bus vėliau.",
                          "fi": "Vain sähköposti — lähetämme vahvistuksen myöhemmin.", "sv": "Bara e-post — vi skickar en bekräftelse senare."},
    "chat_signin_btn":   {"en": "Continue →",        "et": "Jätka →",            "lt": "Tęsti →",
                          "fi": "Jatka →", "sv": "Fortsätt →"},

    # ── News panel ───────────────────────────────────────────────
    "news_title":        {"en": "News",              "et": "Uudised",            "lt": "Naujienos",
                          "fi": "Uutiset", "sv": "Nyheter"},
    "news_loading":      {"en": "Loading news...",   "et": "Uudiste laadimine...", "lt": "Kraunamos naujienos...",
                          "fi": "Ladataan uutisia...", "sv": "Laddar nyheter..."},
    "news_empty":        {"en": "No news available", "et": "Uudiseid pole saadaval", "lt": "Naujienų nėra",
                          "fi": "Ei uutisia saatavilla", "sv": "Inga nyheter tillgängliga"},
    "news_ago_min":      {"en": "{n}m ago",          "et": "{n}m tagasi",        "lt": "prieš {n}m",
                          "fi": "{n}m sitten", "sv": "{n}m sedan"},
    "news_ago_hour":     {"en": "{n}h ago",          "et": "{n}t tagasi",        "lt": "prieš {n}h",
                          "fi": "{n}t sitten", "sv": "{n}t sedan"},
    "news_ago_day":      {"en": "{n}d ago",          "et": "{n}p tagasi",        "lt": "prieš {n}d",
                          "fi": "{n}pv sitten", "sv": "{n}d sedan"},

    # ── Chat config ───────────────────────────────────────────────
    "cfg_currency":      {"en": "Currency",          "et": "Valuuta",             "lt": "Valiuta",
                          "fi": "Valuutta", "sv": "Valuta"},
    "cfg_currency_help": {"en": "affects agents + displays",
                          "et": "mõjutab agente ja kuva",
                          "lt": "įtakoja agentus ir atvaizdavimą",
                          "fi": "vaikuttaa agentteihin ja näyttöihin", "sv": "påverkar agenter och visning"},
    "cfg_integrations":  {"en": "Integrations",      "et": "Integratsioonid",    "lt": "Integracijos",
                          "fi": "Integraatiot", "sv": "Integrationer"},
    "cfg_connected":     {"en": "connected",         "et": "ühendatud",          "lt": "prijungta",
                          "fi": "yhdistetty", "sv": "ansluten"},
    "cfg_off":           {"en": "off",               "et": "väljas",             "lt": "išj.",
                          "fi": "pois", "sv": "av"},
    "cfg_language":      {"en": "Language",          "et": "Keel",               "lt": "Kalba",
                          "fi": "Kieli", "sv": "Språk"},

    # ── JS strings (injected as JSON) ─────────────────────────────
    "js_thinking":       {"en": "Thinking… ",        "et": "Mõtlen… ",           "lt": "Galvoju… ",
                          "fi": "Ajattelen… ", "sv": "Tänker… "},
    "js_calling":        {"en": "calling ",          "et": "kutsun ",            "lt": "vykdau ",
                          "fi": "kutsun ", "sv": "anropar "},
    "js_copy_csv":       {"en": "Copy CSV",          "et": "Kopeeri CSV",        "lt": "Kopijuoti CSV",
                          "fi": "Kopioi CSV", "sv": "Kopiera CSV"},
    "js_copied":         {"en": "Copied!",           "et": "Kopeeritud!",        "lt": "Nukopijuota!",
                          "fi": "Kopioitu!", "sv": "Kopierat!"},
    "js_download_csv":   {"en": "Download CSV",      "et": "Laadi CSV alla",     "lt": "Atsisiųsti CSV",
                          "fi": "Lataa CSV", "sv": "Ladda ner CSV"},
    "js_try_prompt":     {"en": "Try a prompt",      "et": "Proovige päringut",  "lt": "Išbandykite užklausą",
                          "fi": "Kokeile promptia", "sv": "Prova en prompt"},
    "js_try_with":       {"en": "Try with ",         "et": "Proovi agendiga ",   "lt": "Išbandykite su ",
                          "fi": "Kokeile agentilla ", "sv": "Prova med "},
    "js_copy_chat":      {"en": "Copy chat",         "et": "Kopeeri vestlus",    "lt": "Kopijuoti pokalbį",
                          "fi": "Kopioi chat", "sv": "Kopiera chatt"},
    "js_share":          {"en": "Share",             "et": "Jaga",               "lt": "Dalintis",
                          "fi": "Jaa", "sv": "Dela"},
    "js_link_copied":    {"en": "Link copied!",      "et": "Link kopeeritud!",   "lt": "Nuoroda nukopijuota!",
                          "fi": "Linkki kopioitu!", "sv": "Länk kopierad!"},
    "js_no_session":     {"en": "No session",        "et": "Vestlus puudub",     "lt": "Nėra pokalbio",
                          "fi": "Ei keskustelua", "sv": "Ingen session"},
    "js_error":          {"en": "Error",             "et": "Viga",               "lt": "Klaida",
                          "fi": "Virhe", "sv": "Fel"},
    "js_error_prefix":   {"en": "Error: ",           "et": "Viga: ",             "lt": "Klaida: ",
                          "fi": "Virhe: ", "sv": "Fel: "},
    "js_rendering":      {"en": "Rendering…",        "et": "Renderdamine…",      "lt": "Generuojama…",
                          "fi": "Renderöidään…", "sv": "Renderar…"},
    "js_open_pdf":       {"en": "✓ Open PDF",        "et": "✓ Ava PDF",          "lt": "✓ Atidaryti PDF",
                          "fi": "✓ Avaa PDF", "sv": "✓ Öppna PDF"},
    "js_render_failed":  {"en": "Render failed",     "et": "Renderdamine ebaõnnestus", "lt": "Generavimas nepavyko",
                          "fi": "Renderöinti epäonnistui", "sv": "Rendering misslyckades"},
    "js_preview_pdf":    {"en": "\U0001f4c4 Preview PDF",  "et": "\U0001f4c4 Eelvaata PDF",  "lt": "\U0001f4c4 Peržiūrėti PDF",
                          "fi": "📄 Esikatsele PDF", "sv": "📄 Förhandsgranska PDF"},
    "js_download_pdf":   {"en": "⬇ Download PDF",    "et": "⬇ Laadi PDF alla",   "lt": "⬇ Atsisiųsti PDF",
                          "fi": "⬇ Lataa PDF", "sv": "⬇ Ladda ner PDF"},
    "js_yes_do":         {"en": "Yes, do that",      "et": "Jah, tee seda",      "lt": "Taip, vykdyk",
                          "fi": "Kyllä, tee se", "sv": "Ja, gör det"},
    "js_no_thanks":      {"en": "No thanks",         "et": "Ei, tänan",          "lt": "Ne, ačiū",
                          "fi": "Ei kiitos", "sv": "Nej tack"},
    "js_canvas":         {"en": "Canvas",            "et": "Lõuend",             "lt": "Drobė",
                          "fi": "Piirtoalusta", "sv": "Arbetsyta"},
    "js_no_rows":        {"en": "No rows.",          "et": "Ridu pole.",          "lt": "Nėra įrašų.",
                          "fi": "Ei rivejä.", "sv": "Inga rader."},
    "js_you":            {"en": "You",               "et": "Sina",               "lt": "Jūs",
                          "fi": "Sinä", "sv": "Du"},
    "js_pehero":         {"en": "PEHero",            "et": "PEHero",             "lt": "PEHero",
                          "fi": "PEHero", "sv": "PEHero"},
    "js_send":           {"en": "Send",              "et": "Saada",              "lt": "Siųsti",
                          "fi": "Lähetä", "sv": "Skicka"},
    "js_pdf_preview":    {"en": "PDF preview",       "et": "PDF eelvaade",       "lt": "PDF peržiūra",
                          "fi": "PDF-esikatselu", "sv": "PDF-förhandsgranskning"},
    "js_memo_preview":   {"en": "Memo preview",      "et": "Memo eelvaade",      "lt": "Memo peržiūra",
                          "fi": "Muistio-esikatselu", "sv": "Memo-förhandsgranskning"},
    "js_news":           {"en": "News",              "et": "Uudised",            "lt": "Naujienos",
                          "fi": "Uutiset", "sv": "Nyheter"},
    "js_news_loading":   {"en": "Loading news...",   "et": "Laadimine...",       "lt": "Kraunama...",
                          "fi": "Ladataan...", "sv": "Laddar..."},
    "js_news_empty":     {"en": "No news available", "et": "Uudiseid pole",      "lt": "Naujienų nėra",
                          "fi": "Ei uutisia", "sv": "Inga nyheter"},
    "js_news_just_now":  {"en": "just now",          "et": "just praegu",        "lt": "ką tik",
                          "fi": "juuri nyt", "sv": "just nu"},
    "js_news_min_ago":   {"en": "{n}m ago",          "et": "{n}m tagasi",        "lt": "prieš {n}m",
                          "fi": "{n}m sitten", "sv": "{n}m sedan"},
    "js_news_hour_ago":  {"en": "{n}h ago",          "et": "{n}t tagasi",        "lt": "prieš {n}val",
                          "fi": "{n}t sitten", "sv": "{n}t sedan"},
    "js_news_day_ago":   {"en": "{n}d ago",          "et": "{n}p tagasi",        "lt": "prieš {n}d",
                          "fi": "{n}pv sitten", "sv": "{n}d sedan"},
    "js_see_more":       {"en": "See more",          "et": "Näita rohkem",       "lt": "Rodyti daugiau",
                          "fi": "Näytä lisää", "sv": "Visa mer"},
    "js_see_less":       {"en": "See less",           "et": "Näita vähem",        "lt": "Rodyti mažiau",
                          "fi": "Näytä vähemmän", "sv": "Visa mindre"},
    "js_download_xls":   {"en": "Download XLS",      "et": "Laadi XLS alla",     "lt": "Atsisiųsti XLS",
                          "fi": "Lataa XLS", "sv": "Ladda ner XLS"},
    "js_download_word":  {"en": "\U0001f4dd Download Word", "et": "\U0001f4dd Laadi Word alla", "lt": "\U0001f4dd Atsisiųsti Word",
                          "fi": "\U0001f4dd Lataa Word", "sv": "\U0001f4dd Ladda ner Word"},
    "js_visualize":      {"en": "Visualize",         "et": "Visualiseeri",       "lt": "Vizualizuoti",
                          "fi": "Visualisoi", "sv": "Visualisera"},

    # ── Pipeline page ─────────────────────────────────────────────
    "pipe_title":        {"en": "Pipeline",          "et": "Pipeline",           "lt": "Pipeline",
                          "fi": "Pipeline", "sv": "Pipeline"},
    "pipe_companies":    {"en": "{n} companies",     "et": "{n} ettevõtet",      "lt": "{n} įmonių",
                          "fi": "{n} yritystä", "sv": "{n} företag"},
    "pipe_all":          {"en": "All",               "et": "Kõik",               "lt": "Visos",
                          "fi": "Kaikki", "sv": "Alla"},
    "pipe_back":         {"en": "Back to chat",      "et": "Tagasi vestlusse",   "lt": "Grįžti į pokalbį",
                          "fi": "Takaisin chattiin", "sv": "Tillbaka till chatten"},
    "pipe_deal_not_found": {"en": "Deal not found",  "et": "Tehingut ei leitud", "lt": "Sandoris nerastas",
                          "fi": "Kauppaa ei löytynyt", "sv": "Deal hittades inte"},
    "pipe_back_pipe":    {"en": "← Pipeline",        "et": "← Pipeline",         "lt": "← Pipeline",
                          "fi": "← Pipeline", "sv": "← Pipeline"},
    "stage_sourced":     {"en": "Sourced",           "et": "Leitud",             "lt": "Surasta",
                          "fi": "Löydetty", "sv": "Funnen"},
    "stage_screened":    {"en": "Screened",          "et": "Sõelutud",           "lt": "Atrinkta",
                          "fi": "Seulottu", "sv": "Screenad"},
    "stage_loi":         {"en": "LOI / IOI",         "et": "LOI / IOI",          "lt": "LOI / IOI",
                          "fi": "LOI / IOI", "sv": "LOI / IOI"},
    "stage_diligence":   {"en": "Diligence",         "et": "Audit",              "lt": "Patikra",
                          "fi": "Due Diligence", "sv": "Due Diligence"},
    "stage_ic":          {"en": "IC",                "et": "IC",                 "lt": "IC",
                          "fi": "IC", "sv": "IC"},
    "stage_signed":      {"en": "Signed",            "et": "Allkirjastatud",     "lt": "Pasirašyta",
                          "fi": "Allekirjoitettu", "sv": "Signerad"},
    "stage_closed":      {"en": "Closed",            "et": "Suletud",            "lt": "Uždaryta",
                          "fi": "Suljettu", "sv": "Stängd"},
    "stage_held":        {"en": "Held",              "et": "Hallatud",           "lt": "Valdoma",
                          "fi": "Hallinnassa", "sv": "Förvaltad"},
    "stage_exited":      {"en": "Exited",            "et": "Väljutud",           "lt": "Parduota",
                          "fi": "Irtauduttu", "sv": "Avyttrad"},
    "stage_passed":      {"en": "Passed",            "et": "Loobutud",           "lt": "Atmesta",
                          "fi": "Ohitettu", "sv": "Passerad"},
    "brief_ltm":         {"en": "LTM financials",    "et": "LTM finantsandmed",  "lt": "LTM finansinės ataskaitos",
                          "fi": "LTM-taloustiedot", "sv": "LTM-finansdata"},
    "brief_customers":   {"en": "Top customers",     "et": "Tippkliendid",       "lt": "Pagrindiniai klientai",
                          "fi": "Pääasiakkaat", "sv": "Toppkunder"},
    "brief_dd":          {"en": "DD findings",       "et": "DD leiud",           "lt": "DD išvados",
                          "fi": "DD-löydökset", "sv": "DD-fynd"},
    "brief_hq":          {"en": "HQ",                "et": "Peakontor",          "lt": "Būstinė",
                          "fi": "Pääkonttori", "sv": "Huvudkontor"},
    "brief_employees":   {"en": "Employees",         "et": "Töötajad",           "lt": "Darbuotojai",
                          "fi": "Työntekijät", "sv": "Anställda"},
    "brief_founded":     {"en": "Founded",           "et": "Asutatud",           "lt": "Įkurta",
                          "fi": "Perustettu", "sv": "Grundat"},
    "brief_ownership":   {"en": "Ownership",         "et": "Omandivorm",         "lt": "Nuosavybė",
                          "fi": "Omistusmuoto", "sv": "Ägarform"},
    "brief_revenue":     {"en": "Revenue",           "et": "Käive",              "lt": "Pajamos",
                          "fi": "Liikevaihto", "sv": "Omsättning"},
    "brief_adj_ebitda":  {"en": "Adj. EBITDA",       "et": "Adj. EBITDA",        "lt": "Adj. EBITDA",
                          "fi": "Adj. EBITDA", "sv": "Adj. EBITDA"},
    "brief_margin":      {"en": "Margin",            "et": "Marginaal",          "lt": "Marža",
                          "fi": "Marginaali", "sv": "Marginal"},
    "brief_ask_ev":      {"en": "Ask EV",            "et": "Küsitav EV",         "lt": "Prašoma EV",
                          "fi": "Pyyntö EV", "sv": "Begärt EV"},
    "brief_no_contracts": {"en": "No contracts loaded.", "et": "Lepinguid pole laaditud.", "lt": "Nėra įkeltų sutarčių.",
                          "fi": "Sopimuksia ei ladattu.", "sv": "Inga avtal laddade."},
    "brief_no_findings": {"en": "No findings yet. Try running VDR Auditor.",
                          "et": "Leide veel pole. Proovige käivitada VDR Auditor.",
                          "lt": "Kol kas nėra išvadų. Išbandykite VDR Auditor.",
                          "fi": "Ei löydöksiä vielä. Kokeile VDR Auditoria.", "sv": "Inga fynd ännu. Prova VDR Auditor."},
    "pipe_chat_hint":    {"en": "Ask about {company} — the deal brief is on the right. Try 'triage this deal', 'draft IC memo', or 'summarize DD findings'.",
                          "et": "Küsige ettevõtte {company} kohta — tehingu ülevaade on paremal. Proovige 'triage this deal', 'draft IC memo' või 'summarize DD findings'.",
                          "lt": "Klauskite apie {company} — sandorio aprašymas dešinėje. Išbandykite 'triage this deal', 'draft IC memo' arba 'summarize DD findings'.",
                          "fi": "Kysy yrityksestä {company} — kaupan tiivistelmä on oikealla.", "sv": "Fråga om {company} — deal-sammanfattningen finns till höger."},
    "pipe_input_hint":   {"en": "Ask about {company} — e.g. triage, LBO, DD findings",
                          "et": "Küsige {company} kohta — nt triage, LBO, DD leiud",
                          "lt": "Klauskite apie {company} — pvz. triage, LBO, DD findings",
                          "fi": "Kysy yrityksestä {company} — esim. triage, LBO, DD-löydökset", "sv": "Fråga om {company} — t.ex. triage, LBO, DD-fynd"},

    # ── Analytics page ────────────────────────────────────────────
    "analytics_title":   {"en": "Analytics",         "et": "Analüütika",         "lt": "Analitika",
                          "fi": "Analytiikka", "sv": "Analys"},
    "analytics_sub":     {"en": "Text → SQL → Plotly",
                          "et": "Tekst → SQL → Plotly",
                          "lt": "Tekstas → SQL → Plotly",
                          "fi": "Teksti → SQL → Plotly", "sv": "Text → SQL → Plotly"},
    "analytics_h2":      {"en": "Ask a question of your PE database.",
                          "et": "Esitage küsimus oma PE andmebaasile.",
                          "lt": "Paklauskite savo PE duomenų bazės.",
                          "fi": "Kysy PE-tietokannaltasi.", "sv": "Ställ en fråga till er PE-databas."},
    "analytics_body":    {"en": "Questions are translated to SQL against the pehero schema, run read-only, "
                                "and rendered as a Plotly chart plus the raw table.",
                          "et": "Küsimused tõlgitakse SQL-iks pehero skeemi vastu, käivitatakse ainult-lugemise režiimis "
                                "ja renderdatakse Plotly graafikuna koos toortabeliga.",
                          "lt": "Užklausos verčiamos į SQL pagal pehero schemą, vykdomos tik-skaitymui "
                                "ir atvaizduojamos Plotly grafike bei lentele.",
                          "fi": "Kysymykset käännetään SQL:ksi pehero-skeemaa vasten, suoritetaan vain-luku-tilassa ja renderöidään Plotly-kaaviona sekä raakana taulukkona.", "sv": "Frågor översätts till SQL mot pehero-schemat, körs som skrivskyddade och renderas som Plotly-diagram plus råtabell."},
    "analytics_run":     {"en": "Run",               "et": "Käivita",            "lt": "Vykdyti",
                          "fi": "Suorita", "sv": "Kör"},
    "analytics_thinking": {"en": "Thinking…",        "et": "Mõtlen…",            "lt": "Galvoju…",
                          "fi": "Ajattelen…", "sv": "Tänker…"},

    # ── Instructions page ─────────────────────────────────────────
    "instr_title":       {"en": "Instructions",      "et": "Juhised",            "lt": "Instrukcijos",
                          "fi": "Ohjeet", "sv": "Instruktioner"},
    "instr_count":       {"en": "{n} agent prompts",  "et": "{n} agendi prompti", "lt": "{n} agentų promptų",
                          "fi": "{n} agentin promptia", "sv": "{n} agentprompts"},
    "instr_intro":       {"en": "Edit the system prompts that drive each agent. Saves write to "
                                "prompts/system/<slug>.md and are versioned in the database.",
                          "et": "Redigeerige süsteemi prompte, mis juhivad iga agenti. Salvestused kirjutatakse "
                                "prompts/system/<slug>.md ja versioonitakse andmebaasis.",
                          "lt": "Redaguokite sistemos promptus, kurie valdo kiekvieną agentą. Išsaugojimai rašomi į "
                                "prompts/system/<slug>.md ir versijuojami duomenų bazėje.",
                          "fi": "Muokkaa järjestelmäprompteja, jotka ohjaavat kutakin agenttia. Tallennukset versioidaan tietokantaan.", "sv": "Redigera systempromptarna som styr varje agent. Sparningar versionshanteras i databasen."},
    "instr_shared":      {"en": "Edit shared PE glossary",
                          "et": "Redigeeri jagatud PE sõnastikku",
                          "lt": "Redaguoti bendrą PE žodyną",
                          "fi": "Muokkaa jaettua PE-sanastoa", "sv": "Redigera delad PE-ordlista"},
    "instr_shared_title": {"en": "Shared PE glossary",
                           "et": "Jagatud PE sõnastik",
                           "lt": "Bendras PE žodynas",
                          "fi": "Jaettu PE-sanasto", "sv": "Delad PE-ordlista"},
    "instr_shared_sub":  {"en": "Prepended to every agent's system prompt",
                          "et": "Lisatakse iga agendi süsteemiprompti ette",
                          "lt": "Pridedėta prie kiekvieno agento sistemos promptų",
                          "fi": "Lisätään jokaisen agentin järjestelmäpromptin alkuun", "sv": "Läggs till före varje agents systemprompt"},
    "instr_editor":      {"en": "Editor",            "et": "Redaktor",           "lt": "Redaktorius",
                          "fi": "Editori", "sv": "Redigerare"},
    "instr_markdown":    {"en": "Markdown",          "et": "Markdown",           "lt": "Markdown",
                          "fi": "Markdown", "sv": "Markdown"},
    "instr_history":     {"en": "History",           "et": "Ajalugu",            "lt": "Istorija",
                          "fi": "Historia", "sv": "Historik"},
    "instr_save":        {"en": "Save",              "et": "Salvesta",           "lt": "Išsaugoti",
                          "fi": "Tallenna", "sv": "Spara"},
    "instr_cancel":      {"en": "Cancel",            "et": "Tühista",            "lt": "Atšaukti",
                          "fi": "Peruuta", "sv": "Avbryt"},
}


def t(key: str, lang: str = DEFAULT_LANG) -> str:
    """Look up a translation. Falls back to English, then to the key itself."""
    entry = TRANSLATIONS.get(key)
    if not entry:
        return key
    return entry.get(lang, entry.get("en", key))


# ── Agent & category translations ─────────────────────────────────────

CATEGORY_TRANSLATIONS: dict[str, dict[str, dict[str, str]]] = {
    "sourcing": {
        "name": {"en": "Deal Sourcing & Screening", "et": "Tehingute otsing ja sõelumine", "lt": "Sandorių paieška ir atranka",
                  "fi": "Tehingute otsing ja sõelumine", "sv": "Deal sourcing & screening"},
        "blurb": {"en": "Find proprietary deals before they hit the auction.",
                  "et": "Leidke ainulaadsed tehingud enne, kui need jõuavad oksjonile.",
                  "lt": "Raskite savitus sandorius anksčiau nei jie pateks į aukcioną."},
    },
    "underwriting": {
        "name": {"en": "LBO Underwriting Engine", "et": "LBO hindamise mootor", "lt": "LBO vertinimo variklis",
                  "fi": "LBO-arviointi", "sv": "LBO-bedömning"},
        "blurb": {"en": "Teaser to IC-ready LBO model in hours.",
                  "et": "Teaserist IC-valmis LBO mudelini tundidega.",
                  "lt": "Nuo teaserio iki IC parengt LBO modelio per valandas."},
    },
    "diligence": {
        "name": {"en": "Due Diligence Stack", "et": "Due Diligence süsteem", "lt": "Due Diligence sistema",
                  "fi": "Due Diligence -järjestelmä", "sv": "Due Diligence-system"},
        "blurb": {"en": "VDR audited, QoE validated, risks surfaced early.",
                  "et": "VDR auditeeritud, QoE valideeritud, riskid varakult tuvastatud.",
                  "lt": "VDR patikrintas, QoE patvirtintas, rizikos atskleistos anksti."},
    },
    "capital": {
        "name": {"en": "Capital & LP Relations", "et": "Kapital ja LP suhted", "lt": "Kapitalas ir LP santykiai",
                  "fi": "Pääoma ja LP-suhteet", "sv": "Kapital & LP-relationer"},
        "blurb": {"en": "IC memos, teasers and LP updates your GP will sign.",
                  "et": "IC memod, teaserid ja LP uuendused, mille teie GP allkirjastab.",
                  "lt": "IC memo, teaser ir LP ataskaitos, kurias jūsų GP pasirašys."},
    },
    "asset_mgmt": {
        "name": {"en": "Portfolio Operations", "et": "Portfelli opereerimine", "lt": "Portfelio operacijos",
                  "fi": "Portfolion hallinnointi", "sv": "Portföljförvaltning"},
        "blurb": {"en": "Drive EBITDA growth and value creation post-close.",
                  "et": "Edendage EBITDA kasvu ja väärtuse loomist pärast sulgemist.",
                  "lt": "Skatinkite EBITDA augimą ir vertės kūrimą po uždarymo."},
    },
}

AGENT_TRANSLATIONS: dict[str, dict[str, dict[str, str]]] = {
    "market_scanner":     {"name": {"en": "Market Scanner",           "et": "Turuskaneer",                  "lt": "Rinkos skeneris",
                                         "fi": "Markkinaskanneri", "sv": "Marknadsskanner"},
                           "one_liner": {"en": "PitchBook + banker feeds + proprietary outreach, ranked by fit.",
                                         "et": "PitchBook + pankurite vood + otsekontaktid, reastatud sobivuse järgi.",
                                         "lt": "PitchBook + bankininkų srautai + tiesioginė paieška, suranguota pagal tinkamumą."}},
    "deal_triage":        {"name": {"en": "Deal Triage Agent",        "et": "Tehingute sõelumisagent",      "lt": "Sandorių atrankos agentas",
                                         "fi": "Kauppojen seulonta-agentti", "sv": "Deal screening-agent"},
                           "one_liner": {"en": "Go / no-go in 90 seconds against your fund mandate.",
                                         "et": "Jah / ei 90 sekundiga vastavalt teie fondi mandaadile.",
                                         "lt": "Taip / ne per 90 sekundžių pagal jūsų fondo mandatą."}},
    "comp_finder":        {"name": {"en": "Transaction Comps Finder", "et": "Tehingute võrdluste otsija",   "lt": "Sandorių lyginamųjų paieška",
                                         "fi": "Kauppavertailujen hakija", "sv": "Transaktionsjämförelsesökare"},
                           "one_liner": {"en": "M&A + trading comps across 3 sources with outlier filtering.",
                                         "et": "M&A + kauplemise võrdlused 3 allikast koos erindite filtreerimisega.",
                                         "lt": "M&A + prekybinės komp. iš 3 šaltinių su išskirčių filtru."}},
    "seller_intent":      {"name": {"en": "Owner Intent Signal",      "et": "Omaniku kavatsuse signaal",    "lt": "Savininko ketinimo signalas",
                                         "fi": "Omistajan aikomus-signaali", "sv": "Ägarsignalanalys"},
                           "one_liner": {"en": "Ranks companies by likelihood of sale in the next 12 months.",
                                         "et": "Reastab ettevõtteid müügi tõenäosuse järgi järgmise 12 kuu jooksul.",
                                         "lt": "Ranguoja įmones pagal pardavimo tikimybę per artimiausius 12 mėnesių."}},
    "outreach_email":     {"name": {"en": "Outreach Email Drafter",   "et": "Kontaktikirjade koostaja",     "lt": "Kontaktinių laiškų rengėjas",
                                         "fi": "Yhteydenottokirjeiden laatija", "sv": "Kontaktmejlsförfattare"},
                           "one_liner": {"en": "Personalized founder/broker outreach emails in your fund's voice.",
                                         "et": "Isikustatud asutaja/maakler kontaktikirjad teie fondi häälega.",
                                         "lt": "Personalizuoti kontaktiniai laiškai įkūrėjams/tarpininkams jūsų fondo tonu."}},
    "loi_writer":         {"name": {"en": "LOI Writer",               "et": "LOI koostaja",                 "lt": "LOI rengėjas",
                                         "fi": "LOI-laatija", "sv": "LOI-författare"},
                           "one_liner": {"en": "Non-binding letter of intent — price, structure, conditions, timeline.",
                                         "et": "Mittesiduv kavatsuskiri — hind, struktuur, tingimused, ajakava.",
                                         "lt": "Neįpareigojantis ketinimo laškas — kaina, struktūra, sąlygos, terminai."}},
    "rent_roll_parser":   {"name": {"en": "Cap Table Parser",         "et": "Cap Table analüsaator",        "lt": "Cap Table analizatorius",
                                         "fi": "Cap Table -analysaattori", "sv": "Cap Table-analysator"},
                           "one_liner": {"en": "Any cap table format → clean, fully-diluted ownership with waterfalls.",
                                         "et": "Mis tahes cap table formaat → puhas, täislahjendatud omandipilt koos juga-analüüsiga.",
                                         "lt": "Bet koks cap table formatas → švarus, pilnai praskiestas nuosavybės vaizdas."}},
    "t12_normalizer":     {"name": {"en": "LTM Financials Normalizer", "et": "LTM finantsandmete normaliseerija", "lt": "LTM finansinių normalizatorius",
                                         "fi": "LTM-taloustietojen normalisoija", "sv": "LTM-finansnormaliserare"},
                           "one_liner": {"en": "Messy owner financials → clean, add-back-adjusted LTM EBITDA.",
                                         "et": "Segased omaniku finantsandmed → puhas, kohandatud LTM EBITDA.",
                                         "lt": "Netvarkingos savininko ataskaitos → švarus, koreguotas LTM EBITDA."}},
    "pro_forma_builder":  {"name": {"en": "LBO Model Builder",        "et": "LBO mudeli ehitaja",           "lt": "LBO modelio statytojas",
                                         "fi": "LBO-mallin rakentaja", "sv": "LBO-modellbyggare"},
                           "one_liner": {"en": "5-year LBO model with sensitivity grid — editable assumptions.",
                                         "et": "5-aasta LBO mudel koos tundlikkuse tabeliga — muudetavad eeldused.",
                                         "lt": "5 metų LBO modelis su jautrumo lentele — redaguojamos prielaidos."}},
    "debt_stack_modeler": {"name": {"en": "Debt Stack Modeler",       "et": "Võlastruktuuri modelleerija",   "lt": "Skolos struktūros modeliuotojas",
                                         "fi": "Velkarakenteen mallintaja", "sv": "Skuldstrukturmodellerare"},
                           "one_liner": {"en": "Unitranche + mezz + revolver — with live leverage + DSCR.",
                                         "et": "Unitranche + mezz + revolver — reaalajas finantsvõimendus + DSCR.",
                                         "lt": "Unitranche + mezz + revolver — su gyvais sverto + DSCR rodikliais."}},
    "return_metrics":     {"name": {"en": "Return Metrics",           "et": "Tootluse mõõdikud",            "lt": "Grąžos metrikos",
                                         "fi": "Tuottomittarit", "sv": "Avkastningsmått"},
                           "one_liner": {"en": "IRR, MOIC, levered/unlevered, with a value-creation bridge.",
                                         "et": "IRR, MOIC, võimendusega/võimenduseta, koos väärtuse loomise sillaga.",
                                         "lt": "IRR, MOIC, su svertu / be sverto, su vertės kūrimo tiltu."}},
    "doc_room_auditor":   {"name": {"en": "VDR Auditor",              "et": "VDR audiitor",                 "lt": "VDR auditorius",
                                         "fi": "VDR-auditoija", "sv": "VDR-revisor"},
                           "one_liner": {"en": "Cross-checks the data room against a full PE DD checklist.",
                                         "et": "Ristkontrollib andmeruumi täieliku PE DD kontrollnimekirja vastu.",
                                         "lt": "Kryžminai tikrina duomenų kambarį pagal pilną PE DD kontrolę."}},
    "lease_abstractor":   {"name": {"en": "Contract Abstractor",      "et": "Lepingute abstraheerija",      "lt": "Sutarčių abstraktorius",
                                         "fi": "Sopimus-abstrahoija", "sv": "Avtalsabstraherare"},
                           "one_liner": {"en": "PDFs → contract abstracts with key terms, options, and risks.",
                                         "et": "PDF-id → lepingute kokkuvõtted põhitingimuste, optsioonide ja riskidega.",
                                         "lt": "PDF → sutarčių santraukos su pagrindinėmis sąlygomis, opcijomis ir rizikomis."}},
    "title_zoning":       {"name": {"en": "Legal & Regulatory Checker", "et": "Juriidiline ja regulatiivne kontroll", "lt": "Teisinės ir reguliavimo patikra",
                                         "fi": "Juridinen ja sääntelytarkistus", "sv": "Juridisk och regulatorisk kontroll"},
                           "one_liner": {"en": "Corporate records + litigation + regulatory review, flags material issues.",
                                         "et": "Äriregistri andmed + kohtuvaidlused + regulatiivne ülevaade, märgib olulised probleemid.",
                                         "lt": "Įmonės dokumentai + bylinjimas + reguliavimo peržiūra, pažymi esminius dalykus."}},
    "physical_condition": {"name": {"en": "Operational Diligence Reviewer", "et": "Operatiivse auditi ülevaataja", "lt": "Operacinės patikros peržiūrėtojas",
                                         "fi": "Operatiivisen auditoinnin tarkastaja", "sv": "Operativ due diligence-granskare"},
                           "one_liner": {"en": "Reads operational DD + QoE, builds a 100-day value-creation plan.",
                                         "et": "Loeb operatiivset DD-d + QoE-d, koostab 100-päevase väärtuse loomise plaani.",
                                         "lt": "Skaito operacinę DD + QoE, kuria 100 dienų vertės kūrimo planą."}},
    "environmental_risk": {"name": {"en": "ESG & Compliance Risk Flagger", "et": "ESG ja vastavusriski märkija", "lt": "ESG ir atitikties rizikos žymiklis",
                                         "fi": "ESG- ja vaatimustenmukaisuusriskien merkitsijä", "sv": "ESG- och efterlevnadsriskflaggare"},
                           "one_liner": {"en": "ESG review — flags environmental, social, governance exposures.",
                                         "et": "ESG ülevaade — tuvastab keskkonna-, sotsiaal- ja valitsemisriskid.",
                                         "lt": "ESG peržiūra — fiksuoja aplinkosaugos, socialines, valdymo rizikas."}},
    "investor_memo":      {"name": {"en": "IC Memo Writer",           "et": "IC memo koostaja",             "lt": "IC Memo rengėjas",
                                         "fi": "IC-muistion laatija", "sv": "IC-memoförfattare"},
                           "one_liner": {"en": "IC memo your investment committee will actually read.",
                                         "et": "IC memo, mida teie investeerimiskomitee tegelikult loeb.",
                                         "lt": "IC memo, kurį jūsų investicijų komitetas tikrai perskaitys."}},
    "deal_teaser":        {"name": {"en": "Teaser Designer",          "et": "Teaseri disainer",             "lt": "Teaserio dizaineris",
                                         "fi": "Teaser-suunnittelija", "sv": "Teaser-designer"},
                           "one_liner": {"en": "2-page teaser with thesis, financials, returns snapshot.",
                                         "et": "2-leheküljeline teaser teesi, finantsandmete ja tootluse hetkeseisuga.",
                                         "lt": "2 puslapių teaseris su teze, finansais, grąžos momentine nuotrauka."}},
    "lp_update":          {"name": {"en": "LP Update Generator",      "et": "LP aruande generaator",        "lt": "LP ataskaitų generatorius",
                                         "fi": "LP-raporttien generaattori", "sv": "LP-uppdateringsgenerator"},
                           "one_liner": {"en": "Quarterly LP letter with portfolio performance + outlook.",
                                         "et": "Kvartali LP kiri portfelli tulemuste ja väljavaatega.",
                                         "lt": "Ketvirtinis LP laiškas su portfelio rezultatais + prognozėmis."}},
    "fundraising_crm":    {"name": {"en": "Fundraising CRM Copilot",  "et": "Raha kaasamise CRM kopiloot",  "lt": "Lėšų pritraukimo CRM kopilotas",
                                         "fi": "Varainhankinta-CRM-kopilotti", "sv": "Fundraising CRM-copilot"},
                           "one_liner": {"en": "LP pipeline ranked by fit, staleness, and commitment size.",
                                         "et": "LP pipeline reastatud sobivuse, vanuse ja kohustuse suuruse järgi.",
                                         "lt": "LP pipeline, suranguotas pagal tinkamumą, senumą ir įsipareigojimo dydį."}},
    "rent_optimization":  {"name": {"en": "Pricing Optimization Agent", "et": "Hinnastamise optimeerimise agent", "lt": "Kainodara optimizavimo agentas",
                                         "fi": "Hinnoittelun optimointiagentti", "sv": "Prissättningsoptimeringsagent"},
                           "one_liner": {"en": "SKU/segment pricing recommendations from elasticity + peer benchmarks.",
                                         "et": "SKU/segmendi hinnastamise soovitused elastsuse + võrdlusettevõtete põhjal.",
                                         "lt": "SKU/segmento kainodaros rekomendacijos pagal elastingumą + lyginamuosius."}},
    "opex_variance":      {"name": {"en": "EBITDA Variance Watcher",  "et": "EBITDA kõrvalekallete jälgija", "lt": "EBITDA nuokrypių stebėtojas",
                                         "fi": "EBITDA-poikkeamien tarkkailija", "sv": "EBITDA-avvikelsebevakare"},
                           "one_liner": {"en": "Monthly EBITDA variance vs. budget — with root-cause commentary.",
                                         "et": "Igakuine EBITDA kõrvalekalletest eelarvest — algpõhjuse kommentaariga.",
                                         "lt": "Mėnesinis EBITDA nuokrypis nuo biudžeto — su priežasčių komentarais."}},
    "capex_prioritizer":  {"name": {"en": "Value Creation Prioritizer", "et": "Väärtuse loomise prioritiseerija", "lt": "Vertės kūrimo prioritizatorius",
                                         "fi": "Arvonluonnin priorisoija", "sv": "Värdeskapandeprioriteterare"},
                           "one_liner": {"en": "Ranks value-creation initiatives by EBITDA impact and ROI.",
                                         "et": "Reastab väärtuse loomise algatusi EBITDA mõju ja ROI järgi.",
                                         "lt": "Ranguoja vertės kūrimo iniciatyvas pagal EBITDA poveikį ir ROI."}},
    "tenant_churn":       {"name": {"en": "Customer Churn Predictor", "et": "Kliendikao ennustaja",         "lt": "Klientų praradimo prognozuotojas",
                                         "fi": "Asiakaspoistuman ennustaja", "sv": "Kundchurn-prediktor"},
                           "one_liner": {"en": "Scores each customer's renewal likelihood; drives retention actions.",
                                         "et": "Hindab iga kliendi uuendamise tõenäosust; juhib hoidmistegevusi.",
                                         "lt": "Vertina kiekvieno kliento atsinaujinimo tikimybę; skatina išlaikymo veiksmus."}},
}


def agent_t(slug: str, field: str, lang: str = DEFAULT_LANG) -> str:
    """Translate an agent field. Falls back to English AgentSpec attribute."""
    entry = AGENT_TRANSLATIONS.get(slug, {}).get(field)
    if entry:
        return entry.get(lang, entry.get("en", ""))
    from agents.registry import AGENTS_BY_SLUG
    spec = AGENTS_BY_SLUG.get(slug)
    if spec:
        return getattr(spec, field, "")
    return ""


def category_t(key: str, field: str, lang: str = DEFAULT_LANG) -> str:
    """Translate a category field."""
    entry = CATEGORY_TRANSLATIONS.get(key, {}).get(field)
    if entry:
        return entry.get(lang, entry.get("en", ""))
    return key


def js_translations(lang: str = DEFAULT_LANG) -> dict[str, str]:
    """Return the ~30 JS-facing translation strings for the given language."""
    return {k.removeprefix("js_"): t(k, lang)
            for k in TRANSLATIONS if k.startswith("js_")}
