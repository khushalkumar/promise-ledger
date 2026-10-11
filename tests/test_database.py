from ledger.database import database_url


def test_database_url_supports_postgres_and_local_sqlite_paths(tmp_path):
    postgres = "postgresql+psycopg://tasklane:secret@localhost:5432/tasklane"

    assert database_url(postgres) == postgres
    assert database_url(tmp_path / "tasklane.db").startswith("sqlite+pysqlite:///")
