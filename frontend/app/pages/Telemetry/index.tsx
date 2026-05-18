import { useEffect, useMemo, useState } from "react";
import { Line } from "react-chartjs-2";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from "chart.js";

import {
  api,
  API_URL,
  type TelemetryPoint,
  type TelemetryListResponse,
} from "~/lib/api";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
);

type HourlyPoint = {
  hour: string;
  avg_sct1: number;
  avg_sct2: number;
  avg_zmpt1: number;
  avg_zmpt2: number;
};

type FilterField = "" | "rms_sct1" | "rms_sct2" | "rms_zmpt1" | "rms_zmpt2";
type FilterOp = "" | "eq" | "lt" | "lte" | "gt" | "gte";

type Filters = {
  from: string; // datetime-local string (browser local time)
  to: string;
  field: FilterField;
  op: FilterOp;
  value: string;
};

const FIELD_LABELS: Record<Exclude<FilterField, "">, string> = {
  rms_sct1: "Corrente — fase 1 (A)",
  rms_sct2: "Corrente — fase 2 (A)",
  rms_zmpt1: "Tensão — fase 1 (V)",
  rms_zmpt2: "Tensão — fase 2 (V)",
};

const OP_LABELS: Record<Exclude<FilterOp, "">, string> = {
  eq: "= igual a",
  lt: "< menor que",
  lte: "≤ menor ou igual",
  gt: "> maior que",
  gte: "≥ maior ou igual",
};

const PAGE_SIZE = 50;
const NOMINAL_CURRENT_FALLBACK = 20;

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

