# Sleep watchdog (Phase 1)

Stops idle tenant runtimes labeled `af.plane=data` after `AF_SLEEP_IDLE_SECONDS`
(default 900) with no activity marker at:

```
data/tenants/{tenant_id}/cache/last_active
```

## Run once

```bash
python runtime/sleep-watchdog/watchdog.py --once --dry-run
python runtime/sleep-watchdog/watchdog.py --once
```

## Loop

```bash
python runtime/sleep-watchdog/watchdog.py --loop --interval 60 --idle-seconds 900
```

Windows:

```powershell
python runtime\sleep-watchdog\watchdog.py --once --dry-run
```

Requires Docker CLI. Does not start GPUs or pad AutoDL billing — it only `docker stop`s labeled containers when idle.
