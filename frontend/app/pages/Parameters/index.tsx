import { useEffect, useState } from "react";
import { api, type Parameter } from "~/lib/api";

export default function ParametersPage() {
  const [items, setItems] = useState<Parameter[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");

  async function load() {
    setLoading(true);
    try {
      const r = await api.get<{ data: Parameter[] }>("/api/parameters");
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

  function startEdit(p: Parameter) {
    setEditingKey(p.key);
    setEditValue(p.value);
  }

  async function saveEdit(key: string) {
    try {
      await api.put(`/api/parameters/${encodeURIComponent(key)}`, {
        value: editValue.trim(),
      });
      setEditingKey(null);
      await load();
    } catch (e: any) {
      setError(e.message);
    }
  }

  return (
    <section className="space-y-6">
      <h1 className="text-2xl font-bold">Parâmetros</h1>
      <p className="text-sm text-gray-600 dark:text-gray-300">
        Ajustes runtime do sistema. Mudanças entram em vigor imediatamente
        (cache invalidado na escrita).
      </p>

      {error && (
        <div className="rounded border border-red-300 bg-red-50 dark:bg-red-900/30 dark:border-red-700 p-3 text-sm text-red-700 dark:text-red-300">
          {error}
        </div>
      )}

      <div className="rounded-lg border border-gray-200 dark:border-gray-800 overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="bg-gray-50 dark:bg-gray-900">
            <tr>
              <th className="px-4 py-2">Chave</th>
              <th className="px-4 py-2">Descrição</th>
              <th className="px-4 py-2">Valor</th>
              <th className="px-4 py-2">Atualizado em</th>
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
                  Nenhum parâmetro cadastrado.
                </td>
              </tr>
            )}
            {items.map((p) => (
              <tr key={p.key} className="border-t border-gray-200 dark:border-gray-800">
                <td className="px-4 py-2 font-mono text-xs">{p.key}</td>
                <td className="px-4 py-2 text-gray-600 dark:text-gray-400">
                  {p.description || "—"}
                </td>
                <td className="px-4 py-2">
                  {editingKey === p.key ? (
                    <input
                      type="text"
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                      className="px-2 py-1 border border-gray-300 dark:border-gray-700 rounded bg-white dark:bg-gray-900 w-32"
                    />
                  ) : (
                    <span className="font-mono">{p.value}</span>
                  )}
                </td>
                <td className="px-4 py-2 text-xs text-gray-500">
                  {new Date(p.updated_at).toLocaleString()}
                </td>
                <td className="px-4 py-2 text-right space-x-3">
                  {editingKey === p.key ? (
                    <>
                      <button
                        onClick={() => saveEdit(p.key)}
                        className="text-blue-600 hover:underline"
                      >
                        Salvar
                      </button>
                      <button
                        onClick={() => setEditingKey(null)}
                        className="text-gray-500 hover:underline"
                      >
                        Cancelar
                      </button>
                    </>
                  ) : (
                    <button
                      onClick={() => startEdit(p)}
                      className="text-blue-600 hover:underline"
                    >
                      Editar
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