function toLocalInput(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function localToUtcIso(local: string): string {
  if (!local) return "";
  return new Date(local).toISOString();
}

function fmtTime(iso: string): string {
  return new Date(iso).toLocaleTimeString();
}

function fmtDateTime(iso: string): string {
  return new Date(iso).toLocaleString();
}

function buildQueryString(applied: Filters): string {
  const qs = new URLSearchParams();
  if (applied.from) qs.set("from", localToUtcIso(applied.from));
  if (applied.to) qs.set("to", localToUtcIso(applied.to));
  if (applied.field && applied.op && applied.value !== "") {
    qs.set("field", applied.field);
    qs.set("op", applied.op);
    qs.set("value", applied.value);
  }
  return qs.toString();
}

const initialFilters = (): Filters => {
  const to = new Date();
  const from = new Date(to.getTime() - 60 * 60 * 1000);
  return {
    from: toLocalInput(from),
    to: toLocalInput(to),
    field: "",
    op: "",
    value: "",
  };
};

export default function TelemetryPage() {
  // Live state
  const [recent, setRecent] = useState<TelemetryPoint[]>([]);
  const [hourly, setHourly] = useState<HourlyPoint[]>([]);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [liveError, setLiveError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  // Filter state (form vs applied)
  const [form, setForm] = useState<Filters>(initialFilters);
  const [applied, setApplied] = useState<Filters>(initialFilters);
  const [page, setPage] = useState(0);

  // Table state
  const [rows, setRows] = useState<TelemetryPoint[]>([]);
  const [total, setTotal] = useState(0);
  const [tableLoading, setTableLoading] = useState(false);
  const [tableError, setTableError] = useState<string | null>(null);

  async function loadLive() {
    try {
      const [recentRes, hourlyRes] = await Promise.all([
        api.get<{ data: TelemetryPoint[] }>("/api/telemetry/recent?n=120"),
        api.get<{ data: HourlyPoint[] }>("/api/telemetry/hourly?hours=24"),
      ]);
      setRecent(recentRes.data);
      setHourly(hourlyRes.data);
      setLiveError(null);
      setLastUpdate(new Date());
    } catch (e: any) {
      setLiveError(e.message);
    }
  }

  async function loadTable() {
    setTableLoading(true);
    try {
      const qs = buildQueryString(applied);
      const params = qs ? `${qs}&` : "";
      const r = await api.get<TelemetryListResponse>(
        `/api/telemetry?${params}limit=${PAGE_SIZE}&offset=${page * PAGE_SIZE}`,
      );
      setRows(r.data);
      setTotal(r.total);
      setTableError(null);
    } catch (e: any) {
      setTableError(e.message);
    } finally {
      setTableLoading(false);
    }
  }

  useEffect(() => {
    loadLive();
  }, []);

  useEffect(() => {
    if (!autoRefresh) return;
    const id = setInterval(loadLive, 3000);
    return () => clearInterval(id);
  }, [autoRefresh]);

  useEffect(() => {
    loadTable();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [applied, page]);

  function applyFilters(e: React.FormEvent) {
    e.preventDefault();
    setPage(0);
    setApplied(form);
  }

  function clearFilters() {
    const next = initialFilters();
    setForm(next);
    setApplied(next);
    setPage(0);
  }

  // ----- stats -----
  const stats = useMemo(() => {
    if (recent.length === 0) return null;
    const last = recent[recent.length - 1];
    let sumI = 0;
    let sumV = 0;
    let maxI = 0;
    for (const p of recent) {
      const totalI = p.rms_sct1 + p.rms_sct2;
      sumI += totalI;
      sumV += (p.rms_zmpt1 + p.rms_zmpt2) / 2;
      if (totalI > maxI) maxI = totalI;
    }
    const avgI = sumI / recent.length;
    const avgV = sumV / recent.length;
    const currentI = last.rms_sct1 + last.rms_sct2;
    return {
      currentI,
      avgI,
      maxI,
      avgV,
      pctNominal: (currentI / NOMINAL_CURRENT_FALLBACK) * 100,
      latest: last.timestamp,
    };
  }, [recent]);

  // ----- chart datasets -----
  const liveCurrentChart = useMemo(() => {
    const labels = recent.map((p) => fmtTime(p.timestamp));
    return {
      labels,
      datasets: [
        {
          label: "sct1 (A)",
          data: recent.map((p) => p.rms_sct1),
          borderColor: "rgb(59, 130, 246)",
          backgroundColor: "rgba(59, 130, 246, 0.1)",
          pointRadius: 0,
          tension: 0.3,
          borderWidth: 2,
        },
        {
          label: "sct2 (A)",
          data: recent.map((p) => p.rms_sct2),
          borderColor: "rgb(16, 185, 129)",
          backgroundColor: "rgba(16, 185, 129, 0.1)",
          pointRadius: 0,
          tension: 0.3,
          borderWidth: 2,
        },
      ],
    };
  }, [recent]);

  const liveVoltageChart = useMemo(() => {
    const labels = recent.map((p) => fmtTime(p.timestamp));
    return {
      labels,
      datasets: [
        {
          label: "zmpt1 (V)",
          data: recent.map((p) => p.rms_zmpt1),
          borderColor: "rgb(168, 85, 247)",
          backgroundColor: "rgba(168, 85, 247, 0.1)",
          pointRadius: 0,
          tension: 0.3,
          borderWidth: 2,
        },
        {
          label: "zmpt2 (V)",
          data: recent.map((p) => p.rms_zmpt2),
          borderColor: "rgb(249, 115, 22)",
          backgroundColor: "rgba(249, 115, 22, 0.1)",
          pointRadius: 0,
          tension: 0.3,
          borderWidth: 2,
        },
      ],
    };
  }, [recent]);

  const hourlyChart = useMemo(() => {
    const labels = hourly.map((p) => {
      const d = new Date(p.hour);
      return `${pad(d.getDate())}/${pad(d.getMonth() + 1)} ${pad(d.getHours())}h`;
    });
    return {
      labels,
      datasets: [
        {
          label: "Corrente total média (A)",
          data: hourly.map((p) => p.avg_sct1 + p.avg_sct2),
          borderColor: "rgb(59, 130, 246)",
          backgroundColor: "rgba(59, 130, 246, 0.2)",
          fill: true,
          tension: 0.3,
          borderWidth: 2,
          pointRadius: 2,
        },
      ],
    };
  }, [hourly]);

  const chartOpts = {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 0 } as const,
    plugins: {
      legend: { position: "top" as const, labels: { boxWidth: 12 } },
      tooltip: { mode: "index" as const, intersect: false },
    },
    interaction: { mode: "nearest" as const, axis: "x" as const, intersect: false },
    scales: {
      x: { ticks: { autoSkip: true, maxTicksLimit: 8 } },
      y: { beginAtZero: false },
    },
  };

  const exportUrl = `${API_URL}/api/telemetry/export.csv${
    buildQueryString(applied) ? "?" + buildQueryString(applied) : ""
  }`;

  const showingFrom = total === 0 ? 0 : page * PAGE_SIZE + 1;
  const showingTo = Math.min((page + 1) * PAGE_SIZE, total);
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <section className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-bold">Telemetria</h1>
        <div className="flex items-center gap-3 text-sm">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
            />
            Auto-refresh (3s)
          </label>
          {lastUpdate && (
            <span className="text-gray-500">
              atualizado {fmtTime(lastUpdate.toISOString())}
            </span>
          )}
        </div>
      </div>

      {liveError && (
        <div className="rounded border border-red-300 bg-red-50 dark:bg-red-900/30 dark:border-red-700 p-3 text-sm text-red-700 dark:text-red-300">
          {liveError}
        </div>
      )}

      {/* Stats cards */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Corrente total agora"
          value={stats ? `${stats.currentI.toFixed(2)} A` : "—"}
          hint={stats ? `% do nominal: ${stats.pctNominal.toFixed(1)}%` : ""}
        />
        <StatCard
          label="Média (últimos 120 pts)"
          value={stats ? `${stats.avgI.toFixed(2)} A` : "—"}
          hint={stats ? `Tensão média ${stats.avgV.toFixed(1)} V` : ""}
        />
        <StatCard
          label="Pico (últimos 120 pts)"
          value={stats ? `${stats.maxI.toFixed(2)} A` : "—"}
        />
        <StatCard
          label="Última leitura"
          value={stats ? fmtDateTime(stats.latest) : "—"}
        />
      </div>

      {/* Live charts */}
      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title="Corrente ao vivo (últimos 120 pts)">
          <Line data={liveCurrentChart} options={chartOpts} />
        </ChartCard>
        <ChartCard title="Tensão ao vivo (últimos 120 pts)">
          <Line data={liveVoltageChart} options={chartOpts} />
        </ChartCard>
      </div>

      {/* Hourly aggregate */}
      <ChartCard title="Corrente total média por hora (últimas 24h disponíveis)">
        <Line data={hourlyChart} options={chartOpts} />
      </ChartCard>

      {/* Filters */}
      <div className="rounded-lg border border-gray-200 dark:border-gray-800 p-4 space-y-4">
        <h2 className="font-semibold">Pesquisa e filtros</h2>
        <form onSubmit={applyFilters} className="space-y-3">
          <div className="flex flex-wrap gap-3">
            <div className="flex flex-col flex-1 min-w-[180px]">
              <label className="text-xs text-gray-500 mb-1">De</label>
              <input
                type="datetime-local"
                value={form.from}
                onChange={(e) => setForm({ ...form, from: e.target.value })}
                className="px-3 py-2 border border-gray-300 dark:border-gray-700 rounded bg-white dark:bg-gray-900"
              />
            </div>
            <div className="flex flex-col flex-1 min-w-[180px]">
              <label className="text-xs text-gray-500 mb-1">Até</label>
              <input
                type="datetime-local"
                value={form.to}
                onChange={(e) => setForm({ ...form, to: e.target.value })}
                className="px-3 py-2 border border-gray-300 dark:border-gray-700 rounded bg-white dark:bg-gray-900"
              />
            </div>
            <div className="flex flex-col flex-1 min-w-[200px]">
              <label className="text-xs text-gray-500 mb-1">Campo</label>
              <select
                value={form.field}
                onChange={(e) =>
                  setForm({ ...form, field: e.target.value as FilterField })
                }
                className="px-3 py-2 border border-gray-300 dark:border-gray-700 rounded bg-white dark:bg-gray-900"
              >
                <option value="">(sem filtro de valor)</option>
                {Object.entries(FIELD_LABELS).map(([k, label]) => (
                  <option key={k} value={k}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col flex-1 min-w-[170px]">
              <label className="text-xs text-gray-500 mb-1">Comparação</label>
              <select
                value={form.op}
                onChange={(e) =>
                  setForm({ ...form, op: e.target.value as FilterOp })
                }
                disabled={!form.field}
                className="px-3 py-2 border border-gray-300 dark:border-gray-700 rounded bg-white dark:bg-gray-900 disabled:opacity-40"
              >
                <option value="">—</option>
                {Object.entries(OP_LABELS).map(([k, label]) => (
                  <option key={k} value={k}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col flex-1 min-w-[120px]">
              <label className="text-xs text-gray-500 mb-1">Valor</label>
              <input
                type="number"
                step="0.001"
                value={form.value}
                disabled={!form.field}
                onChange={(e) => setForm({ ...form, value: e.target.value })}
                className="px-3 py-2 border border-gray-300 dark:border-gray-700 rounded bg-white dark:bg-gray-900 disabled:opacity-40"
              />
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="submit"
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
            >
              Aplicar
            </button>
            <button
              type="button"
              onClick={clearFilters}
              className="px-4 py-2 border border-gray-300 dark:border-gray-700 rounded hover:bg-gray-50 dark:hover:bg-gray-800"
            >
              Limpar
            </button>
            <a
              href={exportUrl}
              download="telemetria.csv"
              className="px-4 py-2 border border-emerald-500 text-emerald-700 dark:text-emerald-400 rounded hover:bg-emerald-50 dark:hover:bg-emerald-900/30"
            >
              Exportar CSV ({total.toLocaleString()} linhas)
            </a>
          </div>
        </form>

        {tableError && (
          <div className="rounded border border-red-300 bg-red-50 dark:bg-red-900/30 dark:border-red-700 p-3 text-sm text-red-700 dark:text-red-300">
            {tableError}
          </div>
        )}

        <div className="overflow-x-auto rounded border border-gray-200 dark:border-gray-800">
          <table className="w-full text-left text-sm">
            <thead className="bg-gray-50 dark:bg-gray-900">
              <tr>
                <th className="px-3 py-2">Quando</th>
                <th className="px-3 py-2 text-right">Corrente fase 1 (A)</th>
                <th className="px-3 py-2 text-right">Corrente fase 2 (A)</th>
                <th className="px-3 py-2 text-right">Tensão fase 1 (V)</th>
                <th className="px-3 py-2 text-right">Tensão fase 2 (V)</th>
              </tr>
            </thead>
            <tbody>
              {tableLoading && (
                <tr>
                  <td colSpan={5} className="px-3 py-3 text-gray-500">
                    Carregando...
                  </td>
                </tr>
              )}
              {!tableLoading && rows.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-3 py-3 text-gray-500">
                    Nenhum ponto na janela/filtro selecionados.
                  </td>
                </tr>
              )}
              {rows.map((p) => (
                <tr
                  key={p.timestamp}
                  className="border-t border-gray-200 dark:border-gray-800"
                >
                  <td className="px-3 py-2 whitespace-nowrap font-mono text-xs">
                    {fmtDateTime(p.timestamp)}
                  </td>
                  <td className="px-3 py-2 text-right">{p.rms_sct1.toFixed(3)}</td>
                  <td className="px-3 py-2 text-right">{p.rms_sct2.toFixed(3)}</td>
                  <td className="px-3 py-2 text-right">{p.rms_zmpt1.toFixed(3)}</td>
                  <td className="px-3 py-2 text-right">{p.rms_zmpt2.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
          <div className="text-gray-600 dark:text-gray-400">
            {total > 0
              ? `Mostrando ${showingFrom.toLocaleString()}–${showingTo.toLocaleString()} de ${total.toLocaleString()}`
              : "0 resultados"}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="px-3 py-1 border border-gray-300 dark:border-gray-700 rounded disabled:opacity-40 hover:bg-gray-50 dark:hover:bg-gray-800"
            >
              ← Anterior
            </button>
            <span className="text-gray-500">
              Página {page + 1} / {totalPages.toLocaleString()}
            </span>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={page >= totalPages - 1}
              className="px-3 py-1 border border-gray-300 dark:border-gray-700 rounded disabled:opacity-40 hover:bg-gray-50 dark:hover:bg-gray-800"
            >
              Próxima →
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}

function StatCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="rounded-lg border border-gray-200 dark:border-gray-800 p-4">
      <div className="text-xs uppercase tracking-wider text-gray-500">{label}</div>
      <div className="mt-1 text-xl font-semibold">{value}</div>
      {hint && <div className="text-xs text-gray-500 mt-1">{hint}</div>}
    </div>
  );
}

function ChartCard({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-gray-200 dark:border-gray-800 p-4">
      <div className="text-sm font-semibold mb-2">{title}</div>
      <div className="h-64">{children}</div>
    </div>
  );
}
