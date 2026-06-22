"""Seed the PEHero databases with synthetic PE data.

Usage:
    python -m synthetic.generate                  # seed=42, ~40 companies, indexes RAG
    python -m synthetic.generate --seed 7
    python -m synthetic.generate --skip-rag       # OLTP only
    python -m synthetic.generate --limit 5        # small subset for quick testing
    python -m synthetic.generate --fresh          # truncates tables first (safer than --drop)
"""

from __future__ import annotations

import argparse
import json
import logging
import random
from datetime import date

from dateutil.relativedelta import relativedelta

from db import connect
from rag.indexer import DocIn, upsert_documents, build_ann_index
from synthetic import properties as P       # companies
from synthetic import rent_rolls as RR      # cap tables
from synthetic import t12s as T12           # monthly financials
from synthetic import comps as CMP          # txn + trading comps
from synthetic import market_signals as MS
from synthetic import lps as LP
from synthetic import leases as LEASE       # customer MSA bodies
from synthetic import documents as DOC

log = logging.getLogger(__name__)

TRUNCATE_TABLES = [
    "pehero.agent_invocations",
    "pehero.dd_findings",
    "pehero.portfolio_kpis",
    "pehero.market_signals",
    "pehero.investor_crm",
    "pehero.debt_stacks",
    "pehero.lbo_models",
    "pehero.trading_comps",
    "pehero.transaction_comps",
    "pehero.contracts",
    "pehero.financials",
    "pehero.cap_tables",
    "pehero.companies",
    # chat left alone to preserve user sessions across reseed
]


def _truncate():
    with connect() as conn, conn.cursor() as cur:
        for t in TRUNCATE_TABLES:
            cur.execute(f"TRUNCATE TABLE {t} RESTART IDENTITY CASCADE")
        cur.execute("TRUNCATE TABLE pehero_rag.rag_queries RESTART IDENTITY")
        cur.execute("TRUNCATE TABLE pehero_rag.embeddings RESTART IDENTITY")
        cur.execute("TRUNCATE TABLE pehero_rag.chunks RESTART IDENTITY CASCADE")
        cur.execute("TRUNCATE TABLE pehero_rag.documents RESTART IDENTITY CASCADE")
        conn.commit()


def _insert_companies(specs: list[dict]) -> dict[str, int]:
    slug_to_id: dict[str, int] = {}
    with connect() as conn, conn.cursor() as cur:
        for s in specs:
            cur.execute(
                """
                INSERT INTO pehero.companies
                  (slug, name, hq_city, hq_state, country, sector, sub_sector, website,
                   founded_year, employees, revenue_ltm, ebitda_ltm, ebitda_margin,
                   growth_rate, ownership, deal_stage, deal_type, enterprise_value,
                   ask_multiple, description, seller_intent, triage_score, triage_priority)
                VALUES (%(slug)s, %(name)s, %(hq_city)s, %(hq_state)s, %(country)s,
                        %(sector)s, %(sub_sector)s, %(website)s,
                        %(founded_year)s, %(employees)s, %(revenue_ltm)s, %(ebitda_ltm)s,
                        %(ebitda_margin)s, %(growth_rate)s, %(ownership)s, %(deal_stage)s,
                        %(deal_type)s, %(enterprise_value)s, %(ask_multiple)s,
                        %(description)s, %(seller_intent)s, %(triage_score)s, %(triage_priority)s)
                ON CONFLICT (slug) DO UPDATE SET
                  name = EXCLUDED.name, description = EXCLUDED.description
                RETURNING id, slug
                """,
                s,
            )
            row = cur.fetchone()
            slug_to_id[row[1]] = row[0]
        conn.commit()
    return slug_to_id


