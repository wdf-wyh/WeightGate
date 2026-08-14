<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import { api, type Tenant, type UsageSummary } from "../api";

const tenants = ref<Tenant[]>([]);
const tenantId = ref("");
const usage = ref<UsageSummary | null>(null);
const error = ref("");

async function bootstrap() {
  error.value = "";
  try {
    tenants.value = await api.listTenants();
    if (!tenantId.value && tenants.value.length) tenantId.value = tenants.value[0].id;
    await load();
  } catch (e) {
    error.value = String(e);
  }
}

async function load() {
  if (!tenantId.value) {
    usage.value = null;
    return;
  }
  usage.value = await api.getUsage(tenantId.value);
}

watch(tenantId, () => {
  load().catch((e) => (error.value = String(e)));
});

onMounted(bootstrap);
</script>

<template>
  <section>
    <h1>Usage</h1>
    <p class="lead">Token and route usage recorded by the gateway through control-plane.</p>
    <p v-if="error" class="err">{{ error }}</p>

    <div class="panel">
      <div class="row">
        <select v-model="tenantId">
          <option v-for="t in tenants" :key="t.id" :value="t.id">{{ t.id }}</option>
        </select>
        <button @click="load">Refresh</button>
      </div>
      <p v-if="usage" class="muted">
        Events: <span class="mono">{{ usage.total_events }}</span> · tokens
        <span class="mono">{{ usage.total_tokens }}</span>
        (prompt {{ usage.prompt_tokens }} / completion {{ usage.completion_tokens }})
      </p>
      <p v-if="usage" class="muted">
        By route:
        <span v-for="(n, route) in usage.by_route" :key="route" class="badge" style="margin-right: 0.35rem">
          {{ route }}: {{ n }}
        </span>
        <span v-if="!Object.keys(usage.by_route || {}).length">—</span>
      </p>
    </div>

    <div class="panel">
      <table>
        <thead>
          <tr>
            <th>When</th>
            <th>Model</th>
            <th>Route</th>
            <th>Tokens</th>
            <th>Latency</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="e in usage?.events || []" :key="e.id">
            <td class="mono muted">{{ e.created_at }}</td>
            <td class="mono">{{ e.model }}</td>
            <td><span class="badge">{{ e.route }}</span></td>
            <td class="mono">{{ e.total_tokens }}</td>
            <td class="mono">{{ e.latency_ms }}ms</td>
          </tr>
        </tbody>
      </table>
      <p v-if="usage && !usage.events.length" class="muted">No usage events yet.</p>
    </div>
  </section>
</template>
