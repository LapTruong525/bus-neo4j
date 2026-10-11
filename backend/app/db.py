"""Kết nối Neo4j (driver chính thức, giao thức Bolt)."""
from neo4j import GraphDatabase

from . import config

_driver = None


def get_driver():
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(
            config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD)
        )
    return _driver


def close_driver():
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None


def verify():
    get_driver().verify_connectivity()


def read(query: str, **params):
    with get_driver().session(database=config.NEO4J_DATABASE) as s:
        return s.execute_read(lambda tx: [r.data() for r in tx.run(query, **params)])


def write(fn):
    """Chạy fn(tx) trong một write-transaction (tự rollback nếu có lỗi)."""
    with get_driver().session(database=config.NEO4J_DATABASE) as s:
        return s.execute_write(fn)
