# Energy Monitor

MVP de monitoramento de energia com identificação de risco de queda de disjuntor e
load shedding via MQTT. Um ESP medidor coleta correntes (SCT) e tensões (ZMPT) da
rede elétrica e publica para o backend; quando a corrente se aproxima do limite
nominal do disjuntor, o backend envia comandos de desligamento para ESPs de cargas
de menor prioridade.

## Componentes

- `backend/` — Flask + paho-mqtt + SQLAlchemy. Ingestão MQTT, API HTTP, motor de
  detecção e shedding (em construção).
- `frontend/` — React Router 7 + Tailwind 4. Dashboard.
- `ai/cost-predictor/` — notebooks de previsão de consumo (trilha separada).
- `infra/mosquitto/` — config e dados persistentes do broker.
- `docker-compose.yml` — broker Mosquitto + TimescaleDB.

## Pré-requisitos

- Docker e Docker Compose
- Python 3.11+

## Setup

### 1. Subir broker e banco

```bash
docker compose up -d
```

### 2. Variáveis de ambiente do backend

Crie um `.env` em `backend/`:

```
DATABASE_URL=postgresql+psycopg2://postgres:senha123@localhost:6432/postgres
HOST=0.0.0.0
PORT=8000
DEBUG=True
```

### 3. Venv, dependências, migrações e seed

```bash
cd backend
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python3 migrate.py
python3 seed.py
```

### 4. Rodar o backend

Com a venv ativa:

```bash
python3 app.py
```

Em sessões futuras, basta `source backend/venv/bin/activate` antes de rodar
qualquer script (`migrate.py`, `seed.py`, `app.py`).

### 5. Frontend

```bash
cd frontend
npm install
npm run dev
```

Dashboard em `http://localhost:5173` com as telas de cadastro (dispositivos,
prioridades, limites e parâmetros). A URL do backend é configurável via
`VITE_API_URL` em `frontend/.env` (default: `http://localhost:8000`).

## Banco de dados

Migrações em [backend/infra/database/sql/migrations/](backend/infra/database/sql/migrations/),
aplicadas em ordem alfabética pelo runner e controladas pela tabela `schema_migration`.

| Tabela | Função |
|---|---|
| `breaker` | Telemetria do ESP medidor — hypertable Timescale, particionada por `breaker_id` |
| `priority_level` | Níveis de prioridade. `rank` maior = mais prioritário (religa antes, desliga por último) |
| `device` | Cadastro de cargas. `device_id` é manual (ex. MAC do ESP) |
| `device_state` | Estado atual da carga (`on`/`off`/`unknown`), origem (`auto`/`manual`) e `last_seen` |
| `safety_limit` | Por disjuntor: corrente nominal e limiares de shedding/restore (%) |
| `parameter` | Pares chave/valor para parâmetros runtime |
| `event` | Log dos eventos do mecanismo (shedding, restore, alertas, offline, etc.) |
| `schema_migration` | Controle interno do runner |

### Parâmetros default (seed)

| Chave | Valor | Descrição |
|---|---|---|
| `heartbeat_interval_s` | 30 | Intervalo entre pings do backend aos ESPs de carga |
| `heartbeat_timeout_s` | 90 | Tempo sem resposta para considerar uma carga offline |
| `cache_refresh_s` | 300 | Refresh do cache de parâmetros/limites/prioridades |
| `restore_guard_time_s` | 30 | Intervalo mínimo entre religamentos automáticos |
| `shed_duration_s` | 5 | Tempo acima do limiar antes de disparar desligamento |

Limite padrão semeado para `breaker_id=1`: 20 A nominal, shedding a 90%, restore a 70%.

### Scripts

- `backend/migrate.py` — aplica migrações pendentes em ordem. Reentrada segura.
- `backend/seed.py` — seed completo de desenvolvimento: prioridades (Baixa/Média/Alta),
  limite default do disjuntor 1, parâmetros runtime **e** ~1.7M pontos de telemetria
  simulada em `breaker` (20 dias × 1 ponto/s) via `COPY`, em ~30-60s. A geração da
  telemetria só roda se a tabela estiver vazia para `breaker_id='1'` na janela de
  20 dias; para regerar, `TRUNCATE breaker;` manualmente antes. Reentrada segura.
- `backend/initparam.py` — seed enxuto para produção: apenas `priority_level`,
  `safety_limit` e `parameter`. Sem dispositivos nem telemetria. Idempotente.
- `backend/truncateall.py` — apaga todos os dados (event, breaker, device_state,
  device, safety_limit, priority_level, parameter) com `TRUNCATE ... RESTART
  IDENTITY CASCADE`. Preserva `schema_migration`. **Destrutivo e irreversível.**

O arquivo legado [backend/infra/database/sql/monitor.sql](backend/infra/database/sql/monitor.sql)
fica preservado como referência da modelagem inicial — o runner usa apenas
`migrations/`.

## API HTTP

Base: `http://localhost:8000` (configurável via `HOST`/`PORT`).

