"""Tenant isolation helpers + re-exports."""

from .fs import (
    TENANT_SUBDIRS,
    TenantIsolationError,
    assert_model_allowed_for_tenant,
    data_root,
    ensure_tenant_layout,
    safe_tenant_path,
    tenant_root,
    validate_tenant_id,
)
from .keys import (
    KeyRecord,
    default_dev_keys,
    generate_api_key,
    hash_api_key,
    key_prefix,
    load_keys_from_env,
    resolve_key,
)
from .vector import (
    LocalVectorStore,
    chroma_persist_dir,
    tenant_vector_dir,
)

__all__ = [
    "TENANT_SUBDIRS",
    "TenantIsolationError",
    "KeyRecord",
    "LocalVectorStore",
    "assert_model_allowed_for_tenant",
    "chroma_persist_dir",
    "data_root",
    "default_dev_keys",
    "ensure_tenant_layout",
    "generate_api_key",
    "hash_api_key",
    "key_prefix",
    "load_keys_from_env",
    "resolve_key",
    "safe_tenant_path",
    "tenant_root",
    "tenant_vector_dir",
    "validate_tenant_id",
]
