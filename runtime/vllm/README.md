# vLLM runtime (production / Phase 3 multi-LoRA)

Higher-throughput OpenAI-compatible serving for single-GPU boxes (e.g. AutoDL).

## Start (one GPU)

```bash
# Linux / AutoDL shell
pip install vllm   # on the GPU machine only; not required for local smoke
export MODEL=Qwen/Qwen2.5-7B-Instruct
chmod +x runtime/vllm/start_single_gpu.sh
./runtime/vllm/start_single_gpu.sh
```

Windows (when a local NVIDIA GPU + vLLM env exists):

```powershell
$env:MODEL = "Qwen/Qwen2.5-7B-Instruct"
.\runtime\vllm\start_single_gpu.ps1
```

## Multi-LoRA (same base, tenant-scoped adapters)

```bash
export TENANT_ID=tenant_a
export MODEL=Qwen/Qwen2.5-7B-Instruct
export LORA_MODULES="law-v1=./data/tenants/tenant_a/loras/law-v1,trade-v1=./data/tenants/tenant_a/loras/trade-v1"
chmod +x runtime/vllm/start_multi_lora.sh
./runtime/vllm/start_multi_lora.sh
```

Gateway selects adapters with `X-AF-Adapter` / body `adapter` (cross-tenant → 403). Compose fragment: `templates/vllm-multi-lora.yml.j2`.

Default listen port: `8001`. Point gateway `VLLM_BASE_URL` at that host.

## Docs

- Pay-as-you-go GPU handbook + cost estimate: [docs/deploy-autodl.md](../../docs/deploy-autodl.md)
- Examples: [law-lora](../../examples/law-lora/README.md), [trade-agent](../../examples/trade-agent/README.md)
