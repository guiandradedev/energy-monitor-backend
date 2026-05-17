"""Cache em memória de parâmetros, limites de segurança e níveis de prioridade.

Refresh periódico em thread de fundo + invalidação ativa via `refresh()` para os
CRUDs chamarem após escrita.
"""
import threading
from typing import Optional

from infra.database.postgres import get_engine, text

_DEFAULT_REFRESH_S = 300


class ConfigCache:
    def __init__(self):
        self._lock = threading.RLock()
        self._parameters: dict[str, str] = {}
        self._safety_limits: dict[str, dict] = {}
        self._priorities: list[dict] = []
        self._refresh_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def refresh(self):
        """Relê tudo do banco e troca o estado atomicamente."""
        engine = get_engine()
        with engine.connect() as conn:
            params_rows = conn.execute(
                text("SELECT key, value FROM parameter")
            ).fetchall()
            limits_rows = conn.execute(text("""
                SELECT breaker_id, nominal_current_a, shed_threshold_pct, restore_threshold_pct
                FROM safety_limit
            """)).fetchall()
            priorities_rows = conn.execute(text("""
                SELECT id, label, rank FROM priority_level ORDER BY rank DESC
            """)).fetchall()

        new_parameters = {r.key: r.value for r in params_rows}
        new_limits = {
            r.breaker_id: {
                "nominal_current_a": float(r.nominal_current_a),
                "shed_threshold_pct": float(r.shed_threshold_pct),
                "restore_threshold_pct": float(r.restore_threshold_pct),
            }
            for r in limits_rows
        }
        new_priorities = [
            {"id": r.id, "label": r.label, "rank": r.rank}
            for r in priorities_rows
        ]

        with self._lock:
            self._parameters = new_parameters
            self._safety_limits = new_limits
            self._priorities = new_priorities

    def get_parameter(self, key: str, default: Optional[str] = None) -> Optional[str]:
        with self._lock:
            return self._parameters.get(key, default)

    def get_parameter_int(self, key: str, default: int) -> int:
        value = self.get_parameter(key)
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            return default

    def get_parameter_float(self, key: str, default: float) -> float:
        value = self.get_parameter(key)
        if value is None:
            return default
        try:
            return float(value)
        except ValueError:
            return default

    def get_safety_limit(self, breaker_id: str) -> Optional[dict]:
        with self._lock:
            limit = self._safety_limits.get(breaker_id)
            return dict(limit) if limit is not None else None

    def get_priorities(self) -> list[dict]:
        with self._lock:
            return [dict(p) for p in self._priorities]

    def start(self):
        """Bootstrap síncrono + thread daemon de refresh periódico."""
        self.refresh()
        if self._refresh_thread is not None and self._refresh_thread.is_alive():
            return
        self._stop_event.clear()
        self._refresh_thread = threading.Thread(
            target=self._refresh_loop,
            daemon=True,
            name="config-cache-refresh",
        )
        self._refresh_thread.start()

    def stop(self):
        self._stop_event.set()

    def _refresh_loop(self):
        while not self._stop_event.is_set():
            interval = self.get_parameter_int("cache_refresh_s", _DEFAULT_REFRESH_S)
            if self._stop_event.wait(timeout=interval):
                return
            try:
                self.refresh()
            except Exception as exc:
                print(f"[config_cache] refresh falhou: {exc}")


config_cache = ConfigCache()
