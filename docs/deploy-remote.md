# Deploy on customer-owned machines (Phase 4)

This path is for **代运维**: the customer owns the GPU box; you run control-plane + gateway
(or they do) and reach the box over SSH. You do **not** prepay a GPU pool.

## 1. Prerequisites on the customer host

- SSH key login for a non-root ops user (recommended)
- Docker (optional) and/or NVIDIA driver if they will run vLLM
- Outbound network for model pulls if needed

## 2. Register the host in control-plane

```bash
curl -s http://127.0.0.1:8080/v1/hosts \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "factory-a10",
    "ssh_host": "203.0.113.10",
    "ssh_port": 22,
    "ssh_user": "ubuntu",
    "identity_file": "/home/ops/.ssh/customer_a",
    "tenant_id": "tenant_a"
  }'
```

Store only the **path** to the private key on the control-plane host. Never commit key material.

## 3. Enable real SSH (optional)

Defaults simulate SSH so local demos stay zero-cost:

```bash
export AF_SSH_DRIVER=on
export AF_SSH_CONNECT_TIMEOUT=8
export AF_REMOTE_AGENT_DIR='~/automatic-funicular-agent'
```

Then:

```bash
curl -X POST http://127.0.0.1:8080/v1/hosts/<id>/probe
curl -X POST http://127.0.0.1:8080/v1/hosts/<id>/install-agent
```

Agent scripts live in `runtime/remote-agent/`.

## 4. Start an instance on that host

```bash
curl -s http://127.0.0.1:8080/v1/tenants/tenant_a/instances \
  -H 'Content-Type: application/json' \
  -d '{"preset_id":"qwen2.5-7b-instruct","host_id":"<host_id>"}'
```

Without `host_id`, control-plane uses the local Docker Compose driver (`AF_DOCKER_DRIVER`).

## 5. Alerts for ops subscription

```bash
export AF_DISK_WARN_RATIO=0.9
export AF_ALERT_WEBHOOK_URL='https://hooks.example/af'   # optional
curl -X POST http://127.0.0.1:8080/v1/alerts/scan
```

Kinds: `instance_down`, `quota_exhausted`, `disk_low`.

Cron example:

```cron
*/5 * * * * curl -fsS -X POST http://127.0.0.1:8080/v1/alerts/scan >/dev/null
```

## 6. Vertical packs

Issue + activate a catalog license so the tenant gets `loras/<slug>/adapter_config.json`
(and copied `manifest.yaml`). Real weights stay outside git / on the customer disk.
