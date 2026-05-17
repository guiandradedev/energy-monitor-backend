import { useEffect, useState } from "react";
import { api, type Priority } from "~/lib/api";

export default function PrioritiesPage() {
  const [items, setItems] = useState<Priority[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const [newLabel, setNewLabel] = useState("");
  const [newRank, setNewRank] = useState("");

  const [editingId, setEditingId] = useState<number | null>(null);
  const [editLabel, setEditLabel] = useState("");
  const [editRank, setEditRank] = useState("");

  async function load() {
    setLoading(true);
    try {
      const r = await api.get<{ data: Priority[] }>("/api/priorities");
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

  async function create(e: React.FormEvent) {
    e.preventDefault();
    try {
      await api.post("/api/priorities", {
        label: newLabel.trim(),
        rank: parseInt(newRank, 10),
      });
      setNewLabel("");
      setNewRank("");
      await load();
    } catch (e: any) {
      setError(e.message);
    }
  }

  function startEdit(p: Priority) {
    setEditingId(p.id);
    setEditLabel(p.label);
    setEditRank(String(p.rank));
  }

  async function saveEdit(id: number) {
    try {
      await api.put(`/api/priorities/${id}`, {
        label: editLabel.trim(),
        rank: parseInt(editRank, 10),
      });
      setEditingId(null);
      await load();
    } catch (e: any) {
      setError(e.message);
    }
  }

  async function remove(id: number) {
    if (!confirm("Excluir esta prioridade?")) return;
    try {
      await api.del(`/api/priorities/${id}`);
      await load();
    } catch (e: any) {
      setError(e.message);
    }
  }

  return (
    <section className="space-y-6">
      <h1 className="text-2xl font-bold">Prioridades</h1>
      <p className="text-sm text-gray-600 dark:text-gray-300">
        Rank maior = mais prioritário. Religa antes, desliga por último.
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
          <label className="text-xs text-gray-500 mb-1">Label</label>
          <input
            type="text"
            value={newLabel}
            onChange={(e) => setNewLabel(e.target.value)}
            required
            className="px-3 py-2 border border-gray-300 dark:border-gray-700 rounded bg-white dark:bg-gray-900"
          />
        </div>
        <div className="flex flex-col">
          <label className="text-xs text-gray-500 mb-1">Rank</label>
          <input
            type="number"
            value={newRank}
            onChange={(e) => setNewRank(e.target.value)}
            min={1}
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
              <th className="px-4 py-2">Label</th>
              <th className="px-4 py-2">Rank</th>
              <th className="px-4 py-2 text-right">Ações</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={3} className="px-4 py-3 text-gray-500">
                  Carregando...
                </td>
              </tr>
            )}
            {!loading && items.length === 0 && (
              <tr>
                <td colSpan={3} className="px-4 py-3 text-gray-500">
                  Nenhuma prioridade cadastrada.
                </td>
              </tr>
            )}
            {items.map((p) => (
              <tr key={p.id} className="border-t border-gray-200 dark:border-gray-800">
                {editingId === p.id ? (
                  <>
                    <td className="px-4 py-2">
                      <input
                        type="text"
                        value={editLabel}
                        onChange={(e) => setEditLabel(e.target.value)}
                        className="px-2 py-1 border border-gray-300 dark:border-gray-700 rounded bg-white dark:bg-gray-900 w-full"
                      />
                    </td>
                    <td className="px-4 py-2">
                      <input
                        type="number"
                        value={editRank}
                        onChange={(e) => setEditRank(e.target.value)}
                        min={1}
                        className="px-2 py-1 border border-gray-300 dark:border-gray-700 rounded bg-white dark:bg-gray-900 w-24"
                      />
                    </td>
                    <td className="px-4 py-2 text-right space-x-3">
                      <button
                        onClick={() => saveEdit(p.id)}
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
                    <td className="px-4 py-2">{p.label}</td>
                    <td className="px-4 py-2">{p.rank}</td>
                    <td className="px-4 py-2 text-right space-x-3">
                      <button
                        onClick={() => startEdit(p)}
                        className="text-blue-600 hover:underline"
                      >
                        Editar
                      </button>
                      <button
                        onClick={() => remove(p.id)}
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
