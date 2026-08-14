# Single-GPU vLLM OpenAI-compatible server (prod / AutoDL).
# Example:
#   $env:MODEL = "Qwen/Qwen2.5-7B-Instruct"
#   .\runtime\vllm\start_single_gpu.ps1
$ErrorActionPreference = "Stop"
if (-not $env:MODEL) { throw "set MODEL to a HF id or local path" }
$Port = if ($env:PORT) { $env:PORT } else { "8001" }
$MaxLen = if ($env:MAX_MODEL_LEN) { $env:MAX_MODEL_LEN } else { "4096" }
$Util = if ($env:GPU_MEMORY_UTILIZATION) { $env:GPU_MEMORY_UTILIZATION } else { "0.90" }

python -m vllm.entrypoints.openai.api_server `
  --model $env:MODEL `
  --host 0.0.0.0 `
  --port $Port `
  --max-model-len $MaxLen `
  --gpu-memory-utilization $Util @args
