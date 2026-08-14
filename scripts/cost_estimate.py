#!/usr/bin/env python3
"""Rough GPU / cloud cost estimator for AutoDL-style pay-as-you-go (Phase 3).

No live billing APIs — inputs are yours; output is a back-of-envelope figure.

Examples:
  python scripts/cost_estimate.py --gpu rtx4090 --hourly-cny 2.0 --hours 4 --quant awq
  python scripts/cost_estimate.py --gpu a100-40g --hourly-cny 8.5 --hours 24 --quant fp16 --night-fraction 0.4
  python scripts/cost_estimate.py --list-gpus
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass

# Indicative VRAM / sweet-spot notes (not a price sheet — prices vary by region/promo).
GPU_CATALOG: dict[str, dict] = {
    "rtx3060": {"vram_gb": 12, "notes": "7B Q4 / small demos"},
    "rtx3090": {"vram_gb": 24, "notes": "7B–14B comfortable"},
    "rtx4090": {"vram_gb": 24, "notes": "common AutoDL pick for 7B–14B"},
    "a10": {"vram_gb": 24, "notes": "cloud T4/A10 class"},
    "a100-40g": {"vram_gb": 40, "notes": "14B–32B / multi-LoRA headroom"},
    "a100-80g": {"vram_gb": 80, "notes": "larger context / higher concurrency"},
    "h100-80g": {"vram_gb": 80, "notes": "throughput; check hourly carefully"},
}

QUANT_VRAM_FACTOR: dict[str, float] = {
    "fp16": 1.0,
    "bf16": 1.0,
    "int8": 0.55,
    "awq": 0.4,
    "gptq": 0.4,
    "q4": 0.35,
    "q5": 0.45,
}


@dataclass
class Estimate:
    gpu: str
    hourly_cny: float
    hours: float
    quant: str
    night_fraction: float
    night_discount: float
    base_cost_cny: float
    effective_cost_cny: float
    vram_gb: int
    approx_params_b_fp16: float


def approx_params_for_vram(vram_gb: int, quant: str) -> float:
    """Very rough: usable params (B) ≈ VRAM * factor / 2 (fp16 bytes/param heuristic)."""
    factor = QUANT_VRAM_FACTOR.get(quant.lower(), 0.5)
    # Leave ~30% for KV / runtime
    usable = vram_gb * 0.7 * (1.0 / max(factor, 0.2))
    # fp16 ~ 2 bytes/param → params_b ≈ usable_gb / 2
    return round(usable / 2.0, 1)


def estimate(
    *,
    gpu: str,
    hourly_cny: float,
    hours: float,
    quant: str,
    night_fraction: float,
    night_discount: float,
) -> Estimate:
    meta = GPU_CATALOG.get(gpu.lower())
    if meta is None:
        raise SystemExit(f"unknown gpu {gpu!r}; use --list-gpus")
    if hours < 0 or hourly_cny < 0:
        raise SystemExit("hours and hourly-cny must be >= 0")
    night_fraction = min(max(night_fraction, 0.0), 1.0)
    night_discount = min(max(night_discount, 0.0), 1.0)

    day_h = hours * (1.0 - night_fraction)
    night_h = hours * night_fraction
    base = hourly_cny * hours
    effective = hourly_cny * day_h + hourly_cny * night_discount * night_h
    return Estimate(
        gpu=gpu.lower(),
        hourly_cny=hourly_cny,
        hours=hours,
        quant=quant.lower(),
        night_fraction=night_fraction,
        night_discount=night_discount,
        base_cost_cny=round(base, 2),
        effective_cost_cny=round(effective, 2),
        vram_gb=int(meta["vram_gb"]),
        approx_params_b_fp16=approx_params_for_vram(int(meta["vram_gb"]), quant),
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="AutoDL-style rough cost estimate (no live billing).")
    p.add_argument("--gpu", default="rtx4090", help="gpu slug (see --list-gpus)")
    p.add_argument("--hourly-cny", type=float, default=2.0, help="instance CNY per hour")
    p.add_argument("--hours", type=float, default=4.0, help="planned runtime hours")
    p.add_argument("--quant", default="awq", help="quant tier: fp16|int8|awq|gptq|q4|q5")
    p.add_argument(
        "--night-fraction",
        type=float,
        default=0.0,
        help="fraction of hours inside night window (0-1)",
    )
    p.add_argument(
        "--night-discount",
        type=float,
        default=0.5,
        help="multiplier during night window (e.g. 0.5 = 50%% off)",
    )
    p.add_argument("--list-gpus", action="store_true")
    p.add_argument("--json", action="store_true", help="print JSON")
    args = p.parse_args(argv)

    if args.list_gpus:
        for name, meta in sorted(GPU_CATALOG.items()):
            print(f"{name:12} VRAM={meta['vram_gb']:3}GB  {meta['notes']}")
        return 0

    est = estimate(
        gpu=args.gpu,
        hourly_cny=args.hourly_cny,
        hours=args.hours,
        quant=args.quant,
        night_fraction=args.night_fraction,
        night_discount=args.night_discount,
    )
    payload = {
        "gpu": est.gpu,
        "vram_gb": est.vram_gb,
        "quant": est.quant,
        "hourly_cny": est.hourly_cny,
        "hours": est.hours,
        "night_fraction": est.night_fraction,
        "night_discount": est.night_discount,
        "base_cost_cny": est.base_cost_cny,
        "effective_cost_cny": est.effective_cost_cny,
        "approx_max_params_b_rule_of_thumb": est.approx_params_b_fp16,
        "disclaimer": "Rough estimate only. Confirm live AutoDL/cloud prices and night promos yourself.",
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"GPU {est.gpu} ({est.vram_gb}GB)  quant={est.quant}")
        print(f"  {est.hours}h × ¥{est.hourly_cny}/h → base ¥{est.base_cost_cny}")
        if est.night_fraction > 0:
            print(
                f"  night {est.night_fraction:.0%} @ ×{est.night_discount} → effective ¥{est.effective_cost_cny}"
            )
        else:
            print(f"  effective ¥{est.effective_cost_cny}")
        print(f"  rule-of-thumb max params ~ {est.approx_params_b_fp16}B (very rough)")
        print("  (not a quote — shut down when idle; see docs/deploy-autodl.md)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
