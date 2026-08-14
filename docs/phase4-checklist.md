# Phase 4 acceptance checklist

Phase 4 = delivery productization on top of Phase 3: **SSH remote hosts**, **alerts**, **vertical mirror licenses**. Still no K8s / self-built GPU pool / streaming rewrite.

## Must pass

- [x] Host CRUD + `probe` / `install-agent` (`control-plane/ssh_driver.py`, `runtime/remote-agent/`)
- [x] Instance create accepts optional `host_id` (remote runtime vs local Docker)
- [x] `AF_SSH_DRIVER=off` (default) simulates SSH — no seller-side GPU padding
- [x] Alerts: scan for `instance_down` / `quota_exhausted` / `disk_low`; ack / resolve APIs
- [x] Optional `AF_ALERT_WEBHOOK_URL` webhook on scan
- [x] Mirror catalog `templates/mirror-catalog.yaml` + issue / activate license → tenant `loras/{slug}/`
- [x] Example manifests: `examples/law-lora/manifest.yaml`, `examples/trade-agent/manifest.yaml`
- [x] Console pages: Hosts / Alerts / Catalog
- [x] `docs/deploy-remote.md` + `docs/phase4-checklist.md`; README Phase 4 Done
- [x] `python scripts/smoke_test.py` and `python scripts/deep_test.py` (Phase 4 paths)

## Explicitly deferred

- K8s / fixed GPU pool purchased with seller capital
- Live payment gateway for mirror store
- Paramiko-only agent (system `ssh`/`scp` is enough)
- Streaming chat

## How to demo Phase 4 (short)

```powershell
.\scripts\bootstrap.ps1
pip install -r requirements-dev.txt
python scripts\smoke_test.py
python scripts\deep_test.py

# control-plane only (SQLite in-memory via unset DATABASE_URL is fine for unit paths;
# for API demo use compose --profile app)
docker compose -f compose/docker-compose.yml --profile app up -d --build

# 1) register a customer host (simulated when AF_SSH_DRIVER=off)
curl http://127.0.0.1:8080/v1/hosts -H "Content-Type: application/json" -d "{\"name\":\"demo\",\"ssh_host\":\"127.0.0.1\",\"ssh_user\":\"ubuntu\",\"tenant_id\":\"tenant_a\"}"
curl -X POST http://127.0.0.1:8080/v1/hosts/<host_id>/probe
curl -X POST http://127.0.0.1:8080/v1/hosts/<host_id>/install-agent

# 2) start instance on that host
curl http://127.0.0.1:8080/v1/tenants/tenant_a/instances -H "Content-Type: application/json" -d "{\"preset_id\":\"small-7b\",\"host_id\":\"<host_id>\"}"

# 3) alerts
curl -X POST http://127.0.0.1:8080/v1/alerts/scan
curl http://127.0.0.1:8080/v1/alerts?status=open

# 4) mirror license → activate installs marker under data/tenants/tenant_a/loras/
curl http://127.0.0.1:8080/v1/mirrors
curl http://127.0.0.1:8080/v1/mirrors/law-lora-v1/licenses -H "Content-Type: application/json" -d "{\"tenant_id\":\"tenant_a\"}"
# use returned license_key:
curl http://127.0.0.1:8080/v1/mirrors/activate -H "Content-Type: application/json" -d "{\"license_key\":\"lic-af-...\"}"
```

Ops playbook: [deploy-remote.md](deploy-remote.md).
