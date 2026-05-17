import { Link } from "react-router";

const SECTIONS = [
  {
    to: "/devices",
    title: "Dispositivos",
    desc: "Cadastro de cargas (ESPs) com prioridade associada.",
  },
  {
    to: "/priorities",
    title: "Prioridades",
    desc: "Níveis de prioridade. Rank maior religa primeiro.",
  },
  {
    to: "/safety-limits",
    title: "Limites de segurança",
    desc: "Corrente nominal e limiares (%) de shedding e restore por disjuntor.",
  },
  {
    to: "/parameters",
    title: "Parâmetros",
    desc: "Heartbeat, cooldown, refresh de cache e demais ajustes runtime.",
  },
];

export default function HomePage() {
  return (
    <section className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Energy Monitor</h1>
        <p className="text-gray-600 dark:text-gray-300 mt-1">
          Configure cargas, limites e parâmetros do sistema.
        </p>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        {SECTIONS.map((s) => (
          <Link
            key={s.to}
            to={s.to}
            className="block rounded-lg border border-gray-200 dark:border-gray-800 p-4 hover:border-blue-500 dark:hover:border-blue-400 transition"
          >
            <h2 className="font-semibold">{s.title}</h2>
            <p className="text-sm text-gray-600 dark:text-gray-300 mt-1">{s.desc}</p>
          </Link>
        ))}
      </div>
    </section>
  );
}
