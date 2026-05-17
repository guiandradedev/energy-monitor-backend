"""Popula apenas as tabelas de configuração (`parameter`, `safety_limit`,
`priority_level`). Pensado para inicializar um ambiente de produção, sem dados
de teste (sem cadastro de dispositivos nem telemetria simulada). Idempotente."""
from dotenv import load_dotenv
load_dotenv()

from infra.database.postgres import get_engine
from seed import seed_priorities, seed_safety_limits, seed_parameters


def main():
    engine = get_engine()
    with engine.begin() as conn:
        seed_priorities(conn)
        seed_safety_limits(conn)
        seed_parameters(conn)
    print("Parâmetros de produção populados (priority_level, safety_limit, parameter).")


if __name__ == "__main__":
    main()