| Recurso | Endpoints |
|---|---|
| Prioridades | `GET/POST /api/priorities`, `PUT/DELETE /api/priorities/<id>` |
| Dispositivos | `GET/POST /api/devices`, `PUT/DELETE /api/devices/<id>`, `POST /api/devices/<id>/cmd` (manual on/off) |
| Limites | `GET/POST /api/safety-limits`, `PUT/DELETE /api/safety-limits/<id>` |
| Parâmetros | `GET /api/parameters`, `PUT /api/parameters/<key>` |
| Eventos | `GET /api/events?limit=&since=&type=&device_id=` |
| Telemetria (filtrável) | `GET /api/telemetry?from=&to=&field=&op=&value=&limit=&offset=&breaker_id=`, `GET /api/telemetry/recent?n=&breaker_id=`, `GET /api/telemetry/hourly?hours=&breaker_id=`, `GET /api/telemetry/export.csv?<mesmos_filtros>` (streaming) |
| Telemetria (legado) | `GET /api/initial-data`, `GET /api/data/<breaker_id>?group=24h|7d|30d|3m|6m|1y|2y|at`, SSE `GET /api/stream` |

**Filtros de `/api/telemetry`:** `field ∈ {rms_sct1, rms_sct2, rms_zmpt1, rms_zmpt2}`,
`op ∈ {eq, lt, lte, gt, gte}` — apenas uma comparação por vez. `from`/`to` em ISO 8601.
A página `/telemetry` no front gera URL para `/api/telemetry/export.csv` repetindo
os filtros aplicados; a resposta é em streaming, sem limite artificial de linhas.

Respostas seguem `{"data": ...}` em sucesso e `{"error": "..."}` em falha.
Writes nos endpoints de prioridades, limites e parâmetros disparam refresh
imediato do cache em memória ([backend/services/config_cache.py](backend/services/config_cache.py)),
que também recarrega periodicamente em thread daemon (intervalo controlado
pelo parâmetro `cache_refresh_s`).

## MQTT

| Direção | Tópico | Payload |
|---|---|---|
| ESP medidor → backend | `teste/esp` | binário `<Iffff` (uint32 ts + 4 floats: sct1, sct2, zmpt1, zmpt2) |
| Backend → ESP carga | `cargas/<device_id>/cmd` | JSON `{action, reason, req_id}` |
| ESP carga → backend | `cargas/<device_id>/state` | JSON `{state, source, req_id?, ts}` |
| ESP carga → backend | `cargas/<device_id>/hello` | JSON `{device_id, fw, state, ts}` |
| Backend → ESP carga | `cargas/<device_id>/ping` | JSON `{req_id, ts}` |
| ESP carga → backend | `cargas/<device_id>/pong` | JSON `{req_id, state, ts}` |

`device_id` é o identificador único da carga (recomendado: MAC do ESP).
`source=auto` indica desligamento/religamento causado pelo sistema; `source=manual`
cobre o usuário no botão físico ou perda de contato (sem resposta a pings).

**Convenção de `reason` no cmd**: o backend envia `reason="manual"` para comandos
originados no dashboard, `reason="load_shedding"` para desligamento automático
e `reason="restore"` para religamento. Cabe ao firmware da carga responder com
`source="auto"` quando o reason for `load_shedding`/`restore` e `source="manual"`
caso contrário — assim o religamento automático só toca em cargas que ele
próprio desligou.

### Supervisor de cargas

Thread daemon ([backend/services/device_supervisor.py](backend/services/device_supervisor.py))
roda a cada `heartbeat_interval_s`:

1. Publica `ping` em todos os dispositivos cadastrados.
2. Marca como `state=off, source=manual` qualquer dispositivo cujo `last_seen`
   esteja mais antigo que `heartbeat_timeout_s`, registrando evento `device_offline`.

Dispositivos sem nenhum `last_seen` (nunca contataram o backend) permanecem
`state=unknown` indefinidamente — não são marcados offline.

### Simulador local (`mock_device.py`)

Útil para testar o fluxo sem ESPs reais. Cadastre primeiro o dispositivo no
dashboard com o mesmo `device_id`, depois rode:

```bash
cd backend
source venv/bin/activate
python3 scripts/mock_device.py AA:BB:CC:DD:EE:01 on
```

O script publica `hello`, responde a `ping` com `pong` e a `cmd` com `state`,
inferindo `source` a partir do `reason` recebido.

### Autenticação MQTT (opcional)

Broker hoje aceita conexões anônimas. Para gerar o arquivo de senha:

```bash
docker run --rm -it -v "$(pwd)/infra/mosquitto/config:/mosquitto/config" \
  eclipse-mosquitto mosquitto_passwd -c /mosquitto/config/pwfile iotuser
```

Em seguida, descomente as linhas `allow_anonymous false` e `password_file` em
[infra/mosquitto/config/mosquitto.conf](infra/mosquitto/config/mosquitto.conf).
