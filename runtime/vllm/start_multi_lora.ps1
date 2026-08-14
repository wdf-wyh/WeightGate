# Multi-LoRA vLLM server (Windows / local GPU) — Phase 3 template.
# See start_multi_lora.sh for env semantics.
param(
  [string]$Model = $env:MODEL,
  [string]$Port = $(if ($env:PORT) { $env:PORT } else { "8001" }),
  [string]$MaxModelLen = $(if ($env:MAX_MODEL_LEN) { $env:MAX_MODEL_LEN } else { "4096" }),
  [string]$GpuMem = $(if ($env:GPU_MEMORY_UTILIZATION) { $env:GPU_MEMORY_UTILIZATION } else { "0.90" }),
  [string]$MaxLoras = $(if ($env:MAX_LORAS) { $env:MAX_LORAS } else { "4" }),
  [string]$MaxLoraRank = $(if ($env:MAX_LORA_RANK) { $env:MAX_LORA_RANK } else { "16" }),
  [string]$LoraModules = $env:LORA_MODULES,
  [string]$TenantId = $env:TENANT_ID
)

if (-not $Model) { throw "set MODEL (env or -Model)" }
if (-not $LoraModules) {
  throw "set LORA_MODULES as name=path pairs, comma-separated (e.g. law-v1=.\data\tenants\tenant_a\loras\law-v1)"
}

if ($TenantId) {
  foreach ($pair in $LoraModules.Split(",")) {
    $path = ($pair -split "=", 2)[1]
    $needle = "tenants\$TenantId"
    $needle2 = "tenants/$TenantId"
    if ($path -notlike "*$needle*" -and $path -notlike "*$needle2*") {
      throw "LoRA path '$path' does not include tenants/$TenantId — refuse to mix tenants"
    }
  }
}

python -m vllm.entrypoints.openai.api_server `
  --model $Model `
  --host 0.0.0.0 `
  --port $Port `
  --max-model-len $MaxModelLen `
  --gpu-memory-utilization $GpuMem `
  --enable-lora `
  --max-loras $MaxLoras `
  --max-lora-rank $MaxLoraRank `
  --lora-modules $LoraModules
