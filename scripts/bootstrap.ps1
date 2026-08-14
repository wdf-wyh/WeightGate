# Phase 1 PowerShell bootstrap (Windows). Creates dual-tenant dirs; no GPU required.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "==> ensuring dual-tenant data roots (gitignored)"
foreach ($tid in @("tenant_a", "tenant_b", "_example")) {
  foreach ($sub in @("models", "loras", "cache", "logs", "vector")) {
    New-Item -ItemType Directory -Force -Path "data\tenants\$tid\$sub" | Out-Null
  }
}
# Marker adapters for isolation smoke (empty placeholders, not real weights)
$markerA = "data\tenants\tenant_a\loras\adapter_a.txt"
$markerB = "data\tenants\tenant_b\loras\adapter_b.txt"
if (-not (Test-Path $markerA)) { Set-Content -Path $markerA -Value "tenant_a adapter placeholder" }
if (-not (Test-Path $markerB)) { Set-Content -Path $markerB -Value "tenant_b adapter placeholder" }

if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
  Write-Host "==> wrote .env from .env.example (dev defaults only)"
} else {
  Write-Host "==> .env already exists; leaving untouched"
}

Write-Host "==> validating compose config"
if (Get-Command docker -ErrorAction SilentlyContinue) {
  docker compose -f compose/docker-compose.yml config | Out-Null
  docker compose -f compose/docker-compose.yml --profile app config | Out-Null
  docker compose -f compose/docker-compose.yml --profile ollama config | Out-Null
  Write-Host "    compose config: OK (default/app/ollama)"
} else {
  Write-Host "    docker not found; skip compose config"
}

Write-Host "==> Phase 1 bootstrap done"
Write-Host "    Next: pip install -r requirements-dev.txt"
Write-Host "          python scripts/smoke_test.py"
Write-Host "    Chat stack:"
Write-Host "      docker compose -f compose/docker-compose.yml --profile app --profile ollama up -d --build"
Write-Host "      docker compose -f compose/docker-compose.yml --profile ollama exec ollama ollama pull tinyllama"
