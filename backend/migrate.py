"""Aplica migrações SQL pendentes em ordem alfabética. Idempotente."""
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from infra.database.postgres import get_engine, text

MIGRATIONS_DIR = Path(__file__).parent / "infra" / "database" / "sql" / "migrations"

CREATE_TRACKING_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migration (
    filename TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


def applied_filenames(conn):
    rows = conn.execute(text("SELECT filename FROM schema_migration")).fetchall()
    return {r.filename for r in rows}


def apply_migration(conn, path: Path):
    sql = path.read_text()
    conn.exec_driver_sql(sql)
    conn.execute(
        text("INSERT INTO schema_migration (filename) VALUES (:fn)"),
        {"fn": path.name},
    )


def main():
    engine = get_engine()
    with engine.begin() as conn:
        conn.exec_driver_sql(CREATE_TRACKING_TABLE)
        already_applied = applied_filenames(conn)
        files = sorted(MIGRATIONS_DIR.glob("*.sql"))
        pending = [f for f in files if f.name not in already_applied]

        if not pending:
            print("Nenhuma migração pendente.")
            return

        for f in pending:
            print(f"Aplicando {f.name}...")
            apply_migration(conn, f)
        print(f"{len(pending)} migração(ões) aplicada(s).")


if __name__ == "__main__":
    main()