def _insert_cap_tables(cos_with_ids: list[tuple[int, dict]], rng: random.Random) -> int:
    n = 0
    as_of = date.today().replace(day=1)
    with connect() as conn, conn.cursor() as cur:
        for cid, co in cos_with_ids:
            ct = RR.generate_for_company(co, as_of, rng)
            cur.execute(
                """
                INSERT INTO pehero.cap_tables (company_id, as_of_date, holders, total_shares, post_money)
                VALUES (%s, %s::date, %s::jsonb, %s, %s)
                ON CONFLICT (company_id, as_of_date) DO UPDATE SET
                  holders = EXCLUDED.holders,
                  total_shares = EXCLUDED.total_shares,
                  post_money = EXCLUDED.post_money
                """,
                (cid, ct["as_of_date"], json.dumps(ct["holders"]),
                 ct["total_shares"], ct["post_money"]),
            )
            n += 1
        conn.commit()
    return n


def _insert_financials(cos_with_ids: list[tuple[int, dict]], rng: random.Random) -> int:
    n = 0
    end_month = date.today().replace(day=1) - relativedelta(months=1)
    with connect() as conn, conn.cursor() as cur:
        for cid, co in cos_with_ids:
            rows = T12.generate_for_company(co, end_month, rng)
            for r in rows:
                cur.execute(
                    """
                    INSERT INTO pehero.financials
                      (company_id, month, revenue, cogs, gross_profit, opex, ebitda,
                       adjustments, adj_ebitda, arr, gross_retention, net_retention)
                    VALUES (%s, %s::date, %s, %s, %s, %s::jsonb, %s, %s::jsonb, %s, %s, %s, %s)
                    ON CONFLICT (company_id, month) DO UPDATE SET
                      revenue = EXCLUDED.revenue, cogs = EXCLUDED.cogs,
                      gross_profit = EXCLUDED.gross_profit, opex = EXCLUDED.opex,
                      ebitda = EXCLUDED.ebitda, adjustments = EXCLUDED.adjustments,
                      adj_ebitda = EXCLUDED.adj_ebitda,
                      arr = EXCLUDED.arr, gross_retention = EXCLUDED.gross_retention,
                      net_retention = EXCLUDED.net_retention
                    """,
                    (cid, r["month"], r["revenue"], r["cogs"], r["gross_profit"],
                     json.dumps(r["opex"]), r["ebitda"], json.dumps(r["adjustments"]),
                     r["adj_ebitda"], r["arr"], r["gross_retention"], r["net_retention"]),
                )
                n += 1
        conn.commit()
    return n


def _insert_contracts(cos_with_ids: list[tuple[int, dict]], rng: random.Random) -> int:
    """Insert synthetic customer MSAs (and a handful of supplier + employment) per company."""
    n = 0
    with connect() as conn, conn.cursor() as cur:
        for cid, co in cos_with_ids:
            # customer MSAs
            n_customers = rng.randint(8, 20)
            for _ in range(n_customers):
                start = date.today() - relativedelta(days=rng.randint(180, 1200))
                term_years = rng.choice([1, 2, 3, 3, 5])
                end = start + relativedelta(years=term_years)
                annual_value = rng.randint(60_000, 3_500_000)
                cur.execute(
                    """
                    INSERT INTO pehero.contracts
                      (company_id, counterparty, contract_type, start_date, end_date,
                       annual_value, auto_renew, change_of_control_trigger,
                       termination_notice_days, exclusivity, status)
                    VALUES (%s, %s, %s, %s::date, %s::date, %s, %s, %s, %s, %s, %s)
                    """,
                    (cid,
                     rng.choice([
                         "Acme Industrial", "Vector Logistics", "Harborlight Holdings",
                         "Cascade Retail", "Northwind Distributors", "Meridian Hospitals",
                         "Alpine Foods", "Orbit Communications", "Brightline Logistics",
                         "Summit Health Systems", "Wavecrest Retail", "Keystone Partners",
                     ]) + " " + rng.choice(["Inc", "LLC", "Corp", "Co"]),
                     "customer_msa", start.isoformat(), end.isoformat(), annual_value,
                     rng.random() < 0.7, rng.random() < 0.35,
                     rng.choice([30, 60, 90, 90, 120]),
                     rng.random() < 0.12,
                     "active" if end > date.today() else "expired"),
                )
                n += 1
            # a few suppliers
            for _ in range(rng.randint(2, 6)):
                start = date.today() - relativedelta(days=rng.randint(90, 900))
                end = start + relativedelta(years=rng.choice([2, 3, 5]))
                cur.execute(
                    """
                    INSERT INTO pehero.contracts
                      (company_id, counterparty, contract_type, start_date, end_date,
                       annual_value, auto_renew, change_of_control_trigger,
                       termination_notice_days, exclusivity, status)
                    VALUES (%s, %s, %s, %s::date, %s::date, %s, %s, %s, %s, %s, %s)
                    """,
                    (cid,
                     rng.choice(["Global Components", "Rising Sun Manufacturing",
                                 "Pinecrest Services", "Nimbus Cloud Infra",
                                 "Westbridge Logistics", "Twin Cities Staffing"])
                     + " " + rng.choice(["Inc", "LLC", "Corp"]),
                     "supplier", start.isoformat(), end.isoformat(),
                     rng.randint(80_000, 1_500_000),
                     rng.random() < 0.5, rng.random() < 0.2,
                     rng.choice([30, 60, 90]), rng.random() < 0.2,
                     "active"),
                )
                n += 1
        conn.commit()
    return n


