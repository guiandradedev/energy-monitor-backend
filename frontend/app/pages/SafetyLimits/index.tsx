import { useEffect, useState } from "react";
import { api, type SafetyLimit } from "~/lib/api";

type Draft = {
  breaker_id: string;
  nominal_current_a: string;
  shed_threshold_pct: string;
  restore_threshold_pct: string;
};

const EMPTY: Draft = {
  breaker_id: "",
  nominal_current_a: "",
  shed_threshold_pct: "",
  restore_threshold_pct: "",
};

export default function SafetyLimitsPage() {
  const [items, setItems] = useState<SafetyLimit[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [draft, setDraft] = useState<Draft>(EMPTY);

  const [editingId, setEditingId] = useState<number | null>(null);
  const [editDraft, setEditDraft] = useState<Draft>(EMPTY);

  async function load() {
    setLoading(true);
    try {
      const r = await api.get<{ data: SafetyLimit[] }>("/api/safety-limits");
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
  }, []);

  function toPayload(d: Draft) {
    return {
      breaker_id: d.breaker_id.trim(),
      nominal_current_a: parseFloat(d.nominal_current_a),
      shed_threshold_pct: parseFloat(d.shed_threshold_pct),
      restore_threshold_pct: parseFloat(d.restore_threshold_pct),
    };
  }

  async function create(e: React.FormEvent) {
    e.preventDefault();
    try {
      await api.post("/api/safety-limits", toPayload(draft));
      setDraft(EMPTY);
      await load();
    } catch (e: any) {
      setError(e.message);
    }
  }

  function startEdit(s: SafetyLimit) {
    setEditingId(s.id);
    setEditDraft({
      breaker_id: s.breaker_id,
      nominal_current_a: String(s.nominal_current_a),
      shed_threshold_pct: String(s.shed_threshold_pct),
      restore_threshold_pct: String(s.restore_threshold_pct),
    });
  }

  async function saveEdit(id: number) {
    try {
      await api.put(`/api/safety-limits/${id}`, toPayload(editDraft));
      setEditingId(null);
      await load();
    } catch (e: any) {
      setError(e.message);
    }
  }

  async function remove(id: number) {
    if (!confirm("Excluir este limite?")) return;
    try {
      await api.del(`/api/safety-limits/${id}`);
      await load();
    } catch (e: any) {
      setError(e.message);
    }
  }

  const numInput =
    "px-2 py-1 border border-gray-300 dark:border-gray-700 rounded bg-white dark:bg-gray-900 w-24";
  const txtInput =
    "px-2 py-1 border border-gray-300 dark:border-gray-700 rounded bg-white dark:bg-gray-900 w-24";

  return (
    <section className="space-y-6">
      <h1 className="text-2xl font-bold">Limites de segurança</h1>
      <p className="text-sm text-gray-600 dark:text-gray-300">
        Corrente nominal por disjuntor e os limiares (%) para disparar shedding
        e religamento. Restore deve ser menor que shed.
      </p>

      {error && (
        <div className="rounded border border-red-300 bg-red-50 dark:bg-red-900/30 dark:border-red-700 p-3 text-sm text-red-700 dark:text-red-300">
          {error}
        </div>
      )}

      <form
        onSubmit={create}
        className="flex flex-wrap items-end gap-3 rounded-lg border border-gray-200 dark:border-gray-800 p-4"
      >
        <div className="flex flex-col">
          <label className="text-xs text-gray-500 mb-1">breaker_id</label>
          <input
            type="text"
            value={draft.breaker_id}
            onChange={(e) => setDraft({ ...draft, breaker_id: e.target.value })}
            required
            className="px-3 py-2 border border-gray-300 dark:border-gray-700 rounded bg-white dark:bg-gray-900 w-32"
          />
        </div>
        <div className="flex flex-col">
          <label className="text-xs text-gray-500 mb-1">Nominal (A)</label>
          <input
            type="number"
            step="0.1"
            min="0.1"
            value={draft.nominal_current_a}
            onChange={(e) =>
              setDraft({ ...draft, nominal_current_a: e.target.value })
            }
            required
            className="px-3 py-2 border border-gray-300 dark:border-gray-700 rounded bg-white dark:bg-gray-900 w-28"
          />
        </div>
        <div className="flex flex-col">
          <label className="text-xs text-gray-500 mb-1">Shed (%)</label>
          <input
            type="number"
            step="0.1"
            min="0.1"
            max="100"
            value={draft.shed_threshold_pct}
            onChange={(e) =>
              setDraft({ ...draft, shed_threshold_pct: e.target.value })
            }
            required
            className="px-3 py-2 border border-gray-300 dark:border-gray-700 rounded bg-white dark:bg-gray-900 w-24"
          />
        </div>
        <div className="flex flex-col">
          <label className="text-xs text-gray-500 mb-1">Restore (%)</label>
          <input
            type="number"
            step="0.1"
            min="0.1"
            max="100"
            value={draft.restore_threshold_pct}
            onChange={(e) =>
              setDraft({ ...draft, restore_threshold_pct: e.target.value })
            }
            required
            className="px-3 py-2 border border-gray-300 dark:border-gray-700 rounded bg-white dark:bg-gray-900 w-24"
          />
        </div>
        <button
          type="submit"
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          Adicionar
        </button>
      </form>

      <div className="rounded-lg border border-gray-200 dark:border-gray-800 overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="bg-gray-50 dark:bg-gray-900">
            <tr>
              <th className="px-4 py-2">breaker_id</th>
              <th className="px-4 py-2">Nominal (A)</th>
              <th className="px-4 py-2">Shed (%)</th>
              <th className="px-4 py-2">Restore (%)</th>
              <th className="px-4 py-2 text-right">Ações</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={5} className="px-4 py-3 text-gray-500">
                  Carregando...
                </td>
              </tr>
            )}
            {!loading && items.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-3 text-gray-500">
                  Nenhum limite cadastrado.
                </td>
              </tr>
            )}
            {items.map((s) => (
              <tr key={s.id} className="border-t border-gray-200 dark:border-gray-800">
                {editingId === s.id ? (
                  <>
                    <td className="px-4 py-2">
                      <input
                        type="text"
                        value={editDraft.breaker_id}
                        onChange={(e) =>
                          setEditDraft({ ...editDraft, breaker_id: e.target.value })
                        }
                        className={txtInput}
                      />
                    </td>
                    <td className="px-4 py-2">
                      <input
                        type="number"
                        step="0.1"
                        value={editDraft.nominal_current_a}
                        onChange={(e) =>
                          setEditDraft({
                            ...editDraft,
                            nominal_current_a: e.target.value,
                          })
                        }
                        className={numInput}
                      />
                    </td>
                    <td className="px-4 py-2">
                      <input
                        type="number"
                        step="0.1"
                        value={editDraft.shed_threshold_pct}
                        onChange={(e) =>
                          setEditDraft({
                            ...editDraft,
                            shed_threshold_pct: e.target.value,
                          })
                        }
                        className={numInput}
                      />
                    </td>
                    <td className="px-4 py-2">
                      <input
                        type="number"
                        step="0.1"
                        value={editDraft.restore_threshold_pct}
                        onChange={(e) =>
                          setEditDraft({
                            ...editDraft,
                            restore_threshold_pct: e.target.value,
                          })
                        }
                        className={numInput}
                      />
                    </td>
                    <td className="px-4 py-2 text-right space-x-3">
                      <button
                        onClick={() => saveEdit(s.id)}
                        className="text-blue-600 hover:underline"
                      >
                        Salvar
                      </button>
                      <button
                        onClick={() => setEditingId(null)}
                        className="text-gray-500 hover:underline"
                      >
                        Cancelar
                      </button>
                    </td>
                  </>
                ) : (
                  <>
                    <td className="px-4 py-2 font-mono text-xs">{s.breaker_id}</td>
                    <td className="px-4 py-2">{s.nominal_current_a}</td>
                    <td className="px-4 py-2">{s.shed_threshold_pct}</td>
                    <td className="px-4 py-2">{s.restore_threshold_pct}</td>
                    <td className="px-4 py-2 text-right space-x-3">
                      <button
                        onClick={() => startEdit(s)}
                        className="text-blue-600 hover:underline"
                      >
                        Editar
                      </button>
                      <button
                        onClick={() => remove(s.id)}
                        className="text-red-600 hover:underline"
                      >
                        Excluir
                      </button>
                    </td>
                  </>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
