# Ollama health check — exit 0 when /api/tags responds.
$ErrorActionPreference = "Stop"
$Base = if ($env:OLLAMA_BASE_URL) { $env:OLLAMA_BASE_URL.TrimEnd("/") } else { "http://127.0.0.1:11434" }
try {
  Invoke-RestMethod -Uri "$Base/api/tags" -TimeoutSec 5 | Out-Null
  Write-Host "OK ollama health: $Base"
  exit 0
} catch {
  Write-Error "FAIL ollama health: $Base — $($_.Exception.Message)"
  exit 1
}
