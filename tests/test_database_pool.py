"""Process-wide database pool ownership."""

from types import SimpleNamespace

import db


def test_psycopg_pool_is_singleton(monkeypatch):
    created = []

    class FakePool:
        check_connection = staticmethod(lambda connection: None)

        def __init__(self, **kwargs):
            created.append(kwargs)

        def open(self):
            pass

        def close(self):
            pass

    db.close_database_pools()
    monkeypatch.setattr(db, "ConnectionPool", FakePool)
    monkeypatch.setattr(db, "settings", lambda: SimpleNamespace(db_url="postgresql://unused/pe"))

    assert db.pool() is db.pool()
    assert len(created) == 1
    assert created[0]["min_size"] == 0
    assert created[0]["max_size"] == 3
    db.close_database_pools()
