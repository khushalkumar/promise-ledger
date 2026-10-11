from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


def database_url(database: str | Path) -> str:
    value = str(database)
    if value.startswith("postgres://"):
        return value.replace("postgres://", "postgresql+psycopg://", 1)
    if "://" in value:
        return value
    return f"sqlite+pysqlite:///{Path(value).resolve()}"


def create_database_engine(database: str | Path) -> Engine:
    url = database_url(database)
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, pool_pre_ping=True, connect_args=connect_args)
