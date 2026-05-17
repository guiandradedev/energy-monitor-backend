import { useEffect, useState } from "react";
import { api, type Device, type Priority } from "~/lib/api";

const STATE_BADGE: Record<Device["state"]["state"], string> = {
  on: "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300",
  off: "bg-gray-200 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
  unknown:
    "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300",
};

export default function DevicesPage() {
  const [items, setItems] = useState<Device[]>([]);
  const [priorities, setPriorities] = useState<Priority[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [newDeviceId, setNewDeviceId] = useState("");
  const [newName, setNewName] = useState("");
  const [newPriorityId, setNewPriorityId] = useState<string>("");

  const [editingId, setEditingId] = useState<number | null>(null);
  const [editName, setEditName] = useState("");
  const [editPriorityId, setEditPriorityId] = useState<string>("");

  async function load() {
    setLoading(true);
    try {
      const [devicesRes, prioritiesRes] = await Promise.all([
        api.get<{ data: Device[] }>("/api/devices"),
        api.get<{ data: Priority[] }>("/api/priorities"),
      ]);
      setItems(devicesRes.data);
      setPriorities(prioritiesRes.data);
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
      await api.post("/api/devices", {
        device_id: newDeviceId.trim(),
        name: newName.trim(),
        priority_id: parseInt(newPriorityId, 10),
      });
      setNewDeviceId("");
      setNewName("");
      setNewPriorityId("");
      await load();
    } catch (e: any) {
      setError(e.message);
    }
  }

  function startEdit(d: Device) {
    setEditingId(d.id);
    setEditName(d.name);
    setEditPriorityId(String(d.priority.id));
  }

  async function saveEdit(id: number) {
    try {
      await api.put(`/api/devices/${id}`, {
        name: editName.trim(),
        priority_id: parseInt(editPriorityId, 10),
      });
      setEditingId(null);
      await load();
    } catch (e: any) {
      setError(e.message);
    }
  }

  async function remove(id: number) {
    if (!confirm("Excluir este dispositivo?")) return;
    try {
      await api.del(`/api/devices/${id}`);
      await load();
    } catch (e: any) {
      setError(e.message);
    }
  }

  async function sendCmd(id: number, action: "on" | "off") {
    try {
      await api.post(`/api/devices/${id}/cmd`, { action });
      // ACK chega via MQTT em ~ms; refresh em 1s pega o novo state.
      setTimeout(load, 1000);
    } catch (e: any) {
      setError(e.message);
    }
  }

  return (
    <section className="space-y-6">
      <h1 className="text-2xl font-bold">Dispositivos</h1>
      <p className="text-sm text-gray-600 dark:text-gray-300">
        Cadastro manual. <code>device_id</code> é o identificador único da
        carga (recomendado: MAC do ESP).
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
          <label className="text-xs text-gray-500 mb-1">device_id (MAC)</label>
          <input
            type="text"
            value={newDeviceId}
            onChange={(e) => setNewDeviceId(e.target.value)}
            required
            placeholder="AA:BB:CC:DD:EE:FF"
            className="px-3 py-2 border border-gray-300 dark:border-gray-700 rounded bg-white dark:bg-gray-900 font-mono text-sm"
          />
        </div>
        <div className="flex flex-col">
          <label className="text-xs text-gray-500 mb-1">Nome</label>
          <input
            type="text"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            required
            className="px-3 py-2 border border-gray-300 dark:border-gray-700 rounded bg-white dark:bg-gray-900"
          />
        </div>
        <div className="flex flex-col">
          <label className="text-xs text-gray-500 mb-1">Prioridade</label>
          <select
            value={newPriorityId}
            onChange={(e) => setNewPriorityId(e.target.value)}
            required
            className="px-3 py-2 border border-gray-300 dark:border-gray-700 rounded bg-white dark:bg-gray-900"
          >
            <option value="">Selecionar...</option>
            {priorities.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label} (rank {p.rank})
              </option>
            ))}
          </select>
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
              <th className="px-4 py-2">device_id</th>
              <th className="px-4 py-2">Nome</th>
              <th className="px-4 py-2">Prioridade</th>
              <th className="px-4 py-2">Estado</th>
              <th className="px-4 py-2">Último contato</th>
              <th className="px-4 py-2 text-right">Ações</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={6} className="px-4 py-3 text-gray-500">
                  Carregando...
                </td>
              </tr>
            )}
            {!loading && items.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-3 text-gray-500">
                  Nenhum dispositivo cadastrado.
                </td>
              </tr>
            )}
            {items.map((d) => (
              <tr key={d.id} className="border-t border-gray-200 dark:border-gray-800">
                <td className="px-4 py-2 font-mono text-xs">{d.device_id}</td>
                {editingId === d.id ? (
                  <>
                    <td className="px-4 py-2">
                      <input
                        type="text"
                        value={editName}
                        onChange={(e) => setEditName(e.target.value)}
                        className="px-2 py-1 border border-gray-300 dark:border-gray-700 rounded bg-white dark:bg-gray-900 w-full"
                      />
                    </td>
                    <td className="px-4 py-2">
                      <select
                        value={editPriorityId}
                        onChange={(e) => setEditPriorityId(e.target.value)}
                        className="px-2 py-1 border border-gray-300 dark:border-gray-700 rounded bg-white dark:bg-gray-900"
                      >
                        {priorities.map((p) => (
                          <option key={p.id} value={p.id}>
                            {p.label}
                          </option>
                        ))}
                      </select>
                    </td>
                  </>
                ) : (
                  <>
                    <td className="px-4 py-2">{d.name}</td>
                    <td className="px-4 py-2">
                      {d.priority.label}{" "}
                      <span className="text-gray-400 text-xs">
                        (rank {d.priority.rank})
                      </span>
                    </td>
                  </>
                )}
                <td className="px-4 py-2">
                  <span
                    className={`px-2 py-0.5 rounded text-xs font-medium ${
                      STATE_BADGE[d.state.state]
                    }`}
                  >
                    {d.state.state}
                  </span>
                  <span className="text-gray-400 text-xs ml-1">
                    ({d.state.source})
                  </span>
                </td>
                <td className="px-4 py-2 text-xs text-gray-500">
                  {d.state.last_seen
                    ? new Date(d.state.last_seen).toLocaleString()
                    : "—"}
                </td>
                <td className="px-4 py-2 text-right space-x-3">
                  {editingId === d.id ? (
                    <>
                      <button
                        onClick={() => saveEdit(d.id)}
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
                    </>
                  ) : (
                    <>
                      <button
                        onClick={() => sendCmd(d.id, "on")}
                        disabled={d.state.state === "on"}
                        className="text-green-700 dark:text-green-400 hover:underline disabled:opacity-40 disabled:no-underline"
                      >
                        Ligar
                      </button>
                      <button
                        onClick={() => sendCmd(d.id, "off")}
                        disabled={d.state.state === "off"}
                        className="text-orange-700 dark:text-orange-400 hover:underline disabled:opacity-40 disabled:no-underline"
                      >
                        Desligar
                      </button>
                      <button
                        onClick={() => startEdit(d)}
                        className="text-blue-600 hover:underline"
                      >
                        Editar
                      </button>
                      <button
                        onClick={() => remove(d.id)}
                        className="text-red-600 hover:underline"
                      >
                        Excluir
                      </button>
                    </>
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
