# Deploy on AutoDL (pay-as-you-go GPU) — Phase 3 handbook

Goal: run a **single-GPU vLLM** (optionally multi-LoRA) OpenAI-compatible server without padding balance beyond a short experiment, then point **WeightGate** gateway `VLLM_BASE_URL` at it.

This project is middleware, not a GPU marketplace. AutoDL (or similar) is an optional **prod** backend next to local Ollama.

## Principles (no pad / 不垫资)

1. Prefer **按量计费** instances; shut down when idle.
2. Pull only the model size you need (7B/14B first); match `min_vram_gb` in `templates/model-presets.yaml`.
3. Use `runtime/sleep-watchdog` labels on tenant runtimes so idle boxes stop.
4. Do **not** commit HF tokens, SSH keys, API keys, or weights into this repo.
5. Estimate before you start: `python scripts/cost_estimate.py --gpu rtx4090 --hourly-cny 2.0 --hours 4 --quant awq`

## Scripts in this repo

| Script | Role |
|--------|------|
| `runtime/vllm/start_single_gpu.sh` / `.ps1` | One model, OpenAI-compatible on `:8001` |
| `runtime/vllm/start_multi_lora.sh` / `.ps1` | Same base + `--enable-lora` / `--lora-modules` |
| `templates/vllm-multi-lora.yml.j2` | Compose fragment scoped to one `tenant_id` |
| `runtime/sleep-watchdog/watchdog.py` | Idle stop helper |
| `scripts/cost_estimate.py` | Rough CNY estimate (no live price API) |

## Suggested flow (single model)

1. Create a short-lived AutoDL instance (one GPU, CUDA matching current vLLM).
2. Clone this repo (or copy `runtime/vllm/`).
3. Install vLLM in the instance venv (`pip install vllm` — pin on the box).
4. Start:

```bash
export MODEL=Qwen/Qwen2.5-7B-Instruct
export PORT=8001
./runtime/vllm/start_single_gpu.sh
```

5. Expose / tunnel port `8001` (AutoDL custom service / SSH reverse tunnel).
6. On the gateway host:

```bash
export VLLM_BASE_URL=http://<autodl-host>:8001
export AF_ROUTE_DEGRADE=1
# hybrid / cloud policies as needed
```

Smoke the GPU box alone:

```bash
curl http://127.0.0.1:8001/v1/models
curl http://127.0.0.1:8001/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"'"$MODEL"'","messages":[{"role":"user","content":"ping"}],"max_tokens":16}'
```

7. **Release the instance** when done. Idle GPU time is the main cost.

## Multi-LoRA (same base)

Place adapters only under **one** tenant tree, then:

```bash
export TENANT_ID=tenant_a
export MODEL=Qwen/Qwen2.5-7B-Instruct
export LORA_MODULES="law-v1=./data/tenants/tenant_a/loras/law-v1,trade-v1=./data/tenants/tenant_a/loras/trade-v1"
./runtime/vllm/start_multi_lora.sh
```

Clients select adapters through the gateway (`X-AF-Adapter` / `adapter`); cross-tenant paths return **403**. Walkthroughs: `examples/law-lora`, `examples/trade-agent`.

## Cloud providers (non-GPU fallback / hybrid)

Gateway cloud adapter is OpenAI-compatible and switched by env (no code fork per vendor):

| Provider | `AF_CLOUD_PROVIDER` | Default base (override with `AF_CLOUD_BASE_URL`) |
|----------|---------------------|--------------------------------------------------|
| 阿里云百炼 compatible-mode | `dashscope` (alias `bailian`) | `https://dashscope.aliyuncs.com/compatible-mode` |
| DeepSeek | `deepseek` | `https://api.deepseek.com` |
| Generic OpenAI-compatible | `openai` | `https://api.openai.com` |

Also set `AF_CLOUD_API_KEY` and optionally `AF_CLOUD_MODEL`. Failures degrade to Ollama when `AF_ROUTE_DEGRADE=1`.

### Night discount window (configurable, no billing API)

Providers often discount overnight; AF only documents / estimates the window:

```bash
AF_CLOUD_NIGHT_START=22:00
AF_CLOUD_NIGHT_END=08:00
AF_CLOUD_NIGHT_DISCOUNT=0.5
AF_CLOUD_NIGHT_TZ=Asia/Shanghai
```

Exposed on gateway `GET /health` as `night_window` / `in_night_window`. Confirm real promos in the vendor console; `scripts/cost_estimate.py --night-fraction 0.4 --night-discount 0.5` applies the same idea to GPU hours.

## Cost control checklist

- [ ] Instance type matched to `min_vram_gb` in `templates/model-presets.yaml`
- [ ] `MAX_MODEL_LEN` kept modest (e.g. 4096) unless needed
- [ ] Ran `cost_estimate.py` before long runs
- [ ] Watchdog or manual stop after idle
- [ ] No always-on “reserved” pad balance required for this handbook
- [ ] Secrets only in env / AutoDL vault — never in git

## Local vs AutoDL

| Path | Backend | When |
|------|---------|------|
| Laptop / free | Ollama (`--profile ollama`) | Daily chat / zero-GPU demo |
| Rented GPU | vLLM (`start_single_gpu.*` / `start_multi_lora.*`) | Throughput / LoRA |
| Cloud API | DashScope / DeepSeek via `AF_CLOUD_*` | Tools / long context hybrid |

Gateway hybrid routing (Phase 2+) chooses Ollama ↔ vLLM ↔ cloud by tenant `RoutePolicy`. This doc makes the GPU box and provider env startable without padding.
