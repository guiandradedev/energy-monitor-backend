"""Trunca todas as tabelas de dados, mantendo apenas o controle de migrações
(`schema_migration`). Operação destrutiva e irreversível."""
from dotenv import load_dotenv
load_dotenv()

from infra.database.postgres import get_engine, text


TABLES = [
    "event",
    "breaker",
    "device_state",
    "device",
    "safety_limit",
    "priority_level",
    "parameter",
]


def main():
    engine = get_engine()
    print(f"Truncando: {', '.join(TABLES)}...")
    with engine.begin() as conn:
        conn.execute(text(
            f"TRUNCATE TABLE {', '.join(TABLES)} RESTART IDENTITY CASCADE"
        ))
    print("Pronto. (schema_migration preservada)")


if __name__ == "__main__":
    main()
