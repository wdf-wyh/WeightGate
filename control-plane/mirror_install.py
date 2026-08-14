"""Install a vertical mirror pack marker into a tenant's loras/ tree."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from packages.tenantkit import ensure_tenant_layout, safe_tenant_path

ROOT = Path(__file__).resolve().parents[1]


def install_product_marker(
    *,
    tenant_id: str,
    product: dict,
    license_id: str,
) -> str:
    """
    Copy example manifest (if any) and write adapter_config.json under
    data/tenants/{id}/loras/{adapter_slug}/. Returns relative adapter path.
    """
    ensure_tenant_layout(tenant_id)
    slug = str(product["adapter_slug"])
    dest = safe_tenant_path(tenant_id, "loras", slug)
    dest.mkdir(parents=True, exist_ok=True)

    example_rel = product.get("example_path")
    if example_rel:
        example_dir = ROOT / str(example_rel)
        manifest_src = example_dir / "manifest.yaml"
        if manifest_src.is_file():
            shutil.copy2(manifest_src, dest / "manifest.yaml")

    meta = {
        "product_id": product["id"],
        "domain": product.get("domain"),
        "license_id": license_id,
        "placeholder": True,
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "note": "Replace placeholder with real LoRA weights outside git.",
    }
    (dest / "adapter_config.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return f"loras/{slug}"
