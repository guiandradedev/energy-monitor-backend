import { useEffect, useState } from "react";
import { api, type EventItem } from "~/lib/api";

const TYPE_COLORS: Record<string, string> = {
  device_state_changed:
    "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300",
  device_hello:
    "bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300",
  device_offline:
    "bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-300",
  cmd_sent:
    "bg-cyan-100 text-cyan-800 dark:bg-cyan-900/40 dark:text-cyan-300",
  unknown_device:
    "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300",
};

const FALLBACK_COLOR =
  "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300";

export default function EventsPage() {
  const [items, setItems] = useState<EventItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterType, setFilterType] = useState("");
  const [autoRefresh, setAutoRefresh] = useState(true);

  async function load() {
    try {
      const qs = filterType
        ? `?limit=100&type=${encodeURIComponent(filterType)}`
        : "?limit=100";
      const r = await api.get<{ data: EventItem[] }>(`/api/events${qs}`);
      setItems(r.data);
      setError(null);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [filterType]);

  useEffect(() => {
    if (!autoRefresh) return;
    const id = setInterval(load, 3000);
    return () => clearInterval(id);
  }, [autoRefresh, filterType]);

  return (
    <section className="space-y-6">
      <h1 className="text-2xl font-bold">Eventos</h1>
      <p className="text-sm text-gray-600 dark:text-gray-300">
        Log do que o backend observou: lifecycle de cargas, comandos, mudanças
        de estado, ocorrências do mecanismo de detecção.
      </p>

      {error && (
        <div className="rounded border border-red-300 bg-red-50 dark:bg-red-900/30 dark:border-red-700 p-3 text-sm text-red-700 dark:text-red-300">
          {error}
        </div>
      )}

      <div className="flex flex-wrap items-end gap-3 rounded-lg border border-gray-200 dark:border-gray-800 p-4">
        <div className="flex flex-col">
          <label className="text-xs text-gray-500 mb-1">Filtrar por tipo</label>
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="px-3 py-2 border border-gray-300 dark:border-gray-700 rounded bg-white dark:bg-gray-900"
          >
            <option value="">Todos</option>
            <option value="device_state_changed">device_state_changed</option>
            <option value="device_hello">device_hello</option>
            <option value="device_offline">device_offline</option>
            <option value="cmd_sent">cmd_sent</option>
            <option value="unknown_device">unknown_device</option>
          </select>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={autoRefresh}
            onChange={(e) => setAutoRefresh(e.target.checked)}
          />
          Auto-refresh (3s)
        </label>
        <button
          onClick={load}
          className="px-3 py-2 text-sm border border-gray-300 dark:border-gray-700 rounded hover:bg-gray-50 dark:hover:bg-gray-800"
        >
          Atualizar
        </button>
      </div>

      <div className="rounded-lg border border-gray-200 dark:border-gray-800 overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="bg-gray-50 dark:bg-gray-900">
            <tr>
              <th className="px-4 py-2">Quando</th>
              <th className="px-4 py-2">Tipo</th>
              <th className="px-4 py-2">Dispositivo</th>
              <th className="px-4 py-2">Payload</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={4} className="px-4 py-3 text-gray-500">
                  Carregando...
                </td>
              </tr>
            )}
            {!loading && items.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-3 text-gray-500">
                  Nenhum evento.
                </td>
              </tr>
            )}
            {items.map((ev) => (
              <tr key={ev.id} className="border-t border-gray-200 dark:border-gray-800">
                <td className="px-4 py-2 text-xs text-gray-500 whitespace-nowrap">
                  {new Date(ev.ts).toLocaleString()}
                </td>
                <td className="px-4 py-2">
                  <span
                    className={`px-2 py-0.5 rounded text-xs font-medium ${
                      TYPE_COLORS[ev.type] || FALLBACK_COLOR
                    }`}
                  >
                    {ev.type}
                  </span>
                </td>
                <td className="px-4 py-2 text-xs">
                  {ev.device ? (
                    <>
                      <div>{ev.device.name}</div>
                      <div className="font-mono text-gray-500">
                        {ev.device.device_id}
                      </div>
                    </>
                  ) : (
                    <span className="text-gray-500">—</span>
                  )}
                </td>
                <td className="px-4 py-2">
                  <pre className="text-xs font-mono whitespace-pre-wrap break-all text-gray-700 dark:text-gray-300">
                    {ev.payload ? JSON.stringify(ev.payload, null, 2) : "—"}
                  </pre>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
