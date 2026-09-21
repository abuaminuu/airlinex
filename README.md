# Airlinex — Monitoring & Observability

This document describes the observability stack for the Airlinex project: how metrics
are collected, stored, and visualized, and how to run the whole thing locally.

## Overview

The stack has four moving parts:

| Component            | Role                                                        | Port  |
|----------------------|-------------------------------------------------------------|-------|
| Django + Prometheus  | Exposes application metrics at `/metrics`                    | 8000  |
| PostgreSQL           | Stores application data                                      | 5432  |
| Postgres Exporter    | Bridges database metrics into Prometheus format              | 9187  |
| Prometheus           | Scrapes and stores time-series metrics                       | 9090  |
| Grafana              | Queries Prometheus and renders dashboards                    | 3000  |

Data flows in one direction: services expose metrics → Prometheus scrapes them →
Grafana queries Prometheus → you see charts.

## Why Observability Matters

Without monitoring, you find out something is broken when a user tells you.
With it, you find out before they notice. Metrics answer three questions:

- **Is the app healthy?** (error rate, response time, request volume)
- **Is the database healthy?** (connections, cache hits, slow queries)
- **Is the infrastructure healthy?** (scrape status, target availability)

For any business running services in production, that early warning is the
difference between a five-minute fix and a five-hour outage.

## Architecture

```
┌─────────────┐         ┌───────────────┐
│  Django     │◄────────│  Prometheus   │
│  :8000      │ scrape  │  :9090        │
└─────────────┘         └───────┬───────┘
                                │ query
┌─────────────┐         ┌───────▼───────┐
│  Postgres   │◄────────│  Grafana      │
│  :5432      │ exporter│  :3000        │
└─────────────┘  :9187  └───────────────┘
```

All services run on a shared Docker Compose network (`airlinex-network`) and
communicate by service name (`web`, `db`, `prometheus`, `grafana`).

## Getting Started

### Prerequisites

- Docker Engine 24+ (native, not Docker Desktop)
- Docker Compose v2.20+
- 4 GB free RAM

### Start the Stack

```bash
docker compose up -d
docker compose ps
```

You should see five containers: `web`, `db`, `prometheus`, `postgres-exporter`,
and `grafana`.

### Apply Migrations

```bash
docker compose exec web python3 manage.py migrate
```

### Verify It's Working

```bash
# Django is serving metrics
curl -s http://localhost:8000/metrics | head -5

# Prometheus has both targets up
curl -s http://localhost:9090/api/v1/targets \
  | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'

# Grafana is reachable
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000/login
```

Expected results: `200` from Django, both targets `"up"`, and `200` from Grafana.

## Accessing the Dashboards

| Service    | URL                          | Credentials       |
|------------|------------------------------|-------------------|
| Django     | http://localhost:8000        | —                 |
| Prometheus | http://localhost:9090        | —                 |
| Grafana    | http://localhost:3000        | admin / admin     |

> **Important:** The URL `http://prometheus:9090` only works *inside* the Docker
> network (for example, when configuring Grafana's datasource). From your
> browser or host machine, always use `http://localhost:9090`.

## Grafana Dashboards

Three dashboards are imported and available out of the box:

- **Django** — requests, responses, latency, error rates, cache and DB activity
- **Django Prometheus** — view timings, middleware overhead, model operations
- **PostgreSQL Database** — connections, transactions, cache hit ratio, locks

### Connecting Grafana to Prometheus

If the datasource isn't configured automatically, add it manually:

1. Open Grafana → **Connections → Data Sources → Add data source**
2. Choose **Prometheus**
3. Set the URL to `http://prometheus:9090`
4. Click **Save & test** — you should see a green confirmation

## Configuration Files

| File                          | Purpose                                        |
|-------------------------------|------------------------------------------------|
| `docker-compose.yml`          | Service definitions and network config         |
| `prometheus.yml`              | Scrape targets and intervals                   |
| `grafana/provisioning/`       | Datasource and dashboard auto-provisioning     |
| `airline/settings.py`         | Django settings, `django_prometheus` enabled   |
| `airline/urls.py`             | Exposes `/metrics` via `django_prometheus`     |

## Adding a New Scrape Target

1. Open `prometheus.yml`
2. Add a job under `scrape_configs`:

   ```yaml
   - job_name: 'my-service'
     metrics_path: '/metrics'
     static_configs:
       - targets: ['my-service:PORT']
   ```

3. Reload Prometheus without restarting containers:

   ```bash
   docker compose exec prometheus kill -HUP 1
   ```

4. Confirm the target appears at http://localhost:9090/targets

## Troubleshooting

### "NaN" on Dashboard Panels

Not a bug. It means the query returned no data for the current time window.
Generate traffic, wait one or two scrape intervals (15 s each), and refresh:

```bash
for i in {1..20}; do curl -s http://localhost:8000/ > /dev/null; sleep 1; done
```

### "No data" When Testing the Grafana Datasource

The URL is wrong. Use `http://prometheus:9090` (service name), not
`http://localhost:9090`. Grafana runs in a container — `localhost` there refers
to Grafana itself, not your host.

### Prometheus Target Shows "down"

Check the `lastError` field:

```bash
curl -s http://localhost:9090/api/v1/targets \
  | jq '.data.activeTargets[] | select(.health=="down") | {job: .labels.job, lastError}'
```

Common causes:

- **Stale IP** — never hardcode container IPs; use service names
- **Service not listening** — check `docker compose logs <service> --tail 30`
- **Wrong port** — verify the target port matches the service's actual port

### DNS Errors From Inside Containers

If you see `wget: bad address 'web:8000'`, ignore it — BusyBox `wget` is
notoriously misleading and reports connection failures as DNS failures. Verify
with a real tool instead:

```bash
docker compose exec prometheus nslookup web      # BusyBox, but shows the IP
curl -s http://localhost:9090/api/v1/targets     # From host, the truth
```

### Postgres "password authentication failed"

Postgres only reads `POSTGRES_USER` and `POSTGRES_PASSWORD` on **first
initialization** of the volume. If you changed them in `docker-compose.yml`
after the volume was created, the old credentials persist. Fix:

```bash
docker compose down -v
docker compose up -d
```

This wipes the database. For production, create the user manually instead.

## Best Practices

- **Check logs first.** `docker compose logs <service> --tail 30` solves most
  mysteries faster than any other command.
- **Use service names, not IPs.** Container IPs change on every recreation.
- **Never hardcode credentials in Compose files.** Use a `.env` file and keep
  it out of version control.
- **Let containers initialize.** Add healthchecks and `depends_on: condition:
  service_healthy` so dependent services wait for readiness.
- **Reload Prometheus, don't restart it.** `kill -HUP 1` picks up config
  changes without dropping stored metrics.

## Next Steps

- Add alerting rules in `prometheus/alerts.yml`
- Configure Grafana alerts to notify via Slack or email
- Extend the stack with **Loki** for log aggregation
- Add **OpenTelemetry** tracing to see full request flows
- Provision the whole stack on AWS with Terraform

## License

See the project root for license information.
```

---

Drop this in as `README.md` in your repo root. Want me to trim it, expand a section (like the Terraform or AWS parts), or generate a separate `CONTRIBUTING.md` or architecture diagram file?