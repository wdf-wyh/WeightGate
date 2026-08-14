/** Talks to control-plane only — never runtime. No secrets in bundle. */

const BASE = (import.meta.env.VITE_API_BASE || "").replace(/\/$/, "");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status}: ${text || res.statusText}`);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return (await res.json()) as T;
}

export type Tenant = {
  id: string;
  name: string;
  status: string;
  created_at: string;
};

export type RoutePolicy = {
  tenant_id: string;
  mode: "local_only" | "cloud_only" | "hybrid";
  short_max_chars: number;
  updated_at: string;
};

export type Preset = {
  id: string;
  display_name: string;
  params_b: number;
  backend: string;
  quant: string;
  min_vram_gb: number;
  notes?: string | null;
};

export type Instance = {
  id: string;
  tenant_id: string;
  preset_id: string;
  status: string;
  backend: string;
  compose_project?: string | null;
  host_id?: string | null;
  note?: string | null;
  created_at: string;
  updated_at: string;
};

export type Host = {
  id: string;
  name: string;
  ssh_host: string;
  ssh_port: number;
  ssh_user: string;
  identity_file?: string | null;
  tenant_id?: string | null;
  status: string;
  agent_version?: string | null;
  note?: string | null;
  last_seen_at?: string | null;
  created_at: string;
};

export type Alert = {
  id: string;
  fingerprint: string;
  kind: string;
  severity: string;
  tenant_id?: string | null;
  resource_id?: string | null;
  message: string;
  status: string;
  created_at: string;
  updated_at: string;
  resolved_at?: string | null;
};

export type MirrorProduct = {
  id: string;
  display_name: string;
  domain: string;
  price_cny: number;
  example_path: string;
  adapter_slug: string;
  base_preset_hint?: string | null;
  description?: string | null;
};

export type License = {
  id: string;
  product_id: string;
  tenant_id: string;
  key_prefix: string;
  status: string;
  activated_at?: string | null;
  expires_at?: string | null;
  created_at: string;
  license_key?: string | null;
};

export type UsageSummary = {
  tenant_id: string;
  total_events: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  by_route: Record<string, number>;
  events: Array<{
    id: string;
    model: string;
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
    route: string;
    latency_ms: number;
    created_at: string;
  }>;
};

export type ApiKeyIssued = {
  id: string;
  tenant_id: string;
  key_prefix: string;
  rpm_limit: number;
  allowed_models: string[];
  api_key?: string | null;
};

export const api = {
  listTenants: () => request<Tenant[]>("/v1/tenants"),
  createTenant: (body: { id: string; name: string }) =>
    request<Tenant>("/v1/tenants", { method: "POST", body: JSON.stringify(body) }),
  getPolicy: (tenantId: string) =>
    request<RoutePolicy>(`/v1/tenants/${tenantId}/route-policy`),
  putPolicy: (tenantId: string, body: { mode: string; short_max_chars?: number }) =>
    request<RoutePolicy>(`/v1/tenants/${tenantId}/route-policy`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  issueKey: (tenantId: string) =>
    request<ApiKeyIssued>(`/v1/tenants/${tenantId}/keys`, {
      method: "POST",
      body: JSON.stringify({ rpm_limit: 60, allowed_models: [] }),
    }),
  listPresets: () => request<Preset[]>("/v1/presets"),
  listInstances: (tenantId: string) =>
    request<Instance[]>(`/v1/tenants/${tenantId}/instances`),
  createInstance: (tenantId: string, preset_id: string, host_id?: string) =>
    request<Instance>(`/v1/tenants/${tenantId}/instances`, {
      method: "POST",
      body: JSON.stringify({ preset_id, host_id: host_id || null }),
    }),
  stopInstance: (id: string) =>
    request<Instance>(`/v1/instances/${id}/stop`, { method: "POST" }),
  wakeInstance: (id: string) =>
    request<Instance>(`/v1/instances/${id}/wake`, { method: "POST" }),
  getUsage: (tenantId: string) =>
    request<UsageSummary>(`/v1/tenants/${tenantId}/usage`),
  listHosts: () => request<Host[]>("/v1/hosts"),
  createHost: (body: {
    name: string;
    ssh_host: string;
    ssh_port?: number;
    ssh_user?: string;
    identity_file?: string;
    tenant_id?: string;
  }) => request<Host>("/v1/hosts", { method: "POST", body: JSON.stringify(body) }),
  probeHost: (id: string) => request<Host>(`/v1/hosts/${id}/probe`, { method: "POST" }),
  installAgent: (id: string) =>
    request<Host>(`/v1/hosts/${id}/install-agent`, { method: "POST" }),
  listAlerts: (status = "open") =>
    request<Alert[]>(`/v1/alerts?status=${encodeURIComponent(status)}`),
  scanAlerts: () =>
    request<{ created: number; open_total: number; alerts: Alert[] }>("/v1/alerts/scan", {
      method: "POST",
    }),
  ackAlert: (id: string) => request<Alert>(`/v1/alerts/${id}/ack`, { method: "POST" }),
  resolveAlert: (id: string) =>
    request<Alert>(`/v1/alerts/${id}/resolve`, { method: "POST" }),
  listMirrors: () => request<MirrorProduct[]>("/v1/mirrors"),
  issueLicense: (productId: string, tenantId: string) =>
    request<License>(`/v1/mirrors/${productId}/licenses`, {
      method: "POST",
      body: JSON.stringify({ tenant_id: tenantId }),
    }),
  activateLicense: (license_key: string) =>
    request<License>("/v1/mirrors/activate", {
      method: "POST",
      body: JSON.stringify({ license_key }),
    }),
  listLicenses: (tenantId: string) =>
    request<License[]>(`/v1/tenants/${tenantId}/licenses`),
};