def _insert_txn_comps(cos_with_ids: list[tuple[int, dict]], rng: random.Random) -> tuple[int, int]:
    s = r = 0
    with connect() as conn, conn.cursor() as cur:
        for cid, co in cos_with_ids:
            for c in CMP.generate_transaction_comps(co, rng):
                cur.execute(
                    """
                    INSERT INTO pehero.transaction_comps
                      (company_id, target_name, acquirer, sector, sub_sector, country,
                       announce_date, close_date, enterprise_value, revenue, ebitda,
                       ev_revenue, ev_ebitda, deal_type, source)
                    VALUES (%s, %s, %s, %s, %s, %s, %s::date, %s::date, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (cid, c["target_name"], c["acquirer"], c["sector"], c["sub_sector"],
                     c["country"], c["announce_date"], c["close_date"], c["enterprise_value"],
                     c["revenue"], c["ebitda"], c["ev_revenue"], c["ev_ebitda"],
                     c["deal_type"], c["source"]),
                )
                s += 1
            for c in CMP.generate_trading_comps(co, rng):
                cur.execute(
                    """
                    INSERT INTO pehero.trading_comps
                      (company_id, ticker, peer_name, sector, market_cap, ev,
                       revenue_ltm, ebitda_ltm, ev_revenue, ev_ebitda, rev_growth,
                       ebitda_margin, as_of_date, source)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::date, %s)
                    """,
                    (cid, c["ticker"], c["peer_name"], c["sector"], c["market_cap"], c["ev"],
                     c["revenue_ltm"], c["ebitda_ltm"], c["ev_revenue"], c["ev_ebitda"],
                     c["rev_growth"], c["ebitda_margin"], c["as_of_date"], c["source"]),
                )
                r += 1
        conn.commit()
    return s, r


def _insert_market_signals(rows: list[dict]) -> int:
    with connect() as conn, conn.cursor() as cur:
        for r in rows:
            cur.execute(
                """
                INSERT INTO pehero.market_signals
                  (sector, sub_sector, metric, value, as_of_date, source)
                VALUES (%s, %s, %s, %s, %s::date, %s)
                ON CONFLICT (sector, sub_sector, metric, as_of_date) DO UPDATE SET
                  value = EXCLUDED.value, source = EXCLUDED.source
                """,
                (r["sector"], r["sub_sector"], r["metric"], r["value"], r["as_of_date"], r["source"]),
            )
        conn.commit()
    return len(rows)


def _insert_lps(rows: list[dict]) -> int:
    with connect() as conn, conn.cursor() as cur:
        for r in rows:
            cur.execute(
                """
                INSERT INTO pehero.investor_crm
                  (name, firm, lp_type, email, commitment_size, stage, focus, geography,
                   aum, last_touch, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::date, %s)
                """,
                (r["name"], r["firm"], r["lp_type"], r["email"], r["commitment_size"],
                 r["stage"], r["focus"], r["geography"], r["aum"],
                 r["last_touch"], r["notes"]),
            )
        conn.commit()
    return len(rows)


def _index_rag(cos_with_ids: list[tuple[int, dict]], rng: random.Random) -> int:
    """Index DD docs per company + top-2 customer MSAs per company + industry reports."""
    docs: list[DocIn] = []

    # Sample customer MSAs per company (top 2)
    for cid, co in cos_with_ids:
        with connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT counterparty, start_date, end_date, annual_value "
                "FROM pehero.contracts WHERE company_id = %s AND contract_type = 'customer_msa' "
                "ORDER BY annual_value DESC LIMIT 2",
                (cid,),
            )
            msas = cur.fetchall()
        for (counterparty, start_d, end_d, av) in msas:
            av_f = float(av) if av is not None else 0
            unit = {"holder": counterparty, "lease_start": str(start_d),
                    "lease_end": str(end_d), "rent": int(av_f)}
            body = LEASE.generate_lease_body(prop=co, unit=unit, rng=rng)
            docs.append(DocIn(
                title=f"MSA — {co['name']} / {counterparty}",
                doc_type="msa",
                text=body,
                company_id=cid,
                metadata={"counterparty": counterparty, "annual_value": av_f,
                          "sector": co["sector"]},
            ))

    # DD docs per company
    for cid, co in cos_with_ids:
        for d in DOC.generate_all_for_property(co, rng):
            docs.append(DocIn(
                title=d["title"],
                doc_type=d["doc_type"],
                text=d["text"],
                company_id=cid,
                metadata={"sector": co["sector"], "sub_sector": co["sub_sector"]},
            ))

    # Industry reports by sector / sub_sector
    for d in DOC.generate_market_reports([c for _, c in cos_with_ids], rng):
        docs.append(DocIn(
            title=d["title"],
            doc_type=d["doc_type"],
            text=d["text"],
            metadata={},
        ))

    log.info("embedding + upserting %d documents", len(docs))
    ids = upsert_documents(docs, replace=False)
    return len(ids)


def run(seed: int = 42, skip_rag: bool = False, limit: int | None = None, fresh: bool = False) -> None:
    if fresh:
        print("truncating pehero tables (preserving chat history)…")
        _truncate()

    rng = random.Random(seed)
    specs = P.generate(seed=seed)
    if limit:
        specs = specs[:limit]
    print(f"generated {len(specs)} companies")

    slug_to_id = _insert_companies(specs)
    cos_with_ids = [(slug_to_id[s["slug"]], s) for s in specs]

    n = _insert_cap_tables(cos_with_ids, rng)
    print(f"inserted cap tables for {n} companies")

    n = _insert_financials(cos_with_ids, rng)
    print(f"inserted {n} monthly financial rows")

    n = _insert_contracts(cos_with_ids, rng)
    print(f"inserted {n} contracts (customer MSAs + suppliers)")

    s, r = _insert_txn_comps(cos_with_ids, rng)
    print(f"inserted {s} transaction comps, {r} trading comps")

    ms_rows = MS.generate([c for _, c in cos_with_ids], seed=seed)
    n = _insert_market_signals(ms_rows)
    print(f"inserted {n} market signal rows")

    n = _insert_lps(LP.generate(count=60, seed=seed))
    print(f"inserted {n} LP contacts")

    if not skip_rag:
        n = _index_rag(cos_with_ids, rng)
        print(f"indexed {n} RAG documents")
        build_ann_index()

    print("done")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--skip-rag", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--fresh", action="store_true", help="truncate tables before seeding")
    args = ap.parse_args()
    run(seed=args.seed, skip_rag=args.skip_rag, limit=args.limit, fresh=args.fresh)
