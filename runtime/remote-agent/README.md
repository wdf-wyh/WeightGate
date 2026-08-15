# Remote agent (Phase 4)

Thin scripts installed on **customer-owned** machines. Control-plane SSHes in
(when `AF_SSH_DRIVER=on`) to probe, install, and start/stop a runtime marker.

## Files

| Script | Role |
|--------|------|
| `install.sh` | chmod + layout |
| `healthcheck.sh` | docker / GPU / disk snapshot |
| `start_runtime.sh` | write per-instance state JSON; optional hint to vLLM scripts |

## Security

- Prefer SSH key auth (`identity_file` on the Host record). Never commit private keys.
- Control plane stores only host metadata + optional path to a local identity file.
- Agent does not receive tenant API keys or cloud provider secrets.

## Manual install (no control plane)

```bash
scp -r runtime/remote-agent user@customer-host:~/weightgate-agent
ssh user@customer-host '~/weightgate-agent/install.sh'
```
